"""/api/memory — user profile + master resumes."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.api


async def test_memory_empty_returns_blank(async_client):
    r = await async_client.get("/api/memory")
    assert r.status_code == 200
    body = r.json()
    assert body["full_name"] is None
    assert body["id"]


async def test_memory_upsert_partial(async_client):
    r = await async_client.put(
        "/api/memory",
        json={"full_name": "Ada", "target_roles": ["Backend", "Platform"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["full_name"] == "Ada"
    assert body["target_roles"] == ["Backend", "Platform"]


async def test_memory_upsert_preserves_unspecified_fields(async_client):
    """Sending only ``full_name`` must not blank ``target_roles``."""
    await async_client.put("/api/memory", json={"target_roles": ["X"]})
    await async_client.put("/api/memory", json={"full_name": "Bob"})

    body = (await async_client.get("/api/memory")).json()
    assert body["full_name"] == "Bob"
    assert body["target_roles"] == ["X"]


async def test_memory_delete(async_client):
    await async_client.put("/api/memory", json={"full_name": "Eve"})
    r = await async_client.delete("/api/memory")
    assert r.status_code == 204
    body = (await async_client.get("/api/memory")).json()
    assert body["full_name"] is None


async def test_master_resumes_list_create_default(async_client, sample_resume):
    # First create — becomes default automatically.
    c = await async_client.post(
        "/api/memory/master-resumes",
        json={"name": "Backend v1", "resume": sample_resume},
    )
    assert c.status_code == 200
    body = c.json()
    assert body["is_default"] is True

    # Second create with is_default=True should flip the previous one.
    c2 = await async_client.post(
        "/api/memory/master-resumes",
        json={"name": "Frontend v1", "resume": sample_resume, "is_default": True},
    )
    assert c2.json()["is_default"] is True

    listed = (await async_client.get("/api/memory/master-resumes")).json()
    assert len(listed["items"]) == 2
    default_count = sum(1 for it in listed["items"] if it["is_default"])
    assert default_count == 1


async def test_master_resumes_update_and_delete(async_client, sample_resume):
    c = await async_client.post(
        "/api/memory/master-resumes",
        json={"name": "Original", "resume": sample_resume},
    )
    item_id = c.json()["id"]

    # Update name
    u = await async_client.put(
        f"/api/memory/master-resumes/{item_id}",
        json={"name": "Renamed"},
    )
    assert u.json()["name"] == "Renamed"

    # Empty name is rejected
    bad = await async_client.put(
        f"/api/memory/master-resumes/{item_id}",
        json={"name": "   "},
    )
    assert bad.status_code == 400

    # Delete
    d = await async_client.delete(f"/api/memory/master-resumes/{item_id}")
    assert d.status_code == 204
    assert (await async_client.get(f"/api/memory/master-resumes/{item_id}")).status_code == 404


async def test_master_resume_unknown_id_404(async_client):
    r = await async_client.get("/api/memory/master-resumes/unknown-id")
    assert r.status_code == 404


async def test_load_memory_includes_projects(async_client, db_session):
    """The pipeline loader must surface projects so the Generator can use
    side-project context. Regression test: projects was silently dropped."""
    from app.api._pipeline import _load_memory

    await async_client.put(
        "/api/memory",
        json={
            "full_name": "Ada",
            "projects": [
                {"name": "StackResume", "role": "Creator", "year": 2026,
                 "technologies": ["Python", "FastAPI"]},
            ],
        },
    )
    loaded = await _load_memory(db_session)
    assert loaded is not None
    assert loaded["full_name"] == "Ada"
    assert loaded["projects"]
    assert loaded["projects"][0]["name"] == "StackResume"


async def test_load_memory_returns_none_when_empty(async_client, db_session):
    """No user_memory row yet → loader returns None (not a stub dict)."""
    from app.api._pipeline import _load_memory
    assert await _load_memory(db_session) is None
