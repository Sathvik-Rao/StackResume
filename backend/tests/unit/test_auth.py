"""Auth helpers — hashing, token check, session expiry."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.unit


def test_sha512_matches_stdlib():
    from app.auth import _sha512

    assert _sha512("hunter2") == hashlib.sha512(b"hunter2").hexdigest()


def test_expected_hash_disabled(monkeypatch):
    from app import auth
    monkeypatch.setattr(auth.settings, "auth_enabled", False, raising=False)
    assert auth._expected_hash() is None


def test_expected_hash_misconfigured(monkeypatch):
    """Auth on but no password → MISCONFIGURED sentinel, NOT an empty string."""
    from app import auth
    monkeypatch.setattr(auth.settings, "auth_enabled", True, raising=False)
    monkeypatch.setattr(auth.settings, "auth_username", "admin", raising=False)
    monkeypatch.setattr(auth.settings, "auth_password", "", raising=False)

    user, h = auth._expected_hash()
    assert user == "admin"
    assert "MISCONFIGURED" in h


def test_expected_hash_returns_sha512(monkeypatch):
    from app import auth
    monkeypatch.setattr(auth.settings, "auth_enabled", True, raising=False)
    monkeypatch.setattr(auth.settings, "auth_username", "alice", raising=False)
    monkeypatch.setattr(auth.settings, "auth_password", "s3cr3t", raising=False)

    user, h = auth._expected_hash()
    assert user == "alice"
    assert h == hashlib.sha512(b"s3cr3t").hexdigest()


def test_check_token_expired(monkeypatch):
    from app import auth

    token = str(uuid.uuid4())
    auth._sessions[token] = {
        "user": "x",
        "expires_at": datetime.now(timezone.utc) - timedelta(seconds=1),
    }
    assert auth._check_token(f"Bearer {token}") is None
    # Expired tokens are also evicted from the store.
    assert token not in auth._sessions


def test_check_token_valid():
    from app import auth

    token = str(uuid.uuid4())
    auth._sessions[token] = {
        "user": "x",
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    s = auth._check_token(f"Bearer {token}")
    assert s and s["user"] == "x"
    # Cleanup
    auth._sessions.pop(token, None)


def test_check_token_bad_header():
    from app import auth

    assert auth._check_token(None) is None
    assert auth._check_token("Basic abc") is None
    assert auth._check_token("Bearer unknown-token-xyz") is None


def test_cleanup_sessions_removes_only_expired():
    from app import auth

    auth._sessions.clear()
    live = str(uuid.uuid4())
    dead = str(uuid.uuid4())
    auth._sessions[live] = {"user": "x", "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)}
    auth._sessions[dead] = {"user": "x", "expires_at": datetime.now(timezone.utc) - timedelta(hours=1)}

    auth._cleanup_sessions()
    assert live in auth._sessions
    assert dead not in auth._sessions
    auth._sessions.pop(live, None)
