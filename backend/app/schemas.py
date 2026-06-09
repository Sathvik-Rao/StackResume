from pydantic import BaseModel, field_serializer
from typing import Optional
from datetime import datetime, timezone


def _dt_ms(v: datetime | None) -> int | None:
    """Serialize a datetime (possibly tz-naive from SQLite) as epoch milliseconds."""
    if v is None:
        return None
    if v.tzinfo is None:
        v = v.replace(tzinfo=timezone.utc)
    return int(v.timestamp() * 1000)


# ── Session schemas ───────────────────────────────────────────────────────────
class CreateSessionRequest(BaseModel):
    title: Optional[str] = "New Resume"
    # When None, the API falls back to the currently configured server default
    # (settings.llm_provider / settings.llm_model). Hard-coding "openai" / "gpt-4o"
    # here would silently override a user-configured Gemini/Anthropic/Ollama default.
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None


class CreateSessionFromMasterRequest(BaseModel):
    # Which master resume to seed the new chat with. None → the default master
    # (or the only/earliest one if none is explicitly marked default).
    master_id: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None


class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    is_favorite: Optional[bool] = None
    app_status: Optional[str] = None
    notes: Optional[str] = None
    apply_url: Optional[str] = None
    apply_account: Optional[str] = None
    apply_password: Optional[str] = None


class SessionSummary(BaseModel):
    id: str
    title: str
    llm_provider: str
    llm_model: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    is_processing: bool = False
    is_favorite: bool = False
    app_status: Optional[str] = None
    has_tracker: bool = False
    model_config = {"from_attributes": True}

    @field_serializer("created_at", "updated_at")
    def _serialize_dt(self, v: datetime) -> int:
        return _dt_ms(v)


class MessageOut(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    status: str = "complete"
    resume_json: Optional[dict] = None
    cover_letter: Optional[str] = None
    outreach_emails: Optional[list] = None
    agent_trace: Optional[list] = None
    progress_events: Optional[list] = None
    iteration_count: int = 0
    final_score: Optional[float] = None
    created_at: datetime
    model_config = {"from_attributes": True}

    @field_serializer("created_at")
    def _serialize_dt(self, v: datetime) -> int:
        return _dt_ms(v)


class SessionOut(BaseModel):
    id: str
    title: str
    llm_provider: str
    llm_model: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut] = []
    app_status: Optional[str] = None
    notes: Optional[str] = None
    apply_url: Optional[str] = None
    apply_account: Optional[str] = None
    apply_password: Optional[str] = None
    model_config = {"from_attributes": True}

    @field_serializer("created_at", "updated_at")
    def _serialize_dt(self, v: datetime) -> int:
        return _dt_ms(v)


# ── Message schemas ───────────────────────────────────────────────────────────
class SendMessageRequest(BaseModel):
    content: str
    jd_text: Optional[str] = None             # job description for tailoring
    jd_intensity: Optional[int] = None        # 0–100; how aggressively to tailor to the JD (100 = full rewrite, 0 = barely touch the resume)
    attached_resume: Optional[dict] = None    # uploaded JSON resume to start from / refine
    from_master_name: Optional[str] = None    # name of the master resume this turn was seeded from (for the "sources" note)
    use_memory: Optional[bool] = True         # apply persistent profile memory to this turn
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None


# ── Memory schemas ────────────────────────────────────────────────────────────
class UserMemoryUpsert(BaseModel):
    # Core identity
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    website: Optional[str] = None
    portfolio_url: Optional[str] = None
    # Bio
    summary: Optional[str] = None
    # Career
    target_roles: Optional[list[str]] = None
    total_years_experience: Optional[int] = None
    companies: Optional[list[dict]] = None
    education: Optional[list[dict]] = None
    always_include_skills: Optional[list[str]] = None
    certifications: Optional[list[dict]] = None
    languages_spoken: Optional[list[dict]] = None
    projects: Optional[list[dict]] = None
    # Preferences
    open_to_remote: Optional[bool] = None
    work_authorization: Optional[str] = None
    availability: Optional[str] = None
    # Free-form notes
    personal_notes: Optional[str] = None


class UserMemoryOut(BaseModel):
    id: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    website: Optional[str] = None
    portfolio_url: Optional[str] = None
    summary: Optional[str] = None
    target_roles: Optional[list] = None
    total_years_experience: Optional[int] = None
    companies: Optional[list] = None
    education: Optional[list] = None
    always_include_skills: Optional[list] = None
    certifications: Optional[list] = None
    languages_spoken: Optional[list] = None
    projects: Optional[list] = None
    open_to_remote: Optional[bool] = None
    work_authorization: Optional[str] = None
    availability: Optional[str] = None
    personal_notes: Optional[str] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

    @field_serializer("updated_at")
    def _serialize_dt(self, v: datetime | None) -> int | None:
        return _dt_ms(v)


# ── Paginated sessions ────────────────────────────────────────────────────────
class SessionsPage(BaseModel):
    sessions: list[SessionSummary]
    total: int
    has_more: bool


# ── Document export schemas ───────────────────────────────────────────────────
class PDFGenerateRequest(BaseModel):
    resume_json: dict
    template: str = "classic_ats"    # classic_ats | modern_clean | executive_dark | dark_theme | latex_serif
    font_size: str = "normal"        # small | normal | large
    max_pages: str = "auto"          # 1 | 2 | auto  (only meaningful for PDF)
    format: str = "pdf"              # pdf | docx | odt
    inline: bool = False             # true → render inline (preview iframe), false → download


# ── Manual resume edit schemas ────────────────────────────────────────────────
class ResumeEditRequest(BaseModel):
    resume_json: dict


class CoverLetterEditRequest(BaseModel):
    cover_letter: str
