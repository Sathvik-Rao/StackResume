"""Resume enhancer node — fixes critical issues from the reviewer's feedback."""
import json

from app.agents.state import AgentState
from app.agents.llm_factory import get_llm
from app.agents.prompts import ENHANCER_SYSTEM, JD_TAILOR_ENHANCER_SYSTEM
from .._helpers import (
    _trace_event, _call_llm_timed, _extract_json, _strip_dashes,
    _jd_intensity_directive, format_exc,
)
from app.section_preferences import build_prompt_directive as _section_prefs_directive


def enhance_resume_node(state: AgentState) -> AgentState:
    """Improve resume based on review feedback."""
    if not state.get("resume") or not state.get("review"):
        return state

    trace = state.get("agent_trace", [])
    score = state["review"].get("overall_score", 0)
    issues = state["review"].get("critical_issues", [])
    trace.append(_trace_event(
        "Resume Enhancer", "running",
        f"Fixing {len(issues)} critical issues, rewriting weak bullets, injecting keywords... (score: {score:.0f}/100)"
    ))
    llm = get_llm(state["llm_provider"], state["llm_model"])

    has_jd = bool(state.get("jd_analysis"))
    system = JD_TAILOR_ENHANCER_SYSTEM if has_jd else ENHANCER_SYSTEM
    jd_intensity = state.get("jd_intensity") if state.get("jd_intensity") is not None else 100
    intensity_block = f"\n\n{_jd_intensity_directive(jd_intensity)}" if has_jd else ""

    section_directive = _section_prefs_directive(state.get("section_preferences"))
    section_block = f"\n\n{section_directive}" if section_directive else ""

    human = f"""Current Resume:
{json.dumps(state['resume'], indent=2)}

Reviewer Critique:
{json.dumps(state['review'], indent=2)}
{f"Job Description Analysis:{chr(10)}{json.dumps(state['jd_analysis'], indent=2)}" if has_jd else ""}
{intensity_block}{section_block}
Fix ALL critical issues: {issues}
Rewrite weak bullets: {state['review'].get('weak_bullets', [])}
Inject missing keywords: {state['review'].get('missing_keywords', [])}"""

    try:
        raw, llm_ev = _call_llm_timed(llm, system, human, "Resume Enhancer")
        enhanced = _extract_json(raw)
        if "metadata" not in enhanced:
            enhanced["metadata"] = {}
        # Preserve critical metadata
        orig_meta = state["resume"].get("metadata") or {}
        enhanced["metadata"].update({
            "generated_at": orig_meta.get("generated_at"),
            "llm_provider": state["llm_provider"],
            "llm_model": state["llm_model"],
            "iteration_count": state.get("iteration", 1),
        })
        # Clear manual-edit flag in the output — it was only needed as LLM input context.
        enhanced["metadata"]["manually_edited"] = False
        enhanced["metadata"].pop("manual_edit_count", None)
        enhanced["metadata"].pop("last_manually_edited_at", None)
        # Re-apply memory overrides
        mem = state.get("memory_context") or {}
        pi = enhanced.get("personal_info", {})
        for field, mem_key in [
            ("full_name", "full_name"), ("email", "email"), ("phone", "phone"),
            ("location", "location"), ("linkedin", "linkedin_url"),
            ("github", "github_url"), ("website", "website"),
            ("portfolio", "portfolio_url"),
        ]:
            if mem.get(mem_key):
                pi[field] = mem[mem_key]
        enhanced["personal_info"] = pi

        trace[-1] = _trace_event("Resume Enhancer", "complete",
                                 "Resume strengthened, sending back to reviewer.", llm_ev)
        return {**state, "resume": _strip_dashes(enhanced), "agent_trace": trace, "error": None}
    except Exception as e:
        trace[-1] = _trace_event("Resume Enhancer", "error", format_exc(e))
        return {**state, "agent_trace": trace}
