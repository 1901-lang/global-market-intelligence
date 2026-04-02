import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

import aiosqlite
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from database import DB_PATH, init_db
from models.schemas import (
    AssetPrice,
    Alert,
    Brief,
    ConsensusResult,
    FullMarketData,
    MarketContext,
    ModelOutput,
    ModelPerformance,
)
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

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

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
    async with aiosqlite.connect(DB_PATH) as db:
        for a in assets:
            await db.execute(
                """INSERT INTO price_data (symbol, price, change_1h, change_24h, volume_24h, market_cap, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (a.symbol, a.price, a.change_1h, a.change_24h, a.volume_24h, a.market_cap, datetime.utcnow()),
            )
        await db.commit()


async def _persist_context(ctx: MarketContext):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO market_context (usd_index, bond_yield_10y, vix, news_sentiment, on_chain_activity, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ctx.usd_index, ctx.bond_yield_10y, ctx.vix, ctx.news_sentiment, ctx.on_chain_activity, datetime.utcnow()),
        )
        await db.commit()


async def _persist_consensus(c: ConsensusResult):
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    asyncio.create_task(_background_scheduler())
    yield


app = FastAPI(
    title="AIP — Agentic Multi-Model Market Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow()}


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
async def mark_read(alert_id: int):
    await mark_alert_read(alert_id)
    return {"status": "ok"}


@app.get("/api/brief", response_model=Optional[Brief])
async def get_brief():
    return await get_latest_brief()


@app.post("/api/brief/generate")
async def trigger_brief_generation(background_tasks: BackgroundTasks):
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
async def trigger_refresh(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_update_cycle)
    return {"status": "refresh triggered"}


@app.get("/api/history/{symbol}")
async def get_price_history(symbol: str, limit: int = 100):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM price_data WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?",
                (symbol.upper(), limit),
            ) as cursor:
                rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
