"""Cover Letter + Outreach Writer nodes."""
from __future__ import annotations

import copy

import pytest

pytestmark = pytest.mark.agents


def test_cover_letter_requires_resume_and_jd(base_state, fake_llm):
    from app.agents.graph import cover_letter_node

    out = cover_letter_node(base_state)
    assert out is base_state
    assert fake_llm.invocations == []


def test_cover_letter_strips_salutation_and_trailing_name(base_state, fake_llm, sample_resume):
    """Letterhead is rendered by the UI/PDF, not the body. The agent must
    strip the leading salutation and the candidate's trailing signature so
    we never show the name twice."""
    from app.agents.graph import cover_letter_node

    base_state["resume"] = copy.deepcopy(sample_resume)
    base_state["jd_analysis"] = {"job_title": "Senior Backend"}
    fake_llm.set("cover_letter", {
        "cover_letter": (
            "Dear Hiring Team,\n\n"
            "I am thrilled to apply.\n\n"
            "My background fits well.\n\n"
            "Ada Lovelace"
        ),
        "hiring_manager": "Hiring Team",
    })
    out = cover_letter_node(base_state)
    body = out["cover_letter"]
    assert not body.lower().startswith("dear")
    assert not body.strip().endswith("Ada Lovelace")
    assert "thrilled" in body or "fits" in body


def test_cover_letter_strips_greetings_salutation(base_state, fake_llm, sample_resume):
    """Regression: the original strip list missed single-word openers like
    'Greetings,' which then got rendered twice (once in the body, once via
    the UI's letterhead salutation)."""
    from app.agents.graph import cover_letter_node

    base_state["resume"] = sample_resume
    base_state["jd_analysis"] = {"job_title": "Senior Backend"}
    fake_llm.set("cover_letter", {
        "cover_letter": (
            "Greetings,\n\n"
            "I am thrilled to apply for the Senior Backend role.\n\n"
            "My background fits well."
        ),
        "hiring_manager": "Hiring Team",
    })
    body = cover_letter_node(base_state)["cover_letter"]
    assert not body.lower().startswith("greetings")
    assert "thrilled" in body


def test_cover_letter_strips_explicit_signoff(base_state, fake_llm, sample_resume):
    """When the LLM emits a bare 'Sincerely,' line (with no trailing name)
    that signoff is also stripped — the PDF renders its own."""
    from app.agents.graph import cover_letter_node

    base_state["resume"] = copy.deepcopy(sample_resume)
    base_state["jd_analysis"] = {"job_title": "Senior Backend"}
    fake_llm.set("cover_letter", {
        "cover_letter": (
            "Dear team,\n\n"
            "I am applying.\n\n"
            "Sincerely,"
        ),
        "hiring_manager": "Hiring Team",
    })
    body = cover_letter_node(base_state)["cover_letter"]
    assert "sincerely" not in body.lower()
    assert not body.lower().startswith("dear")


def test_cover_letter_error_recorded(base_state, fake_llm, sample_resume):
    from app.agents.graph import cover_letter_node

    base_state["resume"] = copy.deepcopy(sample_resume)
    base_state["jd_analysis"] = {"job_title": "X"}
    fake_llm.fail_with("cover_letter", RuntimeError("LLM error"))
    out = cover_letter_node(base_state)
    assert out["cover_letter"] is None
    assert out["agent_trace"][-1]["status"] == "error"


def test_outreach_emits_email_list(base_state, fake_llm, sample_resume):
    from app.agents.graph import outreach_node

    base_state["resume"] = copy.deepcopy(sample_resume)
    base_state["jd_analysis"] = {"job_title": "X"}
    fake_llm.set("outreach", {"emails": [
        {"type": "cold_application", "subject": "S1", "body": "B1"},
        {"type": "referral", "subject": "S2", "body": "B2"},
    ]})
    out = outreach_node(base_state)
    assert len(out["outreach_emails"]) == 2
    assert out["outreach_emails"][0]["type"] == "cold_application"


def test_outreach_skipped_without_jd(base_state, fake_llm, sample_resume):
    from app.agents.graph import outreach_node

    base_state["resume"] = copy.deepcopy(sample_resume)
    out = outreach_node(base_state)
    assert out is base_state
