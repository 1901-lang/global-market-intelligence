"""Agent 6 – Market Research Analyst.

Produces institutional-grade, structured research artifacts:
- Daily research note (platform-wide)
- Intraday update memo
- Asset-specific deep research note
- Thesis change summary (comparing prior vs new thesis)
- Catalyst watch summary

Scheduled tasks
---------------
- Daily 07:30 : pre-market research note
- Daily 17:00 : end-of-day research wrap

API routes (registered in main.py)
-----------------------------------
GET  /api/agents/research/status        – agent status + last run
GET  /api/agents/research/latest        – latest research note (all assets or filtered)
GET  /api/agents/research/notes         – paginated note history
POST /api/agents/research/generate      – generate platform-wide note on demand
POST /api/agents/research/deep-dive     – deep research for a specific asset
POST /api/agents/research/thesis-change – compare prior vs current thesis for an asset
GET  /api/agents/research/catalysts     – latest catalyst events
GET  /api/agents/research/regime        – current regime classification
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from db import get_db
from agents.llm import llm_chat
from services.regime_classifier import classify_regime
from models.schemas import (
    MarketRegime,
    ResearchNote,
    ThesisChange,
    CatalystEvent,
    ScenarioCase,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are the Market Research Analyst AI agent for AIP — an institutional-grade market intelligence platform.
Your role is to produce structured, thesis-driven research for professional users: discretionary macro traders,
crypto macro traders, family offices, and research analysts.

Your research outputs must be:
1. Explicit about the thesis, confidence level, key drivers, and invalidation conditions.
2. Structured with bull/base/bear scenario analysis where appropriate.
3. Honest about contradictory evidence and risks — do not overstate certainty.
4. Regime-aware: incorporate the current market regime into your analytical framing.
5. Clearly labelled as informational and decision-support content — not financial advice.

Always return valid JSON matching the structure requested. Be precise, not verbose.
"""

AGENT_NAME = "research_analyst"

# LLM generation parameters
_LLM_NOTE_MAX_TOKENS = 900
_LLM_DEEP_MAX_TOKENS = 1000
_LLM_THESIS_MAX_TOKENS = 400
_LLM_CATALYST_MAX_TOKENS = 700
_LLM_TEMPERATURE = 0.3


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

async def _save_activity(action_type: str, summary: str, details: Any = None):
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO agent_activities (agent_name, action_type, summary, details, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (AGENT_NAME, action_type, summary, json.dumps(details) if details else None, datetime.utcnow()),
            )
            await db.commit()
    except Exception as exc:
        logger.warning("_save_activity failed: %s", exc)


async def _save_research_note(note: ResearchNote) -> int:
    """Persist a ResearchNote to the database. Returns the inserted row id."""
    try:
        async with get_db() as db:
            await db.execute(
                """INSERT INTO research_notes
                   (asset, note_type, time_horizon, market_regime, thesis, confidence,
                    key_drivers, confirming_evidence, contradictory_evidence, key_risks,
                    catalysts, invalidation_conditions, scenario_analysis, summary, payload, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    note.asset,
                    note.note_type,
                    note.time_horizon,
                    note.market_regime,
                    note.thesis,
                    note.confidence,
                    json.dumps(note.key_drivers),
                    json.dumps(note.confirming_evidence),
                    json.dumps(note.contradictory_evidence),
                    json.dumps(note.key_risks),
                    json.dumps(note.catalysts),
                    json.dumps(note.invalidation_conditions),
                    json.dumps([s.model_dump() for s in note.scenario_analysis]),
                    note.summary,
                    json.dumps(note.model_dump(mode="json")),
                    datetime.utcnow(),
                ),
            )
            await db.commit()
            row = await db.fetchone("SELECT last_insert_rowid() as id")
            return row["id"] if row else 0
    except Exception as exc:
        logger.warning("_save_research_note failed: %s", exc)
        return 0


async def _save_thesis_change(change: ThesisChange):
    try:
        async with get_db() as db:
            await db.execute(
                """INSERT INTO thesis_history
                   (asset, prior_thesis, new_thesis, change_summary, drivers_of_change, confidence_delta, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    change.asset,
                    change.prior_thesis,
                    change.new_thesis,
                    change.change_summary,
                    json.dumps(change.drivers_of_change),
                    change.confidence_delta,
                    datetime.utcnow(),
                ),
            )
            await db.commit()
    except Exception as exc:
        logger.warning("_save_thesis_change failed: %s", exc)


