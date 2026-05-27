"""ReportLab cover letter PDF — every template × font size."""
from __future__ import annotations

import io

import pytest
from pypdf import PdfReader

pytestmark = pytest.mark.documents


def _extract_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


@pytest.mark.parametrize("template", ["classic_ats", "modern_clean", "executive_dark", "dark_theme"])
@pytest.mark.parametrize("font_size", ["small", "normal", "large"])
def test_cover_letter_pdf_renders_all_combos(sample_resume, template, font_size):
    from app.documents.pdf_generator import generate_cover_letter_pdf

    body = (
        "I am thrilled to apply for the Senior Backend role.\n\n"
        "My background at Acme aligns with your needs."
    )
    pdf = generate_cover_letter_pdf(
        cover_letter=body,
        resume=sample_resume,
        template=template,
        font_size=font_size,
    )
    assert pdf.startswith(b"%PDF")
    text = _extract_text(pdf)
    assert "Ada Lovelace" in text
    assert "Sincerely" in text  # signature line added by the renderer


def test_cover_letter_with_recipient(sample_resume):
    from app.documents.pdf_generator import generate_cover_letter_pdf

    body = "I am applying for the role."
    pdf = generate_cover_letter_pdf(
        cover_letter=body,
        resume=sample_resume,
        hiring_manager="Jane Smith",
        company_name="Acme Corp",
    )
    text = _extract_text(pdf)
    assert "Jane Smith" in text or "Jane" in text
    assert "Acme" in text


def test_cover_letter_with_custom_date(sample_resume):
    from app.documents.pdf_generator import generate_cover_letter_pdf

    pdf = generate_cover_letter_pdf(
        cover_letter="Hi.",
        resume=sample_resume,
        date_str="January 15, 2026",
    )
    assert "January 15, 2026" in _extract_text(pdf)


def test_cover_letter_missing_name_uses_placeholder(sample_resume):
    """Resumes without a name still produce a sensible letter."""
    from app.documents.pdf_generator import generate_cover_letter_pdf

    sample_resume["personal_info"] = {}
    pdf = generate_cover_letter_pdf(
        cover_letter="Hello team.",
        resume=sample_resume,
    )
    assert pdf.startswith(b"%PDF")
    assert "Your Name" in _extract_text(pdf)


def test_cover_letter_dark_theme_paints_background(sample_resume):
    """Dark theme must draw the dark page background; otherwise the light
    text would be invisible against ReportLab's default white canvas.

    Light templates skip the page-fill rectangle, so the dark variant must
    yield a measurably larger PDF (one extra ``onFirstPage`` callback that
    issues a fill + rectangle path).
    """
    from app.documents.pdf_generator import generate_cover_letter_pdf

    base = generate_cover_letter_pdf(
        cover_letter="Hi team.", resume=sample_resume, template="modern_clean",
    )
    dark = generate_cover_letter_pdf(
        cover_letter="Hi team.", resume=sample_resume, template="dark_theme",
    )
    assert dark.startswith(b"%PDF")
    # The dark background draw call adds a filled-rectangle operator to the
    # page content stream. Even gzipped it changes the page object size, so
    # the dark variant should be at least a few dozen bytes larger.
    assert len(dark) > len(base) + 20
