import json
import logging
from datetime import datetime
from typing import List, Optional
import aiosqlite
from database import DB_PATH
from models.schemas import Alert, ConsensusResult

logger = logging.getLogger(__name__)

HIGH_CONFIDENCE_THRESHOLD = 0.65
_previous_signals: dict = {}


async def _save_alert(alert: Alert):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO alerts (asset, alert_type, message, signal, confidence, severity, is_read, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    alert.asset,
                    alert.alert_type,
                    alert.message,
                    alert.signal,
                    alert.confidence,
                    alert.severity,
                    datetime.utcnow(),
                ),
            )
            await db.commit()
    except Exception as exc:
        logger.warning(f"_save_alert failed: {exc}")


async def process_consensus_for_alerts(consensus: ConsensusResult):
    asset = consensus.asset
    signal = consensus.final_signal
    confidence = consensus.confidence
    prev = _previous_signals.get(asset)

    # Signal change alert
    if prev and prev != signal:
        alert = Alert(
            asset=asset,
            alert_type="signal_change",
            message=f"{asset}: Signal changed {prev} → {signal} (confidence {confidence:.0%})",
            signal=signal,
            confidence=confidence,
            severity="warning" if signal == "SELL" else "info",
            timestamp=datetime.utcnow(),
        )
        await _save_alert(alert)

    # High confidence alert
    if confidence >= HIGH_CONFIDENCE_THRESHOLD:
        severity = "critical" if confidence >= 0.80 else "warning"
        alert = Alert(
            asset=asset,
            alert_type="high_confidence",
            message=f"{asset}: High-confidence {signal} signal ({confidence:.0%}) — {consensus.agreement_level} model agreement",
            signal=signal,
            confidence=confidence,
            severity=severity,
            timestamp=datetime.utcnow(),
        )
        await _save_alert(alert)

    _previous_signals[asset] = signal


async def get_recent_alerts(limit: int = 50) -> List[Alert]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
        return [
            Alert(
                id=r["id"],
                asset=r["asset"],
                alert_type=r["alert_type"],
                message=r["message"],
                signal=r["signal"],
                confidence=r["confidence"],
                severity=r["severity"],
                is_read=bool(r["is_read"]),
                timestamp=r["timestamp"],
            )
            for r in rows
        ]
    except Exception as exc:
        logger.warning(f"get_recent_alerts failed: {exc}")
        return []


async def mark_alert_read(alert_id: int):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE alerts SET is_read = 1 WHERE id = ?", (alert_id,)
            )
            await db.commit()
    except Exception as exc:
        logger.warning(f"mark_alert_read failed: {exc}")
