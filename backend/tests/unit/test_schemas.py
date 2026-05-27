"""Pydantic request/response models."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.unit


def test_dt_ms_naive_treated_as_utc():
    from app.schemas import _dt_ms

    naive = datetime(2026, 5, 24, 12, 0, 0)  # no tzinfo
    aware = naive.replace(tzinfo=timezone.utc)
    assert _dt_ms(naive) == int(aware.timestamp() * 1000)


def test_dt_ms_none():
    from app.schemas import _dt_ms

    assert _dt_ms(None) is None


def test_create_session_defaults():
    from app.schemas import CreateSessionRequest

    req = CreateSessionRequest()
    assert req.title == "New Resume"
    # llm_provider / llm_model intentionally default to None so the
    # create_session endpoint falls back to the currently configured server
    # defaults (settings.llm_provider / settings.llm_model). A hard-coded
    # default here would silently mask a user-configured provider.
    assert req.llm_provider is None
    assert req.llm_model is None


def test_send_message_request_validation():
    from app.schemas import SendMessageRequest

    req = SendMessageRequest(content="Hi")
    assert req.use_memory is True
    assert req.jd_intensity is None

    req2 = SendMessageRequest(content="Hi", jd_intensity=42, use_memory=False)
    assert req2.jd_intensity == 42
    assert req2.use_memory is False


def test_pdf_generate_request_defaults():
    from app.schemas import PDFGenerateRequest

    req = PDFGenerateRequest(resume_json={"foo": "bar"})
    assert req.template == "classic_ats"
    assert req.font_size == "normal"
    assert req.max_pages == "auto"
    assert req.format == "pdf"
    assert req.inline is False


def test_user_memory_upsert_partial():
    """exclude_unset should only ship the fields the client actually sent."""
    from app.schemas import UserMemoryUpsert

    payload = UserMemoryUpsert(full_name="Ada", target_roles=["Backend"])
    dumped = payload.model_dump(exclude_unset=True)
    assert dumped == {"full_name": "Ada", "target_roles": ["Backend"]}
