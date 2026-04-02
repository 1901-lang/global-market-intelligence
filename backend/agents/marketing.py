"""Agent 2 – Marketing Agent (Marketing Director).

Generates market-themed awareness content, lead-ready insights, social posts,
and newsletter copy tied to live platform signals.

Scheduled tasks
---------------
- Daily 08:30 : generate a daily market insight teaser (social/newsletter).
- Every 2 h   : generate a lead-nurture snippet based on current signals.

API routes (registered in main.py)
-----------------------------------
GET  /api/agents/marketing/content         – latest generated content (paginated)
POST /api/agents/marketing/generate        – trigger on-demand content generation
POST /api/agents/marketing/lead-insight    – generate insight for a specific lead context
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from db import get_db

from agents.llm import llm_chat

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are the Marketing Director AI agent for AIP — an AI-powered market intelligence \
platform for commodities and crypto. Your responsibilities:
1. Create compelling, data-driven content (social posts, email newsletters, insight snippets) \
that showcases AIP's real-time intelligence and multi-model consensus signals.
2. Generate lead-nurture copy that moves prospects through the funnel.
3. Highlight platform capabilities with specific, credible market data.
Tone: professional, energetic, data-backed. Always include a call-to-action.
"""


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

async def _save_content(content_type: str, title: str, content: str, asset_context: Any = None):
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO marketing_content (content_type, title, content, asset_context, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (content_type, title, content, json.dumps(asset_context) if asset_context else None, datetime.utcnow()),
            )
            await db.commit()
    except Exception as exc:
        logger.warning("_save_content failed: %s", exc)


async def get_recent_content(limit: int = 20) -> List[Dict]:
    try:
        async with get_db() as db:
            rows = await db.fetchall(
                "SELECT * FROM marketing_content ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
        return [
            {
                "id": r["id"],
                "content_type": r["content_type"],
                "title": r["title"],
                "content": r["content"],
                "asset_context": json.loads(r["asset_context"] or "null"),
                "timestamp": r["timestamp"],
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning("get_recent_content failed: %s", exc)
        return []


async def _save_activity(agent_name: str, action_type: str, summary: str):
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO agent_activities (agent_name, action_type, summary, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (agent_name, action_type, summary, datetime.utcnow()),
            )
            await db.commit()
    except Exception as exc:
        logger.warning("_save_activity failed: %s", exc)


# ---------------------------------------------------------------------------
# Core agent logic
# ---------------------------------------------------------------------------

async def generate_daily_teaser(state: Dict):
    """Create a daily market insight teaser for social / newsletter use."""
    assets = state.get("assets", [])
    consensus = state.get("consensus", [])
    today = date.today().strftime("%B %d, %Y")

    top_signal = next(
        (c for c in sorted(consensus, key=lambda c: c.confidence, reverse=True) if c.confidence > 0.6),
        None,
    )
    asset_snapshot = " | ".join(
        f"{a.symbol} {(a.change_24h or 0):+.1f}%" for a in assets[:4]
    )

    if top_signal:
        market_hook = (
            f"Our multi-model consensus just flagged a {top_signal.confidence:.0%}-confidence "
            f"{top_signal.final_signal} signal on {top_signal.asset}."
        )
    else:
        market_hook = f"Markets today: {asset_snapshot or 'live data loading'}."

    prompt = (
        f"Write a short, punchy LinkedIn/Twitter market insight post for {today}.\n\n"
        f"Market hook: {market_hook}\n"
        f"Mention AIP's real-time AI consensus platform. Include a CTA ('See full analysis at AIP'). "
        "Under 220 characters for Twitter, a slightly longer version for LinkedIn. "
        "Separate them with '---'."
    )
    content = await llm_chat(
        SYSTEM_PROMPT, prompt, temperature=0.6, max_tokens=300,
        fallback=(
            f"📊 {today} — {market_hook} "
            "AIP's multi-model AI consensus gives you the edge. "
            "👉 Get your daily brief at AIP. #Markets #AI #Crypto #Commodities"
        ),
    )
    title = f"Daily Teaser — {today}"
    await _save_content("social_post", title, content, asset_snapshot)
    await _save_activity("marketing", "daily_teaser", title)
    logger.info("Marketing: daily teaser generated")
    return content


async def generate_lead_nurture(state: Dict):
    """Generate a lead-nurture email snippet based on current signals."""
    consensus = state.get("consensus", [])
    top_signals = sorted(consensus, key=lambda c: c.confidence, reverse=True)[:3]
    signal_text = "; ".join(
        f"{s.asset} → {s.final_signal} ({s.confidence:.0%} confidence)" for s in top_signals
    ) or "markets actively monitored by AIP's AI"

    prompt = (
        f"Write a 3-paragraph lead nurture email for a prospect considering AIP.\n\n"
        f"Today's top AI signals: {signal_text}\n\n"
        "Para 1: Grab attention with today's market insight. "
        "Para 2: Explain how AIP's multi-model consensus gives an edge. "
        "Para 3: Clear CTA to start a free trial. Under 180 words total."
    )
    content = await llm_chat(
        SYSTEM_PROMPT, prompt, max_tokens=350,
        fallback=(
            "Subject: Today's AI Market Signals\n\n"
            f"Top signals right now: {signal_text}.\n\n"
            "AIP aggregates GPT, Claude, and Gemini into a single consensus signal for every "
            "major asset — giving you an institutional-grade edge without the Bloomberg price tag.\n\n"
            "Start your free trial today →"
        ),
    )
    title = f"Lead Nurture — {date.today().isoformat()}"
    await _save_content("lead_nurture", title, content)
    await _save_activity("marketing", "lead_nurture", title)
    logger.info("Marketing: lead nurture email generated")
    return content


async def generate_lead_insight(lead_context: str, state: Dict) -> str:
    """Generate a personalised insight snippet for a specific lead context."""
    consensus = state.get("consensus", [])
    signal_text = "; ".join(
        f"{s.asset} {s.final_signal} {s.confidence:.0%}" for s in consensus[:4]
    ) or "live signals available"

    prompt = (
        f"Write a personalised 1-paragraph insight for a prospect with this context:\n"
        f"{lead_context}\n\n"
        f"Current AIP signals: {signal_text}\n\n"
        "Make it relevant, data-backed, and end with a soft CTA. Under 100 words."
    )
    result = await llm_chat(SYSTEM_PROMPT, prompt, max_tokens=200)
    await _save_activity("marketing", "lead_insight", lead_context[:100])
    return result
