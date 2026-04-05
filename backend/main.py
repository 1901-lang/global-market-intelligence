import asyncio
import json
import logging
import os
import subprocess
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, HTTPException, BackgroundTasks, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from auth import (
    Token,
    User,
    UserCreate,
    RefreshRequest,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    create_user,
    get_optional_user,
    require_auth,
    require_role,
    SECRET_KEY,
    REQUIRE_AUTH,
    _decode_token,
)
from database import init_db
from pydantic import BaseModel as PydanticBaseModel

from db import get_db
from models.schemas import (
    AdminQueryRequest,
    AgentActivity,
    AgentStatus,
    AnomalyCheckRequest,
    AssetPrice,
    Alert,
    AnalyticsReport,
    Brief,
    ChatRequest,
    ConsensusResult,
    DeepDiveRequest,
    FullMarketData,
    LeadInsightRequest,
    MarketContext,
    MarketIntelReport,
    MarketingContentItem,
    ModelOutput,
    ModelPerformance,
    OnboardRequest,
    OrchestratorBriefing,
)


# ── Request/response models for new endpoints ──────────────────────────────────

class AssetConfigRequest(PydanticBaseModel):
    symbol: str
    name: str
    asset_type: str   # "crypto" or "commodity"
    source_id: str    # CoinGecko ID for crypto, Yahoo Finance ticker for commodity


class UserPreferencesModel(PydanticBaseModel):
    preferred_assets: List[str] = []
    notify_email: bool = True
    email_address: Optional[str] = None
    notifications_enabled: bool = True


class UserUpdateModel(PydanticBaseModel):
    role: Optional[str] = None          # admin | analyst | readonly
    is_active: Optional[bool] = None
from security import sanitize_input
from services.data_service import fetch_all_assets, fetch_macro_context, load_configured_assets
from services.signal_engine import generate_all_signals
from services.model_wrapper import query_all_models, debate_loop
from services.consensus_engine import compute_consensus
from services.learning_engine import (
    get_model_weights,
    record_prediction,
    record_outcome,
    evaluate_past_predictions,
    get_all_performance,
)
from services.alert_engine import (
    get_recent_alerts,
    mark_alert_read,
    process_consensus_for_alerts,
)
from services.brief_generator import generate_brief, get_latest_brief

import agents.orchestrator as orch_agent
import agents.marketing as mkt_agent
import agents.market_intelligence as intel_agent
import agents.customer_success as cs_agent
import agents.analytics as analytics_agent

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Sentry (optional) ─────────────────────────────────────────────────────────
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.1,
    )
    logger.info("Sentry initialised")

# ── Rate limiter ───────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# In-memory state for latest data
_state: dict = {
    "assets": [],
    "context": None,
    "signals": [],
    "consensus": [],
    "model_outputs": [],
    "last_updated": None,
}


async def run_update_cycle():
    logger.info("Running market intelligence update cycle...")
    try:
        assets, context = await asyncio.gather(
            fetch_all_assets(),
            fetch_macro_context(),
        )

        base_signals = generate_all_signals(assets, context)

        all_model_outputs: List[ModelOutput] = []
        all_consensus: List[ConsensusResult] = []

        for signal in base_signals:
            weights = await get_model_weights(signal.asset)
            initial_outputs = await query_all_models(signal, context)
            refined_outputs = await debate_loop(signal, context, initial_outputs)

            for out in refined_outputs:
                await record_prediction(out.asset, out.model_name)

            consensus = compute_consensus(signal.asset, refined_outputs, weights)
            await process_consensus_for_alerts(consensus)

            all_model_outputs.extend(refined_outputs)
            all_consensus.append(consensus)

            # Persist to database
            await _persist_consensus(consensus)
            await _persist_model_outputs(refined_outputs)

        await _persist_assets(assets)
        await _persist_context(context)

        _state["assets"] = assets
        _state["context"] = context
        _state["signals"] = base_signals
        _state["consensus"] = all_consensus
        _state["model_outputs"] = all_model_outputs
        _state["last_updated"] = datetime.now(timezone.utc)

        # Evaluate predictions made ~1 hour ago against current prices
        current_prices = {a.symbol: a.price for a in assets}
        await evaluate_past_predictions(current_prices)

        logger.info(f"Update cycle complete. Assets: {len(assets)}, Consensus results: {len(all_consensus)}")
    except Exception as exc:
        logger.exception(f"Update cycle failed: {exc}")


