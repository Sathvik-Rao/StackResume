"""Message endpoints — send, cancel, poll, manual edit, rescore."""
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Session, Message, AppSettings
from app.runtime_settings import apply_overlay_from_row
from app.schemas import (
    SendMessageRequest, MessageOut, ResumeEditRequest, CoverLetterEditRequest,
)
from app.config import settings

from ._pipeline import (
    get_cancel_event, _load_memory, _run_pipeline_background,
)


router = APIRouter(prefix="/api", tags=["messages"])


@router.post("/sessions/{session_id}/messages", status_code=202)
async def send_message(
    session_id: str,
    req: SendMessageRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session).options(selectinload(Session.messages)).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    use_memory = True if req.use_memory is None else bool(req.use_memory)

    # If no JD on this turn, reuse the most recent JD from any prior user message
    # so refinement turns ("enhance it", "tighten the summary") still produce
    # the cover letter and outreach emails.
    effective_jd = (req.jd_text or "").strip()
    if not effective_jd:
        for m in reversed(session.messages):
            if m.role == "user" and (m.jd_text or "").strip():
                effective_jd = m.jd_text
                break

    # Clamp the JD-tailoring slider to a sane 0–100 range. Default 100 so we
    # don't change behaviour for callers that haven't been updated yet.
    try:
        jd_intensity = int(req.jd_intensity) if req.jd_intensity is not None else 100
    except (TypeError, ValueError):
        jd_intensity = 100
    jd_intensity = max(0, min(100, jd_intensity))

    # Remember the slider position for next time — but only when the user
    # actually used a JD on this turn (otherwise the value is meaningless).
    if effective_jd and req.jd_intensity is not None:
        settings_res = await db.execute(select(AppSettings).limit(1))
        settings_row = settings_res.scalar_one_or_none()
        if not settings_row:
            settings_row = AppSettings()
            db.add(settings_row)
        if settings_row.default_jd_intensity != jd_intensity:
            settings_row.default_jd_intensity = jd_intensity
            apply_overlay_from_row(settings_row)

    user_msg = Message(
        session_id=session_id, role="user",
        content=req.content, status="complete",
        jd_text=req.jd_text or None,
        use_memory=use_memory,
    )
    db.add(user_msg)
    await db.flush()

    history = [{"role": m.role, "content": m.content} for m in session.messages if m.content]

    # Attached resume from upload takes priority; otherwise fall back to the
    # latest resume produced earlier in this session.
    existing_resume = req.attached_resume
    if not existing_resume:
        for m in reversed(session.messages):
            if m.resume_json:
                existing_resume = m.resume_json
                break

    memory_context = await _load_memory(db) if use_memory else None

    # Load global section preferences (one per install). Missing/empty = all on.
    section_prefs = None
    try:
        sp_res = await db.execute(select(AppSettings).limit(1))
        sp_row = sp_res.scalar_one_or_none()
        if sp_row and sp_row.section_preferences:
            v = sp_row.section_preferences
            if isinstance(v, str):
                import json as _json
                try:
                    v = _json.loads(v)
                except Exception:
                    v = None
            if isinstance(v, dict):
                section_prefs = v
    except Exception:
        section_prefs = None

    provider = req.llm_provider or session.llm_provider
    model = req.llm_model or session.llm_model

    initial_events = [{"agent": "Intent Guard", "status": "running",
                       "notes": "Analyzing your request…",
                       "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000)}]
    asst_msg = Message(
        session_id=session_id, role="assistant",
        content="", status="processing",
        progress_events=initial_events,
    )
    db.add(asst_msg)
    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(asst_msg)

    initial_state = {
        "session_id": session_id,
        "current_input": req.content,
        "jd_text": effective_jd or "",
        "jd_intensity": jd_intensity,
        "conversation_history": history,
        "existing_resume": existing_resume,
        "memory_context": memory_context,
        "llm_provider": provider,
        "llm_model": model,
        "is_off_topic": False,
        "off_topic_response": None,
        "jd_analysis": None,
        "parsed_data": None,
        "request_type": "create",
        "resume": None,
        "review": None,
        "cover_letter": None,
        "outreach_emails": None,
        "iteration": 0,
        "agent_trace": [],
        "error": None,
        "section_preferences": section_prefs,
    }

    # Provenance for the reply's "sources" note — what fed this generation.
    run_meta = {
        "used_memory": bool(memory_context),
        "from_master_name": (req.from_master_name or "").strip() or None,
    }

    background_tasks.add_task(
        _run_pipeline_background,
        asst_msg.id, session_id, initial_state, run_meta,
    )

    return {"user_message_id": user_msg.id, "assistant_message_id": asst_msg.id, "status": "processing"}


@router.post("/messages/{message_id}/cancel", status_code=200)
async def cancel_message(message_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Message).where(Message.id == message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(404, "Message not found")
    ev = get_cancel_event(message_id)
    if ev:
        ev.set()
    if msg.status == "processing":
        msg.status = "cancelled"
        msg.content = "⏹ Generation stopped."
        existing = msg.progress_events or []
        existing.append({
            "agent": "Pipeline", "status": "error",
            "notes": "Cancelled by user.",
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
        })
        msg.progress_events = existing
        msg.agent_trace = existing
        await db.commit()
    return {"status": "cancelled"}


@router.get("/messages/{message_id}/poll", response_model=MessageOut)
async def poll_message(message_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Message).where(Message.id == message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(404, "Message not found")
    return msg


@router.patch("/messages/{message_id}/resume", response_model=MessageOut)
async def edit_resume(message_id: str, req: ResumeEditRequest, db: AsyncSession = Depends(get_db)):
    """Save user edits to a resume.

    Stamps metadata.manually_edited=true plus a counter + timestamp so future
    pipeline runs can preserve manual changes instead of overwriting them.
    """
    result = await db.execute(select(Message).where(Message.id == message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(404, "Message not found")
    if msg.status == "processing":
        raise HTTPException(409, "Cannot edit while generation is in progress")

    resume = dict(req.resume_json or {})
    meta = dict(resume.get("metadata") or {})
    meta["manually_edited"] = True
    meta["manual_edit_count"] = int(meta.get("manual_edit_count") or 0) + 1
    meta["last_manually_edited_at"] = datetime.now(timezone.utc).isoformat()
    resume["metadata"] = meta

    msg.resume_json = resume
    if msg.final_score is None:
        msg.final_score = meta.get("overall_score")
    await db.commit()
    await db.refresh(msg)
    return msg


@router.patch("/messages/{message_id}/cover-letter", response_model=MessageOut)
async def edit_cover_letter(
    message_id: str, req: CoverLetterEditRequest, db: AsyncSession = Depends(get_db)
):
    """Save user edits to a cover letter body.

    The body is stored as-is. Salutation/sign-off/name are reapplied on render,
    so the saved text should be just the body paragraphs.
    """
    result = await db.execute(select(Message).where(Message.id == message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(404, "Message not found")
    if msg.status == "processing":
        raise HTTPException(409, "Cannot edit while generation is in progress")
    msg.cover_letter = (req.cover_letter or "").strip()
    await db.commit()
    await db.refresh(msg)
    return msg


@router.post("/messages/{message_id}/rescore", response_model=MessageOut)
async def rescore_resume(message_id: str, db: AsyncSession = Depends(get_db)):
    """Re-run the Quality Reviewer agent against the stored resume JSON.

    Lighter than re-running the whole pipeline: only the Reviewer is invoked,
    so scores reflect any manual edits without rewriting the content.
    """
    # Import lazily — keeps the agents.graph import cost off the request hot
    # path when this endpoint isn't used.
    from app.agents.graph import review_resume_node

    result = await db.execute(
        select(Message).options(selectinload(Message.session)).where(Message.id == message_id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(404, "Message not found")
    if msg.status == "processing":
        raise HTTPException(409, "Cannot rescore while generation is in progress")
    if not msg.resume_json:
        raise HTTPException(400, "Message has no resume to rescore")

    session = msg.session
    state = {
        "resume": dict(msg.resume_json),
        "iteration": 0,
        "agent_trace": [],
        "llm_provider": session.llm_provider if session else settings.llm_provider,
        "llm_model": session.llm_model if session else settings.llm_model,
    }
    loop = asyncio.get_running_loop()
    try:
        new_state = await loop.run_in_executor(None, review_resume_node, state)
    except Exception as e:
        raise HTTPException(500, f"Rescore failed: {e}")

    resume = new_state.get("resume") or state["resume"]
    meta = dict(resume.get("metadata") or {})
    # Mark that this score reflects manual edits (if any) so the UI can flag it.
    if meta.get("manually_edited"):
        meta["last_rescored_at"] = datetime.now(timezone.utc).isoformat()
    resume["metadata"] = meta

    msg.resume_json = resume
    msg.final_score = meta.get("overall_score", msg.final_score)
    await db.commit()
    await db.refresh(msg)
    return msg
