"""Session CRUD endpoints — list/create/read/update/delete one or all."""
import copy
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Session, Message, MasterResume
from app.schemas import (
    CreateSessionRequest, CreateSessionFromMasterRequest, SessionOut,
    SessionSummary, UpdateSessionRequest, SessionsPage,
)
from app.config import settings

from ._pipeline import get_cancel_event
from .memory_routes import _resolve_default


router = APIRouter(prefix="/api", tags=["sessions"])


@router.get("/sessions", response_model=SessionsPage)
async def list_sessions(
    skip: int = 0, limit: int = 25, search: str = "",
    db: AsyncSession = Depends(get_db),
):
    skip = max(0, skip)
    limit = max(1, min(limit, 100))
    search = search[:500]
    base = select(Session).order_by(Session.is_favorite.desc(), Session.updated_at.desc())
    count_q = select(func.count(Session.id))
    if search:
        pattern = f"%{search}%"
        base = base.where(Session.title.ilike(pattern))
        count_q = count_q.where(Session.title.ilike(pattern))

    total_r = await db.execute(count_q)
    total = total_r.scalar() or 0

    result = await db.execute(base.offset(skip).limit(limit))
    sessions = result.scalars().all()
    if not sessions:
        return SessionsPage(sessions=[], total=total, has_more=(skip + limit) < total)

    session_ids = [s.id for s in sessions]

    msg_counts_r = await db.execute(
        select(Message.session_id, func.count(Message.id).label("cnt"))
        .where(Message.session_id.in_(session_ids))
        .group_by(Message.session_id)
    )
    msg_count_map = {row.session_id: row.cnt for row in msg_counts_r}

    proc_counts_r = await db.execute(
        select(Message.session_id, func.count(Message.id).label("cnt"))
        .where(Message.session_id.in_(session_ids), Message.status == "processing")
        .group_by(Message.session_id)
    )
    proc_count_map = {row.session_id: row.cnt for row in proc_counts_r}

    out = [
        SessionSummary(
            id=s.id, title=s.title, llm_provider=s.llm_provider,
            llm_model=s.llm_model, created_at=s.created_at,
            updated_at=s.updated_at,
            message_count=msg_count_map.get(s.id, 0),
            is_processing=proc_count_map.get(s.id, 0) > 0,
            is_favorite=bool(s.is_favorite),
            app_status=s.app_status,
            has_tracker=bool(s.app_status or s.notes or s.apply_url or s.apply_account or s.apply_password),
        )
        for s in sessions
    ]
    return SessionsPage(sessions=out, total=total, has_more=(skip + limit) < total)


