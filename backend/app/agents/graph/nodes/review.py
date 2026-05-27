"""Quality reviewer node — scores the resume and emits a critique."""
import json

from app.agents.state import AgentState
from app.agents.llm_factory import get_llm
from app.agents.prompts import REVIEWER_SYSTEM
from app.config import settings
from .._helpers import _trace_event, _call_llm_timed, _extract_json, format_exc


def review_resume_node(state: AgentState) -> AgentState:
    """Score and critique the resume."""
    if not state.get("resume"):
        return state

    trace = state.get("agent_trace", [])
    iteration = state.get("iteration", 0)
    trace.append(_trace_event(
        "Quality Reviewer", "running",
        f"Scoring ATS, quality, impact & completeness (review pass {iteration + 1}/{settings.max_review_iterations})..."
    ))
    llm = get_llm(state["llm_provider"], state["llm_model"])

    human = f"""Review this software engineering resume. Be a demanding senior recruiter.

{json.dumps(state['resume'], indent=2)}"""

    try:
        raw, llm_ev = _call_llm_timed(llm, REVIEWER_SYSTEM, human, "Quality Reviewer")
        review = _extract_json(raw)
        resume = state["resume"]
        if "metadata" not in resume:
            resume["metadata"] = {}
        resume["metadata"].update({
            "ats_score": review.get("ats_score", 0),
            "quality_score": review.get("quality_score", 0),
            "impact_score": review.get("impact_score", 0),
            "completeness_score": review.get("completeness_score", 0),
            "overall_score": review.get("overall_score", 0),
            "review_notes": review.get("reviewer_notes", ""),
            "improvement_suggestions": review.get("improvement_suggestions", []),
            "keywords_included": review.get("keywords_found", []),
            "keywords_to_consider": review.get("missing_keywords", []),
        })
        score = review.get("overall_score", 0)
        issues = len(review.get("critical_issues", []))
        trace[-1] = _trace_event(
            "Quality Reviewer", "complete",
            f"Score: {score:.0f}/100 | {issues} critical issues | "
            f"{'Excellent ✓' if score >= 88 else 'Enhancing...' if score < settings.min_quality_score else 'Good ✓'}",
            llm_ev,
        )
        return {**state, "resume": resume, "review": review,
                "iteration": iteration + 1, "agent_trace": trace, "error": None}
    except Exception as e:
        trace[-1] = _trace_event("Quality Reviewer", "error", format_exc(e))
        return {**state, "iteration": iteration + 1, "agent_trace": trace}
