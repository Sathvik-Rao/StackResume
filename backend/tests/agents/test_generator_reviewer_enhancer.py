"""Generator / Reviewer / Enhancer agent nodes."""
from __future__ import annotations

import copy

import pytest

pytestmark = pytest.mark.agents


# ── Generator ─────────────────────────────────────────────────────────────────


def test_generator_create_path(base_state, fake_llm):
    from app.agents.graph import generate_resume_node

    out = generate_resume_node(base_state)
    assert out["resume"] is not None
    assert out["resume"]["personal_info"]["full_name"]
    meta = out["resume"]["metadata"]
    assert meta["generated_at"]
    assert meta["llm_provider"] == base_state["llm_provider"]


def test_generator_modify_path_clears_manual_edit_lineage(base_state, fake_llm, sample_resume):
    """The generator uses the manual-edit lineage as INPUT context (so the
    prompt warns the LLM to preserve user wording), but clears it on OUTPUT —
    after a fresh LLM rewrite, the resume is no longer 'the user's manual edit'.
    """
    from app.agents.graph import generate_resume_node

    base_state["request_type"] = "modify"
    base_state["existing_resume"] = copy.deepcopy(sample_resume)
    base_state["existing_resume"]["metadata"]["manually_edited"] = True
    base_state["existing_resume"]["metadata"]["manual_edit_count"] = 3
    base_state["existing_resume"]["metadata"]["last_manually_edited_at"] = "2026-01-01T00:00:00Z"

    out = generate_resume_node(base_state)
    out_meta = out["resume"]["metadata"]
    assert out_meta["manually_edited"] is False
    assert "manual_edit_count" not in out_meta
    assert "last_manually_edited_at" not in out_meta


def test_generator_applies_memory_overrides(base_state, fake_llm):
    """Memory contact details always override whatever the LLM hallucinated."""
    from app.agents.graph import generate_resume_node

    base_state["memory_context"] = {
        "full_name": "Real Name", "email": "real@example.com",
        "linkedin_url": "https://linkedin.com/in/real",
    }
    out = generate_resume_node(base_state)
    pi = out["resume"]["personal_info"]
    assert pi["full_name"] == "Real Name"
    assert pi["email"] == "real@example.com"
    assert pi["linkedin"] == "https://linkedin.com/in/real"


def test_generator_jd_tailored_metadata(base_state, fake_llm):
    from app.agents.graph import generate_resume_node

    base_state["jd_analysis"] = {"job_title": "Senior Backend Engineer"}
    out = generate_resume_node(base_state)
    meta = out["resume"]["metadata"]
    assert meta["jd_tailored"] is True
    assert meta["jd_role"] == "Senior Backend Engineer"


def test_generator_error_records_in_trace(base_state, fake_llm):
    from app.agents.graph import generate_resume_node

    fake_llm.fail_with("generator", RuntimeError("crashed"))
    out = generate_resume_node(base_state)
    assert out["resume"] is None
    assert out["error"]
    assert out["agent_trace"][-1]["status"] == "error"


def test_generator_strips_em_dashes_from_output(base_state, fake_llm):
    from app.agents.graph import generate_resume_node

    fake_llm.set("generator", {
        "metadata": {"version": "1"},
        "personal_info": {"full_name": "Ada — Lovelace"},
        "professional_summary": "Senior — engineer",
    })
    out = generate_resume_node(base_state)
    assert "—" not in out["resume"]["personal_info"]["full_name"]
    assert "—" not in out["resume"]["professional_summary"]


# ── Reviewer ──────────────────────────────────────────────────────────────────


def test_reviewer_writes_scores_into_metadata(base_state, fake_llm, sample_resume):
    from app.agents.graph import review_resume_node

    base_state["resume"] = copy.deepcopy(sample_resume)
    fake_llm.set("reviewer", {
        "ats_score": 91, "quality_score": 85, "impact_score": 80,
        "completeness_score": 90, "overall_score": 87,
        "reviewer_notes": "looks great",
        "improvement_suggestions": ["add cert"],
        "critical_issues": [],
        "weak_bullets": [],
        "keywords_found": ["Python"], "missing_keywords": ["Kotlin"],
    })
    out = review_resume_node(base_state)
    meta = out["resume"]["metadata"]
    assert meta["overall_score"] == 87
    assert meta["ats_score"] == 91
    assert meta["review_notes"] == "looks great"
    assert out["iteration"] == 1


def test_reviewer_no_resume_is_noop(base_state, fake_llm):
    from app.agents.graph import review_resume_node

    out = review_resume_node(base_state)
    assert out is base_state
    assert fake_llm.invocations == []


def test_reviewer_error_increments_iteration(base_state, fake_llm, sample_resume):
    """An LLM failure during review must still bump the iteration counter so
    the loop's safety cap actually kicks in."""
    from app.agents.graph import review_resume_node

    base_state["resume"] = copy.deepcopy(sample_resume)
    fake_llm.fail_with("reviewer", RuntimeError("nope"))
    out = review_resume_node(base_state)
    assert out["iteration"] == 1
    assert out["agent_trace"][-1]["status"] == "error"


# ── Enhancer ──────────────────────────────────────────────────────────────────


def test_enhancer_needs_resume_and_review(base_state, fake_llm):
    from app.agents.graph import enhance_resume_node

    # Missing both — no-op.
    out = enhance_resume_node(base_state)
    assert out is base_state


def test_enhancer_clears_manual_edit_lineage(base_state, fake_llm, sample_resume):
    """Enhancer rewrites the resume — once it runs, the result is no longer
    a manual user edit, so the lineage flags are cleared. (They survive only
    long enough to feed the *input* prompt; see enhance.py.)"""
    from app.agents.graph import enhance_resume_node

    base_state["resume"] = copy.deepcopy(sample_resume)
    base_state["resume"]["metadata"]["manually_edited"] = True
    base_state["resume"]["metadata"]["manual_edit_count"] = 5
    base_state["resume"]["metadata"]["last_manually_edited_at"] = "2026-01-01T00:00:00Z"
    base_state["review"] = {"overall_score": 60, "critical_issues": ["x"]}

    out = enhance_resume_node(base_state)
    new_meta = out["resume"]["metadata"]
    assert new_meta["manually_edited"] is False
    assert "manual_edit_count" not in new_meta
    assert "last_manually_edited_at" not in new_meta


def test_enhancer_reapplies_memory_overrides(base_state, fake_llm, sample_resume):
    from app.agents.graph import enhance_resume_node

    base_state["resume"] = copy.deepcopy(sample_resume)
    base_state["review"] = {"overall_score": 70, "critical_issues": []}
    base_state["memory_context"] = {"full_name": "Override Name"}

    out = enhance_resume_node(base_state)
    assert out["resume"]["personal_info"]["full_name"] == "Override Name"
