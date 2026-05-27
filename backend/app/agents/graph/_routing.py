"""LangGraph conditional-edge routers.

Each function takes the current AgentState and returns the next-edge key as a
string. The edges themselves are wired up in ``_builder.py``.
"""
from app.agents.state import AgentState
from app.config import settings


def route_after_intent(state: AgentState) -> str:
    return "off_topic" if state.get("is_off_topic") else "parse"


def route_after_parse(state: AgentState) -> str:
    jd = state.get("jd_text", "")
    return "jd_analyze" if (jd and jd.strip()) else "generate"


def should_enhance(state: AgentState) -> str:
    if state.get("error") and not state.get("resume"):
        return "finalize"
    if state.get("iteration", 0) >= settings.max_review_iterations:
        return "finalize"
    score = (state.get("review") or {}).get("overall_score", 100)
    return "finalize" if score >= settings.min_quality_score else "enhance"


def route_after_finalize(state: AgentState) -> str:
    """Only run cover-letter / outreach when a JD was provided AND we have a resume."""
    if state.get("resume") and state.get("jd_analysis"):
        return "cover_letter"
    return "end"
