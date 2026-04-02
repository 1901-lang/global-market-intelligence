"""Tests for backend/auth.py — JWT token creation/validation."""

import os
import pytest
from datetime import datetime, timedelta

# Set required env vars before importing auth
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32chars!")
os.environ.setdefault("REQUIRE_AUTH", "false")

from auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    _decode_token,
    ALGORITHM,
    SECRET_KEY,
)
from jose import jwt


class TestTokenCreation:
    def test_access_token_contains_subject(self):
        token = create_access_token({"sub": "alice"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "alice"

    def test_access_token_type_field(self):
        token = create_access_token({"sub": "alice"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["type"] == "access"

    def test_refresh_token_type_field(self):
        token = create_refresh_token({"sub": "alice"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["type"] == "refresh"

    def test_access_token_has_expiry(self):
        token = create_access_token({"sub": "alice"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload

    def test_refresh_token_longer_lived(self):
        access = create_access_token({"sub": "alice"})
        refresh = create_refresh_token({"sub": "alice"})
        a_exp = jwt.decode(access, SECRET_KEY, algorithms=[ALGORITHM])["exp"]
        r_exp = jwt.decode(refresh, SECRET_KEY, algorithms=[ALGORITHM])["exp"]
        assert r_exp > a_exp


class TestDecodeToken:
    def test_decode_valid_access_token(self):
        token = create_access_token({"sub": "bob"})
        assert _decode_token(token, "access") == "bob"

    def test_decode_access_token_with_wrong_type_fails(self):
        token = create_access_token({"sub": "bob"})
        assert _decode_token(token, "refresh") is None

    def test_decode_refresh_token(self):
        token = create_refresh_token({"sub": "carol"})
        assert _decode_token(token, "refresh") == "carol"

    def test_decode_invalid_token_returns_none(self):
        assert _decode_token("invalid.token.here", "access") is None

    def test_decode_no_secret_returns_none(self, monkeypatch):
        import auth as auth_module
        monkeypatch.setattr(auth_module, "SECRET_KEY", "")
        token = create_access_token({"sub": "dave"})
        # Patch the module-level SECRET_KEY used inside _decode_token
        assert auth_module._decode_token(token, "access") is None


class TestPasswordHashing:
    def test_verify_correct_password(self):
        hashed = hash_password("mysecret")
        assert verify_password("mysecret", hashed) is True

    def test_reject_wrong_password(self):
        hashed = hash_password("mysecret")
        assert verify_password("wrongpass", hashed) is False

    def test_hashes_are_unique(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt uses random salt
