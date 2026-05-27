"""JD analyzer node — extracts keywords/skills/seniority from a job description."""
from app.agents.state import AgentState
from app.agents.llm_factory import get_llm
from app.agents.prompts import JD_ANALYZER_SYSTEM
from .._helpers import _trace_event, _call_llm_timed, _extract_json, format_exc


def jd_analyze_node(state: AgentState) -> AgentState:
    """Analyze the job description and extract tailoring signals."""
    jd_text = state.get("jd_text", "")
    if not jd_text or not jd_text.strip():
        return state

    trace = state.get("agent_trace", [])
    trace.append(_trace_event("JD Analyzer", "running",
                              "Extracting key requirements, keywords, and skills from job description..."))
    llm = get_llm(state["llm_provider"], state["llm_model"])

    human = f"""Analyze this job description and extract all tailoring signals:

{jd_text}"""

    try:
        raw, llm_ev = _call_llm_timed(llm, JD_ANALYZER_SYSTEM, human, "JD Analyzer")
        jd_analysis = _extract_json(raw)
        trace[-1] = _trace_event(
            "JD Analyzer", "complete",
            f"Identified {len(jd_analysis.get('ats_keywords', []))} ATS keywords | "
            f"Role: {jd_analysis.get('job_title', 'unknown')}",
            llm_ev,
        )
        return {**state, "jd_analysis": jd_analysis, "agent_trace": trace}
    except Exception as e:
        trace[-1] = _trace_event("JD Analyzer", "error", format_exc(e))
        return {**state, "agent_trace": trace}
