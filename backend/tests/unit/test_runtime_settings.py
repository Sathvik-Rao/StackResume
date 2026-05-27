"""Runtime overlay layer — baseline ⇄ DB row ⇄ env side-effects."""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.unit


def test_baseline_snapshot_is_idempotent():
    from app import runtime_settings as rs

    rs._BASELINE.clear()
    rs._snapshot_baseline_once()
    snapshot1 = dict(rs._BASELINE)
    rs._snapshot_baseline_once()
    assert rs._BASELINE == snapshot1


def test_apply_overlay_with_none_restores_baseline(monkeypatch):
    from app import runtime_settings as rs
    from app.config import settings

    rs._BASELINE.clear()
    rs._snapshot_baseline_once()

    settings.llm_provider = "anthropic"
    rs._apply_overlay(None)
    assert settings.llm_provider == rs._BASELINE["llm_provider"]


def test_apply_overlay_applies_non_empty_fields():
    from app import runtime_settings as rs
    from app.config import settings
    from app.models import AppSettings

    rs._BASELINE.clear()
    rs._snapshot_baseline_once()

    row = AppSettings(
        llm_provider="anthropic",
        llm_model="claude-sonnet-4-6",
        llm_temperature=0.2,
        openai_api_key="",                  # empty string → ignored
        anthropic_api_key="sk-xxx",
        max_review_iterations=5,
    )
    rs._apply_overlay(row)

    assert settings.llm_provider == "anthropic"
    assert settings.llm_model == "claude-sonnet-4-6"
    assert settings.llm_temperature == 0.2
    assert settings.anthropic_api_key == "sk-xxx"
    assert settings.max_review_iterations == 5
    # Empty string didn't blank the baseline
    assert settings.openai_api_key == rs._BASELINE["openai_api_key"]


def test_env_side_effects_set_and_unset(monkeypatch):
    from app import runtime_settings as rs
    from app.config import settings

    monkeypatch.setattr(settings, "openai_api_key", "sk-test", raising=False)
    monkeypatch.setattr(settings, "langsmith_tracing", False, raising=False)
    monkeypatch.setattr(settings, "langsmith_api_key", None, raising=False)
    os.environ.pop("LANGSMITH_TRACING", None)

    rs._apply_env_side_effects()
    assert os.environ.get("OPENAI_API_KEY") == "sk-test"
    assert "LANGSMITH_TRACING" not in os.environ

    monkeypatch.setattr(settings, "langsmith_tracing", True, raising=False)
    monkeypatch.setattr(settings, "langsmith_api_key", "ls-test", raising=False)
    monkeypatch.setattr(settings, "langsmith_project", "myproj", raising=False)
    rs._apply_env_side_effects()
    assert os.environ.get("LANGSMITH_TRACING") == "true"
    assert os.environ.get("LANGSMITH_PROJECT") == "myproj"


def test_overlay_view_masks_secrets(monkeypatch):
    from app import runtime_settings as rs
    from app.config import settings

    monkeypatch.setattr(settings, "openai_api_key", "sk-real", raising=False)
    monkeypatch.setattr(settings, "anthropic_api_key", None, raising=False)

    view = rs.current_overlay_view()
    # Plain key still exists in the view (the masking happens in the route
    # serializer, not here) — but the booleans flag must be accurate.
    assert view["_secrets_set"]["openai_api_key"] is True
    assert view["_secrets_set"]["anthropic_api_key"] is False
