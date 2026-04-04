"""Agent 3 – Market Intelligence Agent (Chief Analyst).

Produces deeper narrative analysis and asset deep-dives that go beyond
the existing consensus engine's structured JSON output.

Scheduled tasks
---------------
- Daily 07:00 : generate a pre-market narrative report.
- Daily 16:30 : generate an end-of-day narrative summary.

API routes (registered in main.py)
-----------------------------------
GET  /api/agents/market-intel/narrative    – latest narrative report
POST /api/agents/market-intel/deep-dive   – deep-dive on a named asset
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional

from db import get_db

from agents.llm import llm_chat

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are the Market Intelligence AI agent for AIP — an institutional-grade market intelligence \
platform serving professional traders, portfolio managers, and risk desks at hedge funds, \
asset managers, and proprietary trading firms globally. You are the Chief Analyst.
Your responsibilities:
1. Produce rigorous, institutional-grade narrative analysis — covering price action, technicals, \
   macro regime context, cross-asset correlations, and structural trends.
2. Frame analysis in terms professional traders use: momentum, mean-reversion, carry, \
   convexity, risk-adjusted returns, drawdown risk, and positioning dynamics.
3. Identify macro themes and regime shifts (risk-on / risk-off, USD carry unwind, \
   commodity supercycle, yield curve dynamics) relevant to multi-asset portfolios.
4. Always note: content is for informational purposes only — not investment advice. \
   Institutional clients should apply their own risk frameworks.
Be data-first, rigorous, and precise. Avoid retail-oriented language.
"""


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

async def _save_narrative(report_type: str, content: str, assets_covered: List[str]):
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO market_intel_reports (report_type, content, assets_covered, date, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    report_type,
                    content,
                    json.dumps(assets_covered),
                    date.today().isoformat(),
                    datetime.now(timezone.utc),
                ),
            )
            await db.commit()
    except Exception as exc:
        logger.warning("_save_narrative failed: %s", exc)


async def get_latest_narrative() -> Optional[Dict]:
    try:
        async with get_db() as db:
            row = await db.fetchone(
                "SELECT * FROM market_intel_reports ORDER BY timestamp DESC LIMIT 1"
            )
        if not row:
            return None
        return {
            "id": row["id"],
            "report_type": row["report_type"],
            "content": row["content"],
            "assets_covered": json.loads(row["assets_covered"] or "[]"),
            "date": row["date"],
            "timestamp": row["timestamp"],
        }
    except Exception as exc:
        logger.warning("get_latest_narrative failed: %s", exc)
        return None


async def _save_activity(action_type: str, summary: str):
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO agent_activities (agent_name, action_type, summary, timestamp) "
                "VALUES (?, ?, ?, ?)",
                ("market_intelligence", action_type, summary, datetime.now(timezone.utc)),
            )
            await db.commit()
    except Exception as exc:
        logger.warning("_save_activity failed: %s", exc)


def _build_market_snapshot(state: Dict) -> str:
    assets = state.get("assets", [])
    consensus = state.get("consensus", [])
    ctx = state.get("context")

    lines = [f"- {a.symbol}: ${a.price:,.2f} ({(a.change_24h or 0):+.2f}%)" for a in assets]
    signal_lines = [
        f"- {c.asset}: {c.final_signal} ({c.confidence:.0%}, {c.agreement_level} agreement)"
        for c in consensus
    ]
    ctx_line = ""
    if ctx:
        parts = []
        if ctx.usd_index:
            parts.append(f"DXY {ctx.usd_index:.2f}")
        if ctx.bond_yield_10y:
            parts.append(f"10Y {ctx.bond_yield_10y:.2f}%")
        if ctx.vix:
            parts.append(f"VIX {ctx.vix:.1f}")
        if ctx.news_sentiment is not None:
            parts.append(f"Sentiment {ctx.news_sentiment:+.2f}")
        ctx_line = "Macro: " + ", ".join(parts) if parts else ""

    snapshot = "Prices:\n" + ("\n".join(lines) or "No data")
    if signal_lines:
        snapshot += "\n\nConsensus:\n" + "\n".join(signal_lines)
    if ctx_line:
        snapshot += f"\n\n{ctx_line}"
    return snapshot


