"""/api/upload/resume — parse uploaded resumes."""
from __future__ import annotations

import json

import pytest

from tests.fixtures.files import (
    make_docx_bytes,
    make_json_resume_bytes,
    make_pdf_bytes,
    make_text_bytes,
)

pytestmark = pytest.mark.api


async def test_upload_json_resume(async_client):
    data = make_json_resume_bytes()
    r = await async_client.post(
        "/api/upload/resume",
        files={"file": ("ada.json", data, "application/json")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "json"
    assert body["resume"]["personal_info"]["full_name"] == "Linus Torvalds"


async def test_upload_invalid_json_400(async_client):
    r = await async_client.post(
        "/api/upload/resume",
        files={"file": ("broken.json", b"{not valid", "application/json")},
    )
    assert r.status_code == 400


async def test_upload_non_dict_json_400(async_client):
    r = await async_client.post(
        "/api/upload/resume",
        files={"file": ("arr.json", b"[1,2,3]", "application/json")},
    )
    assert r.status_code == 400


async def test_upload_txt_resume(async_client):
    r = await async_client.post(
        "/api/upload/resume",
        files={"file": ("notes.txt", make_text_bytes("Some resume text."), "text/plain")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "text"
    assert body["format"] == "txt"
    assert "Some resume text." in body["text"]


async def test_upload_pdf_extracts_text(async_client):
    pdf = make_pdf_bytes("Senior backend engineer.")
    r = await async_client.post(
        "/api/upload/resume",
        files={"file": ("r.pdf", pdf, "application/pdf")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "text"
    assert body["format"] == "pdf"
    assert "Senior backend engineer" in body["text"]


async def test_upload_docx_extracts_text(async_client):
    docx = make_docx_bytes("Python engineer with 10 years.")
    r = await async_client.post(
        "/api/upload/resume",
        files={"file": (
            "r.docx", docx,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "text"
    assert body["format"] == "docx"
    assert "Python engineer" in body["text"]


async def test_upload_empty_file_400(async_client):
    r = await async_client.post(
        "/api/upload/resume",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert r.status_code == 400


async def test_upload_unknown_extension_400(async_client):
    r = await async_client.post(
        "/api/upload/resume",
        files={"file": ("malicious.exe", b"\x4d\x5a", "application/octet-stream")},
    )
    assert r.status_code == 400


async def test_upload_oversized_400(async_client):
    huge = b"x" * (21 * 1024 * 1024)  # 21 MB > 20 MB limit
    r = await async_client.post(
        "/api/upload/resume",
        files={"file": ("big.txt", huge, "text/plain")},
    )
    assert r.status_code == 400
    assert "too large" in r.text.lower()