async def _save_regime(regime: MarketRegime):
    try:
        async with get_db() as db:
            await db.execute(
                """INSERT INTO market_regimes
                   (label, rationale, contributing_factors, confidence, timestamp)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    regime.label,
                    regime.rationale,
                    json.dumps(regime.contributing_factors),
                    regime.confidence,
                    datetime.utcnow(),
                ),
            )
            await db.commit()
    except Exception as exc:
        logger.warning("_save_regime failed: %s", exc)


async def _save_catalyst(catalyst: CatalystEvent):
    try:
        async with get_db() as db:
            await db.execute(
                """INSERT INTO catalyst_events
                   (title, event_type, asset_scope, event_time, importance, expected_impact, status, notes, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    catalyst.title,
                    catalyst.event_type,
                    json.dumps(catalyst.asset_scope),
                    catalyst.event_time.isoformat() if catalyst.event_time else None,
                    catalyst.importance,
                    catalyst.expected_impact,
                    catalyst.status,
                    catalyst.notes,
                    datetime.utcnow(),
                ),
            )
            await db.commit()
    except Exception as exc:
        logger.warning("_save_catalyst failed: %s", exc)


def _row_to_note(row: Dict) -> Dict:
    """Convert a raw DB row to a serialisable dict for API responses."""
    return {
        "id": row["id"],
        "asset": row["asset"],
        "note_type": row["note_type"],
        "time_horizon": row["time_horizon"],
        "market_regime": row["market_regime"],
        "thesis": row["thesis"],
        "confidence": row["confidence"],
        "key_drivers": json.loads(row["key_drivers"] or "[]"),
        "confirming_evidence": json.loads(row["confirming_evidence"] or "[]"),
        "contradictory_evidence": json.loads(row["contradictory_evidence"] or "[]"),
        "key_risks": json.loads(row["key_risks"] or "[]"),
        "catalysts": json.loads(row["catalysts"] or "[]"),
        "invalidation_conditions": json.loads(row["invalidation_conditions"] or "[]"),
        "scenario_analysis": json.loads(row["scenario_analysis"] or "[]"),
        "summary": row["summary"],
        "timestamp": row["timestamp"],
    }


async def get_latest_note(asset: Optional[str] = None) -> Optional[Dict]:
    try:
        async with get_db() as db:
            if asset:
                row = await db.fetchone(
                    "SELECT * FROM research_notes WHERE asset = ? ORDER BY timestamp DESC LIMIT 1",
                    (asset.upper(),),
                )
            else:
                row = await db.fetchone(
                    "SELECT * FROM research_notes ORDER BY timestamp DESC LIMIT 1"
                )
        return _row_to_note(row) if row else None
    except Exception as exc:
        logger.warning("get_latest_note failed: %s", exc)
        return None


