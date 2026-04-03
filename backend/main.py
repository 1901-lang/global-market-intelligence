import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, HTTPException, BackgroundTasks, Request, status
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
    CatalystEvent,
    ChatRequest,
    ConsensusResult,
    DeepDiveRequest,
    FullMarketData,
    GenerateResearchRequest,
    LeadInsightRequest,
    MarketContext,
    MarketIntelReport,
    MarketRegime,
    MarketingContentItem,
    ModelOutput,
    ModelPerformance,
    OnboardRequest,
    OrchestratorBriefing,
    ResearchAgentStatus,
    ResearchNote,
    ThesisChange,
    ThesisChangeRequest,
)
from security import sanitize_input
from services.data_service import fetch_all_assets, fetch_macro_context
from services.signal_engine import generate_all_signals
from services.model_wrapper import query_all_models, debate_loop
from services.consensus_engine import compute_consensus
from services.learning_engine import (
    get_model_weights,
    record_prediction,
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
import agents.research as research_agent

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
        _state["last_updated"] = datetime.utcnow()

        logger.info(f"Update cycle complete. Assets: {len(assets)}, Consensus results: {len(all_consensus)}")
    except Exception as exc:
        logger.exception(f"Update cycle failed: {exc}")


async def _persist_assets(assets: List[AssetPrice]):
    async with get_db() as db:
        for a in assets:
            await db.execute(
                """INSERT INTO price_data (symbol, price, change_1h, change_24h, volume_24h, market_cap, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (a.symbol, a.price, a.change_1h, a.change_24h, a.volume_24h, a.market_cap, datetime.utcnow()),
            )
        await db.commit()


async def _persist_context(ctx: MarketContext):
    async with get_db() as db:
        await db.execute(
            """INSERT INTO market_context (usd_index, bond_yield_10y, vix, news_sentiment, on_chain_activity, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ctx.usd_index, ctx.bond_yield_10y, ctx.vix, ctx.news_sentiment, ctx.on_chain_activity, datetime.utcnow()),
        )
        await db.commit()


async def _persist_consensus(c: ConsensusResult):
    async with get_db() as db:
        await db.execute(
            """INSERT INTO consensus_results (asset, final_signal, confidence, agreement_level, models_json, dissenting_models, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                c.asset, c.final_signal, c.confidence, c.agreement_level,
                json.dumps(c.models), json.dumps(c.dissenting_models), datetime.utcnow(),
            ),
        )
        await db.commit()


async def _persist_model_outputs(outputs: List[ModelOutput]):
    async with get_db() as db:
        for o in outputs:
            await db.execute(
                """INSERT INTO model_outputs (asset, model_name, signal, confidence, reasoning, raw_response, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (o.asset, o.model_name, o.signal, o.confidence, json.dumps(o.reasoning), o.raw_response, datetime.utcnow()),
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

    # Research Analyst – pre-market 07:30, EOD wrap 17:00
    sched.add_job(
        research_agent.run_premarket_note,
        "cron", hour=7, minute=30, id="research_premarket",
        args=[_state],
    )
    sched.add_job(
        research_agent.run_eod_wrap,
        "cron", hour=17, minute=0, id="research_eod_wrap",
        args=[_state],
    )

    return sched


def _startup_key_check():
    """Warn on missing keys; fail fast in production (REQUIRE_AUTH=true)."""
    missing = []
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if not os.getenv("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")
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
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        "timestamp": datetime.utcnow(),
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
async def get_brief():
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


@app.get("/api/performance")
async def get_performance():
    return await get_all_performance()


@app.get("/api/full", response_model=FullMarketData)
async def get_full_data():
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


# ── Agent 6: Market Research Analyst ─────────────────────────────────────────

@app.get("/api/agents/research/status")
async def get_research_agent_status():
    """Return research analyst agent status."""
    return await research_agent.get_agent_status()


@app.get("/api/agents/research/latest")
async def get_latest_research_note(asset: Optional[str] = None):
    """Return the latest research note (platform-wide or asset-specific)."""
    return await research_agent.get_latest_note(asset)


@app.get("/api/agents/research/notes")
async def get_research_notes(limit: int = 20, asset: Optional[str] = None):
    """Return paginated research note history."""
    return await research_agent.get_notes(limit, asset)


@app.post("/api/agents/research/generate")
@limiter.limit("5/minute")
async def generate_research_note(
    request: Request,
    req: GenerateResearchRequest,
    background_tasks: BackgroundTasks,
    _: User = Depends(require_auth),
):
    """Trigger on-demand research note generation."""
    background_tasks.add_task(research_agent.generate_daily_note, _state)
    return {"status": "generating", "note_type": req.note_type}


@app.post("/api/agents/research/deep-dive")
@limiter.limit("10/minute")
async def research_deep_dive(
    request: Request,
    req: DeepDiveRequest,
    _: User = Depends(require_auth),
):
    """Generate an asset-specific deep research note."""
    note = await research_agent.generate_deep_research(req.symbol, _state)
    return note.model_dump(mode="json")


@app.post("/api/agents/research/thesis-change")
@limiter.limit("10/minute")
async def research_thesis_change(
    request: Request,
    req: ThesisChangeRequest,
    _: User = Depends(require_auth),
):
    """Compare prior vs current thesis for an asset."""
    try:
        symbol = sanitize_input(req.symbol)
    except ValueError:
        raise HTTPException(status_code=400, detail="Input contains disallowed content")
    change = await research_agent.generate_thesis_change(symbol, _state)
    return change.model_dump(mode="json")


@app.get("/api/agents/research/catalysts")
async def get_research_catalysts(limit: int = 20, status: Optional[str] = None):
    """Return recent catalyst events."""
    return await research_agent.get_catalysts(limit, status)


@app.post("/api/agents/research/catalysts/generate")
@limiter.limit("5/minute")
async def generate_catalysts(
    request: Request,
    background_tasks: BackgroundTasks,
    _: User = Depends(require_auth),
):
    """Trigger on-demand catalyst memo generation."""
    background_tasks.add_task(research_agent.generate_catalyst_memo, _state)
    return {"status": "generating"}


@app.get("/api/agents/research/regime")
async def get_market_regime():
    """Return the latest market regime classification."""
    saved = await research_agent.get_latest_regime()
    if saved:
        return saved
    from services.regime_classifier import classify_regime
    regime = classify_regime(_state.get("context"))
    return regime.model_dump(mode="json")
