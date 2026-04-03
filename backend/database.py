import os
import aiosqlite
from datetime import datetime
from typing import Optional

from db import DB_PATH, IS_POSTGRES, get_db

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
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

-- ── Research Analyst tables ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS research_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset TEXT NOT NULL,
    note_type TEXT NOT NULL,
    time_horizon TEXT,
    market_regime TEXT,
    thesis TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.5,
    key_drivers TEXT,
    confirming_evidence TEXT,
    contradictory_evidence TEXT,
    key_risks TEXT,
    catalysts TEXT,
    invalidation_conditions TEXT,
    scenario_analysis TEXT,
    summary TEXT NOT NULL,
    payload TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS thesis_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset TEXT NOT NULL,
    prior_thesis TEXT,
    new_thesis TEXT NOT NULL,
    change_summary TEXT,
    drivers_of_change TEXT,
    confidence_delta REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS catalyst_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    event_type TEXT NOT NULL,
    asset_scope TEXT,
    event_time TIMESTAMP,
    importance TEXT NOT NULL DEFAULT 'medium',
    expected_impact TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    notes TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_regimes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    rationale TEXT NOT NULL,
    contributing_factors TEXT,
    confidence REAL NOT NULL DEFAULT 0.7,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _make_pg_ddl(sqlite_ddl: str) -> str:
    """Convert the SQLite DDL to PostgreSQL-compatible DDL."""
    pg = sqlite_ddl
    # AUTOINCREMENT not valid in PostgreSQL; use SERIAL instead
    pg = pg.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    return pg


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
