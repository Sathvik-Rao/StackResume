"""GET /api/metrics — usage analytics aggregated across all sessions."""
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Session, Message

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


def _bucket(ev: dict | None) -> tuple[str | None, int, int]:
    """Pull (model, in_tokens, out_tokens) from one trace event's llm_event."""
    if not ev or not isinstance(ev, dict):
        return None, 0, 0
    le = ev.get("llm_event") or {}
    return le.get("model"), int(le.get("input_tokens") or 0), int(le.get("output_tokens") or 0)


@router.get("")
async def get_metrics(db: AsyncSession = Depends(get_db)):
    sess_count = (await db.execute(select(func.count(Session.id)))).scalar() or 0
    msg_count = (await db.execute(select(func.count(Message.id)))).scalar() or 0
    asst_complete = (await db.execute(
        select(func.count(Message.id)).where(
            Message.role == "assistant", Message.status == "complete",
        )
    )).scalar() or 0
    asst_proc = (await db.execute(
        select(func.count(Message.id)).where(
            Message.role == "assistant", Message.status == "processing",
        )
    )).scalar() or 0
    asst_failed = (await db.execute(
        select(func.count(Message.id)).where(
            Message.role == "assistant", Message.status == "failed",
        )
    )).scalar() or 0
    asst_cancelled = (await db.execute(
        select(func.count(Message.id)).where(
            Message.role == "assistant", Message.status == "cancelled",
        )
    )).scalar() or 0

    avg_score = (await db.execute(
        select(func.avg(Message.final_score)).where(Message.final_score.isnot(None))
    )).scalar()

    # Pull all completed assistant messages and aggregate trace-level stats.
    rows = (await db.execute(
        select(Message.agent_trace, Message.resume_json, Message.cover_letter,
               Message.outreach_emails, Message.iteration_count, Message.created_at,
               Message.final_score)
        .where(Message.role == "assistant", Message.status == "complete")
    )).all()

    by_model: dict[str, dict[str, int]] = defaultdict(lambda: {"calls": 0, "in_tokens": 0, "out_tokens": 0, "ms": 0})
    by_agent: dict[str, dict[str, int]] = defaultdict(lambda: {"calls": 0, "in_tokens": 0, "out_tokens": 0, "ms": 0})
    total_in_tokens = 0
    total_out_tokens = 0
    total_iters = 0
    cover_letters = 0
    outreach_emails_total = 0
    jd_tailored = 0

    # 9-day UTC window gives enough buffer for any client timezone (UTC-12 to UTC+14)
    cutoff_9d = datetime.now(timezone.utc) - timedelta(days=9)
    recent_resume_timestamps: list[int] = []

    for trace, resume, cover, outreach, iters, created, score in rows:
        total_iters += int(iters or 0)
        if cover:
            cover_letters += 1
        if outreach:
            outreach_emails_total += len(outreach)
        if resume and isinstance(resume, dict) and resume.get("metadata", {}).get("jd_tailored"):
            jd_tailored += 1

        if created:
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created >= cutoff_9d:
                recent_resume_timestamps.append(int(created.timestamp() * 1000))

        for ev in (trace or []):
            model, ti, to = _bucket(ev)
            ms = int(((ev or {}).get("llm_event") or {}).get("duration_ms") or 0)
            agent = (ev or {}).get("agent") or "Unknown"
            if model or ti or to or ms:
                by_model[model or "unknown"]["calls"] += 1
                by_model[model or "unknown"]["in_tokens"] += ti
                by_model[model or "unknown"]["out_tokens"] += to
                by_model[model or "unknown"]["ms"] += ms
                by_agent[agent]["calls"] += 1
                by_agent[agent]["in_tokens"] += ti
                by_agent[agent]["out_tokens"] += to
                by_agent[agent]["ms"] += ms
                total_in_tokens += ti
                total_out_tokens += to

    return {
        "totals": {
            "sessions": sess_count,
            "messages": msg_count,
            "resumes_completed": asst_complete,
            "in_flight": asst_proc,
            "failed": asst_failed,
            "cancelled": asst_cancelled,
            "average_score": round(float(avg_score), 1) if avg_score is not None else None,
            "total_input_tokens": total_in_tokens,
            "total_output_tokens": total_out_tokens,
            "total_tokens": total_in_tokens + total_out_tokens,
            "average_iterations": round(total_iters / asst_complete, 2) if asst_complete else 0,
            "cover_letters_generated": cover_letters,
            "outreach_emails_generated": outreach_emails_total,
            "jd_tailored_resumes": jd_tailored,
        },
        "by_model": [
            {"model": m, **stats} for m, stats in sorted(by_model.items(), key=lambda x: -x[1]["calls"])
        ],
        "by_agent": [
            {"agent": a, **stats} for a, stats in sorted(by_agent.items(), key=lambda x: -x[1]["calls"])
        ],
        "recent_resume_timestamps": sorted(recent_resume_timestamps),
    }


@router.delete("")
async def reset_metrics(db: AsyncSession = Depends(get_db)):
    """Wipe all trace/score data from messages without deleting the sessions."""
    await db.execute(
        sa_update(Message).values(
            agent_trace=None,
            final_score=None,
            iteration_count=0,
            progress_events=None,
        )
    )
    await db.commit()
    return {"status": "reset"}
