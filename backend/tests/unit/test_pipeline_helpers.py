"""Pure-function helpers inside app/api/_pipeline.py — score coercion and the
summary / no-resume-error message builders. These run without FastAPI or the DB.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ── _safe_score ───────────────────────────────────────────────────────────────

class TestSafeScore:
    def test_numeric_passthrough(self):
        from app.api._pipeline import _safe_score
        assert _safe_score(87) == 87.0
        assert _safe_score(82.5) == 82.5
        assert _safe_score("91") == 91.0

    def test_non_numeric_returns_zero(self):
        """Regression: a buggy LLM that emits `overall_score: "high"` or `null`
        used to crash `f"{score:.0f}"` and take the whole pipeline summary
        down. Coercion now floors to 0.0 instead."""
        from app.api._pipeline import _safe_score
        assert _safe_score(None) == 0.0
        assert _safe_score("high") == 0.0
        assert _safe_score({}) == 0.0
        assert _safe_score([]) == 0.0


# ── _build_summary ────────────────────────────────────────────────────────────

class TestBuildSummary:
    def test_returns_placeholder_when_no_resume(self):
        from app.api._pipeline import _build_summary
        out = _build_summary(None)
        assert "issue" in out.lower()

    def test_happy_path_includes_score_and_name(self):
        from app.api._pipeline import _build_summary
        resume = {
            "metadata": {"overall_score": 87, "iteration_count": 2},
            "personal_info": {"full_name": "Ada", "professional_title": "Eng"},
        }
        out = _build_summary(resume)
        assert "Ada" in out and "87/100" in out
        assert "Refinement passes: 2" in out

    def test_non_numeric_score_does_not_crash(self):
        """Regression: bad LLM payload must not bring down the whole reply."""
        from app.api._pipeline import _build_summary
        resume = {
            "metadata": {"overall_score": "high", "jd_match_score": "lots"},
            "personal_info": {"full_name": "Ada"},
        }
        out = _build_summary(resume)
        # Should fall back to 0/100 rather than raising.
        assert "0/100" in out
        # JD match should also fall back cleanly when non-numeric.
        assert "lots" not in out

    def test_cover_letter_and_emails_called_out(self):
        from app.api._pipeline import _build_summary
        resume = {"metadata": {"overall_score": 90}, "personal_info": {"full_name": "Ada"}}
        out = _build_summary(resume, has_cover=True, n_emails=3)
        assert "cover letter" in out
        assert "3 outreach email templates" in out


# ── _build_no_resume_error ────────────────────────────────────────────────────

class TestBuildNoResumeError:
    def test_attributes_failure_to_last_failing_agent(self):
        from app.api._pipeline import _build_no_resume_error
        state = {
            "agent_trace": [
                {"agent": "Resume Generator", "status": "error",
                 "notes": "anthropic.BadRequestError: invalid_api_key"},
            ],
            "error": "anthropic.BadRequestError: invalid_api_key",
        }
        out = _build_no_resume_error(state, provider="anthropic", model="claude-sonnet-4-6")
        assert "Resume Generator" in out
        assert "invalid_api_key" in out
        assert "anthropic" in out
        # The collapsible @@TRACEBACK@@ block must be emitted when there's a trace.
        assert "@@TRACEBACK@@" in out