async def get_notes(limit: int = 20, asset: Optional[str] = None) -> List[Dict]:
    try:
        async with get_db() as db:
            if asset:
                rows = await db.fetchall(
                    "SELECT * FROM research_notes WHERE asset = ? ORDER BY timestamp DESC LIMIT ?",
                    (asset.upper(), limit),
                )
            else:
                rows = await db.fetchall(
                    "SELECT * FROM research_notes ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                )
        return [_row_to_note(r) for r in rows]
    except Exception as exc:
        logger.warning("get_notes failed: %s", exc)
        return []


async def get_latest_regime() -> Optional[Dict]:
    try:
        async with get_db() as db:
            row = await db.fetchone(
                "SELECT * FROM market_regimes ORDER BY timestamp DESC LIMIT 1"
            )
        if not row:
            return None
        return {
            "id": row["id"],
            "label": row["label"],
            "rationale": row["rationale"],
            "contributing_factors": json.loads(row["contributing_factors"] or "[]"),
            "confidence": row["confidence"],
            "timestamp": row["timestamp"],
        }
    except Exception as exc:
        logger.warning("get_latest_regime failed: %s", exc)
        return None


async def get_catalysts(limit: int = 20, status: Optional[str] = None) -> List[Dict]:
    try:
        async with get_db() as db:
            if status:
                rows = await db.fetchall(
                    "SELECT * FROM catalyst_events WHERE status = ? ORDER BY timestamp DESC LIMIT ?",
                    (status, limit),
                )
            else:
                rows = await db.fetchall(
                    "SELECT * FROM catalyst_events ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                )
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "event_type": r["event_type"],
                "asset_scope": json.loads(r["asset_scope"] or "[]"),
                "event_time": r["event_time"],
                "importance": r["importance"],
                "expected_impact": r["expected_impact"],
                "status": r["status"],
                "notes": r["notes"],
                "timestamp": r["timestamp"],
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning("get_catalysts failed: %s", exc)
        return []


async def get_agent_status() -> Dict:
    try:
        async with get_db() as db:
            last_activity = await db.fetchone(
                "SELECT * FROM agent_activities WHERE agent_name = ? ORDER BY timestamp DESC LIMIT 1",
                (AGENT_NAME,),
            )
            latest_note = await db.fetchone(
                "SELECT note_type, asset, timestamp FROM research_notes ORDER BY timestamp DESC LIMIT 1"
            )
        return {
            "agent": AGENT_NAME,
            "status": "active",
            "last_run": last_activity["timestamp"] if last_activity else None,
            "latest_note_type": latest_note["note_type"] if latest_note else None,
            "latest_note_asset": latest_note["asset"] if latest_note else None,
            "notes": "Generating structured research artifacts for institutional users",
        }
    except Exception as exc:
        logger.warning("get_agent_status failed: %s", exc)
        return {"agent": AGENT_NAME, "status": "idle", "notes": "Status check failed"}


# ---------------------------------------------------------------------------
# Snapshot builder
# ---------------------------------------------------------------------------

def _build_research_context(state: Dict) -> str:
    assets = state.get("assets", [])
    consensus = state.get("consensus", [])
    ctx = state.get("context")

    lines = [f"- {a.symbol} ({a.name}): ${a.price:,.2f}, 24h {(a.change_24h or 0):+.2f}%, vol ${(a.volume_24h or 0)/1e9:.1f}B" for a in assets]
    cons_lines = [
        f"- {c.asset}: {c.final_signal} confidence={c.confidence:.0%} agreement={c.agreement_level}"
        + (f" dissenting={c.dissenting_models}" if c.dissenting_models else "")
        for c in consensus
    ]
    macro_parts = []
    if ctx:
        if ctx.usd_index:
            macro_parts.append(f"DXY={ctx.usd_index:.2f}")
        if ctx.bond_yield_10y:
            macro_parts.append(f"10Y={ctx.bond_yield_10y:.2f}%")
        if ctx.vix:
            macro_parts.append(f"VIX={ctx.vix:.1f}")
        if ctx.news_sentiment is not None:
            macro_parts.append(f"Sentiment={ctx.news_sentiment:+.2f}")

    result = "ASSET PRICES:\n" + ("\n".join(lines) or "No live data available")
    if cons_lines:
        result += "\n\nAI CONSENSUS SIGNALS:\n" + "\n".join(cons_lines)
    if macro_parts:
        result += "\n\nMACRO CONTEXT: " + ", ".join(macro_parts)
    return result


# ---------------------------------------------------------------------------
# Structured note generation
# ---------------------------------------------------------------------------

def _fallback_note(asset: str, note_type: str, state: Dict, regime: MarketRegime) -> ResearchNote:
    """Build a deterministic fallback note when no LLM key is available."""
    assets = state.get("assets", [])
    consensus = state.get("consensus", [])

    top_signal = next((c for c in consensus), None)

    if asset == "PLATFORM":
        thesis = (
            f"Platform-wide view: {len(assets)} assets monitored under a {regime.label.replace('_',' ')} regime. "
            f"Dominant AI signal: {top_signal.final_signal if top_signal else 'mixed'}."
        )
        drivers = [
            f"Regime: {regime.label}",
            f"Consensus signals: {', '.join(c.asset + ':' + c.final_signal for c in consensus[:4])}",
            f"Macro: {regime.rationale[:100]}",
        ]
        summary = f"Platform operating in {regime.label} regime. {len(consensus)} assets with AI consensus. Add OPENAI_API_KEY for full institutional research."
    else:
        a = next((x for x in assets if x.symbol == asset), None)
        c = next((x for x in consensus if x.asset == asset), None)
        thesis = (
            f"{asset}: price ${a.price:,.2f} " if a else f"{asset}: no live price data. "
        ) + (f"AI consensus: {c.final_signal} ({c.confidence:.0%})." if c else "No consensus yet.")
        drivers = [
            f"AI signal: {c.final_signal if c else 'unavailable'}",
            f"Regime: {regime.label}",
        ]
        summary = f"Fallback note for {asset}. Add OPENAI_API_KEY for full structured research output."

    return ResearchNote(
        asset=asset,
        note_type=note_type,
        time_horizon="1-3d",
        market_regime=regime.label,
        thesis=thesis,
        confidence=0.4,
        key_drivers=drivers,
        confirming_evidence=[],
        contradictory_evidence=[],
        key_risks=["No API key configured — analysis quality reduced"],
        catalysts=[],
        invalidation_conditions=["Add OPENAI_API_KEY to enable full research"],
        scenario_analysis=[
            ScenarioCase(label="base", thesis=thesis, probability=0.5, catalysts=[], risks=[])
        ],
        summary=summary,
        timestamp=datetime.utcnow(),
    )


def _parse_llm_note(raw: str, asset: str, note_type: str, regime: MarketRegime) -> Optional[ResearchNote]:
    """Try to parse an LLM JSON response into a ResearchNote. Returns None on failure."""
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        data = json.loads(raw[start:end])

        scenarios = []
        for s in data.get("scenario_analysis", []):
            scenarios.append(ScenarioCase(
                label=s.get("label", "base"),
                probability=s.get("probability"),
                thesis=s.get("thesis", ""),
                price_target=s.get("price_target"),
                catalysts=s.get("catalysts", []),
                risks=s.get("risks", []),
            ))

        return ResearchNote(
            asset=asset,
            note_type=note_type,
            time_horizon=data.get("time_horizon", "1-3d"),
            market_regime=regime.label,
            thesis=data.get("thesis", ""),
            confidence=float(data.get("confidence", 0.5)),
            key_drivers=data.get("key_drivers", []),
            confirming_evidence=data.get("confirming_evidence", []),
            contradictory_evidence=data.get("contradictory_evidence", []),
            key_risks=data.get("key_risks", []),
            catalysts=data.get("catalysts", []),
            invalidation_conditions=data.get("invalidation_conditions", []),
            scenario_analysis=scenarios,
            summary=data.get("summary", ""),
            timestamp=datetime.utcnow(),
        )
    except Exception as exc:
        logger.warning("_parse_llm_note failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Core agent tasks
# ---------------------------------------------------------------------------

async def generate_daily_note(state: Dict) -> ResearchNote:
    """Generate and persist a platform-wide daily research note."""
    logger.info("ResearchAnalyst: generating daily note")
    ctx = state.get("context")
    regime = classify_regime(ctx)
    await _save_regime(regime)

    context_str = _build_research_context(state)
    today = date.today().strftime("%B %d, %Y")

    prompt = f"""Today: {today}
Regime: {regime.label} (confidence {regime.confidence:.0%})
Regime rationale: {regime.rationale}

{context_str}

Generate a structured daily research note as JSON with EXACTLY this structure:
{{
  "time_horizon": "1-3d",
  "thesis": "one clear sentence stating the directional view",
  "confidence": 0.0-1.0,
  "key_drivers": ["driver1", "driver2", "driver3"],
  "confirming_evidence": ["evidence1", "evidence2"],
  "contradictory_evidence": ["counter1", "counter2"],
  "key_risks": ["risk1", "risk2"],
  "catalysts": ["catalyst1", "catalyst2"],
  "invalidation_conditions": ["if X happens, thesis is wrong"],
  "scenario_analysis": [
    {{"label": "bull", "probability": 0.3, "thesis": "...", "price_target": null, "catalysts": [], "risks": []}},
    {{"label": "base", "probability": 0.5, "thesis": "...", "price_target": null, "catalysts": [], "risks": []}},
    {{"label": "bear", "probability": 0.2, "thesis": "...", "price_target": null, "catalysts": [], "risks": []}}
  ],
  "summary": "2-3 sentence executive summary"
}}

Return ONLY the JSON object. No markdown, no explanation."""

    raw = await llm_chat(
        SYSTEM_PROMPT, prompt,
        max_tokens=_LLM_NOTE_MAX_TOKENS,
        temperature=_LLM_TEMPERATURE,
        fallback="",
    )

    note = _parse_llm_note(raw, "PLATFORM", "daily_note", regime) if raw else None
    if note is None:
        note = _fallback_note("PLATFORM", "daily_note", state, regime)

    await _save_research_note(note)
    await _save_activity("daily_note", f"Platform daily note — regime: {regime.label}")
    logger.info("ResearchAnalyst: daily note saved (regime=%s)", regime.label)
    return note


async def generate_deep_research(asset_symbol: str, state: Dict) -> ResearchNote:
    """Generate and persist an asset-specific deep research note."""
    asset_symbol = asset_symbol.upper()
    logger.info("ResearchAnalyst: deep research for %s", asset_symbol)

    ctx = state.get("context")
    regime = classify_regime(ctx)

    assets = state.get("assets", [])
    consensus = state.get("consensus", [])
    asset = next((a for a in assets if a.symbol == asset_symbol), None)
    cons = next((c for c in consensus if c.asset == asset_symbol), None)

    asset_line = (
        f"{asset.name} ({asset_symbol}): ${asset.price:,.2f}, "
        f"1h {(asset.change_1h or 0):+.2f}%, 24h {(asset.change_24h or 0):+.2f}%, "
        f"vol ${(asset.volume_24h or 0)/1e9:.2f}B"
        if asset else f"{asset_symbol}: price data unavailable"
    )
    cons_line = ""
    if cons:
        model_votes = "; ".join(
            f"{m}: {v.get('signal','?')}({v.get('confidence',0):.0%})"
            for m, v in (cons.models or {}).items()
        )
        cons_line = (
            f"Consensus: {cons.final_signal} ({cons.confidence:.0%}, {cons.agreement_level} agreement)\n"
            f"Model votes: {model_votes}\n"
            f"Dissenting: {cons.dissenting_models or 'none'}"
        )

    macro_parts = []
    if ctx:
        for label, val, fmt in [
            ("DXY", ctx.usd_index, "{:.2f}"),
            ("10Y", ctx.bond_yield_10y, "{:.2f}%"),
            ("VIX", ctx.vix, "{:.1f}"),
            ("Sentiment", ctx.news_sentiment, "{:+.2f}"),
        ]:
            if val is not None:
                macro_parts.append(f"{label}={fmt.format(val)}")

    prompt = f"""Asset: {asset_symbol}
Regime: {regime.label} ({regime.rationale[:120]})
{asset_line}
{cons_line}
Macro: {', '.join(macro_parts) or 'unavailable'}

Generate a deep research note as JSON:
{{
  "time_horizon": "1w",
  "thesis": "clear directional thesis for {asset_symbol}",
  "confidence": 0.0-1.0,
  "key_drivers": ["driver1", "driver2", "driver3", "driver4"],
  "confirming_evidence": ["evidence1", "evidence2"],
  "contradictory_evidence": ["counter1", "counter2"],
  "key_risks": ["risk1", "risk2", "risk3"],
  "catalysts": ["catalyst1", "catalyst2"],
  "invalidation_conditions": ["condition that would invalidate thesis"],
  "scenario_analysis": [
    {{"label": "bull", "probability": 0.3, "thesis": "bull case for {asset_symbol}", "price_target": "$X", "catalysts": [], "risks": []}},
    {{"label": "base", "probability": 0.5, "thesis": "base case", "price_target": "$X", "catalysts": [], "risks": []}},
    {{"label": "bear", "probability": 0.2, "thesis": "bear case", "price_target": "$X", "catalysts": [], "risks": []}}
  ],
  "summary": "2-3 sentence analytical summary"
}}

Return ONLY the JSON object."""

    raw = await llm_chat(
        SYSTEM_PROMPT, prompt,
        max_tokens=_LLM_DEEP_MAX_TOKENS,
        temperature=_LLM_TEMPERATURE,
        fallback="",
    )

    note = _parse_llm_note(raw, asset_symbol, "deep_research", regime) if raw else None
    if note is None:
        note = _fallback_note(asset_symbol, "deep_research", state, regime)

    await _save_research_note(note)
    await _save_activity("deep_research", f"Deep research: {asset_symbol}")
    return note


async def generate_thesis_change(asset_symbol: str, state: Dict) -> ThesisChange:
    """Compare the two most recent notes for an asset to produce a ThesisChange."""
    asset_symbol = asset_symbol.upper()
    logger.info("ResearchAnalyst: thesis change for %s", asset_symbol)

    try:
        async with get_db() as db:
            rows = await db.fetchall(
                "SELECT * FROM research_notes WHERE asset = ? ORDER BY timestamp DESC LIMIT 2",
                (asset_symbol,),
            )
    except Exception:
        rows = []

    if len(rows) < 2:
        prior_note = await get_latest_note(asset_symbol)
        current_note = await generate_deep_research(asset_symbol, state)
        prior_thesis = prior_note["thesis"] if prior_note else "No prior thesis on record."
        current_thesis = current_note.thesis
    else:
        current_row, prior_row = rows[0], rows[1]
        current_thesis = current_row["thesis"]
        prior_thesis = prior_row["thesis"]

    ctx = state.get("context")
    regime = classify_regime(ctx)

    prompt = f"""Asset: {asset_symbol}
Prior thesis: {prior_thesis}
Current thesis: {current_thesis}
Regime: {regime.label}

Analyse what changed between the prior and current thesis. Return JSON:
{{
  "change_summary": "one sentence describing what changed and why",
  "drivers_of_change": ["key driver 1", "key driver 2"],
  "confidence_delta": -0.3 to +0.3 (change in conviction)
}}

Return ONLY the JSON object."""

    raw = await llm_chat(
        SYSTEM_PROMPT, prompt,
        max_tokens=_LLM_THESIS_MAX_TOKENS,
        temperature=_LLM_TEMPERATURE,
        fallback="",
    )

    change_summary = "View unchanged or insufficient data to determine thesis shift."
    drivers = []
    confidence_delta = 0.0

    if raw:
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > 0:
                data = json.loads(raw[start:end])
                change_summary = data.get("change_summary", change_summary)
                drivers = data.get("drivers_of_change", [])
                confidence_delta = float(data.get("confidence_delta", 0.0))
        except Exception:
            pass

    change = ThesisChange(
        asset=asset_symbol,
        prior_thesis=prior_thesis,
        new_thesis=current_thesis,
        change_summary=change_summary,
        drivers_of_change=drivers,
        confidence_delta=confidence_delta,
        timestamp=datetime.utcnow(),
    )
    await _save_thesis_change(change)
    await _save_activity("thesis_change", f"Thesis change: {asset_symbol}")
    return change


async def generate_catalyst_memo(state: Dict) -> List[CatalystEvent]:
    """Generate catalyst events from current market state."""
    logger.info("ResearchAnalyst: generating catalyst memo")

    context_str = _build_research_context(state)
    ctx = state.get("context")
    regime = classify_regime(ctx)
    today = date.today().strftime("%B %d, %Y")

    prompt = f"""Today: {today}
Regime: {regime.label}

{context_str}

Identify 3-5 key catalyst events relevant to the tracked assets. Return a JSON array:
[
  {{
    "title": "Event title",
    "event_type": "economic_data|central_bank|earnings|geopolitical|technical|other",
    "asset_scope": ["BTC", "Gold"],
    "importance": "high|medium|low",
    "expected_impact": "brief statement of directional impact",
    "status": "pending|active",
    "notes": "context note"
  }}
]

Return ONLY the JSON array."""

    raw = await llm_chat(
        SYSTEM_PROMPT, prompt,
        max_tokens=_LLM_CATALYST_MAX_TOKENS,
        temperature=_LLM_TEMPERATURE,
        fallback="",
    )

    catalysts: List[CatalystEvent] = []
    if raw:
        try:
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start != -1 and end > 0:
                items = json.loads(raw[start:end])
                for item in items:
                    cat = CatalystEvent(
                        title=item.get("title", "Unknown event"),
                        event_type=item.get("event_type", "other"),
                        asset_scope=item.get("asset_scope", []),
                        importance=item.get("importance", "medium"),
                        expected_impact=item.get("expected_impact"),
                        status=item.get("status", "pending"),
                        notes=item.get("notes"),
                        timestamp=datetime.utcnow(),
                    )
                    catalysts.append(cat)
                    await _save_catalyst(cat)
        except Exception as exc:
            logger.warning("catalyst parse failed: %s", exc)

    if not catalysts:
        # Fallback: generate placeholder catalysts from signals
        consensus = state.get("consensus", [])
        for c in consensus[:3]:
            if c.final_signal in ("BUY", "SELL"):
                cat = CatalystEvent(
                    title=f"{c.asset} AI signal change: {c.final_signal} ({c.confidence:.0%})",
                    event_type="technical",
                    asset_scope=[c.asset],
                    importance="medium" if c.confidence < 0.8 else "high",
                    expected_impact=f"Consensus shifted to {c.final_signal} with {c.agreement_level} model agreement",
                    status="active",
                    notes="Generated from AI consensus — add OPENAI_API_KEY for richer catalyst analysis",
                    timestamp=datetime.utcnow(),
                )
                catalysts.append(cat)
                await _save_catalyst(cat)

    await _save_activity("catalyst_memo", f"Generated {len(catalysts)} catalysts")
    return catalysts


async def run_premarket_note(state: Dict):
    """Scheduled task: pre-market research note at 07:30."""
    await generate_daily_note(state)


async def run_eod_wrap(state: Dict):
    """Scheduled task: end-of-day research wrap at 17:00."""
    ctx = state.get("context")
    regime = classify_regime(ctx)
    await _save_regime(regime)

    context_str = _build_research_context(state)
    today = date.today().strftime("%B %d, %Y")

    prompt = f"""Today: {today} (End of Day)
Regime: {regime.label}

{context_str}

Generate an end-of-day research wrap note as JSON:
{{
  "time_horizon": "overnight",
  "thesis": "end-of-day directional view",
  "confidence": 0.0-1.0,
  "key_drivers": ["key mover 1", "key mover 2"],
  "confirming_evidence": [],
  "contradictory_evidence": [],
  "key_risks": ["overnight risk 1", "overnight risk 2"],
  "catalysts": ["tomorrow's key catalyst"],
  "invalidation_conditions": ["what would change the overnight view"],
  "scenario_analysis": [
    {{"label": "bull", "probability": 0.35, "thesis": "bull overnight case", "price_target": null, "catalysts": [], "risks": []}},
    {{"label": "base", "probability": 0.45, "thesis": "base case", "price_target": null, "catalysts": [], "risks": []}},
    {{"label": "bear", "probability": 0.20, "thesis": "bear overnight case", "price_target": null, "catalysts": [], "risks": []}}
  ],
  "summary": "end-of-day summary and overnight positioning note"
}}

Return ONLY the JSON object."""

    raw = await llm_chat(SYSTEM_PROMPT, prompt, max_tokens=_LLM_NOTE_MAX_TOKENS, temperature=_LLM_TEMPERATURE, fallback="")
    note = _parse_llm_note(raw, "PLATFORM", "intraday_update", regime) if raw else None
    if note is None:
        note = _fallback_note("PLATFORM", "intraday_update", state, regime)

    await _save_research_note(note)
    await _save_activity("eod_wrap", f"EOD wrap — regime: {regime.label}")
    logger.info("ResearchAnalyst: EOD wrap saved")
