"""Input parser node — extracts structured resume data from the user message."""
from app.agents.state import AgentState
from app.agents.llm_factory import get_llm
from app.agents.prompts import PARSER_SYSTEM
from .._helpers import (
    _trace_event, _call_llm_timed, _extract_json,
    _build_history_text, _memory_context_str,
)


def parse_input_node(state: AgentState) -> AgentState:
    """Extract structured data from user input."""
    trace = state.get("agent_trace", [])
    trace.append(_trace_event("Input Parser", "running", "Extracting resume data from your message..."))
    llm = get_llm(state["llm_provider"], state["llm_model"])

    history_text = _build_history_text(state.get("conversation_history", []))
    memory_str = _memory_context_str(state.get("memory_context"))
    existing_info = ""
    if state.get("existing_resume"):
        pi = state["existing_resume"].get("personal_info", {})
        existing_info = f"\nExisting resume: {pi.get('full_name', '?')} — {pi.get('professional_title', '')}"

    profile_block = f"Stored user profile:\n{memory_str}\n" if memory_str else ""
    human = f"""Conversation history:
{history_text}

User message:
\"\"\"{state['current_input']}\"\"\"
{existing_info}

{profile_block}
Extract all resume data and classify the request."""

    try:
        raw, llm_ev = _call_llm_timed(llm, PARSER_SYSTEM, human, "Input Parser")
        parsed = _extract_json(raw)
        request_type = parsed.get("request_type", "create")

        # Auto-detect JD
        if state.get("jd_text") and request_type not in ("tailor_jd",):
            request_type = "tailor_jd"
            parsed["request_type"] = "tailor_jd"
            parsed["jd_detected"] = True

        trace[-1] = _trace_event("Input Parser", "complete",
                                 f"Detected: {request_type} | Role: {parsed.get('target_role', 'auto')}",
                                 llm_ev)
        return {**state, "parsed_data": parsed, "request_type": request_type,
                "agent_trace": trace, "error": None}
    except Exception:
        fallback = {
            "request_type": "tailor_jd" if state.get("jd_text") else (
                "modify" if state.get("existing_resume") else "create"),
            "target_role": state["current_input"][:120],
            "other_context": state["current_input"],
        }
        trace[-1] = _trace_event("Input Parser", "complete", "Parsed from raw input (fallback)")
        return {**state, "parsed_data": fallback, "request_type": fallback["request_type"],
                "agent_trace": trace, "error": None}
