import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON, Integer, Float, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def _now():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(255), default="New Resume")
    # Provider / model are populated by the create_session endpoint from the
    # current runtime settings — these column defaults only fire if a row is
    # inserted via raw SQL or a direct ORM call that bypasses the endpoint.
    llm_provider: Mapped[str] = mapped_column(String(50), default="google")
    llm_model: Mapped[str] = mapped_column(String(100), default="gemini-2.5-flash")
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    app_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    apply_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    apply_account: Mapped[str | None] = mapped_column(String(500), nullable=True)
    apply_password: Mapped[str | None] = mapped_column(String(500), nullable=True)

    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="session",
        order_by="Message.created_at", cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_sessions_favorite_updated", "is_favorite", "updated_at"),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20))       # user | assistant
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="complete")  # processing | complete | failed | cancelled
    resume_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    outreach_emails: Mapped[list | None] = mapped_column(JSON, nullable=True)
    jd_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    use_memory: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    agent_trace: Mapped[list | None] = mapped_column(JSON, nullable=True)
    progress_events: Mapped[list | None] = mapped_column(JSON, nullable=True)
    iteration_count: Mapped[int] = mapped_column(Integer, default=0)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped["Session"] = relationship("Session", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_session_id", "session_id"),
        Index("ix_messages_session_id_status", "session_id", "status"),
        Index("ix_messages_role_status", "role", "status"),
    )


class AppSettings(Base):
    """Single-row table holding runtime-editable application settings.

    Anything stored here OVERRIDES the corresponding value loaded from .env at
    server startup. Keys with empty/null values fall back to the env baseline.
    """
    __tablename__ = "app_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # Provider defaults
    llm_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    llm_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Last-used model per provider — lets the AI Models tab prefill the
    # right model when the user switches the provider dropdown. Shape:
    # {"openai": "gpt-4o-mini", "anthropic": "claude-haiku-3", ...}
    models_by_provider: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # API keys
    openai_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    anthropic_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    google_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Ollama
    ollama_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Custom / OpenAI-compatible provider endpoint
    openai_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # LangSmith
    langsmith_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    langsmith_project: Mapped[str | None] = mapped_column(String(200), nullable=True)
    langsmith_tracing: Mapped[bool | None] = mapped_column(Boolean, default=None, nullable=True)
    # Pipeline tuning
    max_review_iterations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Last-used JD tailoring slider (0–100). Persisted so the UI starts on the
    # user's preferred intensity instead of resetting to 100 every reload.
    default_jd_intensity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Per-user section/field enable map. Shape:
    #   {"sections": {"languages": false, ...}, "fields": {"personal_info.website": false, ...}}
    # Missing keys default to enabled.
    section_preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class UserMemory(Base):
    """Persistent user profile — like ChatGPT memory. One record per installation."""
    __tablename__ = "user_memory"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # Core identity
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Career
    target_roles: Mapped[list | None] = mapped_column(JSON, nullable=True)     # ["Backend Engineer", "Staff SWE"]
    total_years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    companies: Mapped[list | None] = mapped_column(JSON, nullable=True)        # [{name, title, from_year, to_year}]
    education: Mapped[list | None] = mapped_column(JSON, nullable=True)        # [{institution, degree, graduation_year}]
    # Skills to always include
    always_include_skills: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Additional profile fields
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)           # professional bio/summary
    portfolio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    open_to_remote: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    work_authorization: Mapped[str | None] = mapped_column(String(200), nullable=True)
    availability: Mapped[str | None] = mapped_column(String(200), nullable=True)
    certifications: Mapped[list | None] = mapped_column(JSON, nullable=True)   # [{name, issuer, year, url}]
    languages_spoken: Mapped[list | None] = mapped_column(JSON, nullable=True) # [{language, proficiency}]
    projects: Mapped[list | None] = mapped_column(JSON, nullable=True)          # [{name, role, description, technologies, url, year}]
    # Free-form notes
    personal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class MasterResume(Base):
    """Saved resume templates the user can attach to chats. Multiple per install,
    each with its own editable name. Exactly one row is marked is_default and is
    used when the user attaches without picking a specific one."""

    __tablename__ = "master_resumes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), default="Master Resume")
    resume: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        Index("ix_master_resumes_is_default", "is_default"),
    )
