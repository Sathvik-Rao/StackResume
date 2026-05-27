"""Top-level pytest fixtures.

The goals here:
  1. Make sure every test runs against an isolated SQLite file — no test
     touches the developer's real ``/data/resume_builder.db``.
  2. Provide an ``async_client`` that talks to the live FastAPI app over the
     in-process ASGI transport (httpx.AsyncClient) — close to a real HTTP test
     but with no network or port binding.
  3. Provide a ``fake_llm`` fixture that monkey-patches the LLM factory so
     agent / pipeline tests run deterministically without any provider key.

Fixtures live here so any sub-package (unit / api / agents / documents) gets
them automatically via pytest's discovery rules.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import AsyncIterator, Iterator

import pytest


# ── Environment bootstrap ─────────────────────────────────────────────────────
# This must run BEFORE the app modules are imported, because ``app/database.py``
# constructs the engine at module load time from ``settings.database_url``.

_TEST_DB_FILE = Path(tempfile.gettempdir()) / "stackresume_pytest.db"
if _TEST_DB_FILE.exists():
    _TEST_DB_FILE.unlink()

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB_FILE}"
# Make sure no real provider key leaks into tests.
for _k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
           "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY"):
    os.environ.pop(_k, None)
os.environ["AUTH_ENABLED"] = "false"
os.environ["CORS_ORIGINS"] = "*"
os.environ["DEBUG"] = "false"

# Ensure the backend package is importable when tests run from repo root.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


# ── Database lifecycle ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop_policy():
    """Use the default policy — keeps macOS / Linux behaviour identical."""
    import asyncio
    return asyncio.get_event_loop_policy()


@pytest.fixture(autouse=True)
async def _reset_database() -> AsyncIterator[None]:
    """Drop + recreate all tables before each test for guaranteed isolation.

    Cheap on SQLite (≪ 50ms) and avoids cross-test data bleed without forcing
    every test to clean up after itself.
    """
    from app.database import Base, engine
    # Importing models registers every table on Base.metadata.
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


# ── FastAPI client ────────────────────────────────────────────────────────────

@pytest.fixture
async def async_client() -> AsyncIterator:
    """In-process httpx client bound to the FastAPI ASGI app."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client


# ── DB session for direct-DB tests ────────────────────────────────────────────

@pytest.fixture
async def db_session() -> AsyncIterator:
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        yield session


# ── Fake LLM (deterministic, free, offline) ───────────────────────────────────

@pytest.fixture
def fake_llm(monkeypatch) -> "FakeLLM":
    """Monkey-patch ``app.agents.llm_factory.get_llm`` to return a deterministic
    fake. Tests can override individual agent responses via ``fake_llm.set(...)``.

    Patches both the factory module AND any already-imported references inside
    ``app.agents.graph`` so the agents pick up the fake regardless of how they
    obtained their LLM handle.
    """
    from tests.fixtures.llm_fakes import FakeLLM, install_fake

    fake = FakeLLM()
    install_fake(monkeypatch, fake)
    return fake


# ── Sample data ───────────────────────────────────────────────────────────────

@pytest.fixture
def sample_resume() -> dict:
    from tests.fixtures.resumes import SAMPLE_RESUME
    # Return a deep copy so tests can mutate freely.
    import copy
    return copy.deepcopy(SAMPLE_RESUME)


@pytest.fixture
def minimal_resume() -> dict:
    from tests.fixtures.resumes import MINIMAL_RESUME
    import copy
    return copy.deepcopy(MINIMAL_RESUME)


@pytest.fixture
def jd_text() -> str:
    return (
        "Senior Backend Engineer at Acme.\n"
        "Requirements: 5+ years Python, FastAPI, PostgreSQL, AWS, Kubernetes.\n"
        "Nice to have: LangChain, async I/O, distributed systems.\n"
        "You will own the resume builder pipeline and ship to production weekly."
    )
