"""Intent guard — fast regex pre-filter + LLM fallback for ambiguous messages.

Hands off to ``intent_check_node`` (the LangGraph node) and ``off_topic_node``
(the terminal node for off-topic replies).
"""
import re

from app.agents.state import AgentState
from app.agents.llm_factory import get_llm
from app.agents.prompts import INTENT_SYSTEM
from ._helpers import _trace_event, _call_llm_timed, _extract_json


# ── Off-topic keywords (fast pre-filter before LLM) ───────────────────────────
_RESUME_KEYWORDS = re.compile(
    r"\b(resume|cv|curriculum|job|career|experience|skill|education|"
    r"developer|engineer|programmer|hire|ats|linkedin|github|portfolio|"
    r"role|seniority|internship|work|company|position|certif|project|"
    r"tailor|senior|junior|architect|devops|frontend|backend|fullstack|"
    r"python|java|react|node|spring|aws|docker|kubernetes|ml|ai|"
    r"open.?source|publication|salary|interview|recruit|apply|applica)\b",
    re.IGNORECASE,
)

# Pure social/exit chatter that should ONLY ever be off-topic.
_SOCIAL_ONLY = re.compile(
    r"^(hi+|hey+|hello+|bye+|goodbye+|see ya|cya|"
    r"what'?s up|how are you|how r u|good morning|good night|"
    r"who are you|what can you do|what do you do|are you a bot|"
    r"weather|joke|tell me a joke|sing|dance)\W*$",
    re.IGNORECASE,
)

# Refinement / conversational verbs that imply "do this to the resume".
# Treated as resume-related ONLY when there is an existing resume in the
# conversation (otherwise they're ambiguous and we let the LLM decide).
_REFINEMENT_VERBS = re.compile(
    r"^(enhance|improve|fix|rewrite|rework|update|change|edit|tweak|polish|"
    r"refine|make|add|remove|delete|drop|include|exclude|expand|shorten|"
    r"trim|cut|condense|reorder|reorganize|emphasize|tone down|strengthen|"
    r"weaken|sharpen|simplify|elaborate|clarify|reformat|restructure|"
    r"redo|redo it|do it again|try again|regenerate|another|"
    r"better|stronger|shorter|longer|more|less|too)"
    r"\b",
    re.IGNORECASE,
)


def _quick_intent(text: str, has_existing_resume: bool = False) -> str | None:
    """Return 'off_topic' / 'resume_related' without an LLM call, or None if ambiguous.

    `has_existing_resume` flips us into "refinement mode" — once the user has a
    resume in the conversation, almost any short instruction is a refinement
    rather than off-topic. This prevents prompts like "enhance it", "make it
    better", or "shorter" from being incorrectly blocked.
    """
    stripped = text.strip()
    if not stripped:
        return "off_topic"

    # Pure social chatter is always off-topic
    if _SOCIAL_ONLY.match(stripped):
        return "off_topic"

    # Anything with a resume keyword is on-topic
    if _RESUME_KEYWORDS.search(stripped):
        return "resume_related"

    # In refinement mode, short verb-led messages are clearly refinements
    if has_existing_resume and _REFINEMENT_VERBS.match(stripped):
        return "resume_related"

    # Cold-start with a very short non-resume message — block it
    if not has_existing_resume and len(stripped.split()) < 4:
        return "off_topic"

    # Otherwise, ambiguous — let the LLM intent classifier decide
    return None


def intent_check_node(state: AgentState) -> AgentState:
    """Fast intent guard. Short-circuits non-resume messages."""
    trace = state.get("agent_trace", [])
    text = state["current_input"]
    has_existing = bool(state.get("existing_resume"))

    # Fast pre-filter (no LLM)
    quick = _quick_intent(text, has_existing_resume=has_existing)
    if quick == "resume_related":
        trace.append(_trace_event("Intent Guard", "complete",
                                  "✓ Resume-related request detected (fast path)"))
        return {**state, "is_off_topic": False, "off_topic_response": None, "agent_trace": trace}

    if quick == "off_topic":
        reply = ("👋 Hi! I'm StackResume, your AI resume assistant. I can help you create, "
                 "improve, or tailor your software developer resume. Just tell me your "
                 "role and experience to get started!")
        trace.append(_trace_event("Intent Guard", "complete", "Off-topic (fast path) — politely redirected"))
        return {**state, "is_off_topic": True, "off_topic_response": reply, "agent_trace": trace}

    # Ambiguous — ask LLM
    trace.append(_trace_event("Intent Guard", "running", "Classifying intent with LLM..."))
    llm = get_llm(state["llm_provider"], state["llm_model"])
    try:
        raw, llm_ev = _call_llm_timed(
            llm, INTENT_SYSTEM,
            f"Classify this message:\n\"\"\"{text}\"\"\"",
            "Intent Guard"
        )
        data = _extract_json(raw)
        if data.get("intent") == "off_topic":
            reply = data.get(
                "suggested_reply",
                "I'm here to help with your resume! Tell me your role and experience to get started."
            )
            trace[-1] = _trace_event("Intent Guard", "complete",
                                     "Off-topic detected — politely redirected", llm_ev)
            return {**state, "is_off_topic": True, "off_topic_response": reply, "agent_trace": trace}
        else:
            trace[-1] = _trace_event("Intent Guard", "complete",
                                     "✓ Resume-related intent confirmed", llm_ev)
            return {**state, "is_off_topic": False, "off_topic_response": None, "agent_trace": trace}
    except Exception:
        # Default to resume-related on error
        trace[-1] = _trace_event("Intent Guard", "complete", "✓ Proceeding (intent check error)")
        return {**state, "is_off_topic": False, "off_topic_response": None, "agent_trace": trace}


def off_topic_node(state: AgentState) -> AgentState:
    """Return the polite redirect — no further processing."""
    return state
