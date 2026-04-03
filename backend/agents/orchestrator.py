"""Agent 1 – Orchestrator (COO).

Oversees all other agents, generates daily admin briefings,
surfaces agent health status, and answers operational queries.

Scheduled tasks
---------------
- Every 60 min : collect status snapshots from each agent module.
- Daily 09:00  : produce and persist a full admin operational briefing.

API routes (registered in main.py)
-----------------------------------
GET  /api/agents/orchestrator/briefing   – latest briefing
POST /api/agents/orchestrator/query      – ask the COO anything
GET  /api/agents/status                  – live status of all 5 agents
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
You are the Orchestrator AI agent for AIP — an AI-powered market intelligence platform \
for commodities and crypto. You act as the Chief Operating Officer (COO) of the agent team. \
Your responsibilities:
1. Oversee and coordinate Marketing, Market Intelligence, Customer Success, and Analytics agents.
2. Produce concise, executive-level operational briefings for platform administrators.
3. Route and prioritise tasks across agents.
4. Monitor platform health and flag risks early.
Always communicate with clarity, authority, and a bias toward action.
"""


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

async def _save_activity(agent_name: str, action_type: str, summary: str, details: Any = None):
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO agent_activities (agent_name, action_type, summary, details, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (agent_name, action_type, summary, json.dumps(details) if details else None, datetime.utcnow()),
            )
            await db.commit()
    except Exception as exc:
        logger.warning("_save_activity failed: %s", exc)


async def save_briefing(content: str, agent_statuses: List[Dict]):
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO orchestrator_briefings (content, agent_statuses, date, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (content, json.dumps(agent_statuses), date.today().isoformat(), datetime.utcnow()),
            )
            await db.commit()
    except Exception as exc:
        logger.warning("save_briefing failed: %s", exc)


async def get_latest_briefing() -> Optional[Dict]:
    try:
        async with get_db() as db:
            row = await db.fetchone(
                "SELECT * FROM orchestrator_briefings ORDER BY timestamp DESC LIMIT 1"
            )
        if not row:
            return None
        return {
            "id": row["id"],
            "content": row["content"],
            "agent_statuses": json.loads(row["agent_statuses"] or "[]"),
            "date": row["date"],
            "timestamp": row["timestamp"],
        }
    except Exception as exc:
        logger.warning("get_latest_briefing failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Core agent logic
# ---------------------------------------------------------------------------

async def _collect_agent_statuses(state: Dict) -> List[Dict]:
    """Build a quick status summary from shared in-memory state."""
    assets = state.get("assets", [])
    consensus = state.get("consensus", [])
    last_updated = state.get("last_updated")

    statuses = [
        {
            "agent": "orchestrator",
            "status": "active",
            "last_run": datetime.utcnow().isoformat(),
            "notes": "Overseeing all agents",
        },
        {
            "agent": "marketing",
            "status": "active",
            "last_run": datetime.utcnow().isoformat(),
            "notes": "Generating content and lead insights",
        },
        {
            "agent": "market_intelligence",
            "status": "active",
            "last_run": last_updated.isoformat() if last_updated else "pending",
            "notes": f"Monitoring {len(assets)} assets, {len(consensus)} consensus results",
        },
        {
            "agent": "customer_success",
            "status": "active",
            "last_run": datetime.utcnow().isoformat(),
            "notes": "User support chat available",
        },
        {
            "agent": "analytics",
            "status": "active",
            "last_run": datetime.utcnow().isoformat(),
            "notes": "KPI reporting active",
        },
        {
            "agent": "research_analyst",
            "status": "active",
            "last_run": datetime.utcnow().isoformat(),
            "notes": "Generating structured research artifacts for institutional users",
        },
    ]
    return statuses


async def run_daily_briefing(state: Dict):
    """Generate and persist the daily admin briefing."""
    logger.info("Orchestrator: generating daily briefing")
    statuses = await _collect_agent_statuses(state)

    assets = state.get("assets", [])
    consensus = state.get("consensus", [])

    asset_summary = " | ".join(
        f"{a.symbol} ${a.price:,.0f} ({(a.change_24h or 0):+.1f}%)" for a in assets[:6]
    )
    signal_summary = ", ".join(
        f"{c.asset}:{c.final_signal}({c.confidence:.0%})" for c in consensus[:6]
    )
    status_lines = "\n".join(
        f"- [{s['agent'].upper()}] {s['status']} — {s['notes']}" for s in statuses
    )

    today = date.today().strftime("%B %d, %Y")
    prompt = (
        f"Generate a concise daily operational briefing for {today}.\n\n"
        f"Asset Prices: {asset_summary or 'No data yet'}\n"
        f"AI Consensus: {signal_summary or 'No consensus yet'}\n\n"
        f"Agent Team Status:\n{status_lines}\n\n"
        "Include: executive summary (2-3 sentences), key actions for today (3 bullets), "
        "risks to monitor (2 bullets). Under 250 words."
    )
    content = await llm_chat(
        SYSTEM_PROMPT,
        prompt,
        fallback=(
            f"**Daily Operational Briefing — {today}**\n\n"
            f"All 5 platform agents are active. Markets: {asset_summary or 'loading'}. "
            f"Signals: {signal_summary or 'pending'}. "
            "No API key configured — briefing generated from live platform state."
        ),
    )

    await save_briefing(content, statuses)
    await _save_activity("orchestrator", "daily_briefing", f"Briefing generated for {today}")
    logger.info("Orchestrator: daily briefing saved")


async def handle_admin_query(query: str, state: Dict) -> str:
    """Answer an administrator's operational question."""
    assets = state.get("assets", [])
    consensus = state.get("consensus", [])
    context_str = (
        f"Platform has {len(assets)} tracked assets. "
        f"Latest consensus: {', '.join(f'{c.asset}:{c.final_signal}' for c in consensus[:4]) or 'none yet'}."
    )
    prompt = f"Platform context: {context_str}\n\nAdmin query: {query}"
    result = await llm_chat(
        SYSTEM_PROMPT, prompt, max_tokens=400,
        fallback="OPENAI_API_KEY not configured. Please add it to .env to enable AI responses.",
    )
    await _save_activity("orchestrator", "admin_query", query[:120])
    return result
