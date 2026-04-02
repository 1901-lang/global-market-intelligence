"""Integration tests for database abstraction (db.py) using in-memory SQLite."""

import os
import pytest
import pytest_asyncio

# Force SQLite in-memory for these tests
os.environ.pop("DATABASE_URL", None)
os.environ["DB_PATH"] = ":memory:"

import asyncio
from database import init_db, CREATE_TABLES_SQL
from db import get_db


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="module")
async def db_ready():
    """Initialise the in-memory database once for all tests in this module."""
    # For in-memory SQLite each new connection is a blank DB, so we use a file
    os.environ["DB_PATH"] = "/tmp/aip_test.db"
    import db as db_module
    db_module.DB_PATH = "/tmp/aip_test.db"
    import database as database_module
    database_module.DB_PATH = "/tmp/aip_test.db"
    await init_db()
    yield
    # cleanup
    import os as _os
    try:
        _os.remove("/tmp/aip_test.db")
    except FileNotFoundError:
        pass


@pytest.mark.asyncio
async def test_execute_and_fetchone(db_ready):
    async with get_db() as db:
        await db.execute(
            "INSERT INTO agent_activities (agent_name, action_type, summary, timestamp) VALUES (?, ?, ?, ?)",
            ("test_agent", "test_action", "test summary", "2024-01-01"),
        )
        await db.commit()
        row = await db.fetchone(
            "SELECT * FROM agent_activities WHERE agent_name = ?", ("test_agent",)
        )
    assert row is not None
    assert row["agent_name"] == "test_agent"
    assert row["action_type"] == "test_action"


@pytest.mark.asyncio
async def test_fetchall(db_ready):
    async with get_db() as db:
        rows = await db.fetchall(
            "SELECT * FROM agent_activities WHERE agent_name = ?", ("test_agent",)
        )
    assert isinstance(rows, list)
    assert len(rows) >= 1


@pytest.mark.asyncio
async def test_fetchone_none_when_not_found(db_ready):
    async with get_db() as db:
        row = await db.fetchone(
            "SELECT * FROM agent_activities WHERE agent_name = ?", ("nonexistent",)
        )
    assert row is None


@pytest.mark.asyncio
async def test_commit_persists_across_connections(db_ready):
    key = "persist_test_agent"
    async with get_db() as db:
        await db.execute(
            "INSERT INTO agent_activities (agent_name, action_type, summary, timestamp) VALUES (?, ?, ?, ?)",
            (key, "persist", "check", "2024-01-01"),
        )
        await db.commit()

    # New connection should see the row
    async with get_db() as db2:
        row = await db2.fetchone(
            "SELECT * FROM agent_activities WHERE agent_name = ?", (key,)
        )
    assert row is not None
    assert row["agent_name"] == key
