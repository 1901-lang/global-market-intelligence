import asyncio
import json
import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional
from db import get_db
from models.schemas import Alert, ConsensusResult

logger = logging.getLogger(__name__)

HIGH_CONFIDENCE_THRESHOLD = 0.65
_previous_signals: dict = {}

# ── Outbound notification configuration ──────────────────────────────────────
_ALERT_EMAIL_TO: str = os.getenv("ALERT_EMAIL_TO", "")      # comma-separated
_SMTP_HOST: str = os.getenv("SMTP_HOST", "")
_SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
_SMTP_USER: str = os.getenv("SMTP_USER", "")
_SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
_SMTP_FROM: str = os.getenv("SMTP_FROM", _SMTP_USER)
_ALERT_WEBHOOK_URL: str = os.getenv("ALERT_WEBHOOK_URL", "")
# Only dispatch notifications for alerts at or above this severity level.
# Values (ascending): info < warning < critical
_ALERT_MIN_SEVERITY: str = os.getenv("ALERT_MIN_SEVERITY", "warning")

_SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}


def _severity_meets_threshold(severity: str) -> bool:
    return _SEVERITY_RANK.get(severity, 0) >= _SEVERITY_RANK.get(_ALERT_MIN_SEVERITY, 1)


def _build_email_body(alert: Alert) -> str:
    return (
        f"AIP Market Alert\n"
        f"{'=' * 40}\n"
        f"Asset    : {alert.asset}\n"
        f"Signal   : {alert.signal}\n"
        f"Severity : {alert.severity.upper()}\n"
        f"Confidence: {alert.confidence:.0%}\n"
        f"Type     : {alert.alert_type}\n\n"
        f"{alert.message}\n\n"
        f"Timestamp: {alert.timestamp}\n"
        f"{'=' * 40}\n"
        "This is an automated alert from the AIP Market Intelligence Platform.\n"
    )


def _send_email_sync(alert: Alert, recipients: List[str]):
    """Synchronous SMTP send — run in a thread executor."""
    if not recipients:
        return
    try:
        import ssl
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[AIP Alert] {alert.asset} {alert.signal} — {alert.severity.upper()}"
        msg["From"] = _SMTP_FROM or _SMTP_USER
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(_build_email_body(alert), "plain"))

        ssl_context = ssl.create_default_context()
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=ssl_context)
            if _SMTP_USER and _SMTP_PASSWORD:
                server.login(_SMTP_USER, _SMTP_PASSWORD)
            server.sendmail(msg["From"], recipients, msg.as_string())
        logger.info("Alert email sent for %s %s to %d recipient(s)", alert.asset, alert.signal, len(recipients))
    except Exception as exc:
        logger.warning("Alert email failed: %s", exc)


async def _get_subscribed_user_emails(asset: str) -> List[str]:
    """Return email addresses of users who have opted in to alert notifications.

    A user is included when all three conditions hold:
    - ``notifications_enabled = 1``
    - ``notify_email = 1``
    - ``email_address`` is a non-empty string
    - ``preferred_assets`` is either empty (watches everything) or contains *asset*
    """
    try:
        async with get_db() as db:
            rows = await db.fetchall(
                "SELECT email_address, preferred_assets "
                "FROM user_preferences "
                "WHERE notifications_enabled = 1 AND notify_email = 1 "
                "AND email_address IS NOT NULL AND email_address != ''"
            )
        emails: List[str] = []
        for row in rows:
            preferred = json.loads(row["preferred_assets"] or "[]")
            # Empty watchlist → user watches all assets
            if not preferred or asset in preferred:
                emails.append(row["email_address"].strip())
        return emails
    except Exception as exc:
        logger.warning("_get_subscribed_user_emails failed: %s", exc)
        return []


async def _send_email_notification(alert: Alert):
    if not _SMTP_HOST:
        return
    # Combine global admin recipients with opted-in per-user emails
    global_recipients = [r.strip() for r in _ALERT_EMAIL_TO.split(",") if r.strip()]
    user_recipients = await _get_subscribed_user_emails(alert.asset)
    # Deduplicate while preserving order
    seen: set = set()
    recipients: List[str] = []
    for addr in global_recipients + user_recipients:
        if addr not in seen:
            seen.add(addr)
            recipients.append(addr)
    if not recipients:
        return
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _send_email_sync, alert, recipients)


async def _send_webhook_notification(alert: Alert):
    if not _ALERT_WEBHOOK_URL:
        return
    try:
        import httpx
        payload = {
            "asset": alert.asset,
            "signal": alert.signal,
            "confidence": alert.confidence,
            "severity": alert.severity,
            "alert_type": alert.alert_type,
            "message": alert.message,
            "timestamp": alert.timestamp.isoformat() if alert.timestamp else None,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(_ALERT_WEBHOOK_URL, json=payload)
            resp.raise_for_status()
        logger.info("Alert webhook delivered for %s %s (status %s)", alert.asset, alert.signal, resp.status_code)
    except Exception as exc:
        logger.warning("Alert webhook failed: %s", exc)


async def _dispatch_notification(alert: Alert):
    """Fire email and/or webhook notifications when severity meets threshold."""
    if not _severity_meets_threshold(alert.severity):
        return
    await asyncio.gather(
        _send_email_notification(alert),
        _send_webhook_notification(alert),
        return_exceptions=True,
    )


async def _save_alert(alert: Alert):
    try:
        async with get_db() as db:
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
                    datetime.now(timezone.utc),
                ),
            )
            await db.commit()
    except Exception as exc:
        logger.warning(f"_save_alert failed: {exc}")
        return

    # Dispatch outbound notifications (email / webhook) — non-blocking
    await _dispatch_notification(alert)


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
            timestamp=datetime.now(timezone.utc),
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
            timestamp=datetime.now(timezone.utc),
        )
        await _save_alert(alert)

    _previous_signals[asset] = signal


async def get_recent_alerts(limit: int = 50) -> List[Alert]:
    try:
        async with get_db() as db:
            rows = await db.fetchall(
                "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
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
        async with get_db() as db:
            await db.execute(
                "UPDATE alerts SET is_read = 1 WHERE id = ?", (alert_id,)
            )
            await db.commit()
    except Exception as exc:
        logger.warning(f"mark_alert_read failed: {exc}")
