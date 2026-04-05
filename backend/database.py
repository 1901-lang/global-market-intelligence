import logging
import os
import aiosqlite
from datetime import datetime
from typing import Optional

from db import DB_PATH, IS_POSTGRES, get_db

logger = logging.getLogger(__name__)

# DB_PATH re-exported so existing code that imports it from database still works
__all__ = ["DB_PATH", "init_db"]


CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT DEFAULT '',
    hashed_password TEXT NOT NULL,
    role TEXT DEFAULT 'analyst',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS price_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    price REAL NOT NULL,
    change_1h REAL DEFAULT 0,
    change_24h REAL DEFAULT 0,
    volume_24h REAL DEFAULT 0,
    market_cap REAL DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_context (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usd_index REAL,
    bond_yield_10y REAL,
    vix REAL,
    news_sentiment REAL,
    on_chain_activity REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset TEXT NOT NULL,
    signal TEXT NOT NULL,
    confidence REAL NOT NULL,
    price_change REAL,
    trend TEXT,
    drivers TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset TEXT NOT NULL,
    model_name TEXT NOT NULL,
    signal TEXT NOT NULL,
    confidence REAL NOT NULL,
    reasoning TEXT,
    raw_response TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    evaluated_at TIMESTAMP DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS consensus_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset TEXT NOT NULL,
    final_signal TEXT NOT NULL,
    confidence REAL NOT NULL,
    agreement_level TEXT NOT NULL,
    models_json TEXT,
    dissenting_models TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    message TEXT NOT NULL,
    signal TEXT NOT NULL,
    confidence REAL NOT NULL,
    severity TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS briefs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    key_signals TEXT,
    risks TEXT,
    date TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    asset TEXT NOT NULL,
    total_predictions INTEGER DEFAULT 0,
    correct_predictions INTEGER DEFAULT 0,
    accuracy REAL DEFAULT 0,
    weight REAL DEFAULT 1.0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_name, asset)
);

-- ── Core agent tables ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS agent_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    action_type TEXT NOT NULL,
    summary TEXT,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orchestrator_briefings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    agent_statuses TEXT,
    date TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS marketing_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_type TEXT NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    asset_context TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_intel_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type TEXT NOT NULL,
    content TEXT NOT NULL,
    assets_covered TEXT,
    date TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS support_chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    message TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analytics_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    metrics_json TEXT,
    date TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS configured_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    preferred_assets TEXT DEFAULT '[]',
    notify_email INTEGER DEFAULT 1,
    email_address TEXT DEFAULT '',
    notifications_enabled INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Coordinator / MCP Orchestration Tables ────────────────────────────────────

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    classification TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    context_json TEXT,
    result_json TEXT,
    error_json TEXT
);

CREATE TABLE IF NOT EXISTS task_steps (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    step_order INTEGER NOT NULL DEFAULT 0,
    description TEXT NOT NULL,
    tool TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    input_json TEXT,
    output_json TEXT,
    error TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    requires_approval INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS task_artifacts (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    name TEXT NOT NULL,
    url TEXT,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS coordinator_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    context_json TEXT,
    is_active INTEGER DEFAULT 1
);
"""


def _make_pg_ddl(sqlite_ddl: str) -> str:
    """Convert the SQLite DDL to PostgreSQL-compatible DDL."""
    pg = sqlite_ddl
    # AUTOINCREMENT not valid in PostgreSQL; use SERIAL instead
    pg = pg.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    return pg


async def _run_migrations():
    """Apply additive schema migrations for existing databases.

    Each statement is wrapped in a try/except so that already-applied
    migrations (e.g. column already exists) are silently skipped.
    """
    migrations = [
        # evaluated_at: tracks when a model_output was outcome-evaluated so the
        # learning engine (evaluate_past_predictions) never double-counts a row.
        "ALTER TABLE model_outputs ADD COLUMN evaluated_at TIMESTAMP DEFAULT NULL",
        # configured_assets and user_preferences are handled by CREATE TABLE IF NOT EXISTS
    ]
    async with get_db() as db:
        for stmt in migrations:
            try:
                await db.execute(stmt)
                await db.commit()
            except Exception:
                pass  # Column or table already exists — safe to skip


DEFAULT_ASSETS = [
    ("BTC",  "Bitcoin",   "crypto",    "bitcoin"),
    ("ETH",  "Ethereum",  "crypto",    "ethereum"),
    ("GOLD", "Gold",      "commodity", "GC=F"),
    ("OIL",  "Crude Oil", "commodity", "CL=F"),
]


async def seed_default_assets():
    """Ensure the four default assets exist in configured_assets."""
    async with get_db() as db:
        for symbol, name, asset_type, source_id in DEFAULT_ASSETS:
            try:
                await db.execute(
                    """
                    INSERT INTO configured_assets (symbol, name, asset_type, source_id, is_active)
                    VALUES (?, ?, ?, ?, 1)
                    ON CONFLICT(symbol) DO NOTHING
                    """,
                    (symbol, name, asset_type, source_id),
                )
            except Exception:
                pass
        await db.commit()


async def seed_admin_user():
    """Create an initial admin user from ADMIN_USERNAME / ADMIN_PASSWORD env vars.

    Only runs when both vars are set and no user with that username already exists.
    This gives fresh deployments a working admin account without manual DB access.
    The password must be at least 8 characters long.
    """
    username = os.environ.get("ADMIN_USERNAME", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "").strip()
    if not username or not password:
        return
    if len(password) < 8:
        logger.warning(
            "ADMIN_PASSWORD is too short (minimum 8 characters) — skipping admin seed"
        )
        return
    from auth import create_user, get_user_by_username, UserCreate

    existing = await get_user_by_username(username)
    if existing:
        return
    await create_user(UserCreate(username=username, password=password, role="admin"))
    logger.info("Seeded admin user: %s", username)


async def init_db():
    if IS_POSTGRES:
        pg_ddl = _make_pg_ddl(CREATE_TABLES_SQL)
        async with get_db() as db:
            for statement in pg_ddl.split(";"):
                stmt = statement.strip()
                if stmt:
                    await db.execute(stmt)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            for statement in CREATE_TABLES_SQL.split(";"):
                stmt = statement.strip()
                if stmt:
                    await db.execute(stmt)
            await db.commit()

    await _run_migrations()
    await seed_default_assets()
    await seed_admin_user()
