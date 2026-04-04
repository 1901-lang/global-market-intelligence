"""Agent 4 – Customer Success Agent (CSM).

Handles user-facing support chat, personalised onboarding guidance,
and feedback collection.

Scheduled tasks
---------------
- Daily 10:00 : log a daily engagement check (user-count snapshot).

API routes (registered in main.py)
-----------------------------------
POST /api/agents/support/chat              – submit a user message (session-based)
GET  /api/agents/support/chat/{session_id} – retrieve chat history
POST /api/agents/support/onboard           – get a personalised onboarding guide
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from db import get_db

from agents.llm import llm_chat

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are the Customer Success AI agent for AIP — an AI-powered market intelligence \
platform for commodities and crypto. You help users get the most out of AIP.

Key platform features:
- Real-time price data for major cryptos (BTC, ETH) and commodities (Gold/XAUUSD, Oil/CL=F).
- Multi-model AI consensus signals (GPT, Claude, Gemini) with a debate loop.
- Alert engine for signal changes and high-confidence moves.
- Daily AI-generated market briefs.
- Model performance & accuracy tracking.

Your tone: warm, knowledgeable, concise. Always encourage users to explore the platform. \
If a question is beyond your scope (billing, technical bugs), say so and suggest contacting support.
"""

ONBOARD_SYSTEM = """\
You are onboarding a new user to AIP — an AI-powered market intelligence platform \
for commodities and crypto. Create a friendly, personalised welcome guide.
"""


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

async def save_message(session_id: str, role: str, message: str):
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO support_chats (session_id, role, message, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (session_id, role, message, datetime.utcnow()),
            )
            await db.commit()
    except Exception as exc:
        logger.warning("save_message failed: %s", exc)

# Keep underscore alias for backwards compatibility within this module
_save_message = save_message


async def get_chat_history(session_id: str) -> List[Dict]:
    try:
        async with get_db() as db:
            rows = await db.fetchall(
                "SELECT role, message, timestamp FROM support_chats "
                "WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,),
            )
        return [{"role": r["role"], "message": r["message"], "timestamp": r["timestamp"]} for r in rows]
    except Exception as exc:
        logger.warning("get_chat_history failed: %s", exc)
        return []


async def save_activity(action_type: str, summary: str):
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO agent_activities (agent_name, action_type, summary, timestamp) "
                "VALUES (?, ?, ?, ?)",
                ("customer_success", action_type, summary, datetime.utcnow()),
            )
            await db.commit()
    except Exception as exc:
        logger.warning("save_activity failed: %s", exc)

_save_activity = save_activity


# ---------------------------------------------------------------------------
# Core agent logic
# ---------------------------------------------------------------------------

async def chat(session_id: str, user_message: str, state: Dict) -> str:
    """Process a user chat message and return the agent reply.

    Maintains conversation history so the LLM has context from prior turns.
    """
    history = await get_chat_history(session_id)

    # Build conversation context for the LLM
    extra_messages = [
        {"role": h["role"], "content": h["message"]} for h in history[-10:]
    ]

    # Inject current platform context into the system prompt
    assets = state.get("assets", [])
    consensus = state.get("consensus", [])
    asset_names = ", ".join(a.symbol for a in assets) or "loading"
    top_signals = "; ".join(
        f"{c.asset}:{c.final_signal}({c.confidence:.0%})" for c in consensus[:3]
    ) or "pending"
    enriched_system = (
        SYSTEM_PROMPT
        + f"\n\nCurrent platform state — Tracked assets: {asset_names}. "
        f"Top signals: {top_signals}."
    )

    reply = await llm_chat(
        enriched_system,
        user_message,
        extra_messages=extra_messages,
        max_tokens=400,
        fallback=(
            "Thanks for reaching out! Our AI support agent is temporarily unavailable "
            "(API key not configured). Please check the AIP documentation or contact "
            "the support team directly."
        ),
    )

    await _save_message(session_id, "user", user_message)
    await _save_message(session_id, "assistant", reply)
    await _save_activity("chat", f"session={session_id[:8]} msg={user_message[:60]}")
    return reply


async def onboard_user(name: str, interest: str, experience: str, state: Dict) -> str:
    """Generate a personalised onboarding guide for a new user."""
    assets = state.get("assets", [])
    top_asset = assets[0].symbol if assets else "BTC"

    prompt = (
        f"New user: {name or 'there'}. Interest: {interest or 'markets'}. "
        f"Experience level: {experience or 'intermediate'}.\n\n"
        f"Most active asset on AIP right now: {top_asset}.\n\n"
        "Write a warm, personalised onboarding welcome: "
        "1) Greet them by name, 2) Highlight 3 features matching their interest, "
        "3) Suggest their first action, 4) Invite questions. Under 200 words."
    )
    guide = await llm_chat(
        ONBOARD_SYSTEM, prompt, max_tokens=350,
        fallback=(
            f"Welcome to AIP{', ' + name if name else ''}! 🎉\n\n"
            "Here's how to get started:\n"
            "1. **Asset Cards** — See live prices and AI signals for all tracked assets.\n"
            "2. **Consensus View** — Understand how GPT, Claude, and Gemini vote on each asset.\n"
            "3. **Daily Brief** — Hit 'Generate Brief' for a full AI market summary.\n\n"
            "Feel free to ask the support chat anything!"
        ),
    )
    await _save_activity("onboarding", f"Onboarded: {name or 'anonymous'} ({interest})")
    return guide


async def run_daily_check(state: Dict):
    """Collect platform engagement metrics and log a daily analytics snapshot."""
    from datetime import timedelta
    assets = state.get("assets", [])
    now = datetime.utcnow()
    today = now.date().isoformat()
    seven_days_ago = now - timedelta(days=7)

    metrics: Dict = {"date": today, "assets_tracked": len(assets)}

    try:
        async with get_db() as db:
            # Active user count
            row = await db.fetchone("SELECT COUNT(*) AS cnt FROM users WHERE is_active = 1")
            metrics["active_users"] = row["cnt"] if row else 0

            # Distinct chat sessions in the last 7 days
            row = await db.fetchone(
                "SELECT COUNT(DISTINCT session_id) AS cnt FROM support_chats "
                "WHERE timestamp >= ?",
                (seven_days_ago,),
            )
            metrics["chat_sessions_7d"] = row["cnt"] if row else 0

            # Agent activities today
            row = await db.fetchone(
                "SELECT COUNT(*) AS cnt FROM agent_activities "
                "WHERE timestamp >= ?",
                (today,),
            )
            metrics["agent_activities_today"] = row["cnt"] if row else 0

            # Alerts generated today
            row = await db.fetchone(
                "SELECT COUNT(*) AS cnt FROM alerts WHERE timestamp >= ?",
                (today,),
            )
            metrics["alerts_today"] = row["cnt"] if row else 0

            # High-confidence alerts today
            row = await db.fetchone(
                "SELECT COUNT(*) AS cnt FROM alerts WHERE timestamp >= ? AND severity = 'critical'",
                (today,),
            )
            metrics["critical_alerts_today"] = row["cnt"] if row else 0
    except Exception as exc:
        logger.warning("run_daily_check DB queries failed: %s", exc)

    logger.info("CustomerSuccess daily check: %s", metrics)
    await _save_activity(
        "daily_check",
        f"users={metrics.get('active_users', '?')} "
        f"sessions_7d={metrics.get('chat_sessions_7d', '?')} "
        f"alerts_today={metrics.get('alerts_today', '?')}",
    )
