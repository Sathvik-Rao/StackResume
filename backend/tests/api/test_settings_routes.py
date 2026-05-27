"""/api/app-settings — overlay CRUD + provider smoke test."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.api


async def test_get_settings_masks_secrets(async_client):
    r = await async_client.get("/api/app-settings")
    assert r.status_code == 200
    body = r.json()
    # Secret fields must NOT be returned in plain text.
    for k in ("openai_api_key", "anthropic_api_key", "google_api_key", "langsmith_api_key"):
        assert k not in body
    assert "_secrets_set" in body


async def test_upsert_settings_persists_overlay(async_client):
    r = await async_client.put(
        "/api/app-settings",
        json={
            "llm_provider": "anthropic",
            "llm_model": "claude-sonnet-4-6",
            "llm_temperature": 0.4,
            "max_review_iterations": 4,
            "anthropic_api_key": "sk-test",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["llm_provider"] == "anthropic"
    assert body["llm_model"] == "claude-sonnet-4-6"
    assert body["llm_temperature"] == 0.4
    assert body["max_review_iterations"] == 4
    assert body["_secrets_set"]["anthropic_api_key"] is True


async def test_upsert_empty_string_clears_field(async_client):
    await async_client.put("/api/app-settings", json={"langsmith_project": "myproj"})
    # Now clear it with an empty string.
    r = await async_client.put("/api/app-settings", json={"langsmith_project": ""})
    body = r.json()
    # Either None (cleared) or back to baseline ("stackresume") — both acceptable.
    assert body["langsmith_project"] in (None, "stackresume")


async def test_reset_settings_drops_overlay(async_client):
    await async_client.put("/api/app-settings", json={"max_review_iterations": 7})
    r = await async_client.delete("/api/app-settings")
    assert r.status_code == 200
    body = r.json()
    # Back to baseline (3 by default).
    assert body["max_review_iterations"] == 3


async def test_test_provider_uses_fake_llm(async_client, fake_llm):
    """/api/app-settings/test should hit the LLM and echo back a sample."""
    # Make the (fake) generator respond to a custom prompt by overriding
    # the generator key — any agent key works since fingerprinting falls
    # through to ``generator`` for plain "ping"-style prompts.
    r = await async_client.post(
        "/api/app-settings/test",
        json={"provider": "openai", "model": "gpt-4o", "prompt": "Reply with one word."},
    )
    # Fake returns JSON of the generator default — that's a valid response
    # for the smoke test (200), since the route just asserts the LLM didn't
    # raise.
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["provider"] == "openai"
    assert body["model"] == "gpt-4o"
    assert isinstance(body["duration_ms"], int)


async def test_section_preferences_default_schema(async_client):
    """GET returns the canonical schema even when no overrides have been saved."""
    r = await async_client.get("/api/app-settings/section-preferences")
    assert r.status_code == 200
    body = r.json()
    keys = {s["key"] for s in body["schema"]}
    # Every section the UI renders should be present in the schema.
    for required in ("personal_info", "experience", "technical_skills", "education"):
        assert required in keys
    assert body["preferences"] == {"sections": {}, "fields": {}}


async def test_section_preferences_round_trip(async_client):
    """PUT then GET — saved toggles survive."""
    payload = {
        "sections": {"languages": False, "interests": False},
        "fields": {"personal_info.website": False, "experience.location": False},
    }
    r = await async_client.put("/api/app-settings/section-preferences", json=payload)
    assert r.status_code == 200
    assert r.json()["preferences"] == payload

    g = await async_client.get("/api/app-settings/section-preferences")
    assert g.json()["preferences"] == payload


async def test_test_provider_surfaces_errors(async_client, fake_llm):
    """If the LLM raises, the endpoint returns 400 with the message."""
    fake_llm.fail_with("generator", RuntimeError("boom"))
    r = await async_client.post(
        "/api/app-settings/test",
        json={"provider": "openai", "model": "gpt-4o"},
    )
    assert r.status_code == 400
    assert "RuntimeError" in r.text
    assert "boom" in r.text
