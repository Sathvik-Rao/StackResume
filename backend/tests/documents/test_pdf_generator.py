"""ReportLab PDF generator — every template × font size × max_pages combo.

We don't pixel-diff (ReportLab renders differ across versions). Instead we
assert:
  - The byte stream starts with ``%PDF``
  - The file is non-trivially large (rules out empty failures)
  - The candidate's name is present in the extracted text (pypdf)
  - The page-count cap is respected when ``max_pages != "auto"``
"""
from __future__ import annotations

import io

import pytest
from pypdf import PdfReader

pytestmark = pytest.mark.documents


def _extract_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


@pytest.mark.parametrize("template", ["classic_ats", "modern_clean", "executive_dark"])
@pytest.mark.parametrize("font_size", ["small", "normal", "large"])
def test_resume_pdf_renders_all_combos(sample_resume, template, font_size):
    from app.documents.pdf_generator import generate_pdf

    pdf = generate_pdf(sample_resume, template=template, font_size=font_size, max_pages="auto")
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 5_000  # smoke check — full resume produces >5 KB
    text = _extract_text(pdf)
    assert "Ada Lovelace" in text
    assert "Senior Software Engineer" in text or "Engineer" in text


def test_resume_pdf_dark_theme_renders(sample_resume):
    """Dark theme is the 4th 'bonus' template — verify it still generates."""
    from app.documents.pdf_generator import generate_pdf

    pdf = generate_pdf(sample_resume, template="dark_theme")
    assert pdf.startswith(b"%PDF")


def test_resume_pdf_minimal_resume(minimal_resume):
    from app.documents.pdf_generator import generate_pdf

    pdf = generate_pdf(minimal_resume)
    assert pdf.startswith(b"%PDF")
    text = _extract_text(pdf)
    assert "Grace Hopper" in text


def test_resume_pdf_max_pages_1(sample_resume):
    from app.documents.pdf_generator import generate_pdf, _page_count

    pdf = generate_pdf(sample_resume, max_pages="1", font_size="small")
    # Best-effort — should be ≤ 1 (the generator shrinks fonts to fit).
    assert _page_count(pdf) <= 1


def test_resume_pdf_max_pages_2(sample_resume):
    from app.documents.pdf_generator import generate_pdf, _page_count

    pdf = generate_pdf(sample_resume, max_pages="2")
    assert _page_count(pdf) <= 2


def test_unknown_template_falls_back_silently(sample_resume):
    """The generator dispatches via a palette lookup — bad keys fall back to
    a default rather than crashing. We just need a valid PDF back."""
    from app.documents.pdf_generator import generate_pdf

    pdf = generate_pdf(sample_resume, template="not_a_real_template")  # type: ignore[arg-type]
    assert pdf.startswith(b"%PDF")


def test_pdf_handles_special_chars(sample_resume):
    """ATS rule: em-dashes and curly quotes must not break the output."""
    from app.documents.pdf_generator import generate_pdf

    sample_resume["professional_summary"] = "Senior — engineer with “impact” for clients’ products."
    pdf = generate_pdf(sample_resume)
    assert pdf.startswith(b"%PDF")
