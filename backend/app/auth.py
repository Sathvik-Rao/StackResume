"""Session-based auth with SHA-512 password hashing.

When AUTH_ENABLED=true, every /api/* request (except /api/health and /api/auth/*)
must include a valid session token: Authorization: Bearer <token>

Login flow:
  1. Client hashes the password with SHA-512 and POSTs {username, password_hash}
  2. Server computes SHA-512(configured_password) and compares both hashes
     using constant-time comparison (secrets.compare_digest)
  3. On success, server returns a UUID session token (24h TTL)
  4. All subsequent requests send Authorization: Bearer <token>

Logout: POST /api/auth/logout invalidates the token server-side.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings

# Paths that are always public (no auth required).
_PUBLIC_PATHS = {"/api/health", "/api/auth/check", "/api/auth/login"}
# Static asset prefixes that are always reachable (GET only).
_PUBLIC_PREFIXES_GET = ("/assets/", "/favicon")

# In-memory session store: { token: { "user": str, "expires_at": datetime } }
_sessions: dict[str, dict] = {}
_SESSION_TTL_HOURS = 24


def _sha512(s: str) -> str:
    return hashlib.sha512(s.encode("utf-8")).hexdigest()


_MISCONFIGURED = "__MISCONFIGURED__"


def _expected_hash() -> tuple[str, str] | None:
    """Return (username, sha512_password_hash) if auth is enabled, else None.

    Returns the ``_MISCONFIGURED`` sentinel as the hash slot when AUTH_ENABLED
    is on but AUTH_PASSWORD is empty — login will then reject every attempt
    rather than silently allowing access.
    """
    if not settings.auth_enabled:
        return None
    if not settings.auth_password:
        return settings.auth_username or "admin", _MISCONFIGURED
    return settings.auth_username or "admin", _sha512(settings.auth_password)


def _check_token(header: str | None) -> Optional[dict]:
    """Return session dict if Bearer token is valid, else None."""
    if not header or not header.lower().startswith("bearer "):
        return None
    token = header.split(" ", 1)[1].strip()
    session = _sessions.get(token)
    if not session:
        return None
    if datetime.now(timezone.utc) > session["expires_at"]:
        _sessions.pop(token, None)
        return None
    return session


def _cleanup_sessions() -> None:
    now = datetime.now(timezone.utc)
    expired = [t for t, s in list(_sessions.items()) if now > s["expires_at"]]
    for t in expired:
        _sessions.pop(t, None)


# ── Middleware ─────────────────────────────────────────────────────────────────

class SessionAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.auth_enabled:
            return await call_next(request)
        path = request.url.path
        if path in _PUBLIC_PATHS:
            return await call_next(request)
        if path == "/" and request.method == "GET":
            return await call_next(request)
        if request.method == "GET" and any(
            path.startswith(p) for p in _PUBLIC_PREFIXES_GET
        ):
            return await call_next(request)
        if _check_token(request.headers.get("Authorization")):
            return await call_next(request)
        return JSONResponse({"detail": "Authentication required"}, status_code=401)


# ── Router ─────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password_hash: str  # SHA-512 hex digest of the raw password


@router.post("/login")
async def auth_login(req: LoginRequest):
    """Validate credentials and return a session token."""
    _cleanup_sessions()
    expected = _expected_hash()
    if expected is None:
        # Auth is disabled — issue a token anyway so the flow works uniformly.
        token = str(uuid.uuid4())
        _sessions[token] = {
            "user": req.username,
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=_SESSION_TTL_HOURS),
        }
        return {"token": token, "user": req.username}

    exp_user, exp_hash = expected
    if exp_hash == _MISCONFIGURED:
        # AUTH_ENABLED=true but AUTH_PASSWORD is blank — fail loudly so the
        # operator notices instead of getting "invalid credentials" forever.
        return JSONResponse(
            {"detail": "Server auth misconfigured: AUTH_PASSWORD is not set."},
            status_code=503,
        )
    user_ok = secrets.compare_digest(req.username, exp_user)
    # Both sides are SHA-512 hex digests — compare in constant time.
    pw_ok = secrets.compare_digest(req.password_hash.lower(), exp_hash.lower())
    if not (user_ok and pw_ok):
        return JSONResponse({"detail": "Invalid credentials"}, status_code=401)

    token = str(uuid.uuid4())
    _sessions[token] = {
        "user": req.username,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=_SESSION_TTL_HOURS),
    }
    return {"token": token, "user": req.username}


@router.post("/logout")
async def auth_logout(request: Request):
    """Invalidate the current session token."""
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        token = header.split(" ", 1)[1].strip()
        _sessions.pop(token, None)
    return {"detail": "Logged out"}


@router.get("/check")
async def auth_check(request: Request):
    """Tell the frontend whether auth is on and whether the current token is valid."""
    if not settings.auth_enabled:
        return {"auth_enabled": False, "authenticated": True}
    session = _check_token(request.headers.get("Authorization"))
    if session:
        return {"auth_enabled": True, "authenticated": True, "user": session["user"]}
    return JSONResponse({"auth_enabled": True, "authenticated": False}, status_code=401)