# ---------------------------------------------------------------------------
# Core agent logic
# ---------------------------------------------------------------------------

async def generate_narrative(report_type: str, state: Dict):
    """Generate a narrative market report (pre-market or close summary)."""
    snapshot = _build_market_snapshot(state)
    today = date.today().strftime("%B %d, %Y")
    assets_covered = [a.symbol for a in state.get("assets", [])]

    if report_type == "pre_market":
        instruction = (
            "Write a concise pre-market morning briefing for AIP users. "
            "Cover: overnight macro moves, top themes to watch, and 3 assets flagged by AI consensus. "
            "Under 280 words."
        )
    else:
        instruction = (
            "Write a concise end-of-day summary for AIP users. "
            "Cover: biggest movers, dominant narrative, key cross-asset signals, and tomorrow's outlook. "
            "Under 280 words."
        )

    prompt = f"Today: {today}\n\n{snapshot}\n\n{instruction}"
    content = await llm_chat(
        SYSTEM_PROMPT, prompt, max_tokens=500,
        fallback=(
            f"**{'Pre-Market Briefing' if report_type == 'pre_market' else 'End-of-Day Summary'} — {today}**\n\n"
            f"{snapshot}\n\n"
            "[AI narrative unavailable — OPENAI_API_KEY not configured. "
            "Add it to .env to enable full AI narratives.]"
        ),
    )
    await _save_narrative(report_type, content, assets_covered)
    await _save_activity(f"narrative_{report_type}", f"{report_type} report for {today}")
    logger.info("MarketIntel: %s narrative generated", report_type)
    return content


async def deep_dive(asset_symbol: str, state: Dict) -> str:
    """Produce a detailed narrative deep-dive for a single asset."""
    asset_symbol = asset_symbol.upper()
    assets = state.get("assets", [])
    consensus = state.get("consensus", [])
    ctx = state.get("context")

    asset = next((a for a in assets if a.symbol == asset_symbol), None)
    cons = next((c for c in consensus if c.asset == asset_symbol), None)

    if asset:
        price_line = (
            f"{asset.name} ({asset.symbol}): ${asset.price:,.2f}, "
            f"1h {(asset.change_1h or 0):+.2f}%, 24h {(asset.change_24h or 0):+.2f}%, "
            f"volume ${(asset.volume_24h or 0)/1e9:.2f}B"
        )
    else:
        price_line = f"{asset_symbol}: price data not yet available"

    cons_line = ""
    if cons:
        model_votes = "; ".join(
            f"{m}: {v.get('signal','?')} ({v.get('confidence', 0):.0%})"
            for m, v in (cons.models or {}).items()
        )
        cons_line = (
            f"Consensus: {cons.final_signal} ({cons.confidence:.0%}, {cons.agreement_level} agreement)\n"
            f"Model votes: {model_votes}"
        )

    ctx_line = ""
    if ctx:
        parts = [
            f"DXY {ctx.usd_index:.2f}" if ctx.usd_index else "",
            f"10Y {ctx.bond_yield_10y:.2f}%" if ctx.bond_yield_10y else "",
            f"VIX {ctx.vix:.1f}" if ctx.vix else "",
        ]
        ctx_line = "Macro: " + ", ".join(p for p in parts if p)

    prompt = (
        f"Produce a deep-dive analysis of {asset_symbol}.\n\n"
        f"{price_line}\n{cons_line}\n{ctx_line}\n\n"
        "Structure: 1) Price action & trend, 2) AI model consensus breakdown, "
        "3) Key catalysts & risks, 4) Short-term outlook. Under 350 words. "
        "Disclaimer: informational only, not financial advice."
    )
    result = await llm_chat(SYSTEM_PROMPT, prompt, max_tokens=600)
    await _save_activity("deep_dive", f"Deep dive: {asset_symbol}")
    return result
