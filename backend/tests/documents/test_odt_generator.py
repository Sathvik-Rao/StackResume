"""odfpy ODT output — every template × font size combo."""
from __future__ import annotations

import io
import zipfile

import pytest

pytestmark = pytest.mark.documents


def _extract_text(odt_bytes: bytes) -> str:
    """Pull all `<text:*>` text out of the ODT's content.xml without odfpy
    re-parsing the document (the writer pipeline isn't lossless)."""
    with zipfile.ZipFile(io.BytesIO(odt_bytes)) as zf:
        xml = zf.read("content.xml").decode("utf-8", errors="ignore")
    import re
    # Strip every XML tag — what's left is the rendered text.
    return re.sub(r"<[^>]+>", " ", xml)


@pytest.mark.parametrize("template", ["classic_ats", "modern_clean", "executive_dark", "dark_theme"])
@pytest.mark.parametrize("font_size", ["small", "normal", "large"])
def test_resume_odt_renders_all_combos(sample_resume, template, font_size):
    from app.documents.odt_generator import generate_odt_resume

    data = generate_odt_resume(sample_resume, template=template, font_size=font_size)
    # ODT is a ZIP — magic bytes "PK". XML compresses ~6x, so a complete
    # sample resume comes out around 4 KB in zipped form.
    assert data[:2] == b"PK"
    assert len(data) > 2_000
    text = _extract_text(data)
    assert "Ada Lovelace" in text


def test_odt_minimal(minimal_resume):
    from app.documents.odt_generator import generate_odt_resume

    data = generate_odt_resume(minimal_resume)
    assert data[:2] == b"PK"
    assert "Grace Hopper" in _extract_text(data)


def test_odt_cover_letter(sample_resume):
    from app.documents.odt_generator import generate_odt_cover_letter

    body = "Dear hiring team,\n\nI am applying for the role."
    data = generate_odt_cover_letter(
        cover_letter=body,
        resume=sample_resume,
        template="executive_dark",
    )
    assert data[:2] == b"PK"
    text = _extract_text(data)
    assert "Ada Lovelace" in text


def test_odt_cover_letter_dark_theme_has_background(sample_resume):
    """Dark-theme cover letters must set the page background colour in the
    ODT style, otherwise LibreOffice renders light text on white."""
    from app.documents.odt_generator import generate_odt_cover_letter

    data = generate_odt_cover_letter(
        cover_letter="Hi.",
        resume=sample_resume,
        template="dark_theme",
    )
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        styles_xml = zf.read("styles.xml").decode("utf-8", errors="ignore")
    assert "background-color" in styles_xml.lower()
    assert "0d0f1a" in styles_xml.lower()
