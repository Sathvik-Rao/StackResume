"""/api/sessions CRUD + listing + favouriting + bulk delete."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.api


async def _create(async_client, title="T") -> dict:
    r = await async_client.post("/api/sessions", json={"title": title})
    assert r.status_code == 201
    return r.json()


async def test_create_session_returns_uuid(async_client):
    s = await _create(async_client, "First")
    assert s["title"] == "First"
    assert len(s["id"]) == 36
    assert s["messages"] == []


async def test_get_session_404(async_client):
    r = await async_client.get("/api/sessions/does-not-exist")
    assert r.status_code == 404


async def test_list_sessions_pagination_and_sort(async_client):
    for i in range(5):
        await _create(async_client, f"S{i}")
    r = await async_client.get("/api/sessions?limit=3")
    body = r.json()
    assert r.status_code == 200
    assert len(body["sessions"]) == 3
    assert body["total"] == 5
    assert body["has_more"] is True


async def test_list_sessions_search(async_client):
    await _create(async_client, "Alice resume")
    await _create(async_client, "Bob CV")
    await _create(async_client, "Alice v2")

    r = await async_client.get("/api/sessions?search=Alice")
    body = r.json()
    assert body["total"] == 2
    assert all("Alice" in s["title"] for s in body["sessions"])


async def test_update_session_title_and_favorite(async_client):
    s = await _create(async_client)
    r = await async_client.patch(
        f"/api/sessions/{s['id']}",
        json={"title": "Renamed", "is_favorite": True},
    )
    body = r.json()
    assert r.status_code == 200
    assert body["title"] == "Renamed"
    assert body["is_favorite"] is True


async def test_update_session_404(async_client):
    r = await async_client.patch("/api/sessions/missing", json={"title": "x"})
    assert r.status_code == 404


async def test_favorite_sorts_first(async_client):
    s1 = await _create(async_client, "Plain")
    s2 = await _create(async_client, "Starred")
    await async_client.patch(f"/api/sessions/{s2['id']}", json={"is_favorite": True})

    r = await async_client.get("/api/sessions")
    sessions = r.json()["sessions"]
    assert sessions[0]["id"] == s2["id"]
    assert sessions[0]["is_favorite"] is True


async def test_delete_session(async_client):
    s = await _create(async_client)
    r = await async_client.delete(f"/api/sessions/{s['id']}")
    assert r.status_code == 204
    # 404 on subsequent fetch
    assert (await async_client.get(f"/api/sessions/{s['id']}")).status_code == 404


async def test_delete_all_sessions(async_client):
    for _ in range(3):
        await _create(async_client)
    r = await async_client.delete("/api/sessions")
    assert r.status_code == 200
    assert r.json()["deleted"] == 3
    # Verify
    r2 = await async_client.get("/api/sessions")
    assert r2.json()["total"] == 0


async def test_delete_all_keep_favorites(async_client):
    s1 = await _create(async_client, "Plain")
    s2 = await _create(async_client, "Star")
    await async_client.patch(f"/api/sessions/{s2['id']}", json={"is_favorite": True})

    r = await async_client.delete("/api/sessions?keep_favorites=true")
    assert r.json()["deleted"] == 1
    r2 = await async_client.get("/api/sessions")
    assert r2.json()["total"] == 1
    assert r2.json()["sessions"][0]["id"] == s2["id"]


async def test_session_app_status_fields(async_client):
    s = await _create(async_client)
    r = await async_client.patch(
        f"/api/sessions/{s['id']}",
        json={
            "app_status": "applied",
            "notes": "Followed up via LinkedIn.",
            "apply_url": "https://example.com/careers/123",
        },
    )
    assert r.status_code == 200
    detail = (await async_client.get(f"/api/sessions/{s['id']}")).json()
    assert detail["app_status"] == "applied"
    assert detail["notes"] == "Followed up via LinkedIn."
    assert detail["apply_url"] == "https://example.com/careers/123"
