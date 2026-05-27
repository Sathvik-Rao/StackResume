"""Finalizer node — stamps final metadata and closes the resume pipeline."""
from app.agents.state import AgentState
from app.section_preferences import apply_to_resume as _apply_section_prefs
from .._helpers import _trace_event


def finalize_node(state: AgentState) -> AgentState:
    """Stamp final metadata and close pipeline."""
    trace = state.get("agent_trace", [])
    resume = state.get("resume")
    err = state.get("error")
    # Even if the LLM ignored the section-preferences directive, strip disabled
    # keys before anything downstream (UI, PDF, JSON viewer) sees the resume.
    if resume is not None:
        prefs = state.get("section_preferences")
        if prefs:
            resume = _apply_section_prefs(resume, prefs)
    if not resume:
        # An upstream agent failed and never produced a resume — don't claim
        # success. Mark this step as errored so the trace + UI reflect reality.
        failing = next((e.get("agent") for e in reversed(trace) if e.get("status") == "error"), None)
        why = err or (f"upstream failure in {failing}" if failing else "no resume was produced")
        trace.append(_trace_event(
            "Finalizer", "error",
            f"❌ Pipeline halted — {why}",
        ))
        return {**state, "resume": None, "agent_trace": trace}

    if "metadata" in resume:
        resume["metadata"]["iteration_count"] = state.get("iteration", 1)
    score = (resume.get("metadata") or {}).get("overall_score", 0)
    trace.append(_trace_event(
        "Finalizer", "complete",
        f"✅ Resume ready! Final score: {score:.0f}/100 after {state.get('iteration', 1)} review pass(es)"
    ))
    return {**state, "resume": resume, "agent_trace": trace}
