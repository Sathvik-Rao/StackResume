"""Cover letter writer node — only runs when a JD analysis is present."""
import json
import re

from app.agents.state import AgentState
from app.agents.llm_factory import get_llm
from app.agents.prompts import COVER_LETTER_SYSTEM
from .._helpers import _trace_event, _call_llm_timed, _extract_json, _strip_dashes, format_exc


# Matches the leading salutation line so we can strip it before rendering.
# Single-word greetings ("Greetings," / "Greetings!") need a trailing
# punctuation/space anchor to avoid false-positives like "Greetingsville".
_SALUTATION_RE = re.compile(
    r"^(dear\s|hi\s|hello\s|hey\s|to whom|greetings\b)",
    re.IGNORECASE,
)


def cover_letter_node(state: AgentState) -> AgentState:
    """Generate a tailored cover letter when a JD is present."""
    if not state.get("resume") or not state.get("jd_analysis"):
        return state

    trace = state.get("agent_trace", [])
    trace.append(_trace_event(
        "Cover Letter Writer", "running",
        "Drafting a tailored cover letter from your resume and the job description…",
    ))
    llm = get_llm(state["llm_provider"], state["llm_model"])

    human = f"""Resume JSON:
{json.dumps(state['resume'], indent=2)}

Job Description Analysis:
{json.dumps(state['jd_analysis'], indent=2)}

Raw Job Description (for tone and detail):
\"\"\"{state.get('jd_text', '')[:4000]}\"\"\"

Write the cover letter following all rules. Return ONLY valid JSON."""

    try:
        raw, llm_ev = _call_llm_timed(llm, COVER_LETTER_SYSTEM, human, "Cover Letter Writer")
        data = _extract_json(raw)
        letter = (data.get("cover_letter") or "").strip()
        # Normalise once at the source so the in-app preview and the PDF are identical.
        # Strip any salutation line (the UI/PDF render their own letterhead) and any
        # trailing signature so we never show the candidate's name twice.
        lines = [l.rstrip() for l in letter.split("\n")]
        while lines and _SALUTATION_RE.match(lines[0]):
            lines.pop(0)
            while lines and not lines[0].strip():
                lines.pop(0)
        # Drop a trailing signature block (sign-off line + name line)
        while lines and not lines[-1].strip():
            lines.pop()
        if lines and lines[-1].strip().rstrip(",.").lower() in (
            "sincerely", "best regards", "kind regards", "regards", "warm regards",
            "thank you", "yours truly", "respectfully",
        ):
            lines.pop()
            while lines and not lines[-1].strip():
                lines.pop()
        # Drop a final line that's just the candidate's name
        full_name = ((state.get("resume") or {}).get("personal_info", {}) or {}).get("full_name", "")
        if lines and full_name and lines[-1].strip().lower() == full_name.strip().lower():
            lines.pop()
        cleaned = "\n".join(lines).strip()
        wc = len(cleaned.split())
        trace[-1] = _trace_event(
            "Cover Letter Writer", "complete",
            f"Drafted {wc}-word cover letter for {data.get('hiring_manager', 'hiring team')}",
            llm_ev,
        )
        return {**state, "cover_letter": _strip_dashes(cleaned), "agent_trace": trace}
    except Exception as e:
        trace[-1] = _trace_event("Cover Letter Writer", "error", format_exc(e))
        return {**state, "agent_trace": trace}
