"""Settings + CORS parsing."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_settings_defaults_load():
    from app.config import Settings

    s = Settings(_env_file=None)
    assert s.app_name == "StackResume"
    assert s.llm_provider in ("openai", "anthropic", "google", "ollama", "custom")
    assert 0 <= s.llm_temperature <= 2
    assert s.max_review_iterations >= 1
    assert 0 <= s.min_quality_score <= 100


def test_settings_extra_env_is_ignored(monkeypatch):
    """We set ``extra='ignore'`` so unknown env vars must not raise."""
    monkeypatch.setenv("SOME_TOTALLY_UNRELATED_VAR", "yes")
    from app.config import Settings

    Settings(_env_file=None)  # should not raise


@pytest.mark.parametrize(
    "raw, auth, expected",
    [
        ("*", False, ["*"]),
        ("*", True, []),                                       # collapses to same-origin
        ("https://a.example", False, ["https://a.example"]),
        ("https://a.example, https://b.example", True, ["https://a.example", "https://b.example"]),
        ("  ", False, ["*"]),                                  # empty == wildcard default
    ],
)
def test_cors_parser(raw, auth, expected):
    from app.main import _parse_cors_origins

    assert _parse_cors_origins(raw, auth) == expected
