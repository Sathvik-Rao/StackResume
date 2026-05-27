"""LLM factory dispatch — provider selection without making network calls."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_unsupported_provider_raises():
    from app.agents.llm_factory import get_llm

    with pytest.raises(ValueError, match="Unsupported provider"):
        get_llm(provider="vapourware", model="ghost")


@pytest.mark.parametrize(
    "provider, expected_cls",
    [
        ("openai", "ChatOpenAI"),
        ("anthropic", "ChatAnthropic"),
        ("google", "ChatGoogleGenerativeAI"),
        ("ollama", "ChatOllama"),
    ],
)
def test_provider_dispatch(provider, expected_cls, monkeypatch):
    """Verify each provider branch instantiates the matching LangChain class.

    No actual network handshake happens — LangChain's constructors validate
    args lazily on first invoke.
    """
    from app.config import settings
    monkeypatch.setattr(settings, "openai_api_key", "sk-fake", raising=False)
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-fake", raising=False)
    monkeypatch.setattr(settings, "google_api_key", "fake", raising=False)

    from app.agents.llm_factory import get_llm

    llm = get_llm(provider=provider, model=None)
    assert type(llm).__name__ == expected_cls


def test_defaults_to_settings(monkeypatch):
    from app.config import settings
    from app.agents.llm_factory import get_llm

    monkeypatch.setattr(settings, "llm_provider", "google", raising=False)
    monkeypatch.setattr(settings, "llm_model", "gemini-2.5-flash", raising=False)
    monkeypatch.setattr(settings, "google_api_key", "fake", raising=False)

    llm = get_llm()
    assert type(llm).__name__ == "ChatGoogleGenerativeAI"


def test_custom_provider_uses_openai_compatible(monkeypatch):
    """LLM_PROVIDER=custom routes through ChatOpenAI with OPENAI_BASE_URL."""
    import os
    from app.config import settings
    from app.agents.llm_factory import get_llm

    monkeypatch.setattr(settings, "openai_api_key", "sk-fake", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://custom.example/v1")

    llm = get_llm(provider="custom", model="my-model")
    # Custom uses ChatOpenAI under the hood.
    assert type(llm).__name__ == "ChatOpenAI"
