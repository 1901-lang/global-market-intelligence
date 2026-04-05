"""Tests for the GET /api/admin/db/export endpoint (SQLite path)."""

import asyncio
import os

# Set env vars BEFORE any app modules are imported
os.environ["DB_PATH"] = "/tmp/aip_export_test.db"
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32chars!")
os.environ.setdefault("REQUIRE_AUTH", "true")
os.environ.pop("DATABASE_URL", None)

import db as db_module
db_module.DB_PATH = "/tmp/aip_export_test.db"
db_module.IS_POSTGRES = False

import database as database_module
database_module.DB_PATH = "/tmp/aip_export_test.db"

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from auth import create_access_token, create_user, UserCreate
from database import init_db
from main import app


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="module")
async def admin_token(event_loop):
    """Initialise DB, create an admin user, and return a valid JWT."""
    await init_db()
    await create_user(UserCreate(username="test_admin", password="Test1234!", role="admin"))
    token = create_access_token({"sub": "test_admin"})
    yield token
    # Cleanup
    try:
        os.remove("/tmp/aip_export_test.db")
    except FileNotFoundError:
        pass


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_export_returns_sql_dump(admin_token):
    """SQLite export should stream valid SQL containing table definitions."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/admin/db/export", headers=_auth_headers(admin_token)
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    # SQLite .iterdump() always starts with a BEGIN TRANSACTION block
    assert "BEGIN TRANSACTION" in body or "CREATE TABLE" in body


@pytest.mark.asyncio
async def test_export_content_disposition(admin_token):
    """The response must carry an attachment Content-Disposition header."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/admin/db/export", headers=_auth_headers(admin_token)
        )

    assert response.status_code == 200
    cd = response.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert "backup_" in cd
    assert cd.endswith('.sql"')


@pytest.mark.asyncio
async def test_export_contains_known_table(admin_token):
    """Exported SQL must reference the users table that init_db creates."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/admin/db/export", headers=_auth_headers(admin_token)
        )

    assert response.status_code == 200
    assert "users" in response.text


@pytest.mark.asyncio
async def test_export_requires_auth():
    """Endpoint must reject unauthenticated requests with 401."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/admin/db/export")

    assert response.status_code == 401
