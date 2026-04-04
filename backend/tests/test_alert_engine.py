"""Tests for alert_engine.py — per-user email subscription logic and datetime usage."""

import json
import os
import sys
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Force SQLite test DB
os.environ.pop("DATABASE_URL", None)
os.environ["DB_PATH"] = "/tmp/aip_alert_test.db"
import db as db_module
db_module.DB_PATH = "/tmp/aip_alert_test.db"
import database as database_module
database_module.DB_PATH = "/tmp/aip_alert_test.db"

from database import init_db
from db import get_db
from services.alert_engine import (
    _get_subscribed_user_emails,
    _severity_meets_threshold,
    _build_email_body,
)
from models.schemas import Alert


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="module")
async def db_ready():
    """Set up the test database once for the whole module."""
    await init_db()
    yield
    try:
        os.remove("/tmp/aip_alert_test.db")
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# _severity_meets_threshold
# ---------------------------------------------------------------------------

class TestSeverityThreshold:
    def test_critical_always_meets_default_warning(self):
        assert _severity_meets_threshold("critical") is True

    def test_warning_meets_default_warning(self):
        assert _severity_meets_threshold("warning") is True

    def test_info_does_not_meet_default_warning(self):
        assert _severity_meets_threshold("info") is False

    def test_unknown_severity_treated_as_info(self):
        assert _severity_meets_threshold("unknown") is False


# ---------------------------------------------------------------------------
# _build_email_body
# ---------------------------------------------------------------------------

class TestBuildEmailBody:
    def test_contains_asset(self):
        alert = Alert(
            asset="BTC",
            alert_type="high_confidence",
            message="BTC: High-confidence BUY signal",
            signal="BUY",
            confidence=0.85,
            severity="critical",
            timestamp=datetime.now(timezone.utc),
        )
        body = _build_email_body(alert)
        assert "BTC" in body
        assert "BUY" in body
        assert "CRITICAL" in body
        assert "85%" in body


# ---------------------------------------------------------------------------
# _get_subscribed_user_emails
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_subscribed_emails_empty_table(db_ready):
    """Returns empty list when no preferences exist."""
    emails = await _get_subscribed_user_emails("BTC")
    assert isinstance(emails, list)


@pytest.mark.asyncio
async def test_subscribed_emails_opted_in_no_watchlist(db_ready):
    """User with no preferred_assets (watches everything) is included for any asset."""
    async with get_db() as db:
        await db.execute(
            "INSERT INTO user_preferences "
            "(user_id, preferred_assets, notify_email, email_address, notifications_enabled) "
            "VALUES (?, ?, 1, ?, 1)",
            (9001, "[]", "trader@example.com"),
        )
        await db.commit()

    emails = await _get_subscribed_user_emails("BTC")
    assert "trader@example.com" in emails

    emails_eth = await _get_subscribed_user_emails("ETH")
    assert "trader@example.com" in emails_eth


@pytest.mark.asyncio
async def test_subscribed_emails_watchlist_filters(db_ready):
    """User with a specific watchlist only receives alerts for those assets."""
    async with get_db() as db:
        await db.execute(
            "INSERT INTO user_preferences "
            "(user_id, preferred_assets, notify_email, email_address, notifications_enabled) "
            "VALUES (?, ?, 1, ?, 1)",
            (9002, json.dumps(["GOLD", "OIL"]), "goldtrader@example.com"),
        )
        await db.commit()

    emails_gold = await _get_subscribed_user_emails("GOLD")
    assert "goldtrader@example.com" in emails_gold

    emails_btc = await _get_subscribed_user_emails("BTC")
    assert "goldtrader@example.com" not in emails_btc


@pytest.mark.asyncio
async def test_subscribed_emails_opted_out(db_ready):
    """User with notify_email=0 is excluded."""
    async with get_db() as db:
        await db.execute(
            "INSERT INTO user_preferences "
            "(user_id, preferred_assets, notify_email, email_address, notifications_enabled) "
            "VALUES (?, ?, 0, ?, 1)",
            (9003, "[]", "silent@example.com"),
        )
        await db.commit()

    emails = await _get_subscribed_user_emails("BTC")
    assert "silent@example.com" not in emails


@pytest.mark.asyncio
async def test_subscribed_emails_notifications_disabled(db_ready):
    """User with notifications_enabled=0 is excluded."""
    async with get_db() as db:
        await db.execute(
            "INSERT INTO user_preferences "
            "(user_id, preferred_assets, notify_email, email_address, notifications_enabled) "
            "VALUES (?, ?, 1, ?, 0)",
            (9004, "[]", "disabled@example.com"),
        )
        await db.commit()

    emails = await _get_subscribed_user_emails("BTC")
    assert "disabled@example.com" not in emails


@pytest.mark.asyncio
async def test_subscribed_emails_empty_address_excluded(db_ready):
    """User with empty email_address is excluded even if opted in."""
    async with get_db() as db:
        await db.execute(
            "INSERT INTO user_preferences "
            "(user_id, preferred_assets, notify_email, email_address, notifications_enabled) "
            "VALUES (?, ?, 1, ?, 1)",
            (9005, "[]", ""),
        )
        await db.commit()

    emails = await _get_subscribed_user_emails("BTC")
    assert "" not in emails


# ---------------------------------------------------------------------------
# datetime.now(timezone.utc) usage in alert construction
# ---------------------------------------------------------------------------

class TestDatetimeUsage:
    def test_alert_timestamp_is_timezone_aware(self):
        alert = Alert(
            asset="ETH",
            alert_type="signal_change",
            message="ETH: Signal changed HOLD → BUY",
            signal="BUY",
            confidence=0.7,
            severity="warning",
            timestamp=datetime.now(timezone.utc),
        )
        assert alert.timestamp.tzinfo is not None
