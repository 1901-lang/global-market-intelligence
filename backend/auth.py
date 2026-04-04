"""JWT authentication, user management and token utilities.

Environment variables
---------------------
SECRET_KEY                  (required in production) — random secret for signing JWTs.
ACCESS_TOKEN_EXPIRE_MINUTES  defaults to 30.
REFRESH_TOKEN_EXPIRE_DAYS    defaults to 7.
REQUIRE_AUTH                 set to "false" to disable authentication (local dev only);
                              defaults to "true" — authentication is always enforced
                              in production unless explicitly disabled.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from db import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SECRET_KEY: str = os.getenv("SECRET_KEY", "")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
REQUIRE_AUTH: bool = os.getenv("REQUIRE_AUTH", "true").lower() == "true"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


class User(BaseModel):
    id: Optional[int] = None
    username: str
    email: Optional[str] = None
    role: str = "analyst"  # admin | analyst | readonly
    is_active: bool = True


class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    password: str
    role: str = "analyst"


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str, expected_type: str) -> Optional[str]:
    """Decode a JWT and return the subject username, or None on failure."""
    if not SECRET_KEY:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type:
            return None
        return payload.get("sub")
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

async def get_user_by_username(username: str) -> Optional[dict]:
    async with get_db() as db:
        return await db.fetchone(
            "SELECT * FROM users WHERE username = ? AND is_active = 1",
            (username,),
        )


async def create_user(user: UserCreate) -> Optional[dict]:
    hashed = hash_password(user.password)
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO users (username, email, hashed_password, role, is_active, created_at) "
                "VALUES (?, ?, ?, ?, 1, ?)",
                (user.username, user.email or "", hashed, user.role, datetime.utcnow()),
            )
            await db.commit()
    except Exception as exc:
        logger.warning("create_user failed: %s", exc)
        return None
    return await get_user_by_username(user.username)


async def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = await get_user_by_username(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

def _user_from_row(row: dict) -> User:
    return User(
        id=row.get("id"),
        username=row["username"],
        email=row.get("email"),
        role=row.get("role", "analyst"),
        is_active=bool(row.get("is_active", True)),
    )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service not configured — set SECRET_KEY",
        )
    username = _decode_token(token, "access")
    if not username:
        raise credentials_exception
    row = await get_user_by_username(username)
    if row is None:
        raise credentials_exception
    return _user_from_row(row)


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme_optional),
) -> Optional[User]:
    """Returns the authenticated user or None.  Does NOT raise on missing/invalid tokens."""
    if not token or not SECRET_KEY:
        return None
    username = _decode_token(token, "access")
    if not username:
        return None
    row = await get_user_by_username(username)
    return _user_from_row(row) if row else None


async def require_auth(token: str = Depends(oauth2_scheme)) -> User:
    """Dependency that enforces auth only when REQUIRE_AUTH=true.

    When REQUIRE_AUTH is false (default for dev) any caller is treated as an
    anonymous analyst so the existing frontend keeps working without changes.
    """
    if not REQUIRE_AUTH:
        return User(username="anonymous", role="analyst")
    return await get_current_user(token)


def require_role(*roles: str):
    """Dependency factory that asserts the current user holds one of the given roles."""

    async def _dep(user: User = Depends(require_auth)) -> User:
        if user.role not in roles and REQUIRE_AUTH:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' is not permitted for this action",
            )
        return user

    return _dep
