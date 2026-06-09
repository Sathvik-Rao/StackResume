from pydantic_settings import BaseSettings
from typing import Optional, Literal


class Settings(BaseSettings):
    # App
    app_name: str = "StackResume"
    debug: bool = False
    # Comma-separated list of allowed CORS origins, or "*" to allow all.
    # Production example: CORS_ORIGINS=https://myapp.example.com,https://api.example.com
    cors_origins: str = "*"

    # Database
    database_url: str = "sqlite+aiosqlite:////data/resume_builder.db"

    # LLM Provider — defaults to Google Gemini (set GOOGLE_API_KEY).
    llm_provider: Literal["openai", "anthropic", "google", "ollama", "custom"] = "google"
    llm_model: str = "gemini-2.5-flash"
    llm_temperature: float = 0.7
    # Persisted by the AI Models tab so switching the provider dropdown
    # prefills the last model used with that provider. Not from .env — the
    # DB overlay populates this at runtime.
    models_by_provider: Optional[dict] = None

    # API Keys (also editable in-app and stored in the DB).
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None

    # Ollama
    ollama_base_url: str = "http://localhost:11434"

    # Custom / OpenAI-compatible provider base URL (editable in-app)
    openai_base_url: Optional[str] = None

    # LangSmith tracing (optional)
    langsmith_api_key: Optional[str] = None
    langsmith_project: str = "stackresume"
    langsmith_tracing: bool = False

    # Agent Pipeline
    max_review_iterations: int = 3
    min_quality_score: float = 82.0
    # Remembered JD-tailoring slider value (0–100). DB overlay populates this
    # at runtime — the .env baseline is None so the UI defaults to 100%.
    default_jd_intensity: Optional[int] = None
    # Global "Use memory" default. Baseline ON; the DB overlay flips it when the
    # user toggles the pill, and the value persists across chats/sessions.
    memory_enabled: bool = True

    # ── Optional Basic Auth (single admin user) ────────────────────────────
    # When AUTH_ENABLED=true, every /api/* request requires HTTP Basic auth
    # using AUTH_USERNAME / AUTH_PASSWORD. Off by default.
    auth_enabled: bool = False
    auth_username: str = "admin"
    auth_password: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
