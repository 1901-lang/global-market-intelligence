"""Agent 5 – Analytics Agent (Data Analyst).

Tracks platform-level KPIs, detects anomalies in usage patterns,
and delivers actionable insights to administrators.

Scheduled tasks
---------------
- Daily 08:00  : generate and persist a daily KPI snapshot.
- Every 4 h    : run a quick anomaly check on recent signal data.

API routes (registered in main.py)
-----------------------------------
GET  /api/agents/analytics/kpi             – latest KPI report
POST /api/agents/analytics/anomaly-check   – run anomaly check on provided metrics
GET  /api/agents/analytics/activity        – recent agent activity log
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
You are the Analytics AI agent for AIP — an AI-powered market intelligence platform \
for commodities and crypto. You act as the platform's Data Analyst. Your responsibilities:
1. Track and report key platform metrics: assets tracked, signal distribution, model accuracy, alert frequency.
2. Produce concise, admin-friendly KPI reports in markdown format.
3. Detect anomalies or unusual patterns and surface them with severity ratings.
4. Answer ad-hoc data questions with precision.
Be rigorous, data-first, and translate numbers into clear business implications.
"""


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

async def _save_kpi_report(content: str, metrics: Dict):
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO analytics_reports (content, metrics_json, date, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (content, json.dumps(metrics), date.today().isoformat(), datetime.utcnow()),
            )
            await db.commit()
    except Exception as exc:
        logger.warning("_save_kpi_report failed: %s", exc)


async def get_latest_kpi_report() -> Optional[Dict]:
    try:
        async with get_db() as db:
            row = await db.fetchone(
                "SELECT * FROM analytics_reports ORDER BY timestamp DESC LIMIT 1"
            )
        if not row:
            return None
        return {
            "id": row["id"],
            "content": row["content"],
            "metrics": json.loads(row["metrics_json"] or "{}"),
            "date": row["date"],
            "timestamp": row["timestamp"],
        }
    except Exception as exc:
        logger.warning("get_latest_kpi_report failed: %s", exc)
        return None


