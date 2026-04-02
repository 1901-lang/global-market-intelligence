"""Async database abstraction supporting SQLite (dev) and PostgreSQL (prod).

Set DATABASE_URL=postgresql://user:pass@host:5432/dbname to use PostgreSQL.
Leave unset (or set DB_PATH) to use SQLite.

Usage
-----
    from db import get_db

    async with get_db() as db:
        await db.execute("INSERT INTO table VALUES (?, ?)", (a, b))
        await db.commit()

        rows = await db.fetchall("SELECT * FROM table WHERE id = ?", (id,))
        row  = await db.fetchone("SELECT * FROM table WHERE id = ?", (id,))
"""

from __future__ import annotations

import os
import re
import logging
from contextlib import asynccontextmanager
from typing import Any, List, Optional, Sequence

logger = logging.getLogger(__name__)

DATABASE_URL: str = os.getenv("DATABASE_URL", "")
DB_PATH: str = os.getenv("DB_PATH", "aip.db")

IS_POSTGRES: bool = DATABASE_URL.startswith(("postgresql://", "postgres://"))

_pg_pool = None


async def init_pg_pool():
    """Initialise (or return cached) asyncpg connection pool."""
    global _pg_pool
    if _pg_pool is None:
        import asyncpg  # type: ignore

        url = DATABASE_URL
        # asyncpg requires the postgresql:// scheme
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        _pg_pool = await asyncpg.create_pool(url, min_size=2, max_size=10)
    return _pg_pool


async def close_pg_pool():
    global _pg_pool
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None


# ---------------------------------------------------------------------------
# SQL dialect translation
# ---------------------------------------------------------------------------

def _translate_sql(sql: str) -> str:
    """Convert SQLite ? placeholders and date functions to PostgreSQL equivalents."""
    # Replace ? placeholders with $1, $2, ...
    count = 0
    result: list[str] = []
    for ch in sql:
        if ch == "?":
            count += 1
            result.append(f"${count}")
        else:
            result.append(ch)
    sql = "".join(result)

    # datetime('now', '-N hours') → NOW() - INTERVAL 'N hours'
    sql = re.sub(
        r"datetime\('now',\s*'-(\d+)\s+hours?'\)",
        r"NOW() - INTERVAL '\1 hours'",
        sql,
        flags=re.IGNORECASE,
    )
    # datetime('now', '-N days') → NOW() - INTERVAL 'N days'
    sql = re.sub(
        r"datetime\('now',\s*'-(\d+)\s+days?'\)",
        r"NOW() - INTERVAL '\1 days'",
        sql,
        flags=re.IGNORECASE,
    )
    return sql


# ---------------------------------------------------------------------------
# Row wrapper — dict with attribute access
# ---------------------------------------------------------------------------

class _Row(dict):
    """Dict subclass that also supports attribute-style field access."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None


# ---------------------------------------------------------------------------
# SQLite backend
# ---------------------------------------------------------------------------

class _SQLiteDB:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    async def execute(self, sql: str, params: Sequence = ()) -> None:
        await self._conn.execute(sql, params)

    async def executemany(self, sql: str, params_list: Sequence) -> None:
        await self._conn.executemany(sql, params_list)

    async def fetchall(self, sql: str, params: Sequence = ()) -> List[_Row]:
        import aiosqlite

        self._conn.row_factory = aiosqlite.Row
        async with self._conn.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [_Row(dict(r)) for r in rows]

    async def fetchone(self, sql: str, params: Sequence = ()) -> Optional[_Row]:
        import aiosqlite

        self._conn.row_factory = aiosqlite.Row
        async with self._conn.execute(sql, params) as cur:
            row = await cur.fetchone()
        return _Row(dict(row)) if row else None

    async def commit(self) -> None:
        await self._conn.commit()


# ---------------------------------------------------------------------------
# PostgreSQL backend
# ---------------------------------------------------------------------------

class _PostgresDB:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    async def execute(self, sql: str, params: Sequence = ()) -> None:
        await self._conn.execute(_translate_sql(sql), *params)

    async def executemany(self, sql: str, params_list: Sequence) -> None:
        pg_sql = _translate_sql(sql)
        await self._conn.executemany(pg_sql, params_list)

    async def fetchall(self, sql: str, params: Sequence = ()) -> List[_Row]:
        rows = await self._conn.fetch(_translate_sql(sql), *params)
        return [_Row(dict(r)) for r in rows]

    async def fetchone(self, sql: str, params: Sequence = ()) -> Optional[_Row]:
        row = await self._conn.fetchrow(_translate_sql(sql), *params)
        return _Row(dict(row)) if row else None

    async def commit(self) -> None:
        pass  # PostgreSQL commits automatically on transaction context exit


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@asynccontextmanager
async def get_db():
    """Async context manager yielding a unified database connection wrapper.

    For PostgreSQL each call opens a connection from the pool and wraps it
    in a transaction that commits on clean exit (rolls back on exception).
    For SQLite each call opens a new aiosqlite connection.
    """
    if IS_POSTGRES:
        pool = await init_pg_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                yield _PostgresDB(conn)
    else:
        import aiosqlite

        async with aiosqlite.connect(DB_PATH) as conn:
            yield _SQLiteDB(conn)