async def _persist_assets(assets: List[AssetPrice]):
    async with get_db() as db:
        for a in assets:
            await db.execute(
                """INSERT INTO price_data (symbol, price, change_1h, change_24h, volume_24h, market_cap, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (a.symbol, a.price, a.change_1h, a.change_24h, a.volume_24h, a.market_cap, datetime.now(timezone.utc)),
            )
        await db.commit()


async def _persist_context(ctx: MarketContext):
    async with get_db() as db:
        await db.execute(
            """INSERT INTO market_context (usd_index, bond_yield_10y, vix, news_sentiment, on_chain_activity, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ctx.usd_index, ctx.bond_yield_10y, ctx.vix, ctx.news_sentiment, ctx.on_chain_activity, datetime.now(timezone.utc)),
        )
        await db.commit()


async def _persist_consensus(c: ConsensusResult):
    async with get_db() as db:
        await db.execute(
            """INSERT INTO consensus_results (asset, final_signal, confidence, agreement_level, models_json, dissenting_models, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                c.asset, c.final_signal, c.confidence, c.agreement_level,
                json.dumps(c.models), json.dumps(c.dissenting_models), datetime.now(timezone.utc),
            ),
        )
        await db.commit()


async def _persist_model_outputs(outputs: List[ModelOutput]):
    async with get_db() as db:
        for o in outputs:
            await db.execute(
                """INSERT INTO model_outputs (asset, model_name, signal, confidence, reasoning, raw_response, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (o.asset, o.model_name, o.signal, o.confidence, json.dumps(o.reasoning), o.raw_response, datetime.now(timezone.utc)),
            )
        await db.commit()


async def _background_scheduler():
    while True:
        await run_update_cycle()
        await asyncio.sleep(60)


def _make_agent_scheduler() -> AsyncIOScheduler:
    """Build and return an APScheduler with all agent jobs registered."""
    sched = AsyncIOScheduler()

    # Orchestrator – daily briefing at 09:00
    sched.add_job(
        orch_agent.run_daily_briefing,
        "cron", hour=9, minute=0, id="orch_daily_briefing",
        args=[_state],
    )

    # Marketing – daily teaser at 08:30, lead nurture every 2 h
    sched.add_job(
        mkt_agent.generate_daily_teaser,
        "cron", hour=8, minute=30, id="mkt_daily_teaser",
        args=[_state],
    )
    sched.add_job(
        mkt_agent.generate_lead_nurture,
        "interval", hours=2, id="mkt_lead_nurture",
        args=[_state],
    )

    # Market Intelligence – pre-market 07:00, close 16:30
    sched.add_job(
        intel_agent.generate_narrative,
        "cron", hour=7, minute=0, id="intel_pre_market",
        args=["pre_market", _state],
    )
    sched.add_job(
        intel_agent.generate_narrative,
        "cron", hour=16, minute=30, id="intel_close_summary",
        args=["close_summary", _state],
    )

    # Customer Success – daily check at 10:00
    sched.add_job(
        cs_agent.run_daily_check,
        "cron", hour=10, minute=0, id="cs_daily_check",
        args=[_state],
    )

    # Analytics – daily KPI at 08:00, anomaly check every 4 h
    sched.add_job(
        analytics_agent.generate_kpi_report,
        "cron", hour=8, minute=0, id="analytics_kpi",
        args=[_state],
    )
    sched.add_job(
        analytics_agent.run_anomaly_check,
        "interval", hours=4, id="analytics_anomaly",
        args=[_state],
    )

    return sched


def _startup_key_check():
    """Warn on missing keys; fail fast in production (REQUIRE_AUTH=true)."""
    missing = []
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    # Accept either a direct Anthropic key or an OpenRouter key for Claude.
    if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OPENROUTER_API_KEY"):
        missing.append("ANTHROPIC_API_KEY or OPENROUTER_API_KEY")
    if not os.getenv("GEMINI_API_KEY"):
        missing.append("GEMINI_API_KEY")
    if REQUIRE_AUTH and not SECRET_KEY:
        logger.error("REQUIRE_AUTH=true but SECRET_KEY is not set — refusing to start")
        raise RuntimeError("SECRET_KEY must be set when REQUIRE_AUTH=true")
    if missing:
        logger.warning(
            "API keys not configured (fallback/mock responses will be used): %s",
            ", ".join(missing),
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _startup_key_check()
    await init_db()
    await load_configured_assets()
    asyncio.create_task(_background_scheduler())
    agent_scheduler = _make_agent_scheduler()
    agent_scheduler.start()
    yield
    agent_scheduler.shutdown(wait=False)


# ── CORS ───────────────────────────────────────────────────────────────────────
_ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
ALLOWED_ORIGINS = [o.strip() for o in _ALLOWED_ORIGINS_RAW.split(",") if o.strip()]

app = FastAPI(
    title="AIP — Agentic Multi-Model Market Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# ── Security headers middleware ────────────────────────────────────────────────
# Applied to every response to protect against common web vulnerabilities.

@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    # Prevent browsers from MIME-sniffing the content-type
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Block clickjacking by disallowing framing
    response.headers["X-Frame-Options"] = "DENY"
    # Stop browsers from sending the Referer header to third-party sites
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Restrict browser features
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # HSTS — uncomment and set the domain in production behind HTTPS
    # response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    return response


# ── Health check ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Extended health check: validates DB connectivity and API key presence."""
    db_ok = False
    try:
        async with get_db() as db:
            await db.fetchone("SELECT 1")
        db_ok = True
    except Exception as exc:
        logger.warning("Health check DB failure: %s", exc)

    keys = {
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
    }
    overall = "ok" if db_ok else "degraded"
    return {
        "status": overall,
        "timestamp": datetime.now(timezone.utc),
        "db": "ok" if db_ok else "error",
        "api_keys": keys,
        "auth_required": REQUIRE_AUTH,
    }


# ── Auth endpoints ─────────────────────────────────────────────────────────────

@app.post("/api/auth/register", response_model=User, status_code=201)
@limiter.limit("5/minute")
async def register(request: Request, user_in: UserCreate):
    """Register a new user account."""
    existing = await get_user_by_username_or_none(user_in.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")
    created = await create_user(user_in)
    if not created:
        raise HTTPException(status_code=500, detail="Failed to create user")
    return User(
        id=created.get("id"),
        username=created["username"],
        email=created.get("email"),
        role=created.get("role", "analyst"),
        is_active=bool(created.get("is_active", True)),
    )


async def get_user_by_username_or_none(username: str):
    from auth import get_user_by_username
    return await get_user_by_username(username)


@app.post("/api/auth/login", response_model=Token)
@limiter.limit("10/minute")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate and return JWT access + refresh tokens."""
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token({"sub": user["username"]})
    refresh_token = create_refresh_token({"sub": user["username"]})
    return Token(access_token=access_token, refresh_token=refresh_token)


@app.post("/api/auth/refresh", response_model=Token)
@limiter.limit("20/minute")
async def refresh_token(request: Request, body: RefreshRequest):
    """Issue a new access token using a valid refresh token."""
    username = _decode_token(body.refresh_token, "refresh")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    access_token = create_access_token({"sub": username})
    new_refresh = create_refresh_token({"sub": username})
    return Token(access_token=access_token, refresh_token=new_refresh)


@app.get("/api/assets", response_model=List[AssetPrice])
async def get_assets():
    if not _state["assets"]:
        assets = await fetch_all_assets()
        _state["assets"] = assets
    return _state["assets"]


@app.get("/api/context", response_model=MarketContext)
async def get_context():
    if not _state["context"]:
        ctx = await fetch_macro_context()
        _state["context"] = ctx
    return _state["context"]


@app.get("/api/signals")
async def get_signals():
    return _state["signals"]


@app.get("/api/consensus", response_model=List[ConsensusResult])
async def get_consensus():
    return _state["consensus"]


@app.get("/api/model-outputs", response_model=List[ModelOutput])
async def get_model_outputs():
    return _state["model_outputs"]


@app.get("/api/alerts", response_model=List[Alert])
async def get_alerts(limit: int = 50):
    return await get_recent_alerts(limit)


@app.post("/api/alerts/{alert_id}/read")
@limiter.limit("60/minute")
async def mark_read(request: Request, alert_id: int, _: User = Depends(require_auth)):
    await mark_alert_read(alert_id)
    return {"status": "ok"}


@app.get("/api/brief", response_model=Optional[Brief])
async def get_brief(_: User = Depends(require_auth)):
    return await get_latest_brief()


@app.post("/api/brief/generate")
@limiter.limit("5/minute")
async def trigger_brief_generation(
    request: Request,
    background_tasks: BackgroundTasks,
    _: User = Depends(require_auth),
):
    assets = _state["assets"]
    consensus = _state["consensus"]
    context = _state["context"]
    if not assets:
        assets = await fetch_all_assets()
    if not context:
        context = await fetch_macro_context()
    background_tasks.add_task(generate_brief, assets, consensus, context)
    return {"status": "generating"}


@app.get("/api/me")
async def get_me(current_user: User = Depends(get_optional_user)):
    """Return the currently authenticated user, or null if not authenticated."""
    if current_user is None:
        return {"authenticated": False, "user": None}
    return {
        "authenticated": True,
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "role": current_user.role,
        },
    }


@app.get("/api/correlation")
async def get_correlation(symbols: str = "BTC,ETH,GOLD,OIL", limit: int = 60):
    """Return a pairwise Pearson correlation matrix from recent price history.

    ``symbols`` is a comma-separated list of asset symbols.
    ``limit`` controls how many recent price points to use per symbol.
    """
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if len(syms) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 symbols")

    # Fetch ordered price series for each symbol
    prices: dict[str, list[float]] = {}
    try:
        async with get_db() as db:
            for sym in syms:
                rows = await db.fetchall(
                    "SELECT price FROM price_data WHERE symbol = ? "
                    "ORDER BY timestamp DESC LIMIT ?",
                    (sym, limit),
                )
                if rows:
                    prices[sym] = [r["price"] for r in reversed(rows)]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    def _stats(vals: list[float]) -> tuple[float, float]:
        """Return (mean, std_dev) for a list of floats."""
        n = len(vals)
        mean = sum(vals) / n
        std = sum((v - mean) ** 2 for v in vals) ** 0.5
        return mean, std

    # Symbols that actually have price data
    available = [s for s in syms if s in prices]

    # Pre-compute mean and std-dev once per symbol
    stats: dict[str, tuple[float, float]] = {}
    for sym in available:
        if len(prices[sym]) >= 3:
            stats[sym] = _stats(prices[sym])

    def _pearson(sym_a: str, sym_b: str) -> float | None:
        if sym_a not in stats or sym_b not in stats:
            return None
        x, y = prices[sym_a], prices[sym_b]
        n = min(len(x), len(y))
        if n < 3:
            return None
        x, y = x[:n], y[:n]
        mean_x, std_x = stats[sym_a]
        mean_y, std_y = stats[sym_b]
        if std_x == 0 or std_y == 0:
            return 0.0
        cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        return round(cov / (std_x * std_y), 4)

    matrix: dict[str, dict[str, float | None]] = {}
    for a in available:
        matrix[a] = {}
        for b in available:
            matrix[a][b] = 1.0 if a == b else _pearson(a, b)

    return {"symbols": available, "matrix": matrix, "data_points": limit}


@app.get("/api/performance")
async def get_performance():
    return await get_all_performance()


@app.get("/api/full", response_model=FullMarketData)
async def get_full_data(_: User = Depends(require_auth)):
    return FullMarketData(
        assets=_state["assets"],
        context=_state["context"],
        signals=_state["signals"],
        consensus=_state["consensus"],
        alerts=await get_recent_alerts(20),
        model_outputs=_state["model_outputs"],
    )


@app.post("/api/refresh")
@limiter.limit("5/minute")
async def trigger_refresh(
    request: Request,
    background_tasks: BackgroundTasks,
    _: User = Depends(require_auth),
):
    background_tasks.add_task(run_update_cycle)
    return {"status": "refresh triggered"}


@app.get("/api/history/{symbol}")
async def get_price_history(symbol: str, limit: int = 100):
    try:
        async with get_db() as db:
            rows = await db.fetchall(
                "SELECT * FROM price_data WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?",
                (symbol.upper(), limit),
            )
        return list(rows)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Agent API endpoints ───────────────────────────────────────────────────────
#
# Agent 1 – Orchestrator (COO)
# Agent 2 – Marketing Director
# Agent 3 – Market Intelligence (Chief Analyst)
# Agent 4 – Customer Success (CSM)
# Agent 5 – Analytics (Data Analyst)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/agents/status")
async def get_agent_status():
    """Live status of all 5 platform agents."""
    return await orch_agent._collect_agent_statuses(_state)


@app.get("/api/agents/activity")
async def get_agent_activity(limit: int = 50):
    """Recent activity log across all agents."""
    return await analytics_agent.get_recent_activities(limit)


# ── Agent 1: Orchestrator ─────────────────────────────────────────────────────

@app.get("/api/agents/orchestrator/briefing")
async def get_orchestrator_briefing():
    """Return the latest admin operational briefing."""
    return await orch_agent.get_latest_briefing()


@app.post("/api/agents/orchestrator/briefing/generate")
@limiter.limit("5/minute")
async def trigger_orchestrator_briefing(
    request: Request,
    background_tasks: BackgroundTasks,
    _: User = Depends(require_auth),
):
    """Trigger an on-demand admin briefing."""
    background_tasks.add_task(orch_agent.run_daily_briefing, _state)
    return {"status": "generating"}


@app.post("/api/agents/orchestrator/query")
@limiter.limit("20/minute")
async def orchestrator_query(
    request: Request,
    req: AdminQueryRequest,
    _: User = Depends(require_auth),
):
    """Ask the Orchestrator COO agent an operational question."""
    try:
        query = sanitize_input(req.query)
    except ValueError:
        raise HTTPException(status_code=400, detail="Query contains disallowed content")
    reply = await orch_agent.handle_admin_query(query, _state)
    return {"reply": reply}


# ── Agent 2: Marketing ────────────────────────────────────────────────────────

@app.get("/api/agents/marketing/content")
async def get_marketing_content(limit: int = 20):
    """Return recent AI-generated marketing content."""
    return await mkt_agent.get_recent_content(limit)


@app.post("/api/agents/marketing/generate")
@limiter.limit("5/minute")
async def trigger_marketing_content(
    request: Request,
    background_tasks: BackgroundTasks,
    _: User = Depends(require_auth),
):
    """Trigger on-demand generation of a daily teaser and lead nurture email."""
    background_tasks.add_task(mkt_agent.generate_daily_teaser, _state)
    background_tasks.add_task(mkt_agent.generate_lead_nurture, _state)
    return {"status": "generating"}


@app.post("/api/agents/marketing/lead-insight")
@limiter.limit("10/minute")
async def marketing_lead_insight(
    request: Request,
    req: LeadInsightRequest,
    _: User = Depends(require_auth),
):
    """Generate a personalised insight snippet for a lead context."""
    try:
        lead_context = sanitize_input(req.lead_context)
    except ValueError:
        raise HTTPException(status_code=400, detail="Input contains disallowed content")
    result = await mkt_agent.generate_lead_insight(lead_context, _state)
    return {"insight": result}


# ── Agent 3: Market Intelligence ──────────────────────────────────────────────

@app.get("/api/agents/market-intel/narrative")
async def get_market_narrative():
    """Return the latest narrative market report."""
    return await intel_agent.get_latest_narrative()


@app.post("/api/agents/market-intel/narrative/generate")
@limiter.limit("5/minute")
async def trigger_market_narrative(
    request: Request,
    background_tasks: BackgroundTasks,
    _: User = Depends(require_auth),
):
    """Trigger on-demand generation of a pre-market narrative report."""
    background_tasks.add_task(intel_agent.generate_narrative, "pre_market", _state)
    return {"status": "generating"}


@app.post("/api/agents/market-intel/deep-dive")
@limiter.limit("10/minute")
async def market_intel_deep_dive(
    request: Request,
    req: DeepDiveRequest,
    _: User = Depends(require_auth),
):
    """Produce a detailed AI narrative deep-dive for a single asset."""
    result = await intel_agent.deep_dive(req.symbol, _state)
    return {"asset": req.symbol.upper(), "analysis": result}


# ── Agent 4: Customer Success ─────────────────────────────────────────────────

_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


@app.post("/api/agents/support/chat")
@limiter.limit("30/minute")
async def support_chat(request: Request, req: ChatRequest):
    """Submit a user message to the Customer Success agent.

    If no session_id is provided, a new session is created.
    """
    try:
        msg = sanitize_input(req.message)
    except ValueError:
        raise HTTPException(status_code=400, detail="Message contains disallowed content")
    session_id = req.session_id or str(uuid.uuid4())
    reply = await cs_agent.chat(session_id, msg, _state)
    return {"session_id": session_id, "reply": reply}


@app.post("/api/agents/support/chat/stream")
@limiter.limit("15/minute")
async def support_chat_stream(request: Request, req: ChatRequest):
    """Stream support chat response via Server-Sent Events.

    Emits JSON event objects:
      {"type": "session", "session_id": "..."}
      {"type": "token",   "content": "..."}
      {"type": "done",    "session_id": "..."}
      {"type": "error",   "message": "..."}
    """
    try:
        msg = sanitize_input(req.message)
    except ValueError:
        raise HTTPException(status_code=400, detail="Message contains disallowed content")

    session_id = req.session_id or str(uuid.uuid4())

    async def _event_stream() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"

        if not _OPENAI_API_KEY:
            fallback = (
                "Thanks for reaching out! Our AI support agent is temporarily "
                "unavailable (API key not configured)."
            )
            yield f"data: {json.dumps({'type': 'token', 'content': fallback})}\n\n"
            await cs_agent.save_message(session_id, "user", msg)
            await cs_agent.save_message(session_id, "assistant", fallback)
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
            return

        try:
            from openai import AsyncOpenAI

            history = await cs_agent.get_chat_history(session_id)
            extra_messages = [
                {"role": h["role"], "content": h["message"]} for h in history[-10:]
            ]
            assets = _state.get("assets", [])
            consensus = _state.get("consensus", [])
            asset_names = ", ".join(a.symbol for a in assets) or "loading"
            top_signals = "; ".join(
                f"{c.asset}:{c.final_signal}({c.confidence:.0%})" for c in consensus[:3]
            ) or "pending"
            enriched_system = (
                cs_agent.SYSTEM_PROMPT
                + f"\n\nCurrent platform state — Tracked assets: {asset_names}. "
                f"Top signals: {top_signals}."
            )
            messages = [{"role": "system", "content": enriched_system}]
            messages.extend(extra_messages)
            messages.append({"role": "user", "content": msg})

            client = AsyncOpenAI(api_key=_OPENAI_API_KEY)
            stream = await client.chat.completions.create(
                model="gpt-5.4",
                messages=messages,
                max_tokens=400,
                temperature=0.4,
                stream=True,
            )
            full_reply = ""
            async for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                if content:
                    full_reply += content
                    yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"

            await cs_agent.save_message(session_id, "user", msg)
            await cs_agent.save_message(session_id, "assistant", full_reply)
            await cs_agent.save_activity("chat_stream", f"session={session_id[:8]}")
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
        except Exception as exc:
            logger.warning("SSE chat error: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'message': 'AI service temporarily unavailable'})}\n\n"

    return StreamingResponse(_event_stream(), media_type="text/event-stream")


@app.get("/api/agents/support/chat/{session_id}")
async def get_support_chat_history(session_id: str):
    """Retrieve the full chat history for a support session."""
    history = await cs_agent.get_chat_history(session_id)
    return {"session_id": session_id, "history": history}


@app.post("/api/agents/support/onboard")
@limiter.limit("10/minute")
async def onboard_user(request: Request, req: OnboardRequest):
    """Get a personalised onboarding guide for a new user."""
    guide = await cs_agent.onboard_user(
        req.name or "", req.interest or "", req.experience or "", _state
    )
    return {"guide": guide}


# ── Agent 5: Analytics ────────────────────────────────────────────────────────

@app.get("/api/agents/analytics/kpi")
async def get_kpi_report():
    """Return the latest KPI report from the Analytics agent."""
    return await analytics_agent.get_latest_kpi_report()


@app.post("/api/agents/analytics/kpi/generate")
@limiter.limit("5/minute")
async def trigger_kpi_report(
    request: Request,
    background_tasks: BackgroundTasks,
    _: User = Depends(require_auth),
):
    """Trigger on-demand KPI report generation."""
    background_tasks.add_task(analytics_agent.generate_kpi_report, _state)
    return {"status": "generating"}


@app.post("/api/agents/analytics/anomaly-check")
@limiter.limit("10/minute")
async def anomaly_check(
    request: Request,
    req: AnomalyCheckRequest,
    _: User = Depends(require_auth),
):
    """Run anomaly detection on a custom metrics dictionary."""
    result = await analytics_agent.check_anomalies_from_metrics(req.metrics)
    return {"analysis": result}


# ── Admin: asset configuration ────────────────────────────────────────────────

@app.get("/api/admin/assets")
async def list_configured_assets(_: User = Depends(require_role("admin"))):
    """List all assets in the configured_assets table (active and inactive)."""
    try:
        async with get_db() as db:
            rows = await db.fetchall(
                "SELECT symbol, name, asset_type, source_id, is_active, created_at "
                "FROM configured_assets ORDER BY asset_type, symbol"
            )
        return list(rows)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/admin/assets", status_code=201)
@limiter.limit("20/minute")
async def add_configured_asset(
    request: Request,
    body: AssetConfigRequest,
    _: User = Depends(require_role("admin")),
):
    """Add a new asset to the platform (admin only).

    For crypto, supply the CoinGecko coin ID as ``source_id`` (e.g. ``solana``).
    For commodity, supply the Yahoo Finance ticker (e.g. ``SI=F`` for Silver).
    """
    symbol = body.symbol.upper().strip()
    if body.asset_type not in ("crypto", "commodity"):
        raise HTTPException(status_code=400, detail="asset_type must be 'crypto' or 'commodity'")
    try:
        async with get_db() as db:
            await db.execute(
                """
                INSERT INTO configured_assets (symbol, name, asset_type, source_id, is_active)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(symbol) DO UPDATE SET
                    name = excluded.name,
                    asset_type = excluded.asset_type,
                    source_id = excluded.source_id,
                    is_active = 1
                """,
                (symbol, body.name, body.asset_type, body.source_id),
            )
            await db.commit()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Refresh in-memory asset lists
    await load_configured_assets()
    # Invalidate price caches so new asset is fetched on next cycle
    from services.data_service import _cache
    _cache.pop("crypto_prices", None)
    _cache.pop("commodity_prices", None)

    return {"status": "ok", "symbol": symbol}


@app.delete("/api/admin/assets/{symbol}")
async def remove_configured_asset(
    symbol: str,
    _: User = Depends(require_role("admin")),
):
    """Deactivate an asset (soft-delete).  Default assets can be deactivated
    but will reappear on next restart (they are re-seeded via ``seed_default_assets``).
    """
    sym = symbol.upper().strip()
    try:
        async with get_db() as db:
            await db.execute(
                "UPDATE configured_assets SET is_active = 0 WHERE symbol = ?",
                (sym,),
            )
            await db.commit()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    await load_configured_assets()
    from services.data_service import _cache
    _cache.pop("crypto_prices", None)
    _cache.pop("commodity_prices", None)

    return {"status": "ok", "symbol": sym}


# ── Admin: database export ────────────────────────────────────────────────────

@app.get("/api/admin/db/export")
async def export_database(_: User = Depends(require_role("admin"))):
    """Stream a full SQL dump of the database (admin only).

    For PostgreSQL (production) the dump is produced by ``pg_dump``.
    For SQLite (development) ``aiosqlite``'s ``iterdump()`` is used.

    The response is streamed as an attachment so the caller can pipe it
    directly to a file (equivalent to the Hostinger SSH export guide's
    ``mysqldump … > backup.sql`` pattern, adapted for PostgreSQL/SQLite).
    """
    from db import IS_POSTGRES, DATABASE_URL, DB_PATH

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{timestamp}.sql"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    if IS_POSTGRES:
        # ── PostgreSQL: delegate to pg_dump ───────────────────────────────────
        # Parse connection details from DATABASE_URL so we can pass them as
        # individual pg_dump flags (avoids embedding the password in argv).
        from urllib.parse import urlparse

        parsed = urlparse(DATABASE_URL)
        pg_env = os.environ.copy()
        if parsed.password:
            pg_env["PGPASSWORD"] = parsed.password

        cmd = ["pg_dump", "--no-password"]
        if parsed.hostname:
            cmd += ["-h", parsed.hostname]
        if parsed.port:
            cmd += ["-p", str(parsed.port)]
        if parsed.username:
            cmd += ["-U", parsed.username]
        db_name = parsed.path.lstrip("/")
        if db_name:
            cmd.append(db_name)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=pg_env,
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=500,
                detail="pg_dump not found — install postgresql-client on the server",
            )

        async def _pg_stream() -> AsyncGenerator[bytes, None]:
            assert proc.stdout is not None
            try:
                while True:
                    chunk = await proc.stdout.read(65536)
                    if not chunk:
                        break
                    yield chunk
            finally:
                await proc.wait()
                if proc.returncode != 0:
                    stderr = b""
                    if proc.stderr:
                        stderr = await proc.stderr.read()
                    logger.error("pg_dump failed (rc=%d): %s", proc.returncode, stderr.decode())

        return StreamingResponse(_pg_stream(), media_type="text/plain", headers=headers)

    else:
        # ── SQLite: use aiosqlite iterdump ────────────────────────────────────
        import aiosqlite

        async def _sqlite_stream() -> AsyncGenerator[bytes, None]:
            async with aiosqlite.connect(DB_PATH) as conn:
                async for line in conn.iterdump():
                    yield (line + "\n").encode()

        return StreamingResponse(_sqlite_stream(), media_type="text/plain", headers=headers)


# ── Admin: user management ────────────────────────────────────────────────────

@app.get("/api/admin/users")
async def list_users(_: User = Depends(require_role("admin"))):
    """Return all user accounts (admin only). Passwords are never included."""
    try:
        async with get_db() as db:
            rows = await db.fetchall(
                "SELECT id, username, email, role, is_active, created_at FROM users ORDER BY id"
            )
        return list(rows)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.patch("/api/admin/users/{username}")
@limiter.limit("30/minute")
async def update_user(
    request: Request,
    username: str,
    body: UserUpdateModel,
    current_admin: User = Depends(require_role("admin")),
):
    """Update a user's role or active status (admin only).

    Admins cannot deactivate their own account to prevent lockout.
    """
    if body.role is None and body.is_active is None:
        raise HTTPException(status_code=400, detail="Provide at least one field to update")
    if body.role is not None and body.role not in ("admin", "analyst", "readonly"):
        raise HTTPException(status_code=400, detail="role must be admin, analyst, or readonly")
    # Prevent self-lockout
    if current_admin.username == username and body.is_active is False:
        raise HTTPException(status_code=400, detail="Admins cannot deactivate their own account")
    try:
        async with get_db() as db:
            existing = await db.fetchone(
                "SELECT id FROM users WHERE username = ?", (username,)
            )
            if not existing:
                raise HTTPException(status_code=404, detail="User not found")
            if body.role is not None and body.is_active is not None:
                await db.execute(
                    "UPDATE users SET role = ?, is_active = ? WHERE username = ?",
                    (body.role, 1 if body.is_active else 0, username),
                )
            elif body.role is not None:
                await db.execute(
                    "UPDATE users SET role = ? WHERE username = ?",
                    (body.role, username),
                )
            else:
                await db.execute(
                    "UPDATE users SET is_active = ? WHERE username = ?",
                    (1 if body.is_active else 0, username),
                )
            await db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"status": "ok", "username": username}


# ── User preferences / portfolio ──────────────────────────────────────────────

@app.get("/api/preferences")
async def get_preferences(current_user: User = Depends(require_auth)):
    """Return the authenticated user's preferences."""
    try:
        async with get_db() as db:
            row = await db.fetchone(
                "SELECT preferred_assets, notify_email, email_address, notifications_enabled "
                "FROM user_preferences WHERE user_id = ?",
                (current_user.id,),
            )
        if row is None:
            return UserPreferencesModel()
        return UserPreferencesModel(
            preferred_assets=json.loads(row["preferred_assets"] or "[]"),
            notify_email=bool(row["notify_email"]),
            email_address=row["email_address"] or None,
            notifications_enabled=bool(row["notifications_enabled"]),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.put("/api/preferences")
async def update_preferences(
    body: UserPreferencesModel,
    current_user: User = Depends(require_auth),
):
    """Create or update the authenticated user's preferences."""
    if current_user.id is None:
        raise HTTPException(status_code=400, detail="Cannot save preferences for anonymous user")
    try:
        async with get_db() as db:
            await db.execute(
                """
                INSERT INTO user_preferences
                    (user_id, preferred_assets, notify_email, email_address, notifications_enabled, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    preferred_assets = excluded.preferred_assets,
                    notify_email = excluded.notify_email,
                    email_address = excluded.email_address,
                    notifications_enabled = excluded.notifications_enabled,
                    updated_at = excluded.updated_at
                """,
                (
                    current_user.id,
                    json.dumps(body.preferred_assets),
                    1 if body.notify_email else 0,
                    body.email_address or "",
                    1 if body.notifications_enabled else 0,
                    datetime.now(timezone.utc),
                ),
            )
            await db.commit()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"status": "ok"}