@router.post("/sessions", response_model=SessionOut, status_code=201)
async def create_session(req: CreateSessionRequest, db: AsyncSession = Depends(get_db)):
    s = Session(
        title=req.title or "New Resume",
        llm_provider=req.llm_provider or settings.llm_provider,
        llm_model=req.llm_model or settings.llm_model,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return SessionOut(id=s.id, title=s.title, llm_provider=s.llm_provider,
                      llm_model=s.llm_model, created_at=s.created_at,
                      updated_at=s.updated_at, messages=[])


@router.post("/sessions/from-master", response_model=SessionOut, status_code=201)
async def create_session_from_master(
    req: CreateSessionFromMasterRequest, db: AsyncSession = Depends(get_db)
):
    """Create a new chat seeded with a master resume **verbatim** — no LLM /
    pipeline run, so the resume is guaranteed identical to the master. Lets the
    user start from their master (e.g. to track an application) and edit on top
    of it without re-tailoring. The seeded resume lands as a completed assistant
    message, exactly like a normal pipeline result, so editing/export/diff all
    work unchanged.
    """
    # Resolve which master to load: explicit id, else the default (or earliest).
    # `_resolve_default` is the single source of truth for "which master is the
    # default", shared with the memory routes.
    if req.master_id:
        res = await db.execute(select(MasterResume).where(MasterResume.id == req.master_id))
        master = res.scalar_one_or_none()
        if not master:
            raise HTTPException(404, "Master resume not found")
    else:
        master = await _resolve_default(db)
        if not master:
            raise HTTPException(404, "No master resume saved yet")

    # Deep-copy so later edits to this chat never mutate the stored master.
    resume = copy.deepcopy(master.resume) if isinstance(master.resume, dict) else (master.resume or {})
    pi = resume.get("personal_info") or {}
    meta = resume.get("metadata") or {}
    full_name = (pi.get("full_name") or "").strip()
    role = (pi.get("professional_title") or meta.get("jd_role") or "").strip()
    title = (f"{full_name} — {role}" if full_name and role else full_name or master.name or "Master Resume")[:255]

    try:
        score = float(meta.get("overall_score"))
    except (TypeError, ValueError):
        score = None

    s = Session(
        title=title,
        llm_provider=req.llm_provider or settings.llm_provider,
        llm_model=req.llm_model or settings.llm_model,
    )
    db.add(s)
    await db.flush()

    ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    trace = [{
        "agent": "Master Resume", "status": "complete",
        "notes": f'Loaded "{master.name}" verbatim — no AI changes applied.',
        "timestamp": ts,
    }]
    db.add(Message(
        session_id=s.id, role="user", status="complete",
        content=f'⭐ Start from master resume "{master.name}" (verbatim — no changes).',
    ))
    db.add(Message(
        session_id=s.id, role="assistant", status="complete",
        content=(
            f"⭐ Loaded master resume **{master.name}** as-is — no AI changes were applied.\n\n"
            "Edit any section directly, paste a job description to tailor it, or fill in "
            "the application tracker for this chat."
        ),
        resume_json=resume,
        agent_trace=trace,
        progress_events=trace,
        final_score=score,
    ))
    await db.commit()

    result = await db.execute(
        select(Session).options(selectinload(Session.messages)).where(Session.id == s.id)
    )
    return result.scalar_one()


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Session).options(selectinload(Session.messages)).where(Session.id == session_id)
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Session not found")
    return s


@router.patch("/sessions/{session_id}", response_model=SessionSummary)
async def update_session(session_id: str, req: UpdateSessionRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).where(Session.id == session_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Session not found")
    if req.title is not None:
        s.title = req.title
    if req.llm_provider is not None:
        s.llm_provider = req.llm_provider
    if req.llm_model is not None:
        s.llm_model = req.llm_model
    if req.is_favorite is not None:
        s.is_favorite = bool(req.is_favorite)
    if req.app_status is not None:
        s.app_status = req.app_status or None
    if req.notes is not None:
        s.notes = req.notes or None
    if req.apply_url is not None:
        s.apply_url = req.apply_url or None
    if req.apply_account is not None:
        s.apply_account = req.apply_account or None
    if req.apply_password is not None:
        s.apply_password = req.apply_password or None
    s.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(s)
    count_r = await db.execute(
        select(func.count(Message.id)).where(Message.session_id == session_id)
    )
    return SessionSummary(id=s.id, title=s.title, llm_provider=s.llm_provider,
                          llm_model=s.llm_model, created_at=s.created_at,
                          updated_at=s.updated_at, message_count=count_r.scalar() or 0,
                          is_favorite=bool(s.is_favorite), app_status=s.app_status,
                          has_tracker=bool(s.app_status or s.notes or s.apply_url or s.apply_account or s.apply_password))


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).where(Session.id == session_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Session not found")
    # Cancel any in-flight messages on this session
    msgs = await db.execute(
        select(Message.id).where(Message.session_id == session_id, Message.status == "processing")
    )
    for (mid,) in msgs.all():
        ev = get_cancel_event(mid)
        if ev:
            ev.set()
    await db.delete(s)
    await db.commit()


@router.delete("/sessions", status_code=200)
async def delete_all_sessions(
    keep_favorites: bool = False,
    db: AsyncSession = Depends(get_db),
):
    q = select(Session)
    if keep_favorites:
        q = q.where(Session.is_favorite == False)  # noqa: E712
    sessions = (await db.execute(q)).scalars().all()
    session_ids = {s.id for s in sessions}
    if session_ids:
        proc = await db.execute(
            select(Message.id).where(
                Message.session_id.in_(session_ids),
                Message.status == "processing",
            )
        )
        for (mid,) in proc.all():
            ev = get_cancel_event(mid)
            if ev:
                ev.set()
    for s in sessions:
        await db.delete(s)
    await db.commit()
    return {"deleted": len(sessions)}
