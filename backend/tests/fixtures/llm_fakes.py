"""Deterministic in-memory LLM stand-in.

The real pipeline calls ``get_llm(provider, model).invoke(messages, config=...)``
and parses JSON out of ``response.content``. Tests don't have provider keys
(and shouldn't need them), so we monkey-patch ``get_llm`` to return a
``FakeLLM`` that answers based on the system prompt fingerprint.

A test can override individual agent payloads:

    fake_llm.set("Intent Guard", {"intent": "off_topic", "suggested_reply": "no"})
    fake_llm.set("Resume Generator", custom_resume_dict)

If an agent's prompt fingerprint isn't recognised, the FakeLLM returns a
sensible default so the pipeline never hangs in tests.
"""
from __future__ import annotations

import json
from typing import Any, Iterable


# ── Default JSON payloads per agent ───────────────────────────────────────────
# Keyed by a substring that uniquely identifies the agent's system prompt.

_AGENT_DEFAULTS: dict[str, dict] = {
    "intent": {
        "intent": "resume_related",
        "confidence": "high",
        "suggested_reply": "",
    },
    "parser": {
        "request_type": "create",
        "target_role": "Backend Engineer",
        "years_experience": 5,
        "other_context": "from test input",
    },
    "jd_analyzer": {
        "job_title": "Senior Backend Engineer",
        "company": "Acme",
        "ats_keywords": ["Python", "FastAPI", "PostgreSQL", "AWS"],
        "required_skills": ["Python", "FastAPI"],
        "preferred_skills": ["Kubernetes"],
        "responsibilities": ["Own backend services."],
    },
    "generator": {
        "metadata": {"version": "1"},
        "personal_info": {
            "full_name": "Test Person",
            "professional_title": "Senior Backend Engineer",
            "email": "test@example.com",
            "phone": "+1-555-0000",
            "location": "Remote",
            "linkedin": "https://linkedin.com/in/test",
            "github": "https://github.com/test",
            "website": "",
        },
        "professional_summary": "Backend engineer with deep Python expertise.",
        "core_competencies": ["Python", "FastAPI", "PostgreSQL"],
        "experience": [
            {
                "company": "Acme",
                "title": "Senior Backend Engineer",
                "location": "Remote",
                "start_date": "2022-01",
                "end_date": "Present",
                "responsibilities": ["Owned backend services."],
                "achievements": ["Improved p99 latency by 50%."],
                "technologies": ["Python", "FastAPI"],
            }
        ],
        "education": [{"institution": "MIT", "degree": "BS CS", "graduation_year": 2018}],
        "technical_skills": {
            "programming_languages": ["Python", "Go"],
            "frameworks_and_libraries": ["FastAPI"],
            "databases": ["PostgreSQL"],
            "cloud_and_infrastructure": ["AWS"],
        },
        "projects": [],
        "certifications": [],
    },
    "reviewer": {
        "ats_score": 88,
        "quality_score": 86,
        "impact_score": 85,
        "completeness_score": 90,
        "overall_score": 87,
        "reviewer_notes": "Solid resume, ATS-friendly, strong impact statements.",
        "improvement_suggestions": ["Add one more leadership bullet."],
        "critical_issues": [],
        "weak_bullets": [],
        "keywords_found": ["Python", "FastAPI"],
        "missing_keywords": [],
    },
    "enhancer": None,  # filled in dynamically — echoes the most recent generator payload
    "cover_letter": {
        "cover_letter": (
            "I'm excited to apply for the Senior Backend Engineer role.\n\n"
            "My recent work at Acme aligns with your need for FastAPI expertise."
        ),
        "hiring_manager": "Hiring Team",
    },
    "outreach": {
        "emails": [
            {"type": "cold_application", "subject": "Senior Backend role", "body": "Hi…"},
            {"type": "linkedin", "subject": "", "body": "Hi…"},
            {"type": "referral", "subject": "Referral request", "body": "Hi…"},
        ]
    },
}


def _fingerprint(messages: Iterable[Any]) -> str:
    """Return a normalised agent fingerprint from the system message text.

    The graph always sends ``[SystemMessage, HumanMessage]``. We sniff the
    system text for unique phrases per agent so a test that overrides
    ``"Intent Guard"`` doesn't accidentally also override the parser.
    """
    sys_text = ""
    for m in messages:
        # LangChain SystemMessage exposes .content; tolerate dicts too.
        content = getattr(m, "content", None) or (m.get("content") if isinstance(m, dict) else "")
        role = getattr(m, "type", None) or (m.get("role") if isinstance(m, dict) else "")
        if role in ("system", "SystemMessage"):
            sys_text = content
            break
        # First message in the canonical [System, Human] pair
        if not sys_text:
            sys_text = content
    text = (sys_text or "").lower()
    # Order matters: check the most-specific, opening-line markers first so a
    # later prompt that happens to mention "ats_score" in its schema doesn't
    # masquerade as the reviewer.
    if "strict intent classifier" in text:
        return "intent"
    if "resume data extractor" in text:
        return "parser"
    if "job description analyst" in text:
        return "jd_analyzer"
    if "world-class resume writer" in text:
        return "generator"
    if "senior technical recruiter" in text:
        return "reviewer"
    if "world-class resume editor" in text or "resume tailoring specialist" in text:
        return "enhancer"
    if "cover letters" in text or "career coach who has written cover letters" in text:
        return "cover_letter"
    if "executive recruiter and career coach" in text:
        return "outreach"
    # Default — keep the fall-through behaviour deterministic for tests that
    # bypass the prompt library entirely.
    return "generator"


