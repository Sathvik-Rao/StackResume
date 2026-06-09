"""Runtime settings overlay.

Settings come from two layers:
  1. Baseline — loaded from env / .env at process startup into `settings`.
  2. DB overlay — `app_settings` row, edited live in the UI.

Whenever the DB overlay changes, we mutate the in-memory `settings` object AND
update relevant `os.environ` keys so libraries that auto-read from env (e.g.
LangSmith / LangChain instrumentation) see the new values.
"""
from __future__ import annotations
import os
from typing import Any

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import AppSettings


_BASELINE: dict[str, Any] = {}
_OVERLAY_FIELDS = (
    "llm_provider", "llm_model", "llm_temperature",
    "models_by_provider",
    "openai_api_key", "anthropic_api_key", "google_api_key",
    "ollama_base_url", "openai_base_url",
    "langsmith_api_key", "langsmith_project", "langsmith_tracing",
    "max_review_iterations", "min_quality_score",
    "default_jd_intensity", "memory_enabled",
)


def _snapshot_baseline_once() -> None:
    if _BASELINE:
        return
    for f in _OVERLAY_FIELDS:
        _BASELINE[f] = getattr(settings, f, None)


def _apply_env_side_effects() -> None:
    """Set os.environ keys so LangChain / LangSmith / SDKs pick up new values."""
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    if settings.google_api_key:
        os.environ["GOOGLE_API_KEY"] = settings.google_api_key

    endpoint = "https://api.smith.langchain.com"
    if settings.langsmith_tracing and settings.langsmith_api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGCHAIN_TRACING_V2"] = "true"          # older env var name, still required by some LangChain internals
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project or "stackresume"
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project or "stackresume"
        os.environ.setdefault("LANGSMITH_ENDPOINT", endpoint)
        os.environ.setdefault("LANGCHAIN_ENDPOINT", endpoint)
    else:
        for k in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"):
            os.environ.pop(k, None)


def _apply_overlay(row: AppSettings | None) -> None:
    """Reset to baseline, then apply non-empty fields from the DB row."""
    import json as _json
    _snapshot_baseline_once()
    for f in _OVERLAY_FIELDS:
        setattr(settings, f, _BASELINE.get(f))
    if row is not None:
        for f in _OVERLAY_FIELDS:
            v = getattr(row, f, None)
            if v is None or (isinstance(v, str) and not v.strip()):
                continue
            # Some SQLite/aiosqlite combinations return JSON columns as a
            # string. Coerce dict-typed overlay fields back to a real dict so
            # downstream code (and the API response) doesn't choke.
            if f == "models_by_provider" and isinstance(v, str):
                try:
                    v = _json.loads(v)
                except Exception:
                    continue
            setattr(settings, f, v)
    _apply_env_side_effects()


async def load_settings_from_db() -> AppSettings | None:
    """Read the AppSettings row (if any) and apply it on top of baseline."""
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(AppSettings).limit(1))
        row = res.scalar_one_or_none()
    _apply_overlay(row)
    return row


def apply_overlay_from_row(row: AppSettings | None) -> None:
    """Synchronous overlay application — for callers that already have the row."""
    _apply_overlay(row)


def current_overlay_view() -> dict:
    """A dict of current effective values (baseline + overlay) — safe to return to UI."""
    _snapshot_baseline_once()
    out = {f: getattr(settings, f, None) for f in _OVERLAY_FIELDS}
    # Mark which keys are "set" without leaking the secret value
    out["_secrets_set"] = {
        k: bool(getattr(settings, k))
        for k in ("openai_api_key", "anthropic_api_key", "google_api_key", "langsmith_api_key")
    }
    return out
