"""/api/metrics — aggregates over completed assistant messages."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.api


async def test_metrics_empty_state(async_client):
    r = await async_client.get("/api/metrics")
    assert r.status_code == 200
    body = r.json()
    assert body["totals"]["sessions"] == 0
    assert body["totals"]["resumes_completed"] == 0
    assert body["by_model"] == []
    assert body["by_agent"] == []


async def test_metrics_aggregates_trace(async_client, db_session):
    from app.models import Session, Message

    s = Session(title="X")
    db_session.add(s)
    await db_session.commit()

    trace = [
        {
            "agent": "Resume Generator",
            "llm_event": {"model": "gpt-4o", "input_tokens": 100, "output_tokens": 50, "duration_ms": 1200},
        },
        {
            "agent": "Quality Reviewer",
            "llm_event": {"model": "gpt-4o", "input_tokens": 80, "output_tokens": 40, "duration_ms": 900},
        },
    ]
    m = Message(
        session_id=s.id, role="assistant", content="done", status="complete",
        agent_trace=trace, iteration_count=1, final_score=85.0,
        resume_json={"metadata": {"jd_tailored": True}},
        cover_letter="Hello.",
        outreach_emails=[{"type": "cold_application", "body": "..."}],
    )
    db_session.add(m)
    await db_session.commit()

    r = await async_client.get("/api/metrics")
    body = r.json()
    t = body["totals"]
    assert t["resumes_completed"] == 1
    assert t["total_input_tokens"] == 180
    assert t["total_output_tokens"] == 90
    assert t["total_tokens"] == 270
    assert t["cover_letters_generated"] == 1
    assert t["outreach_emails_generated"] == 1
    assert t["jd_tailored_resumes"] == 1
    assert t["average_score"] == 85.0

    by_model = {row["model"]: row for row in body["by_model"]}
    assert "gpt-4o" in by_model
    assert by_model["gpt-4o"]["calls"] == 2

    by_agent = {row["agent"]: row for row in body["by_agent"]}
    assert "Resume Generator" in by_agent
    assert "Quality Reviewer" in by_agent


async def test_metrics_counts_failed_and_cancelled_assistants(async_client, db_session):
    """Regression: the totals dict must expose ``failed`` / ``cancelled`` /
    ``in_flight`` counts so the Metrics tab can surface broken or stopped runs."""
    from app.models import Session, Message

    s = Session(title="X")
    db_session.add(s)
    await db_session.commit()
    db_session.add_all([
        Message(session_id=s.id, role="assistant", content="ok", status="complete"),
        Message(session_id=s.id, role="assistant", content="boom", status="failed"),
        Message(session_id=s.id, role="assistant", content="stopped", status="cancelled"),
        Message(session_id=s.id, role="assistant", content="…", status="processing"),
    ])
    await db_session.commit()

    body = (await async_client.get("/api/metrics")).json()
    t = body["totals"]
    assert t["resumes_completed"] == 1
    assert t["failed"] == 1
    assert t["cancelled"] == 1
    assert t["in_flight"] == 1


async def test_metrics_reset_clears_trace(async_client, db_session):
    from app.models import Session, Message
    from sqlalchemy import select

    s = Session()
    db_session.add(s)
    await db_session.commit()
    m = Message(
        session_id=s.id, role="assistant", content="done", status="complete",
        agent_trace=[{"agent": "Resume Generator", "llm_event": {"input_tokens": 1, "output_tokens": 1}}],
        final_score=80.0, iteration_count=2,
    )
    db_session.add(m)
    await db_session.commit()

    r = await async_client.delete("/api/metrics")
    assert r.status_code == 200

    # Reset ran in a different DB session — open a fresh one so we see the
    # committed row, not our test-local cache.
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as fresh:
        res = await fresh.execute(select(Message).where(Message.id == m.id))
        refreshed = res.scalar_one()
        assert refreshed.agent_trace is None
        assert refreshed.final_score is None
        assert refreshed.iteration_count == 0
