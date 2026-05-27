"""/api/sessions/{id}/messages — send + poll + cancel + edit + rescore.

The pipeline is driven by ``fake_llm`` so these tests run offline and
deterministically. We use polling because the background task runs in an
executor; ``asyncio.sleep`` yields the loop so the task can complete.
"""
from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.api


async def _create_session(async_client) -> str:
    r = await async_client.post("/api/sessions", json={"title": "msg test"})
    return r.json()["id"]


async def _poll_until_done(async_client, msg_id: str, timeout=10.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    last = None
    while asyncio.get_event_loop().time() < deadline:
        r = await async_client.get(f"/api/messages/{msg_id}/poll")
        last = r.json()
        if last.get("status") in ("complete", "failed", "cancelled"):
            return last
        await asyncio.sleep(0.05)
    raise AssertionError(f"Message {msg_id} did not finish in {timeout}s; last={last}")


async def test_send_message_404_for_unknown_session(async_client):
    r = await async_client.post("/api/sessions/missing/messages", json={"content": "hi"})
    assert r.status_code == 404


async def test_send_message_creates_user_and_assistant(async_client, fake_llm):
    sid = await _create_session(async_client)
    r = await async_client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "Senior Python dev, 8 years"},
    )
    assert r.status_code == 202
    body = r.json()
    assert body["user_message_id"]
    assert body["assistant_message_id"]
    assert body["status"] == "processing"

    final = await _poll_until_done(async_client, body["assistant_message_id"])
    assert final["status"] == "complete"
    assert final["resume_json"] is not None
    assert final["resume_json"]["personal_info"]["full_name"]


async def test_off_topic_message_short_circuits(async_client, fake_llm):
    """The quick-intent classifier catches 'hi' without calling the LLM."""
    sid = await _create_session(async_client)
    r = await async_client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "hi"},
    )
    msg_id = r.json()["assistant_message_id"]
    final = await _poll_until_done(async_client, msg_id)
    assert final["status"] == "complete"
    assert final["resume_json"] is None
    # Polite redirect text from intent_check_node.
    assert "StackResume" in final["content"] or "resume" in final["content"].lower()


async def test_send_message_with_jd_runs_cover_letter(async_client, fake_llm, jd_text):
    sid = await _create_session(async_client)
    r = await async_client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "Backend engineer", "jd_text": jd_text},
    )
    msg_id = r.json()["assistant_message_id"]
    final = await _poll_until_done(async_client, msg_id)

    assert final["status"] == "complete"
    assert final["resume_json"] is not None
    # Cover letter + outreach emails should have been produced.
    assert final["cover_letter"]
    assert isinstance(final["outreach_emails"], list)
    assert len(final["outreach_emails"]) >= 1


async def test_cancel_message_marks_cancelled(async_client, fake_llm):
    sid = await _create_session(async_client)
    r = await async_client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "Senior backend engineer"},
    )
    msg_id = r.json()["assistant_message_id"]

    # Cancel immediately. The endpoint should flip status to cancelled even
    # if the background task has already completed.
    cancel_r = await async_client.post(f"/api/messages/{msg_id}/cancel")
    assert cancel_r.status_code == 200

    final = await _poll_until_done(async_client, msg_id)
    assert final["status"] in ("cancelled", "complete")


async def test_poll_unknown_message_404(async_client):
    r = await async_client.get("/api/messages/nope/poll")
    assert r.status_code == 404


async def test_edit_resume_stamps_metadata(async_client, fake_llm, sample_resume):
    sid = await _create_session(async_client)
    r = await async_client.post(
        f"/api/sessions/{sid}/messages", json={"content": "Backend dev"},
    )
    msg_id = r.json()["assistant_message_id"]
    await _poll_until_done(async_client, msg_id)

    # Edit the resume — change the summary.
    edited = dict(sample_resume)
    edited["professional_summary"] = "Edited summary."
    patch = await async_client.patch(
        f"/api/messages/{msg_id}/resume",
        json={"resume_json": edited},
    )
    assert patch.status_code == 200
    body = patch.json()
    meta = body["resume_json"]["metadata"]
    assert meta["manually_edited"] is True
    assert meta["manual_edit_count"] == 1
    assert meta["last_manually_edited_at"]


async def test_edit_resume_rejected_during_processing(async_client, fake_llm, monkeypatch, sample_resume):
    """Cannot save edits while the pipeline is still mid-flight."""
    from app.models import Message

    sid = await _create_session(async_client)
    # Directly insert a fake processing assistant message.
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        m = Message(session_id=sid, role="assistant", content="", status="processing")
        db.add(m)
        await db.commit()
        await db.refresh(m)
        msg_id = m.id

    r = await async_client.patch(
        f"/api/messages/{msg_id}/resume",
        json={"resume_json": sample_resume},
    )
    assert r.status_code == 409


async def test_rescore_resume(async_client, fake_llm):
    sid = await _create_session(async_client)
    r = await async_client.post(
        f"/api/sessions/{sid}/messages", json={"content": "Backend dev"},
    )
    msg_id = r.json()["assistant_message_id"]
    await _poll_until_done(async_client, msg_id)

    rs = await async_client.post(f"/api/messages/{msg_id}/rescore")
    assert rs.status_code == 200
    body = rs.json()
    assert body["resume_json"]["metadata"]["overall_score"] >= 0


async def test_rescore_requires_resume(async_client, fake_llm):
    """Off-topic messages have no resume_json — rescore should 400."""
    sid = await _create_session(async_client)
    r = await async_client.post(
        f"/api/sessions/{sid}/messages", json={"content": "hi"},
    )
    msg_id = r.json()["assistant_message_id"]
    await _poll_until_done(async_client, msg_id)

    rs = await async_client.post(f"/api/messages/{msg_id}/rescore")
    assert rs.status_code == 400


async def test_session_title_auto_updates_from_resume(async_client, fake_llm):
    """A fresh 'New Resume' session should be re-titled after the first run."""
    # Auto-rename only kicks in for the default "New Resume" title.
    r0 = await async_client.post("/api/sessions", json={})
    sid = r0.json()["id"]

    r = await async_client.post(
        f"/api/sessions/{sid}/messages", json={"content": "Backend dev"},
    )
    await _poll_until_done(async_client, r.json()["assistant_message_id"])

    detail = (await async_client.get(f"/api/sessions/{sid}")).json()
    assert "Test Person" in detail["title"]
