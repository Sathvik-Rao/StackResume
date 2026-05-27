from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import UserMemory, MasterResume
from app.schemas import UserMemoryUpsert, UserMemoryOut


class MasterResumeCreate(BaseModel):
    name: str | None = None
    resume: dict
    is_default: bool | None = False


class MasterResumeUpdate(BaseModel):
    name: str | None = None
    resume: dict | None = None
    is_default: bool | None = None


router = APIRouter(prefix="/api/memory", tags=["memory"])


def _master_to_dict(m: MasterResume) -> dict:
    return {
        "id": m.id,
        "name": m.name,
        "resume": m.resume,
        "is_default": bool(m.is_default),
        "created_at": (m.created_at.isoformat() if m.created_at else None),
        "updated_at": (m.updated_at.isoformat() if m.updated_at else None),
    }


def _default_name_for(resume: dict) -> str:
    if not isinstance(resume, dict):
        return "Master Resume"
    pi = resume.get("personal_info") or {}
    role = pi.get("professional_title") or (resume.get("metadata") or {}).get("jd_role")
    name = pi.get("full_name")
    if name and role:
        return f"{name} — {role}"
    return name or role or "Master Resume"


async def _get_or_create(db: AsyncSession) -> UserMemory:
    result = await db.execute(select(UserMemory).limit(1))
    mem = result.scalar_one_or_none()
    if not mem:
        mem = UserMemory()
        db.add(mem)
        await db.commit()
        await db.refresh(mem)
    return mem


async def _resolve_default(db: AsyncSession) -> MasterResume | None:
    res = await db.execute(select(MasterResume).where(MasterResume.is_default == True).limit(1))  # noqa: E712
    item = res.scalar_one_or_none()
    if item:
        return item
    res = await db.execute(select(MasterResume).order_by(MasterResume.created_at).limit(1))
    return res.scalar_one_or_none()


@router.get("", response_model=UserMemoryOut)
async def get_memory(db: AsyncSession = Depends(get_db)):
    return await _get_or_create(db)


@router.put("", response_model=UserMemoryOut)
async def upsert_memory(req: UserMemoryUpsert, db: AsyncSession = Depends(get_db)):
    mem = await _get_or_create(db)
    for field, val in req.model_dump(exclude_unset=True).items():
        setattr(mem, field, val)
    mem.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(mem)
    return mem


@router.delete("", status_code=204)
async def clear_memory(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserMemory).limit(1))
    mem = result.scalar_one_or_none()
    if mem:
        await db.delete(mem)
        await db.commit()


# ── Master Resumes (multiple) ───────────────────────────────────────────────


@router.get("/master-resumes")
async def list_master_resumes(db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(MasterResume).order_by(MasterResume.is_default.desc(), MasterResume.created_at)
    )
    items = res.scalars().all()
    return {"items": [_master_to_dict(it) for it in items]}


@router.post("/master-resumes")
async def create_master_resume(body: MasterResumeCreate, db: AsyncSession = Depends(get_db)):
    name = (body.name or "").strip() or _default_name_for(body.resume)
    res = await db.execute(select(MasterResume))
    existing = res.scalars().all()
    new = MasterResume(name=name, resume=body.resume, is_default=False)
    if not existing:
        new.is_default = True
    elif body.is_default:
        for it in existing:
            it.is_default = False
        new.is_default = True
    db.add(new)
    await db.commit()
    await db.refresh(new)
    return _master_to_dict(new)


@router.get("/master-resumes/{item_id}")
async def get_master_resume_item(item_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(MasterResume).where(MasterResume.id == item_id))
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Master resume not found")
    return _master_to_dict(item)


@router.put("/master-resumes/{item_id}")
async def update_master_resume_item(item_id: str, body: MasterResumeUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(MasterResume).where(MasterResume.id == item_id))
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Master resume not found")
    if body.name is not None:
        n = body.name.strip()
        if not n:
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        item.name = n
    if body.resume is not None:
        item.resume = body.resume
    if body.is_default:
        res2 = await db.execute(select(MasterResume).where(MasterResume.id != item_id))
        for other in res2.scalars().all():
            other.is_default = False
        item.is_default = True
    item.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(item)
    return _master_to_dict(item)


@router.delete("/master-resumes/{item_id}", status_code=204)
async def delete_master_resume_item(item_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(MasterResume).where(MasterResume.id == item_id))
    item = res.scalar_one_or_none()
    if not item:
        return
    was_default = bool(item.is_default)
    await db.delete(item)
    await db.commit()
    if was_default:
        res2 = await db.execute(select(MasterResume).order_by(MasterResume.created_at).limit(1))
        first = res2.scalar_one_or_none()
        if first:
            first.is_default = True
            await db.commit()