async def get_recent_activities(limit: int = 50) -> List[Dict]:
    """Fetch recent activity log entries for all agents."""
    try:
        async with get_db() as db:
            rows = await db.fetchall(
                "SELECT * FROM agent_activities ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
        return [
            {
                "id": r["id"],
                "agent_name": r["agent_name"],
                "action_type": r["action_type"],
                "summary": r["summary"],
                "details": json.loads(r["details"] or "null"),
                "timestamp": r["timestamp"],
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning("get_recent_activities failed: %s", exc)
        return []


async def _save_activity(action_type: str, summary: str):
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO agent_activities (agent_name, action_type, summary, timestamp) "
                "VALUES (?, ?, ?, ?)",
                ("analytics", action_type, summary, datetime.utcnow()),
            )
            await db.commit()
    except Exception as exc:
        logger.warning("_save_activity failed: %s", exc)


async def _fetch_signal_counts() -> Dict:
    """Count signal distribution from the last 24 hours of consensus results."""
    try:
        async with get_db() as db:
            rows = await db.fetchall(
                "SELECT final_signal, COUNT(*) as cnt FROM consensus_results "
                "WHERE timestamp >= datetime('now', '-24 hours') GROUP BY final_signal"
            )
            alert_row = await db.fetchone(
                "SELECT COUNT(*) as cnt FROM alerts WHERE timestamp >= datetime('now', '-24 hours')"
            )
            chat_row = await db.fetchone(
                "SELECT COUNT(*) as cnt FROM support_chats WHERE timestamp >= datetime('now', '-24 hours')"
            )
        signal_counts = {r["final_signal"]: r["cnt"] for r in rows}
        return {
            "signals_24h": signal_counts,
            "alerts_24h": alert_row["cnt"] if alert_row else 0,
            "support_chats_24h": chat_row["cnt"] if chat_row else 0,
        }
    except Exception as exc:
        logger.warning("_fetch_signal_counts failed: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# Core agent logic
# ---------------------------------------------------------------------------

async def generate_kpi_report(state: Dict):
    """Generate and persist a daily KPI report."""
    assets = state.get("assets", [])
    consensus = state.get("consensus", [])
    today = date.today().strftime("%B %d, %Y")

    db_metrics = await _fetch_signal_counts()
    signal_dist = db_metrics.get("signals_24h", {})
    alerts_24h = db_metrics.get("alerts_24h", 0)
    chats_24h = db_metrics.get("support_chats_24h", 0)

    avg_confidence = (
        sum(c.confidence for c in consensus) / len(consensus) if consensus else 0
    )
    high_conf = sum(1 for c in consensus if c.confidence >= 0.65)

    metrics = {
        "date": today,
        "assets_tracked": len(assets),
        "consensus_results": len(consensus),
        "avg_confidence": round(avg_confidence, 3),
        "high_confidence_signals": high_conf,
        "alerts_24h": alerts_24h,
        "support_chats_24h": chats_24h,
        "signal_distribution": signal_dist,
    }

    prompt = (
        f"Generate a daily KPI report for AIP platform on {today}.\n\n"
        f"Metrics:\n{json.dumps(metrics, indent=2)}\n\n"
        "Format as a markdown report with sections: Summary Table, Signal Health, "
        "User Engagement, and 3 Recommendations. Under 300 words."
    )
    content = await llm_chat(
        SYSTEM_PROMPT, prompt, max_tokens=500,
        fallback=(
            f"## AIP Daily KPI Report — {today}\n\n"
            f"| Metric | Value |\n|---|---|\n"
            + "\n".join(f"| {k} | {v} |" for k, v in metrics.items() if k != "signal_distribution")
            + f"\n\nSignal distribution (24h): {signal_dist or 'no data'}\n\n"
            "_AI narrative unavailable — add OPENAI_API_KEY to .env for full AI reports._"
        ),
    )
    await _save_kpi_report(content, metrics)
    await _save_activity("kpi_report", f"KPI report for {today}")
    logger.info("Analytics: KPI report generated")
    return content


async def run_anomaly_check(state: Dict) -> str:
    """Detect anomalies in the current platform data."""
    assets = state.get("assets", [])
    consensus = state.get("consensus", [])

    spikes = [
        f"{a.symbol}: {(a.change_24h or 0):+.1f}%"
        for a in assets
        if abs(a.change_24h or 0) > 5
    ]
    low_conf = [c.asset for c in consensus if c.confidence < 0.35]
    dissenting = [c.asset for c in consensus if len(c.dissenting_models or []) >= 2]

    metrics_str = (
        f"Price spikes >5% (24h): {spikes or 'none'}\n"
        f"Low-confidence assets (<35%): {low_conf or 'none'}\n"
        f"High model disagreement: {dissenting or 'none'}"
    )

    prompt = (
        f"Anomaly check on AIP platform data:\n\n{metrics_str}\n\n"
        "For each anomaly found, give: name, severity (Low/Medium/High), likely cause, "
        "and recommended action. If none found, say 'No anomalies detected.'"
    )
    result = await llm_chat(SYSTEM_PROMPT, prompt, max_tokens=300, fallback=metrics_str)
    await _save_activity("anomaly_check", f"spikes={len(spikes)}, low_conf={len(low_conf)}")
    logger.info("Analytics: anomaly check complete")
    return result


async def check_anomalies_from_metrics(custom_metrics: Dict) -> str:
    """Run anomaly detection on a user-supplied metrics dictionary."""
    metrics_str = "\n".join(f"- {k}: {v}" for k, v in custom_metrics.items())
    prompt = (
        f"Analyse these AIP platform metrics for anomalies:\n\n{metrics_str}\n\n"
        "For each anomaly: severity (Low/Medium/High), likely cause, recommendation. "
        "If none found, say 'No anomalies detected.'"
    )
    return await llm_chat(SYSTEM_PROMPT, prompt, max_tokens=300)