class _FakeUsage(dict):
    """Mimics a LangChain ``UsageMetadata`` TypedDict."""


class _FakeResponse:
    """Stand-in for a LangChain ``AIMessage``."""

    def __init__(self, content: str, model: str = "fake-test"):
        self.content = content
        self.usage_metadata = _FakeUsage(input_tokens=10, output_tokens=20, total_tokens=30)
        self.response_metadata = {
            "model_name": model,
            "token_usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }


class FakeLLM:
    """A drop-in replacement for any LangChain ``BaseChatModel``.

    Behaviour:
      - ``.invoke(messages, config=...)`` returns a ``_FakeResponse`` whose
        ``.content`` is the JSON-serialised default for the matched agent.
      - Tests can override a specific agent's payload with ``.set("agent_key",
        payload)`` where ``agent_key`` is one of: intent, parser, jd_analyzer,
        generator, reviewer, enhancer, cover_letter, outreach.
      - Tests can force a raw text response (e.g. malformed JSON) via
        ``.set_raw("agent_key", "not json")``.
      - ``.invocations`` records the (agent_key, message_count) of every call,
        so a test can assert which agents ran.
    """

    def __init__(self, model_name: str = "fake-test"):
        self.model_name = model_name
        self.model = model_name  # ollama / google use this attr
        self._overrides: dict[str, Any] = {}
        self._raw_overrides: dict[str, str] = {}
        self._last_resume: dict | None = None
        self.invocations: list[tuple[str, int]] = []

    # ── Test API ──────────────────────────────────────────────────────────────

    def set(self, agent_key: str, payload: dict | list) -> None:
        self._overrides[agent_key] = payload

    def set_raw(self, agent_key: str, text: str) -> None:
        self._raw_overrides[agent_key] = text

    def set_resume(self, resume: dict) -> None:
        """Shortcut: drive generator (and enhancer echo) with a custom resume."""
        self._overrides["generator"] = resume

    def fail_with(self, agent_key: str, exc: BaseException) -> None:
        """Make a specific agent's LLM call raise ``exc`` instead of returning."""
        self._overrides[agent_key] = exc

    # ── LangChain protocol ────────────────────────────────────────────────────

    def invoke(self, messages, config=None, **_kw):
        key = _fingerprint(messages)
        self.invocations.append((key, len(list(messages) if not hasattr(messages, "__len__") else messages)))

        if key in self._raw_overrides:
            return _FakeResponse(self._raw_overrides[key], model=self.model_name)

        override = self._overrides.get(key)
        if isinstance(override, BaseException):
            raise override

        if override is not None:
            payload = override
        elif key == "enhancer":
            # Enhancer should return something resume-shaped. Echo the most
            # recent generator payload so review→enhance→review loops converge.
            payload = self._last_resume or _AGENT_DEFAULTS["generator"]
        else:
            payload = _AGENT_DEFAULTS[key]

        if key in ("generator", "enhancer"):
            self._last_resume = payload  # cache for the next enhancer call

        return _FakeResponse(json.dumps(payload), model=self.model_name)

    # ``ainvoke`` is unused by the pipeline but provided for completeness.
    async def ainvoke(self, messages, config=None, **kw):
        return self.invoke(messages, config=config, **kw)


def install_fake(monkeypatch, fake: FakeLLM) -> None:
    """Patch every place that resolves an LLM so all agents use ``fake``.

    After the graph.py → graph/ package split, each agent node module imports
    ``get_llm`` directly from ``llm_factory``. Patching the factory module
    only catches lazy resolves, so we also patch the bound name in every
    sub-module that already pulled it in (intent + every node).
    """
    from app.agents import llm_factory
    from app.agents import graph
    from app.agents.graph import _intent
    from app.agents.graph.nodes import (
        parse as _parse, jd as _jd, generate as _gen, review as _rev,
        enhance as _enh, cover_letter as _cl, outreach as _out,
    )
    from app.api import settings_routes

    fake_factory = lambda *a, **k: fake  # noqa: E731

    monkeypatch.setattr(llm_factory, "get_llm", fake_factory)
    # Patch the re-exported name on the package too — ``from app.agents.graph import get_llm``
    # resolves through it.
    monkeypatch.setattr(graph, "get_llm", fake_factory)
    for mod in (_intent, _parse, _jd, _gen, _rev, _enh, _cl, _out):
        monkeypatch.setattr(mod, "get_llm", fake_factory)
    # settings_routes.test_provider imports get_llm lazily — patch at the source.
    if hasattr(settings_routes, "get_llm"):
        monkeypatch.setattr(settings_routes, "get_llm", fake_factory)
