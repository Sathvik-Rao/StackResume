"""Resume generator node — first-draft creation or modification of the resume JSON."""
import json
from datetime import datetime, timezone

from app.agents.state import AgentState
from app.agents.llm_factory import get_llm
from app.agents.prompts import GENERATOR_SYSTEM
from .._helpers import (
    _trace_event, _call_llm_timed, _extract_json, _strip_dashes,
    _memory_context_str, _jd_intensity_directive, format_exc,
)
from app.section_preferences import build_prompt_directive as _section_prefs_directive


def generate_resume_node(state: AgentState) -> AgentState:
    """Generate or update the resume."""
    trace = state.get("agent_trace", [])
    is_modify = state.get("request_type") in ("modify", "tailor_jd")
    has_jd = bool(state.get("jd_analysis"))

    notes = "Crafting resume with STAR-format bullets, ATS keywords, and quantified metrics..."
    if is_modify and state.get("existing_resume"):
        notes = "Updating resume based on your instructions..."
    if has_jd:
        notes = "Building resume aligned to the job description requirements..."

    trace.append(_trace_event("Resume Generator", "running", notes))
    llm = get_llm(state["llm_provider"], state["llm_model"])
    now_iso = datetime.now(timezone.utc).isoformat()
    parsed = state.get("parsed_data", {})
    memory_str = _memory_context_str(state.get("memory_context"))
    jd_section = ""
    if state.get("jd_analysis"):
        jd_section = f"\n\nJob Description Analysis (tailor the resume to this):\n{json.dumps(state['jd_analysis'], indent=2)}"

    profile_modify = f"Stored profile to keep accurate:\n{memory_str}\n" if memory_str else ""
    profile_create = f"Stored profile (use this data for accuracy, fill gaps with realistic hallucination):\n{memory_str}\n" if memory_str else ""
    jd_intensity = state.get("jd_intensity") if state.get("jd_intensity") is not None else 100
    if has_jd:
        tailor_directive = _jd_intensity_directive(jd_intensity)
        keyword_directive = (
            "Mirror all JD keywords and requirements" if jd_intensity >= 65
            else "Surface only the most relevant JD keywords; do not stuff"
        )
        task_label = "Tailor" if jd_intensity >= 35 else "Lightly adjust"
    else:
        tailor_directive = "Apply the modifications. Keep everything else."
        keyword_directive = "Make it genuinely impressive"
        task_label = "Modify"
    user_input = state['current_input']

    section_directive = _section_prefs_directive(state.get("section_preferences"))
    section_block = f"\n\n{section_directive}\n" if section_directive else ""

    if is_modify and state.get("existing_resume"):
        existing_meta = (state["existing_resume"].get("metadata") or {})
        manual_note = ""
        if existing_meta.get("manually_edited"):
            edit_count = existing_meta.get("manual_edit_count", 1)
            manual_note = (
                f"\nIMPORTANT: The existing resume was manually edited by the user "
                f"{edit_count} time(s). Treat their edits as deliberate improvements — "
                f"preserve their wording, phrasing, and any custom bullets unless the "
                f"user explicitly asks you to change them. Apply only the requested "
                f"modification on top of their edits.\n"
            )
        human = f"""TASK: {task_label} the existing resume.

User instruction: \"\"\"{user_input}\"\"\"
{jd_section}

Existing Resume:
{json.dumps(state['existing_resume'], indent=2)}
{manual_note}
{profile_modify}
{tailor_directive}{section_block}
Update metadata.generated_at to: {now_iso}
Return the COMPLETE updated resume JSON."""
    else:
        human = f"""TASK: Create a comprehensive software developer resume.

User input:
{json.dumps(parsed, indent=2)}
{jd_section}

{profile_create}
Current datetime: {now_iso}
Provider: {state['llm_provider']} / Model: {state['llm_model']}

Rules:
- Fill missing info with realistic, coherent career history matching role/seniority
- Every experience bullet must use STAR format with specific metrics
- ATS-optimize throughout
- {keyword_directive}
- metadata.version = "1"
{section_block}
Return the COMPLETE resume JSON."""

    try:
        raw, llm_ev = _call_llm_timed(llm, GENERATOR_SYSTEM, human, "Resume Generator")
        resume = _extract_json(raw)
        if "metadata" not in resume:
            resume["metadata"] = {}
        resume["metadata"].update({
            "generated_at": now_iso,
            "llm_provider": state["llm_provider"],
            "llm_model": state["llm_model"],
            "version": resume["metadata"].get("version", "1"),
        })
        if has_jd and state.get("jd_analysis"):
            resume["metadata"]["jd_tailored"] = True
            resume["metadata"]["jd_role"] = state["jd_analysis"].get("job_title")
        # Clear manual-edit flag in the output — it was only needed as LLM input context.
        resume["metadata"]["manually_edited"] = False
        resume["metadata"].pop("manual_edit_count", None)
        resume["metadata"].pop("last_manually_edited_at", None)

        # Apply memory overrides (name, contact always accurate)
        mem = state.get("memory_context") or {}
        pi = resume.get("personal_info", {})
        for field, mem_key in [
            ("full_name", "full_name"), ("email", "email"), ("phone", "phone"),
            ("location", "location"), ("linkedin", "linkedin_url"),
            ("github", "github_url"), ("website", "website"),
            ("portfolio", "portfolio_url"),
        ]:
            if mem.get(mem_key):
                pi[field] = mem[mem_key]
        resume["personal_info"] = pi

        exp_count = len(resume.get("experience", []))
        trace[-1] = _trace_event(
            "Resume Generator", "complete",
            f"Generated {exp_count} experience entries | {len(resume.get('technical_skills', {}).get('programming_languages', []))} languages",
            llm_ev,
        )
        return {**state, "resume": _strip_dashes(resume), "agent_trace": trace, "error": None}
    except Exception as e:
        trace[-1] = _trace_event("Resume Generator", "error", format_exc(e))
        return {**state, "error": format_exc(e), "agent_trace": trace}
