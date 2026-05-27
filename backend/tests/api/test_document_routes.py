"""/api/documents — generate + cover-letter."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.api


@pytest.mark.parametrize("fmt, content_type, magic", [
    ("pdf", "application/pdf", b"%PDF"),
    ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"PK"),
    ("odt", "application/vnd.oasis.opendocument.text", b"PK"),
])
async def test_generate_resume_each_format(async_client, sample_resume, fmt, content_type, magic):
    r = await async_client.post(
        "/api/documents/generate",
        json={"resume_json": sample_resume, "template": "classic_ats", "font_size": "normal", "format": fmt},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith(content_type)
    assert r.content[:4].startswith(magic[:4]) or r.content[:2] == magic[:2]


@pytest.mark.parametrize("template", ["classic_ats", "modern_clean", "executive_dark", "dark_theme"])
async def test_each_template_pdf(async_client, sample_resume, template):
    r = await async_client.post(
        "/api/documents/generate",
        json={"resume_json": sample_resume, "template": template, "format": "pdf"},
    )
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")


async def test_bad_template_400(async_client, sample_resume):
    r = await async_client.post(
        "/api/documents/generate",
        json={"resume_json": sample_resume, "template": "fancy-mauve"},
    )
    assert r.status_code == 400


async def test_bad_font_size_400(async_client, sample_resume):
    r = await async_client.post(
        "/api/documents/generate",
        json={"resume_json": sample_resume, "font_size": "huge"},
    )
    assert r.status_code == 400


async def test_bad_format_400(async_client, sample_resume):
    r = await async_client.post(
        "/api/documents/generate",
        json={"resume_json": sample_resume, "format": "rtf"},
    )
    assert r.status_code == 400


async def test_inline_disposition(async_client, sample_resume):
    r = await async_client.post(
        "/api/documents/generate",
        json={"resume_json": sample_resume, "inline": True},
    )
    assert r.status_code == 200
    assert "inline" in r.headers["content-disposition"]


async def test_attachment_disposition_default(async_client, sample_resume):
    r = await async_client.post(
        "/api/documents/generate",
        json={"resume_json": sample_resume},
    )
    assert "attachment" in r.headers["content-disposition"]


async def test_filename_uses_resume_name(async_client, sample_resume):
    r = await async_client.post(
        "/api/documents/generate",
        json={"resume_json": sample_resume},
    )
    disp = r.headers["content-disposition"]
    assert "ada_lovelace" in disp.lower()


async def test_filename_is_sanitised_against_header_injection(async_client, sample_resume):
    """LLM-generated full_name must not be able to smuggle CR/LF, quotes, or
    path separators into the Content-Disposition header."""
    sample_resume["personal_info"]["full_name"] = 'Evil"\r\nX-Injected: yes\r\n../../etc/passwd'
    r = await async_client.post(
        "/api/documents/generate",
        json={"resume_json": sample_resume},
    )
    assert r.status_code == 200
    disp = r.headers["content-disposition"]
    # No raw quote or newline / path-traversal artefact should remain.
    assert '"' not in disp.split("filename=", 1)[1].rstrip()[1:-1]
    assert "\r" not in disp and "\n" not in disp
    assert "/" not in disp
    # Sanity check: the cleaned filename still has *some* user-derived text.
    assert "evil" in disp.lower()


async def test_filename_falls_back_when_name_only_punctuation(async_client, sample_resume):
    """Names that are entirely strip-able characters should fall back to a default."""
    sample_resume["personal_info"]["full_name"] = "!!!"
    r = await async_client.post(
        "/api/documents/generate",
        json={"resume_json": sample_resume},
    )
    assert r.status_code == 200
    assert "resume_classic_ats" in r.headers["content-disposition"].lower()


async def test_cover_letter_generation(async_client, sample_resume):
    r = await async_client.post(
        "/api/documents/cover-letter",
        json={
            "cover_letter": "Dear team, I am writing to apply.\n\nMy background fits well.",
            "resume_json": sample_resume,
            "template": "modern_clean",
            "format": "pdf",
        },
    )
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")


@pytest.mark.parametrize("fmt", ["pdf", "docx", "odt"])
async def test_cover_letter_each_format(async_client, sample_resume, fmt):
    r = await async_client.post(
        "/api/documents/cover-letter",
        json={
            "cover_letter": "Hello hiring team.\n\nI am applying.",
            "resume_json": sample_resume,
            "format": fmt,
        },
    )
    assert r.status_code == 200
    assert len(r.content) > 200  # non-trivial document
