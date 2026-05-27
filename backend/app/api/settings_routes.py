"""GET / PUT / DELETE /api/app-settings — runtime settings + API keys.

Secrets are returned to the UI as boolean "is set" flags only, NOT plaintext.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AppSettings
from app.agents.graph import _content_to_text
from app.runtime_settings import (
    apply_overlay_from_row, current_overlay_view, load_settings_from_db,
)

router = APIRouter(prefix="/api/app-settings", tags=["settings"])


class AppSettingsUpsert(BaseModel):
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_temperature: Optional[float] = None
    models_by_provider: Optional[dict] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None
    openai_base_url: Optional[str] = None
    langsmith_api_key: Optional[str] = None
    langsmith_project: Optional[str] = None
    langsmith_tracing: Optional[bool] = None
    max_review_iterations: Optional[int] = None
    min_quality_score: Optional[float] = None
    default_jd_intensity: Optional[int] = None
    # {"sections": {key: bool}, "fields": {"section.field": bool}} — missing = enabled
    section_preferences: Optional[dict] = None


class TestProviderRequest(BaseModel):
    provider: str
    model: Optional[str] = None
    prompt: Optional[str] = None


class TestLangsmithRequest(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None


def _serialize(view: dict) -> dict:
    """Strip secret values; only return boolean flags."""
    masked = dict(view)
    for k in ("openai_api_key", "anthropic_api_key", "google_api_key", "langsmith_api_key"):
        masked.pop(k, None)
    return masked


async def _get_or_create(db: AsyncSession) -> AppSettings:
    res = await db.execute(select(AppSettings).limit(1))
    row = res.scalar_one_or_none()
    if not row:
        row = AppSettings()
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


@router.get("")
async def get_settings():
    return _serialize(current_overlay_view())


@router.put("")
async def upsert_settings(req: AppSettingsUpsert, db: AsyncSession = Depends(get_db)):
    row = await _get_or_create(db)
    payload = req.model_dump(exclude_unset=True)
    for field, val in payload.items():
        # Treat empty string as "clear this field"
        if isinstance(val, str) and not val.strip():
            setattr(row, field, None)
        else:
            setattr(row, field, val)
    row.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(row)
    apply_overlay_from_row(row)
    return _serialize(current_overlay_view())


@router.delete("")
async def reset_settings(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(AppSettings).limit(1))
    row = res.scalar_one_or_none()
    if row:
        await db.delete(row)
        await db.commit()
    await load_settings_from_db()
    return _serialize(current_overlay_view())


@router.post("/test")
async def test_provider(req: TestProviderRequest):
    """Quick smoke-test that the configured provider responds.

    Accepts an optional `prompt` so the UI can send a custom message and
    surface the full reply (capped) — used by the "Send test prompt" control.
    """
    from app.agents.llm_factory import get_llm
    from langchain_core.messages import HumanMessage
    import time as _time
    user_prompt = (req.prompt or "").strip() or "ping"
    try:
        llm = get_llm(req.provider, req.model)
        t0 = _time.monotonic()
        resp = llm.invoke([HumanMessage(content=user_prompt)])
        elapsed_ms = int((_time.monotonic() - t0) * 1000)
        text = _content_to_text(resp.content).strip()
        return {
            "ok": True,
            "provider": req.provider,
            "model": req.model,
            "prompt": user_prompt,
            "response": text or "(empty)",
            "sample": (text[:120] or "(empty)"),
            "duration_ms": elapsed_ms,
        }
    except Exception as e:
        raise HTTPException(400, f"{type(e).__name__}: {e}")


@router.get("/section-preferences")
async def get_section_preferences(db: AsyncSession = Depends(get_db)):
    """Return the saved section toggle map plus the canonical schema the UI
    needs to render rows for sections it has never seen toggled."""
    from app.section_preferences import SECTION_SCHEMA
    import json as _json

    res = await db.execute(select(AppSettings).limit(1))
    row = res.scalar_one_or_none()
    prefs: dict = {"sections": {}, "fields": {}}
    if row and row.section_preferences:
        v = row.section_preferences
        if isinstance(v, str):
            try:
                v = _json.loads(v)
            except Exception:
                v = None
        if isinstance(v, dict):
            prefs = {
                "sections": v.get("sections") or {},
                "fields": v.get("fields") or {},
            }
    return {"schema": SECTION_SCHEMA, "preferences": prefs}


class SectionPreferencesUpsert(BaseModel):
    sections: Optional[dict] = None    # {section_key: bool}
    fields: Optional[dict] = None       # {"section.field": bool}


@router.put("/section-preferences")
async def put_section_preferences(
    req: SectionPreferencesUpsert, db: AsyncSession = Depends(get_db)
):
    row = await _get_or_create(db)
    payload = {
        "sections": req.sections or {},
        "fields": req.fields or {},
    }
    row.section_preferences = payload
    row.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(row)
    apply_overlay_from_row(row)
    return {"preferences": payload}


@router.post("/test-langsmith")
async def test_langsmith(req: TestLangsmithRequest | None = None):
    """Send a single trace to LangSmith and return whether the run was created.

    Accepts optional `provider`/`model` so the UI can test the trace using the
    provider/model the user currently has selected in the prov pill — those
    live in localStorage and aren't necessarily what's persisted in AppSettings.
    """
    from app.config import settings as _s
    if not _s.langsmith_tracing:
        raise HTTPException(400, "LangSmith tracing is disabled. Toggle it on, then save.")
    if not _s.langsmith_api_key:
        raise HTTPException(400, "LangSmith API key is not set.")

    provider = (req.provider if req else None) or _s.llm_provider
    model = (req.model if req else None) or _s.llm_model
    try:
        from langsmith import Client
        client = Client(
            api_url="https://api.smith.langchain.com",
            api_key=_s.langsmith_api_key,
        )
        try:
            list(client.list_projects(limit=1))
        except Exception as e:
            raise HTTPException(400, f"LangSmith auth failed: {e}")

        from app.agents.llm_factory import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_core.tracers.langchain import LangChainTracer
        import time as _time

        llm = get_llm(provider, model)
        tracer = LangChainTracer(
            project_name=_s.langsmith_project or "stackresume",
            client=client,
        )
        messages = [
            SystemMessage(content="You are a test."),
            HumanMessage(content="Reply with one word."),
        ]
        t0 = _time.monotonic()
        resp = llm.invoke(
            messages,
            config={"callbacks": [tracer], "run_name": "StackResume · LangSmithTest"},
        )
        elapsed_ms = int((_time.monotonic() - t0) * 1000)
        text = _content_to_text(resp.content).strip()
        return {
            "ok": True,
            "provider": provider,
            "model": model,
            "project": _s.langsmith_project or "stackresume",
            "endpoint": "https://smith.langchain.com",
            "sample": text[:120] or "(empty)",
            "duration_ms": elapsed_ms,
            "hint": "Open the project in LangSmith to see the new run.",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"{type(e).__name__}: {e}")
