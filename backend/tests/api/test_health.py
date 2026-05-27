"""GET /api/health — smoke endpoint + openapi sanity check."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.api


async def test_health_ok(async_client):
    r = await async_client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert isinstance(body["timestamp"], int)


async def test_openapi_renders(async_client):
    r = await async_client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert spec["info"]["title"] == "StackResume"
