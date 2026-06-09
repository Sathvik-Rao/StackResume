from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Lightweight, idempotent schema migrations for SQLite (no Alembic dependency).
# Each entry: (table, column_name, "ALTER TABLE … ADD COLUMN …" SQL).
_MIGRATIONS: list[tuple[str, str, str]] = [
    ("messages", "cover_letter", "ALTER TABLE messages ADD COLUMN cover_letter TEXT"),
    ("messages", "outreach_emails", "ALTER TABLE messages ADD COLUMN outreach_emails JSON"),
    ("messages", "jd_text", "ALTER TABLE messages ADD COLUMN jd_text TEXT"),
    ("messages", "use_memory", "ALTER TABLE messages ADD COLUMN use_memory BOOLEAN"),
    ("sessions", "is_favorite", "ALTER TABLE sessions ADD COLUMN is_favorite BOOLEAN DEFAULT 0"),
    # UserMemory extended profile fields
    ("user_memory", "summary", "ALTER TABLE user_memory ADD COLUMN summary TEXT"),
    ("user_memory", "portfolio_url", "ALTER TABLE user_memory ADD COLUMN portfolio_url VARCHAR(500)"),
    ("user_memory", "open_to_remote", "ALTER TABLE user_memory ADD COLUMN open_to_remote BOOLEAN"),
    ("user_memory", "work_authorization", "ALTER TABLE user_memory ADD COLUMN work_authorization VARCHAR(200)"),
    ("user_memory", "availability", "ALTER TABLE user_memory ADD COLUMN availability VARCHAR(200)"),
    ("user_memory", "certifications", "ALTER TABLE user_memory ADD COLUMN certifications JSON"),
    ("user_memory", "languages_spoken", "ALTER TABLE user_memory ADD COLUMN languages_spoken JSON"),
    # Session application tracker fields
    ("sessions", "app_status", "ALTER TABLE sessions ADD COLUMN app_status VARCHAR(50)"),
    ("sessions", "notes", "ALTER TABLE sessions ADD COLUMN notes TEXT"),
    ("sessions", "apply_url", "ALTER TABLE sessions ADD COLUMN apply_url VARCHAR(1000)"),
    ("sessions", "apply_account", "ALTER TABLE sessions ADD COLUMN apply_account VARCHAR(500)"),
    ("sessions", "apply_password", "ALTER TABLE sessions ADD COLUMN apply_password VARCHAR(500)"),
    ("user_memory", "projects", "ALTER TABLE user_memory ADD COLUMN projects JSON"),
    ("app_settings", "models_by_provider", "ALTER TABLE app_settings ADD COLUMN models_by_provider JSON"),
    ("app_settings", "default_jd_intensity", "ALTER TABLE app_settings ADD COLUMN default_jd_intensity INTEGER"),
    ("app_settings", "section_preferences", "ALTER TABLE app_settings ADD COLUMN section_preferences JSON"),
    ("app_settings", "openai_base_url", "ALTER TABLE app_settings ADD COLUMN openai_base_url VARCHAR(500)"),
    ("app_settings", "memory_enabled", "ALTER TABLE app_settings ADD COLUMN memory_enabled BOOLEAN"),
]


_INDEX_MIGRATIONS: list[str] = [
    "CREATE INDEX IF NOT EXISTS ix_messages_session_id ON messages (session_id)",
    "CREATE INDEX IF NOT EXISTS ix_messages_session_id_status ON messages (session_id, status)",
    "CREATE INDEX IF NOT EXISTS ix_messages_role_status ON messages (role, status)",
    "CREATE INDEX IF NOT EXISTS ix_sessions_favorite_updated ON sessions (is_favorite, updated_at)",
    "CREATE INDEX IF NOT EXISTS ix_master_resumes_is_default ON master_resumes (is_default)",
]


async def _apply_lightweight_migrations(conn) -> None:
    for table, col, ddl in _MIGRATIONS:
        try:
            res = await conn.execute(text(f"PRAGMA table_info({table})"))
            cols = {row[1] for row in res.fetchall()}
            if col not in cols:
                await conn.execute(text(ddl))
        except Exception:
            # Non-SQLite backends won't support PRAGMA — silently skip; create_all will handle.
            pass
    for ddl in _INDEX_MIGRATIONS:
        try:
            await conn.execute(text(ddl))
        except Exception:
            pass


async def init_db():
    from app import models  # noqa – registers models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_lightweight_migrations(conn)
