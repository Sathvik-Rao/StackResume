from typing import TypedDict, Optional


class AgentState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────────────
    session_id: str
    current_input: str
    conversation_history: list[dict]   # [{role, content}]
    existing_resume: Optional[dict]    # latest resume from prior turns
    llm_provider: str
    llm_model: str

    # ── Memory context (persistent user profile) ───────────────────────────────
    memory_context: Optional[dict]     # loaded from UserMemory table

    # ── Section preferences (enabled/disabled sections + fields) ───────────────
    # Shape: {"sections": {key: bool}, "fields": {"section.field": bool}}
    # None or empty = everything enabled (default).
    section_preferences: Optional[dict]

    # ── Intent ────────────────────────────────────────────────────────────────
    is_off_topic: bool                 # True → short-circuit pipeline
    off_topic_response: Optional[str]  # polite reply when off-topic

    # ── Job Description Tailoring ──────────────────────────────────────────────
    jd_text: Optional[str]             # raw JD pasted by user
    jd_analysis: Optional[dict]        # parsed JD requirements/keywords
    jd_intensity: Optional[int]        # 0–100; how aggressively to align the resume to the JD

    # ── Parser output ──────────────────────────────────────────────────────────
    parsed_data: Optional[dict]
    request_type: str                  # "create" | "modify" | "tailor_jd"

    # ── Generator output ───────────────────────────────────────────────────────
    resume: Optional[dict]

    # ── Reviewer output ────────────────────────────────────────────────────────
    review: Optional[dict]

    # ── JD-only artefacts ──────────────────────────────────────────────────────
    cover_letter: Optional[str]
    outreach_emails: Optional[list]

    # ── Pipeline control ───────────────────────────────────────────────────────
    iteration: int
    agent_trace: list[dict]            # [{agent, status, notes, llm_event, timestamp}]
    error: Optional[str]
