"""End-to-end LangGraph pipeline shape — drives the compiled graph with the
FakeLLM and checks the final state matches what the API/background task
expects.

Each test runs the graph synchronously (``.stream``) and walks every node so a
regression in node wiring shows up here even when the API contract still
holds.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.agents


def _run(state: dict) -> dict:
    from app.agents.graph import RESUME_GRAPH

    last = state
    for chunk in RESUME_GRAPH.stream(state):
        last = next(iter(chunk.values()))
    return last


def _initial(**overrides) -> dict:
    base = {
        "session_id": "s",
        "current_input": "Senior backend engineer, 8 years.",
        "conversation_history": [],
        "existing_resume": None,
        "llm_provider": "fake",
        "llm_model": "fake-test",
        "memory_context": None,
        "is_off_topic": False,
        "off_topic_response": None,
        "jd_text": "",
        "jd_analysis": None,
        "jd_intensity": 100,
        "parsed_data": None,
        "request_type": "create",
        "resume": None,
        "review": None,
        "cover_letter": None,
        "outreach_emails": None,
        "iteration": 0,
        "agent_trace": [],
        "error": None,
    }
    base.update(overrides)
    return base


def test_full_pipeline_no_jd(fake_llm):
    final = _run(_initial())
    assert final["resume"] is not None
    assert final["resume"]["personal_info"]["full_name"]
    # Without a JD, neither cover letter nor outreach should have run.
    assert final["cover_letter"] is None
    assert final["outreach_emails"] is None
    # Finalize step recorded.
    agents = [t["agent"] for t in final["agent_trace"]]
    assert "Finalizer" in agents
    assert "Resume Generator" in agents


def test_full_pipeline_with_jd_runs_cover_letter_and_outreach(fake_llm):
    final = _run(_initial(jd_text="Senior backend role at Acme."))
    assert final["resume"] is not None
    assert final["cover_letter"]
    assert final["outreach_emails"]
    agents = [t["agent"] for t in final["agent_trace"]]
    assert "Cover Letter Writer" in agents
    assert "Outreach Writer" in agents


def test_off_topic_short_circuits_whole_pipeline(fake_llm):
    final = _run(_initial(current_input="hi"))
    # Pipeline halted at intent guard — no generator ran.
    assert final["resume"] is None
    assert final["is_off_topic"] is True
    agents = [t["agent"] for t in final["agent_trace"]]
    assert "Resume Generator" not in agents


def test_review_enhance_loop_converges(fake_llm, monkeypatch):
    """Force a low score so the pipeline loops Reviewer → Enhancer → Reviewer
    until the iteration cap, then finalises gracefully."""
    from app.agents import graph

    monkeypatch.setattr(graph.settings, "max_review_iterations", 2, raising=False)
    monkeypatch.setattr(graph.settings, "min_quality_score", 99, raising=False)
    fake_llm.set("reviewer", {
        "ats_score": 50, "quality_score": 50, "impact_score": 50,
        "completeness_score": 50, "overall_score": 50,
        "reviewer_notes": "weak", "improvement_suggestions": [],
        "critical_issues": ["x"], "weak_bullets": [], "keywords_found": [],
        "missing_keywords": [],
    })
    final = _run(_initial())

    # The reviewer must have run more than once and the loop terminated.
    review_runs = sum(1 for t in final["agent_trace"] if t["agent"] == "Quality Reviewer")
    assert review_runs >= 2
    assert final["resume"] is not None
    assert final["agent_trace"][-1]["agent"] == "Finalizer"


def test_generator_failure_finalises_cleanly(fake_llm):
    """If the generator dies mid-pipeline the Finalizer must still terminate
    instead of looping forever."""
    fake_llm.fail_with("generator", RuntimeError("provider exploded"))
    final = _run(_initial())
    assert final["resume"] is None
    # Finalize logs an error.
    finalizer = [t for t in final["agent_trace"] if t["agent"] == "Finalizer"]
    assert finalizer and finalizer[-1]["status"] == "error"
