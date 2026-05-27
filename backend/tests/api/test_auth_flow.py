"""Session-token auth — login, /api/auth/check, middleware gating.

The middleware is wired at app-construction time, so we monkey-patch the
config flags AFTER the app has been built. The middleware reads
``settings.auth_enabled`` per-request so flipping the flag mid-test is safe.
"""
from __future__ import annotations

import hashlib

import pytest

pytestmark = pytest.mark.api


def _sha512(s: str) -> str:
    return hashlib.sha512(s.encode("utf-8")).hexdigest()


async def test_auth_disabled_check_returns_authenticated(async_client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "auth_enabled", False, raising=False)
    r = await async_client.get("/api/auth/check")
    assert r.status_code == 200
    assert r.json() == {"auth_enabled": False, "authenticated": True}


async def test_auth_disabled_endpoints_open(async_client, monkeypatch):
    """With auth off, /api/sessions should be reachable without a token."""
    from app.config import settings
    monkeypatch.setattr(settings, "auth_enabled", False, raising=False)
    r = await async_client.get("/api/sessions")
    assert r.status_code == 200


async def test_auth_enabled_requires_token(async_client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
    monkeypatch.setattr(settings, "auth_username", "admin", raising=False)
    monkeypatch.setattr(settings, "auth_password", "s3cret", raising=False)

    r = await async_client.get("/api/sessions")
    assert r.status_code == 401


async def test_auth_enabled_public_paths_pass(async_client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
    monkeypatch.setattr(settings, "auth_password", "s3cret", raising=False)

    # /api/health and /api/auth/check don't require a token.
    assert (await async_client.get("/api/health")).status_code == 200
    r = await async_client.get("/api/auth/check")
    assert r.status_code == 401  # unauthenticated, but accessible (no 403)
    body = r.json()
    assert body["auth_enabled"] is True


async def test_login_bad_credentials(async_client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
    monkeypatch.setattr(settings, "auth_username", "admin", raising=False)
    monkeypatch.setattr(settings, "auth_password", "s3cret", raising=False)

    r = await async_client.post(
        "/api/auth/login",
        json={"username": "admin", "password_hash": _sha512("wrong")},
    )
    assert r.status_code == 401


async def test_login_misconfigured_password_rejected(async_client, monkeypatch):
    """AUTH_ENABLED=true but AUTH_PASSWORD blank → 503 (operator error), not 401.

    Returning 401 here would hide the misconfiguration from the operator. The
    explicit 503 + detail string tells them exactly what to fix.
    """
    from app.config import settings
    monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
    monkeypatch.setattr(settings, "auth_username", "admin", raising=False)
    monkeypatch.setattr(settings, "auth_password", "", raising=False)

    r = await async_client.post(
        "/api/auth/login",
        json={"username": "admin", "password_hash": _sha512("anything")},
    )
    assert r.status_code == 503
    assert "AUTH_PASSWORD" in r.json()["detail"]


async def test_full_login_then_request_then_logout(async_client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
    monkeypatch.setattr(settings, "auth_username", "alice", raising=False)
    monkeypatch.setattr(settings, "auth_password", "topsecret", raising=False)

    # Login
    r = await async_client.post(
        "/api/auth/login",
        json={"username": "alice", "password_hash": _sha512("topsecret")},
    )
    assert r.status_code == 200
    token = r.json()["token"]
    assert token

    # Authenticated request succeeds
    auth_h = {"Authorization": f"Bearer {token}"}
    listed = await async_client.get("/api/sessions", headers=auth_h)
    assert listed.status_code == 200

    # Check endpoint reports authenticated
    chk = await async_client.get("/api/auth/check", headers=auth_h)
    assert chk.status_code == 200
    assert chk.json()["authenticated"] is True

    # Logout invalidates the token
    out = await async_client.post("/api/auth/logout", headers=auth_h)
    assert out.status_code == 200
    # Subsequent request rejected
    again = await async_client.get("/api/sessions", headers=auth_h)
    assert again.status_code == 401


async def test_login_no_auth_returns_token(async_client, monkeypatch):
    """When auth is disabled the login endpoint still issues a token so the
    frontend's auth check works uniformly across both modes."""
    from app.config import settings
    monkeypatch.setattr(settings, "auth_enabled", False, raising=False)

    r = await async_client.post(
        "/api/auth/login",
        json={"username": "anyone", "password_hash": _sha512("doesntmatter")},
    )
    assert r.status_code == 200
    assert r.json()["token"]
