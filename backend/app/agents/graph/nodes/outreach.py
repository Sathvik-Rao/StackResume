"""Outreach writer node — drafts cold-application / referral / follow-up emails."""
import json

from app.agents.state import AgentState
from app.agents.llm_factory import get_llm
from app.agents.prompts import OUTREACH_SYSTEM
from .._helpers import _trace_event, _call_llm_timed, _extract_json, _strip_dashes, format_exc


def outreach_node(state: AgentState) -> AgentState:
    """Generate a small library of outreach emails when a JD is present."""
    if not state.get("resume") or not state.get("jd_analysis"):
        return state

    trace = state.get("agent_trace", [])
    trace.append(_trace_event(
        "Outreach Writer", "running",
        "Composing cold-application, LinkedIn, referral and follow-up email templates…",
    ))
    llm = get_llm(state["llm_provider"], state["llm_model"])

    human = f"""Resume JSON:
{json.dumps(state['resume'], indent=2)}

Job Description Analysis:
{json.dumps(state['jd_analysis'], indent=2)}

Write all four outreach templates following every rule. Return ONLY valid JSON."""

    try:
        raw, llm_ev = _call_llm_timed(llm, OUTREACH_SYSTEM, human, "Outreach Writer")
        data = _extract_json(raw)
        emails = data.get("emails") or []
        trace[-1] = _trace_event(
            "Outreach Writer", "complete",
            f"Drafted {len(emails)} outreach templates",
            llm_ev,
        )
        return {**state, "outreach_emails": _strip_dashes(emails), "agent_trace": trace}
    except Exception as e:
        trace[-1] = _trace_event("Outreach Writer", "error", format_exc(e))
        return {**state, "agent_trace": trace}
