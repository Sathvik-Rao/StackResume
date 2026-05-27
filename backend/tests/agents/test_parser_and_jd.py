"""Input Parser + JD Analyzer nodes."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.agents


def test_parser_extracts_request_type(base_state, fake_llm):
    from app.agents.graph import parse_input_node

    fake_llm.set("parser", {"request_type": "modify", "target_role": "Staff Engineer"})
    out = parse_input_node(base_state)
    assert out["request_type"] == "modify"
    assert out["parsed_data"]["target_role"] == "Staff Engineer"


def test_parser_promotes_to_tailor_jd_when_jd_present(base_state, fake_llm):
    """If a JD is attached the parser's classification is overridden."""
    from app.agents.graph import parse_input_node

    fake_llm.set("parser", {"request_type": "create", "target_role": "Backend"})
    base_state["jd_text"] = "Senior Backend role at Acme."
    out = parse_input_node(base_state)
    assert out["request_type"] == "tailor_jd"


def test_parser_fallback_on_llm_error(base_state, fake_llm):
    """LLM error → graceful fallback that still keeps the pipeline moving."""
    from app.agents.graph import parse_input_node

    fake_llm.fail_with("parser", RuntimeError("model down"))
    base_state["current_input"] = "I am a senior backend dev"
    out = parse_input_node(base_state)
    assert out["parsed_data"]
    assert out["request_type"] in ("create", "modify", "tailor_jd")
    assert out["error"] is None  # don't poison downstream state


def test_jd_analyzer_no_jd_is_noop(base_state, fake_llm):
    from app.agents.graph import jd_analyze_node

    out = jd_analyze_node(base_state)
    assert out is base_state  # exact same dict returned
    assert fake_llm.invocations == []


def test_jd_analyzer_with_jd_populates_analysis(base_state, fake_llm):
    from app.agents.graph import jd_analyze_node

    base_state["jd_text"] = "Senior backend role. Python + FastAPI + AWS required."
    fake_llm.set("jd_analyzer", {
        "job_title": "Senior Backend Engineer",
        "ats_keywords": ["Python", "FastAPI", "AWS"],
        "required_skills": ["Python"],
    })
    out = jd_analyze_node(base_state)
    assert out["jd_analysis"]["job_title"] == "Senior Backend Engineer"
    assert "AWS" in out["jd_analysis"]["ats_keywords"]


def test_jd_analyzer_records_error_in_trace(base_state, fake_llm):
    from app.agents.graph import jd_analyze_node

    base_state["jd_text"] = "x"
    fake_llm.fail_with("jd_analyzer", RuntimeError("rate-limited"))
    out = jd_analyze_node(base_state)
    assert out["jd_analysis"] is None
    last = out["agent_trace"][-1]
    assert last["status"] == "error"
    assert "RuntimeError" in last["notes"]
