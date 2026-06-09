"""PDF resume + cover-letter generators using ReportLab.

Templates: classic_ats | modern_clean | executive_dark | dark_theme | latex_serif

Design notes (2026 era, not 1990):
- Generous whitespace and clear typographic hierarchy.
- Name set large; role on its own line beneath.
- Contact rendered as one tidy inline list with bullet separators and live links.
- Section headers UPPERCASE with a hairline underline rule.
- Bullets use a true hanging indent and tight leading.
- Skills rendered as a clean 'Label : values' line block.
- For max_pages=1|2 the resume generator transparently shrinks the body until it fits.

`latex_serif` is a separate, light-only layout that recreates the classic LaTeX
("Jake's Resume") look: the bundled Computer Modern (CMU Serif) typeface so the
output is typographically identical to a pdfLaTeX résumé, ~0.5in margins, a
centred small-caps name, an icon-prefixed contact line, Title-Case ruled section
headers, and combined "Company - Title / dates" rows with an italic technologies
line beneath (rendered by `_build_story_serif`). If the CM font files are
missing it transparently falls back to Times.
"""
from __future__ import annotations
import io
import os
from datetime import date
from typing import Literal

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    Table, TableStyle, KeepTogether,
)


TemplateName = Literal[
    "classic_ats", "modern_clean", "executive_dark", "dark_theme", "latex_serif"
]
FontSize = Literal["small", "normal", "large"]
MaxPages = Literal["1", "2", "auto"]


PALETTES = {
    "classic_ats": {
        "name": colors.black,
        "title": colors.HexColor("#222222"),
        "header": colors.black,
        "rule": colors.HexColor("#000000"),
        "body": colors.HexColor("#1a1a1a"),
        "muted": colors.HexColor("#555555"),
        "accent": colors.black,
    },
    "modern_clean": {
        "name": colors.HexColor("#0b1437"),
        "title": colors.HexColor("#3b4dc8"),
        "header": colors.HexColor("#0b1437"),
        "rule": colors.HexColor("#3b4dc8"),
        "body": colors.HexColor("#1f2540"),
        "muted": colors.HexColor("#5a6079"),
        "accent": colors.HexColor("#3b4dc8"),
    },
    "executive_dark": {
        "name": colors.HexColor("#0f172a"),
        "title": colors.HexColor("#475569"),
        "header": colors.HexColor("#0f172a"),
        "rule": colors.HexColor("#94a3b8"),
        "body": colors.HexColor("#1e293b"),
        "muted": colors.HexColor("#64748b"),
        "accent": colors.HexColor("#334155"),
    },
    "dark_theme": {
        "bg": colors.HexColor("#0d0f1a"),
        "name": colors.HexColor("#e8eaf2"),
        "title": colors.HexColor("#a4a8ff"),
        "header": colors.HexColor("#e8eaf2"),
        "rule": colors.HexColor("#7c83ff"),
        "body": colors.HexColor("#d0d4e8"),
        "muted": colors.HexColor("#9098b3"),
        "accent": colors.HexColor("#a4a8ff"),
    },
    # Light-only LaTeX-style template — almost pure black on white, like a
    # freshly compiled `moderncv`/`Jake's Resume`. Rendered by _build_story_serif.
    "latex_serif": {
        "name": colors.black,
        "title": colors.HexColor("#1a1a1a"),
        "header": colors.black,
        "rule": colors.black,
        "body": colors.HexColor("#111111"),
        "muted": colors.HexColor("#333333"),
        "accent": colors.black,
    },
}

FONT_SIZES = {"small": 9.5, "normal": 10.5, "large": 11.5}


def _safe(v) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        # Defensive: when an LLM/coerce step ran `list(<string>)` and turned
        # a sentence into ["A","c","t","i","v","i","t","i","e","s",...], the
        # naive join produces "A, c, t, i, v, ...". Detect and rejoin.
        if len(v) >= 4 and all(isinstance(x, str) for x in v):
            singles = sum(1 for s in v if len(s) <= 1)
            if singles / len(v) >= 0.8:
                joined = "".join(v).strip()
                if joined:
                    return joined
        return ", ".join(_safe(x) for x in v if _safe(x))
    if isinstance(v, dict):
        # "name/title/value" are standard keys; also handle LLM variants like
        # {"action": ..., "result": ...} or {"metric": ...} that local models emit
        parts = [
            v.get("action") or "",
            v.get("result") or "",
            v.get("metric") or "",
        ]
        joined = " ".join(p.strip() for p in parts if p.strip())
        if joined:
            return joined
        return _safe(v.get("name") or v.get("title") or v.get("value") or v.get("text") or v.get("description") or "")
    return str(v)


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _hex(c: colors.Color) -> str:
    return f"#{int(c.red*255):02x}{int(c.green*255):02x}{int(c.blue*255):02x}"


def _normalize_url(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    if s.startswith("http://") or s.startswith("https://") or s.startswith("mailto:"):
        return s
    if "@" in s and "://" not in s:
        return f"mailto:{s}"
    return f"https://{s}"


def _link(text: str, url: str | None, accent_hex: str) -> str:
    text = _esc(text)
    if not url:
        return text
    return f'<link href="{_esc(url)}" color="{accent_hex}">{text}</link>'


def _smallcaps(text: str, small_size: float) -> str:
    """Fake small-caps markup: first letter of each word at the style's size,
    the remainder uppercased at `small_size`. Mimics LaTeX \\scshape headings.
    """
    words = (text or "").split(" ")
    out: list[str] = []
    for w in words:
        if not w:
            continue
        first = _esc(w[0])
        rest = _esc(w[1:].upper())
        out.append(f"{first}<font size=\"{small_size:.1f}\">{rest}</font>" if rest else first)
    return " ".join(out)


_CONTENT_W = letter[0] - 2 * (0.6 * inch)  # 525.6pt for letter + 0.6in margins
_BULLET_COL = 11  # pt: visual indent from bullet to text (consistent at all font sizes)
_TEXT_COL = _CONTENT_W - _BULLET_COL

# The serif (LaTeX) template mimics Jake's-résumé geometry: ink starts ~0.4in
# from each edge, with a tight top and bullets indented under each entry.
#
# SimpleDocTemplate wraps the page in a Frame whose default inner padding is 6pt
# on every side, so the *ink* lands at (margin + 6pt). We therefore pass margins
# reduced by that padding, which makes the real left/right ink edge fall at
# exactly 0.4in — matching the template — while the content width stays 554.4pt.
_SERIF_FRAME_PAD = 6
_SERIF_INK_MARGIN_X = 0.4 * inch                         # where ink should start
_SERIF_MARGIN_X = _SERIF_INK_MARGIN_X - _SERIF_FRAME_PAD  # margin handed to ReportLab
# Top/bottom are tuned to the final ink position (the 6pt pad is already folded
# in): topMargin lands the name top at ~0.3in like the original.
_SERIF_MARGIN_TOP = 0.13 * inch
_SERIF_MARGIN_BOTTOM = 0.4 * inch
_SERIF_CONTENT_W = letter[0] - 2 * _SERIF_INK_MARGIN_X    # 554.4pt frame content width
_SERIF_BULLET_INDENT = 14   # pt: left indent of the bullet glyph under an entry
_SERIF_BULLET_GAP = 11      # pt: bullet glyph column → text column
_SERIF_TEXT_COL = _SERIF_CONTENT_W - _SERIF_BULLET_INDENT - _SERIF_BULLET_GAP


def _styles(p: dict, base: float) -> dict:
    bf, bld = "Helvetica", "Helvetica-Bold"
    return {
        "name": ParagraphStyle(
            "Name", fontName=bld, fontSize=base + 11.5,
            textColor=p["name"], alignment=TA_CENTER,
            spaceAfter=1, leading=(base + 11.5) * 1.05,
        ),
        "title": ParagraphStyle(
            "Title", fontName=bf, fontSize=base + 1,
            textColor=p["title"], alignment=TA_CENTER,
            spaceAfter=4, leading=(base + 1) * 1.3,
        ),
        "contact": ParagraphStyle(
            "Contact", fontName=bf, fontSize=base - 1.5,
            textColor=p["muted"], alignment=TA_CENTER,
            spaceAfter=2, leading=(base - 1.5) * 1.5,
        ),
        "section": ParagraphStyle(
            "Section", fontName=bld, fontSize=base + 0.5,
            textColor=p["header"], spaceBefore=10, spaceAfter=1,
            leading=(base + 0.5) * 1.15,
        ),
        "summary": ParagraphStyle(
            "Summary", fontName=bf, fontSize=base - 0.5,
            textColor=p["body"], alignment=TA_JUSTIFY,
            leading=(base - 0.5) * 1.45, spaceAfter=2,
        ),
        "job_title": ParagraphStyle(
            "JobTitle", fontName=bld, fontSize=base,
            textColor=p["body"], leading=base * 1.2, spaceAfter=0,
        ),
        "company": ParagraphStyle(
            "Company", fontName=bf, fontSize=base - 0.5,
            textColor=p["accent"], leading=(base - 0.5) * 1.25, spaceAfter=0,
        ),
        "dates": ParagraphStyle(
            "Dates", fontName=bf, fontSize=base - 1.5,
            textColor=p["muted"], leading=(base - 1.5) * 1.3, spaceAfter=2,
        ),
        "dates_right": ParagraphStyle(
            "DatesRight", fontName=bf, fontSize=base - 1.5,
            textColor=p["muted"], leading=(base - 1.5) * 1.3, spaceAfter=2,
            alignment=TA_RIGHT,
        ),
        "loc_right": ParagraphStyle(
            "LocRight", fontName=bf, fontSize=base - 1.5,
            textColor=p["muted"], leading=(base - 1.5) * 1.3, spaceAfter=0,
            alignment=TA_RIGHT,
        ),
        # Two-cell table bullet: mark (•) in col-0, body text in col-1.
        # Eliminates dependency on font-metric measurement for hanging indent.
        "bullet_mark": ParagraphStyle(
            "BulletMark", fontName=bf, fontSize=base - 0.5,
            textColor=p["body"], leading=(base - 0.5) * 1.45,
            alignment=TA_LEFT, spaceAfter=0,
        ),
        "bullet_body": ParagraphStyle(
            "BulletBody", fontName=bf, fontSize=base - 0.5,
            textColor=p["body"], leading=(base - 0.5) * 1.45,
            alignment=TA_JUSTIFY, spaceAfter=0,
        ),
        "skill_line": ParagraphStyle(
            "SkillLine", fontName=bf, fontSize=base - 0.5,
            textColor=p["body"], leading=(base - 0.5) * 1.4, spaceAfter=2,
        ),
        "comp_item": ParagraphStyle(
            "CompItem", fontName=bf, fontSize=base - 0.5,
            textColor=p["body"], leading=(base - 0.5) * 1.4, spaceAfter=0,
        ),
        "small": ParagraphStyle(
            "Small", fontName=bf, fontSize=base - 1.5,
            textColor=p["muted"], leading=(base - 1.5) * 1.4,
        ),
        "cert": ParagraphStyle(
            "Cert", fontName=bf, fontSize=base - 0.5,
            textColor=p["body"], leading=(base - 0.5) * 1.4, spaceAfter=2,
        ),
    }


def _section(title: str, st: dict, p: dict) -> list:
    return [
        Paragraph(_esc(title.upper()), st["section"]),
        HRFlowable(width="100%", thickness=0.7,
                   color=p["rule"], spaceBefore=1, spaceAfter=4),
    ]


def _bullet_row(text_markup: str, st: dict, bottom_pad: float | None = None) -> Table:
    """Two-cell table bullet: col-0=•, col-1=text.
    Continuation lines align perfectly because they're in their own column.

    The gap below each bullet defaults to 2pt, but a style set may carry a
    ``"bullet_pad"`` override — the serif (LaTeX) template uses a tighter value
    to pack bullets like a pdfLaTeX résumé.
    """
    if bottom_pad is None:
        bottom_pad = st.get("bullet_pad", 2)
    bullet_col = st.get("bullet_col", _BULLET_COL)
    text_col = st.get("text_col", _TEXT_COL)
    indent = st.get("bullet_indent", 0)
    mark = Paragraph("•", st["bullet_mark"])
    body = Paragraph(text_markup, st["bullet_body"])
    if indent:
        # itemize-style: an empty spacer column indents the bullet under the entry
        row, widths = [["", mark, body]], [indent, bullet_col, text_col]
    else:
        row, widths = [[mark, body]], [bullet_col, text_col]
    t = Table(row, colWidths=widths)
    # Pin to the left margin — reportlab Tables default to hAlign='CENTER', which
    # would drift the row sideways whenever its width != the frame width.
    t.hAlign = "LEFT"
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), bottom_pad),
    ]))
    return t


def _two_col_head(left_para: Paragraph, right_para: Paragraph,
                  left_w: str = "65%", right_w: str = "35%") -> Table:
    """Title-on-the-left / date-on-the-right layout.

    The right paragraph MUST already use a right-aligned style (e.g. `dates_right`)
    so that whatever its column width, the text hugs the right edge of the page.
    """
    t = Table([[left_para, right_para]], colWidths=[left_w, right_w])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


# Vertical gap inserted after every repeating item (Experience role, Project,
# Education entry, Certification, Publication, Patent, OSS contribution,
# Volunteer entry, …). One constant means the gap between two consecutive
# publications looks identical to the gap between two consecutive jobs.
_ITEM_GAP = 4


def _build_story(resume: dict, p: dict, st: dict) -> list:
    """Compose the flowable story for a resume in one pass."""
    accent_hex = _hex(p["accent"])
    muted_hex = _hex(p["muted"])
    sep = '  <font color="#9aa0b4">·</font>  '

    pi = resume.get("personal_info", {}) or {}
    story: list = []

    # ── Header ────────────────────────────────────────────────────────────────
    name = _safe(pi.get("full_name")) or "Your Name"
    story.append(Paragraph(_esc(name), st["name"]))
    role_title = _safe(pi.get("professional_title"))
    if role_title:
        story.append(Paragraph(_esc(role_title), st["title"]))

    contact_bits: list[str] = []
    for key in ("email", "phone", "location"):
        v = _safe(pi.get(key))
        if v:
            contact_bits.append(_esc(v))
    for key in ("linkedin", "github", "website", "portfolio"):
        v = _safe(pi.get(key))
        if v:
            url = _normalize_url(v)
            display = v.replace("https://", "").replace("http://", "").rstrip("/")
            contact_bits.append(_link(display, url, accent_hex))
    if contact_bits:
        story.append(Paragraph(sep.join(contact_bits), st["contact"]))

    story.append(Spacer(1, 4))

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = _safe(resume.get("professional_summary", ""))
    if summary:
        story += _section("Summary", st, p)
        story.append(Paragraph(_esc(summary), st["summary"]))

    # ── Core Competencies (3-col grid, column-major) ──────────────────────────
    competencies = [_safe(c) for c in (resume.get("core_competencies") or []) if _safe(c)]
    if competencies:
        story += _section("Core Competencies", st, p)
        cols = 3
        rows = (len(competencies) + cols - 1) // cols
        grid = [["" for _ in range(cols)] for _ in range(rows)]
        for i, item in enumerate(competencies):
            grid[i % rows][i // rows] = item
        table_data = [
            [Paragraph(f"• {_esc(cell)}" if cell else "", st["comp_item"]) for cell in row]
            for row in grid
        ]
        tbl = Table(table_data, colWidths=["33.3%", "33.3%", "33.4%"])
        tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 2))

    # ── Experience ────────────────────────────────────────────────────────────
    experience = resume.get("experience") or []
    if experience:
        story += _section("Professional Experience", st, p)
        for exp in experience:
            block: list = []
            title_str = _safe(exp.get("title"))
            company_str = _safe(exp.get("company"))
            loc_str = _safe(exp.get("location"))
            start = _safe(exp.get("start_date"))
            end = _safe(exp.get("end_date")) or ("Present" if exp.get("current") else "Present")
            emp_type = _safe(exp.get("employment_type", ""))

            # KeepTogether the *header* (title/dates + company/location +
            # first bullet) so it doesn't get orphaned, but let the rest of the
            # bullets break naturally. Previously the entire block was wrapped
            # in KeepTogether, which forced a long role to the next page and
            # left a giant blank gap on the previous one.
            header_block: list = []
            header_block.append(_two_col_head(
                Paragraph(_esc(title_str), st["job_title"]),
                Paragraph(_esc(f"{start}  -  {end}"), st["dates_right"]),
            ))
            company_inline = company_str
            if emp_type and emp_type.lower() not in ("full-time", "fulltime", ""):
                company_inline = f"{company_str} ({emp_type})" if company_str else emp_type
            if company_inline or loc_str:
                header_block.append(_two_col_head(
                    Paragraph(_esc(company_inline) if company_inline else "",
                              st["company"]),
                    Paragraph(_esc(loc_str) if loc_str else "",
                              st["loc_right"]),
                ))
            header_block.append(Spacer(1, 1.5))

            bullets = list(exp.get("responsibilities") or []) + list(exp.get("achievements") or [])
            dedup_bullets: list[str] = []
            seen: set[str] = set()
            for b in bullets:
                b_str = _safe(b)
                if not b_str or b_str.lower() in seen:
                    continue
                seen.add(b_str.lower())
                dedup_bullets.append(b_str)

            # Pin the first bullet to the header (avoid an orphaned heading at
            # the bottom of a page) then let the rest flow.
            if dedup_bullets:
                header_block.append(_bullet_row(_esc(dedup_bullets[0]), st))
            story.append(KeepTogether(header_block))
            for b_str in dedup_bullets[1:]:
                story.append(_bullet_row(_esc(b_str), st))

            team_size = _safe(exp.get("team_size"))
            techs = [_safe(t) for t in (exp.get("technologies") or []) if _safe(t)]
            meta_parts = []
            if team_size:
                meta_parts.append(f"Team: {_esc(team_size)}")
            if techs:
                meta_parts.append(f"Tech: {_esc(', '.join(techs))}")
            if meta_parts:
                story.append(Paragraph(
                    f'<i><font color="{muted_hex}">{" &nbsp;·&nbsp; ".join(meta_parts)}</font></i>',
                    st["small"],
                ))
            story.append(Spacer(1, _ITEM_GAP))

    # ── Technical Skills ──────────────────────────────────────────────────────
    skills = resume.get("technical_skills") or {}
    skill_cats = [
        ("Languages", skills.get("programming_languages")),
        ("Frameworks & Libraries", skills.get("frameworks_and_libraries")),
        ("Databases", skills.get("databases")),
        ("Cloud & Infrastructure", skills.get("cloud_and_infrastructure")),
        ("DevOps & Tooling", skills.get("devops_and_tools")),
        ("Testing", skills.get("testing")),
        ("Methodologies", skills.get("methodologies")),
        ("Soft Skills", skills.get("soft_skills")),
    ]
    skill_rows = [(k, ", ".join(_safe(x) for x in v if _safe(x))) for k, v in skill_cats if v]
    if skill_rows:
        story += _section("Technical Skills", st, p)
        for label, vals in skill_rows:
            if vals:
                story.append(Paragraph(
                    f'<b>{_esc(label)}:</b>&nbsp;&nbsp;{_esc(vals)}',
                    st["skill_line"],
                ))

    # ── Projects ──────────────────────────────────────────────────────────────
    for proj in (resume.get("projects") or []):
        if proj is (resume.get("projects") or [None])[0]:
            story += _section("Projects", st, p)
        block = []
        p_name = _safe(proj.get("name"))
        url_raw = _safe(proj.get("url") or proj.get("github") or "")
        url = _normalize_url(url_raw) if url_raw else None
        tech = ", ".join(_safe(t) for t in (proj.get("technologies") or []) if _safe(t))
        proj_role = _safe(proj.get("role"))
        proj_type = _safe(proj.get("type"))
        p_start = _safe(proj.get("start_date"))
        p_end = _safe(proj.get("end_date"))

        # Skip sub-parts that the LLM already concatenated into the name
        # (e.g. name="ClipCascade | Lead | Open Source" + role="Lead" + type="Open Source")
        name_lc = p_name.lower()
        head_parts = [f"<b>{_link(p_name, url, accent_hex)}</b>"]
        if proj_role and proj_role.lower() not in name_lc:
            head_parts.append(_esc(proj_role))
        if proj_type and proj_type.lower() not in name_lc:
            head_parts.append(f'<font color="{muted_hex}">{_esc(proj_type)}</font>')
        if tech:
            head_parts.append(f'<font color="{muted_hex}">{_esc(tech)}</font>')

        # Title and dates share one 2-col row (matches Experience / Education),
        # so the gap below the project title is consistent across sections.
        dates_str = ""
        if p_start or p_end:
            dates_str = f"{p_start}  -  {p_end}".strip(" -") if (p_start and p_end) else (p_start or p_end)
        block.append(_two_col_head(
            Paragraph("   -   ".join(head_parts), st["job_title"]),
            Paragraph(_esc(dates_str), st["dates_right"]),
        ))
        # Mirror the breathing room Experience gets from its company row —
        # otherwise bullets crowd the title.
        block.append(Spacer(1, 6))

        desc = _safe(proj.get("description"))
        if desc:
            block.append(_bullet_row(_esc(desc), st))
        for h in (proj.get("highlights") or []):
            h_str = _safe(h)
            if h_str:
                block.append(_bullet_row(_esc(h_str), st))
        block.append(Spacer(1, _ITEM_GAP))
        story.append(KeepTogether(block))

    # ── Open Source ───────────────────────────────────────────────────────────
    for o in (resume.get("open_source_contributions") or []):
        if o is (resume.get("open_source_contributions") or [None])[0]:
            story += _section("Open Source", st, p)
        block = []
        proj = _safe(o.get("project"))
        role = _safe(o.get("role"))
        url_raw = _safe(o.get("url", ""))
        url = _normalize_url(url_raw) if url_raw else None
        stars = _safe(o.get("stars", ""))
        o_lang = _safe(o.get("language", ""))
        head = f"<b>{_link(proj, url, accent_hex)}</b>"
        if role:
            head += f"   -   {_esc(role)}"
        if o_lang:
            head += f"  <font color='{muted_hex}'>{_esc(o_lang)}</font>"
        if stars:
            head += f"  ★ {_esc(stars)}"
        block.append(Paragraph(head, st["job_title"]))
        o_desc = _safe(o.get("description", ""))
        if o_desc:
            block.append(Paragraph(_esc(o_desc), st["small"]))
        for contrib in (o.get("contributions") or []):
            c_str = _safe(contrib)
            if c_str:
                block.append(_bullet_row(_esc(c_str), st))
        block.append(Spacer(1, _ITEM_GAP))
        story.append(KeepTogether(block))

    # ── Education ─────────────────────────────────────────────────────────────
    for edu in (resume.get("education") or []):
        if edu is (resume.get("education") or [None])[0]:
            story += _section("Education", st, p)
        block = []
        deg = _safe(edu.get("degree"))
        field = _safe(edu.get("field_of_study"))
        inst = _safe(edu.get("institution"))
        loc = _safe(edu.get("location"))
        start = _safe(edu.get("start_date"))
        end = _safe(edu.get("end_date"))
        gpa = _safe(edu.get("gpa"))
        honors = _safe(edu.get("honors"))

        deg_line = deg + (f" in {field}" if field else "")
        dates = f"{start}  -  {end}" if (start and end) else (end or start or "")

        block.append(_two_col_head(
            Paragraph(_esc(deg_line), st["job_title"]),
            Paragraph(_esc(dates), st["dates_right"]),
        ))
        if inst or loc:
            block.append(_two_col_head(
                Paragraph(_esc(inst) if inst else "", st["company"]),
                Paragraph(_esc(loc) if loc else "", st["loc_right"]),
            ))
        extras = []
        if gpa:
            extras.append(f"GPA: {_esc(gpa)}")
        if honors:
            extras.append(_esc(honors))
        cw = ", ".join(_safe(c) for c in (edu.get("relevant_coursework") or []) if _safe(c))
        if cw:
            extras.append(f"Coursework: {_esc(cw)}")
        if extras:
            block.append(Paragraph("  ·  ".join(extras), st["small"]))
        acts = ", ".join(_safe(a) for a in (edu.get("activities") or []) if _safe(a))
        if acts:
            block.append(Paragraph(f'Activities: {_esc(acts)}', st["small"]))
        block.append(Spacer(1, _ITEM_GAP))
        story.append(KeepTogether(block))

    # ── Certifications ────────────────────────────────────────────────────────
    for c in (resume.get("certifications") or []):
        if c is (resume.get("certifications") or [None])[0]:
            story += _section("Certifications", st, p)
        c_name = _safe(c.get("name"))
        c_issuer = _safe(c.get("issuer"))
        c_date = _safe(c.get("date"))
        c_expiry = _safe(c.get("expiry"))
        c_cred_id = _safe(c.get("credential_id"))
        c_url_raw = _safe(c.get("url", ""))
        c_url = _normalize_url(c_url_raw) if c_url_raw else None
        name_part = f"<b>{_link(c_name, c_url, accent_hex)}</b>"
        line = name_part
        if c_issuer:
            line += f"   -   {_esc(c_issuer)}"
        date_parts = []
        if c_date:
            date_parts.append(f"issued {_esc(c_date)}")
        if c_expiry:
            date_parts.append(f"expires {_esc(c_expiry)}")
        if date_parts:
            line += f"  <font color='{muted_hex}'>({', '.join(date_parts)})</font>"
        if c_cred_id:
            line += f"  <font color='{muted_hex}'>ID: {_esc(c_cred_id)}</font>"
        story.append(Paragraph(line, st["cert"]))
        story.append(Spacer(1, _ITEM_GAP))

    # ── Publications ──────────────────────────────────────────────────────────
    for pub in (resume.get("publications") or []):
        if pub is (resume.get("publications") or [None])[0]:
            story += _section("Publications", st, p)
        title = _safe(pub.get("title"))
        venue = _safe(pub.get("venue"))
        date_pub = _safe(pub.get("date"))
        pub_type = _safe(pub.get("type", ""))
        url_raw = _safe(pub.get("url", ""))
        url = _normalize_url(url_raw) if url_raw else None
        authors = ", ".join(_safe(a) for a in (pub.get("authors") or []) if _safe(a))
        line = f"<b>{_link(title, url, accent_hex)}</b>"
        # Skip pub_type if it's already echoed in the title (e.g. title="Foo [Article]")
        if pub_type and f"[{pub_type.lower()}]" not in title.lower():
            line += f"  <font color='{muted_hex}'>[{_esc(pub_type)}]</font>"
        if venue:
            line += f"   -   <i>{_esc(venue)}</i>"
        if date_pub:
            line += f"  ({_esc(date_pub)})"
        story.append(Paragraph(line, st["cert"]))
        if authors:
            story.append(Paragraph(_esc(authors), st["small"]))
        story.append(Spacer(1, _ITEM_GAP))

    # ── Patents ───────────────────────────────────────────────────────────────
    for pt in (resume.get("patents") or []):
        if pt is (resume.get("patents") or [None])[0]:
            story += _section("Patents", st, p)
        pt_title = _safe(pt.get("title"))
        pt_url_raw = _safe(pt.get("url", ""))
        pt_url = _normalize_url(pt_url_raw) if pt_url_raw else None
        line = f"<b>{_link(pt_title, pt_url, accent_hex)}</b>"
        num = _safe(pt.get("patent_number"))
        date_pt = _safe(pt.get("date"))
        if num:
            line += f"   -   {_esc(num)}"
        if date_pt:
            line += f"  ({_esc(date_pt)})"
        story.append(Paragraph(line, st["cert"]))
        desc = _safe(pt.get("description"))
        if desc:
            story.append(Paragraph(_esc(desc), st["small"]))
        story.append(Spacer(1, _ITEM_GAP))

    # ── Awards ────────────────────────────────────────────────────────────────
    for a in (resume.get("awards_and_honors") or []):
        if a is (resume.get("awards_and_honors") or [None])[0]:
            story += _section("Awards & Honors", st, p)
        v = _safe(a) if not isinstance(a, dict) else _safe(a.get("name") or a.get("title"))
        if v:
            story.append(_bullet_row(_esc(v), st))

    # ── Volunteer ─────────────────────────────────────────────────────────────
    for v in (resume.get("volunteer_experience") or []):
        if v is (resume.get("volunteer_experience") or [None])[0]:
            story += _section("Volunteer Experience", st, p)
        org = _safe(v.get("organization"))
        role = _safe(v.get("role"))
        sd, ed = _safe(v.get("start_date")), _safe(v.get("end_date"))
        dates_str = f"{sd}  -  {ed}".strip(" -") if (sd or ed) else ""
        head = f"<b>{_esc(role)}</b>" + (f"   -   {_esc(org)}" if org else "")
        # Match Experience / Education: title on the left, dates hugging the
        # right edge on the same line.
        story.append(_two_col_head(
            Paragraph(head, st["job_title"]),
            Paragraph(_esc(dates_str), st["dates_right"]),
        ))
        desc = _safe(v.get("description"))
        if desc:
            story.append(Paragraph(_esc(desc), st["small"]))
        story.append(Spacer(1, _ITEM_GAP))

    # ── Languages ─────────────────────────────────────────────────────────────
    langs = resume.get("languages") or []
    if langs:
        story += _section("Languages", st, p)
        parts = []
        for l in langs:
            lang = _safe(l.get("language"))
            prof = _safe(l.get("proficiency"))
            if lang:
                parts.append(f"<b>{_esc(lang)}</b>" + (f" ({_esc(prof)})" if prof else ""))
        story.append(Paragraph("  ·  ".join(parts), st["skill_line"]))

    # ── Interests ─────────────────────────────────────────────────────────────
    interests = [_safe(i) for i in (resume.get("interests") or []) if _safe(i)]
    if interests:
        story += _section("Interests", st, p)
        story.append(Paragraph(_esc(", ".join(interests)), st["skill_line"]))

    # ── References ────────────────────────────────────────────────────────────
    references = resume.get("references")
    if references:
        story += _section("References", st, p)
        if isinstance(references, str):
            story.append(Paragraph(_esc(references), st["skill_line"]))
        elif isinstance(references, list):
            for ref in references:
                ref_str = _safe(ref)
                if ref_str:
                    story.append(_bullet_row(_esc(ref_str), st))

    return story


# ═══════════════════════════════════════════════════════════════════════════
# latex_serif — a self-contained, light-only LaTeX-style layout.
# ═══════════════════════════════════════════════════════════════════════════


# Bundled Computer Modern (CMU Serif) faces — the actual LaTeX typeface, so the
# template is typographically identical to a pdfLaTeX-compiled résumé. Converted
# from the OFL-licensed cm-unicode OTFs to TrueType (ReportLab can't embed CFF).
_FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")
_CM_FACES = {
    "CMUSerif": "CMUSerif-Roman.ttf",
    "CMUSerif-Bold": "CMUSerif-Bold.ttf",
    "CMUSerif-Italic": "CMUSerif-Italic.ttf",
    "CMUSerif-BoldItalic": "CMUSerif-BoldItalic.ttf",
}
# FontAwesome 6 Free — the exact icon font the LaTeX `fontawesome5` package uses,
# so contact icons are glyph-identical to the template (solid handset/envelope/
# pin) rather than hand-drawn approximations.
_FA_FACES = {
    "FA-Solid": "fa-solid-900.ttf",
    "FA-Brands": "fa-brands-400.ttf",
}
_CM_REGISTERED: bool | None = None  # None = not tried yet
_FA_REGISTERED: bool | None = None


def _ensure_cm_fonts() -> bool:
    """Register the bundled Computer Modern faces once. Returns True if the
    family is usable; False (→ Times fallback) if the files are missing."""
    global _CM_REGISTERED
    if _CM_REGISTERED is not None:
        return _CM_REGISTERED
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        for name, fn in _CM_FACES.items():
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, os.path.join(_FONTS_DIR, fn)))
        # Map <b>/<i> markup (on text whose base font is CMUSerif) to the faces.
        pdfmetrics.registerFontFamily(
            "CMUSerif", normal="CMUSerif", bold="CMUSerif-Bold",
            italic="CMUSerif-Italic", boldItalic="CMUSerif-BoldItalic",
        )
        _CM_REGISTERED = True
    except Exception:
        _CM_REGISTERED = False
    return _CM_REGISTERED


def _ensure_fa_fonts() -> bool:
    """Register the bundled FontAwesome faces once. Returns False (→ no icons)
    if the files are missing."""
    global _FA_REGISTERED
    if _FA_REGISTERED is not None:
        return _FA_REGISTERED
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        for name, fn in _FA_FACES.items():
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, os.path.join(_FONTS_DIR, fn)))
        _FA_REGISTERED = True
    except Exception:
        _FA_REGISTERED = False
    return _FA_REGISTERED


# Contact-field → (FontAwesome face, glyph) — the same icons fontawesome5 emits.
_FA_ICONS = {
    "phone":    ("FA-Solid", ""),   # faPhone (handset)
    "email":    ("FA-Solid", ""),   # faEnvelope (solid)
    "location": ("FA-Solid", ""),   # faMapMarkerAlt / location-dot (pin with cutout)
    "linkedin": ("FA-Brands", ""),  # faLinkedin
    "github":   ("FA-Brands", ""),  # faGithub
    "web":      ("FA-Solid", ""),   # faGlobe
}


def _fa_icon(kind: str, color_hex: str, size: float) -> str:
    """Inline FontAwesome glyph markup for a contact icon, or '' if unavailable."""
    if not _ensure_fa_fonts() or kind not in _FA_ICONS:
        return ""
    face, glyph = _FA_ICONS[kind]
    return (f'<font name="{face}" size="{size:.1f}" color="{color_hex}">'
            f'{glyph}</font>')


def _serif_styles(p: dict, base: float) -> dict:
    """Computer-Modern paragraph styles recreating the classic LaTeX résumé look
    (falls back to Times if the bundled CM fonts can't be loaded)."""
    if _ensure_cm_fonts():
        sf, sb, si, sbi = "CMUSerif", "CMUSerif-Bold", "CMUSerif-Italic", "CMUSerif-BoldItalic"
    else:
        sf, sb, si, sbi = "Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic"
    name_sz = base + 13.5
    return {
        "name": ParagraphStyle(
            "SName", fontName=sb, fontSize=name_sz,
            textColor=p["name"], alignment=TA_CENTER,
            spaceAfter=1, leading=name_sz,
        ),
        "title": ParagraphStyle(
            "STitle", fontName=si, fontSize=base + 0.5,
            textColor=p["muted"], alignment=TA_CENTER,
            spaceAfter=2, leading=(base + 0.5) * 1.2,
        ),
        "contact": ParagraphStyle(
            "SContact", fontName=sf, fontSize=base - 0.5,
            textColor=p["body"], alignment=TA_CENTER,
            spaceAfter=1, leading=(base - 0.5) * 1.45,
        ),
        "section": ParagraphStyle(
            "SSection", fontName=sb, fontSize=base + 2.5,
            textColor=p["header"], spaceBefore=6, spaceAfter=0,
            leading=(base + 2.5) * 1.05,
        ),
        "summary": ParagraphStyle(
            "SSummary", fontName=sf, fontSize=base,
            textColor=p["body"], alignment=TA_JUSTIFY,
            leading=base * 1.2, spaceAfter=1,
        ),
        # Combined "Company - Title" row (bold) + bold dates on the right.
        "head": ParagraphStyle(
            "SHead", fontName=sb, fontSize=base,
            textColor=p["body"], leading=base * 1.2, spaceAfter=0,
        ),
        "head_right": ParagraphStyle(
            "SHeadR", fontName=sb, fontSize=base,
            textColor=p["body"], leading=base * 1.2, spaceAfter=0,
            alignment=TA_RIGHT,
        ),
        # Italic technologies / degree line + italic location on the right.
        "sub": ParagraphStyle(
            "SSub", fontName=si, fontSize=base - 0.5,
            textColor=p["body"], leading=(base - 0.5) * 1.18, spaceAfter=0,
        ),
        # Same as "sub" but nudged in by ~one space — used for the experience
        # "Technologies:" line so it doesn't start at the exact same left edge
        # as the company name above it.
        "sub_indent": ParagraphStyle(
            "SSubIndent", fontName=si, fontSize=base - 0.5,
            textColor=p["body"], leading=(base - 0.5) * 1.18, spaceAfter=0,
            leftIndent=(base - 0.5) * 0.5,
        ),
        "sub_right": ParagraphStyle(
            "SSubR", fontName=si, fontSize=base - 0.5,
            textColor=p["body"], leading=(base - 0.5) * 1.18, spaceAfter=0,
            alignment=TA_RIGHT,
        ),
        "bullet_mark": ParagraphStyle(
            "SBulMark", fontName=sf, fontSize=base - 0.5,
            textColor=p["body"], leading=(base - 0.5) * 1.18,
            alignment=TA_LEFT, spaceAfter=0,
        ),
        "bullet_body": ParagraphStyle(
            "SBulBody", fontName=sf, fontSize=base - 0.5,
            textColor=p["body"], leading=(base - 0.5) * 1.18,
            alignment=TA_JUSTIFY, spaceAfter=0,
        ),
        "skill_line": ParagraphStyle(
            "SSkill", fontName=sf, fontSize=base - 0.5,
            textColor=p["body"], leading=(base - 0.5) * 1.22, spaceAfter=1.5,
        ),
        "comp_item": ParagraphStyle(
            "SComp", fontName=sf, fontSize=base - 0.5,
            textColor=p["body"], leading=(base - 0.5) * 1.3, spaceAfter=0,
        ),
        "small": ParagraphStyle(
            "SSmall", fontName=si, fontSize=base - 1.5,
            textColor=p["muted"], leading=(base - 1.5) * 1.3, spaceAfter=0,
        ),
        "cert": ParagraphStyle(
            "SCert", fontName=sf, fontSize=base - 0.5,
            textColor=p["body"], leading=(base - 0.5) * 1.35, spaceAfter=1,
        ),
        # Non-style overrides read by _bullet_row: tighter bullet spacing, an
        # itemize-style indent, and a wider text column matching 0.4in margins.
        "bullet_pad": 1.0,
        "bullet_col": _SERIF_BULLET_GAP,
        "bullet_indent": _SERIF_BULLET_INDENT,
        "text_col": _SERIF_TEXT_COL,
        # Explicit face names for inline spans whose weight/slant must not be
        # inherited from the surrounding run (e.g. the bold "Technologies" label,
        # or regular-italic project tech sitting inside a bold title), resolved
        # for whichever family is active.
        "bolditalic_font": sbi,
        "italic_font": si,
        "bold_font": sb,
        "regular_font": sf,
    }


def _serif_hrow(left_para: Paragraph, right_plain: str, right_style,
                total_w: float = _SERIF_CONTENT_W) -> Table:
    """LaTeX ``\\hfill`` row: left text flows across the line, the right item
    (date / location) is sized to its own width and hugs the right margin, so a
    long left string uses the full width instead of wrapping inside a fixed cell.
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth
    right_plain = right_plain or ""
    if right_plain:
        rw = stringWidth(right_plain, right_style.fontName, right_style.fontSize) + 3
        rw = min(rw, total_w * 0.5)
    else:
        rw = 0.01
    t = Table([[left_para, Paragraph(_esc(right_plain), right_style)]],
              colWidths=[total_w - rw, rw])
    t.hAlign = "LEFT"  # pin to the left margin (Tables default to CENTER)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _serif_section(title: str, st: dict, p: dict) -> list:
    """Title-Case heading with a hairline rule beneath (no uppercasing)."""
    return [
        Paragraph(_esc(title), st["section"]),
        HRFlowable(width="100%", thickness=0.6,
                   color=p["rule"], spaceBefore=2, spaceAfter=4),
    ]


def _serif_dates(start: str, end: str) -> str:
    if start and end:
        return f"{start} – {end}"
    return end or start or ""


def _build_story_serif(resume: dict, p: dict, st: dict, base: float) -> list:
    """Compose the flowable story for the latex_serif (LaTeX-style) template."""
    accent_hex = _hex(p["accent"])
    muted_hex = _hex(p["muted"])
    icon_hex = _hex(p["body"])
    icon_sz = base - 0.5
    sep = "&nbsp;&nbsp;&nbsp;&nbsp;"

    def _ico(kind: str) -> str:
        g = _fa_icon(kind, icon_hex, icon_sz)
        return f"{g}&nbsp;" if g else ""
    # Computer Modern packs tighter than the sans templates; use a smaller
    # inter-item gap here (shadows the module default just inside this builder)
    # so a typical résumé lands on the same page count as the LaTeX original.
    _ITEM_GAP = 3

    pi = resume.get("personal_info", {}) or {}
    story: list = []

    # ── Header: small-caps name, optional title, icon contact line ────────────
    name = _safe(pi.get("full_name")) or "Your Name"
    # Small-caps body sized to 0.74× the name style's font size (base + 13.5).
    story.append(Paragraph(_smallcaps(name, (base + 13.5) * 0.74), st["name"]))
    role_title = _safe(pi.get("professional_title"))
    if role_title:
        story.append(Paragraph(_esc(role_title), st["title"]))

    # Phone · email · location go on their own row; profile links flow onto the
    # next row. The separators are non-breaking spaces, so without this split a
    # too-long single line would wrap at the only breakable space — the one
    # inside the location ("Austin, TX" → "Austin," / "TX") — which looks broken.
    contact_personal: list[str] = []
    phone = _safe(pi.get("phone"))
    if phone:
        contact_personal.append(_ico("phone") + _esc(phone))
    # LaTeX hyperref underlines the linked contacts; mirror that with <u>.
    email = _safe(pi.get("email"))
    if email:
        contact_personal.append(
            _ico("email") + f"<u>{_link(email, _normalize_url(email), accent_hex)}</u>"
        )
    location = _safe(pi.get("location"))
    if location:
        # Hold the location together so it never splits across a line.
        contact_personal.append(_ico("location") + _esc(location).replace(" ", "&nbsp;"))
    contact_links: list[str] = []
    for key in ("linkedin", "github", "website", "portfolio"):
        v = _safe(pi.get(key))
        if v:
            url = _normalize_url(v)
            display = v.replace("https://", "").replace("http://", "").rstrip("/")
            icon_kind = key if key in ("linkedin", "github") else "web"
            contact_links.append(_ico(icon_kind) + f"<u>{_link(display, url, accent_hex)}</u>")
    contact_rows = [sep.join(row) for row in (contact_personal, contact_links) if row]
    if contact_rows:
        story.append(Paragraph("<br/>".join(contact_rows), st["contact"]))

    story.append(Spacer(1, 1))

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = _safe(resume.get("professional_summary", ""))
    if summary:
        story += _serif_section("Summary", st, p)
        story.append(Paragraph(_esc(summary), st["summary"]))

    # ── Core Competencies (3-col grid, column-major) ──────────────────────────
    competencies = [_safe(c) for c in (resume.get("core_competencies") or []) if _safe(c)]
    if competencies:
        story += _serif_section("Core Competencies", st, p)
        cols = 3
        rows = (len(competencies) + cols - 1) // cols
        grid = [["" for _ in range(cols)] for _ in range(rows)]
        for i, item in enumerate(competencies):
            grid[i % rows][i // rows] = item
        table_data = [
            [Paragraph(f"• {_esc(cell)}" if cell else "", st["comp_item"]) for cell in row]
            for row in grid
        ]
        tbl = Table(table_data, colWidths=["33.3%", "33.3%", "33.4%"])
        tbl.hAlign = "LEFT"
        tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 2))

    # ── Professional Experience ───────────────────────────────────────────────
    experience = resume.get("experience") or []
    if experience:
        story += _serif_section("Professional Experience", st, p)
        for exp in experience:
            title_str = _safe(exp.get("title"))
            company_str = _safe(exp.get("company"))
            loc_str = _safe(exp.get("location"))
            start = _safe(exp.get("start_date"))
            end = _safe(exp.get("end_date")) or ("Present" if exp.get("current") else "Present")
            emp_type = _safe(exp.get("employment_type", ""))

            head_left = " – ".join([x for x in (company_str, title_str) if x]) or title_str
            if emp_type and emp_type.lower() not in ("full-time", "fulltime", ""):
                head_left = f"{head_left} ({emp_type})"

            header_block: list = [_serif_hrow(
                Paragraph(f"<b>{_esc(head_left)}</b>", st["head"]),
                _serif_dates(start, end), st["head_right"],
            )]

            techs = [_safe(t) for t in (exp.get("technologies") or []) if _safe(t)]
            team_size = _safe(exp.get("team_size"))
            # "Technologies" label bold-italic, values italic (matches the source).
            sub_markup = ""
            if techs:
                sub_markup = (f'<font name="{st["bolditalic_font"]}">Technologies</font>: '
                              f'{_esc(", ".join(techs))}')
                if team_size:
                    sub_markup += f"  ·  Team: {_esc(team_size)}"
            elif team_size:
                sub_markup = f"Team: {_esc(team_size)}"
            if sub_markup or loc_str:
                header_block.append(_serif_hrow(
                    Paragraph(sub_markup, st["sub_indent"]), loc_str, st["sub_right"],
                ))
            header_block.append(Spacer(1, 1))

            bullets = list(exp.get("responsibilities") or []) + list(exp.get("achievements") or [])
            dedup: list[str] = []
            seen: set[str] = set()
            for b in bullets:
                b_str = _safe(b)
                if not b_str or b_str.lower() in seen:
                    continue
                seen.add(b_str.lower())
                dedup.append(b_str)

            if dedup:
                header_block.append(_bullet_row(_esc(dedup[0]), st))
            story.append(KeepTogether(header_block))
            for b_str in dedup[1:]:
                story.append(_bullet_row(_esc(b_str), st))
            story.append(Spacer(1, _ITEM_GAP))

    # ── Projects ──────────────────────────────────────────────────────────────
    projects = resume.get("projects") or []
    if projects:
        story += _serif_section("Projects", st, p)
        for proj in projects:
            block: list = []
            p_name = _safe(proj.get("name"))
            url_raw = _safe(proj.get("url") or proj.get("github") or "")
            url = _normalize_url(url_raw) if url_raw else None
            tech = ", ".join(_safe(t) for t in (proj.get("technologies") or []) if _safe(t))
            proj_role = _safe(proj.get("role"))
            proj_type = _safe(proj.get("type"))
            p_start = _safe(proj.get("start_date"))
            p_end = _safe(proj.get("end_date"))
            name_lc = p_name.lower()

            head = f"<b>{_link(p_name, url, accent_hex)}</b>"
            descriptor = next((d for d in (proj_role, proj_type) if d and d.lower() not in name_lc), "")
            if descriptor:
                head += f" <b>({_esc(descriptor)})</b>"
            if tech:
                # Regular-weight separator + regular-italic tech (NOT bold-italic)
                # — explicit faces stop them inheriting the bold title weight.
                head += (f' <font name="{st["regular_font"]}">|</font> '
                         f'<font name="{st["italic_font"]}">{_esc(tech)}</font>')

            dates_str = _serif_dates(p_start, p_end)
            block.append(_serif_hrow(
                Paragraph(head, st["head"]), dates_str, st["head_right"],
            ))
            block.append(Spacer(1, 1))

            desc = _safe(proj.get("description"))
            if desc:
                block.append(_bullet_row(_esc(desc), st))
            for h in (proj.get("highlights") or []):
                h_str = _safe(h)
                if h_str:
                    block.append(_bullet_row(_esc(h_str), st))
            block.append(Spacer(1, _ITEM_GAP))
            story.append(KeepTogether(block))

    # ── Open Source ───────────────────────────────────────────────────────────
    oss = resume.get("open_source_contributions") or []
    if oss:
        story += _serif_section("Open Source", st, p)
        for o in oss:
            block = []
            proj = _safe(o.get("project"))
            role = _safe(o.get("role"))
            url_raw = _safe(o.get("url", ""))
            url = _normalize_url(url_raw) if url_raw else None
            stars = _safe(o.get("stars", ""))
            o_lang = _safe(o.get("language", ""))
            head = f"<b>{_link(proj, url, accent_hex)}</b>"
            if role:
                head += f" – <i>{_esc(role)}</i>"
            if o_lang:
                head += f"  <font color='{muted_hex}'>{_esc(o_lang)}</font>"
            if stars:
                head += f"  ★ {_esc(stars)}"
            block.append(Paragraph(head, st["head"]))
            o_desc = _safe(o.get("description", "")) or _safe(o.get("contribution", ""))
            if o_desc:
                block.append(Paragraph(_esc(o_desc), st["small"]))
            for contrib in (o.get("contributions") or []):
                c_str = _safe(contrib)
                if c_str:
                    block.append(_bullet_row(_esc(c_str), st))
            block.append(Spacer(1, _ITEM_GAP))
            story.append(KeepTogether(block))

    # ── Education ─────────────────────────────────────────────────────────────
    education = resume.get("education") or []
    if education:
        story += _serif_section("Education", st, p)
        for edu in education:
            block = []
            deg = _safe(edu.get("degree"))
            field = _safe(edu.get("field_of_study"))
            inst = _safe(edu.get("institution"))
            loc = _safe(edu.get("location"))
            start = _safe(edu.get("start_date"))
            end = _safe(edu.get("end_date")) or _safe(edu.get("graduation_year"))
            gpa = _safe(edu.get("gpa"))
            honors = _safe(edu.get("honors"))

            # Only append the field when the degree doesn't already mention it,
            # so "M.S. in Computer Science" + field "Computer Science" doesn't
            # become "...Computer Science in Computer Science".
            deg_line = deg
            if field and field.lower() not in deg.lower():
                deg_line = f"{deg} in {field}" if deg else field
            block.append(_serif_hrow(
                Paragraph(f"<b>{_esc(inst)}</b>" if inst else "", st["head"]),
                _serif_dates(start, end), st["head_right"],
            ))
            if deg_line or loc:
                block.append(_serif_hrow(
                    Paragraph(_esc(deg_line) if deg_line else "", st["sub"]),
                    loc, st["sub_right"],
                ))
            extras = []
            if gpa:
                extras.append(f"GPA: {_esc(gpa)}")
            if honors:
                extras.append(_esc(honors))
            cw = ", ".join(_safe(c) for c in (edu.get("relevant_coursework") or []) if _safe(c))
            if cw:
                extras.append(f"Coursework: {_esc(cw)}")
            if extras:
                block.append(Paragraph("  ·  ".join(extras), st["small"]))
            acts = ", ".join(_safe(a) for a in (edu.get("activities") or []) if _safe(a))
            if acts:
                block.append(Paragraph(f"Activities: {_esc(acts)}", st["small"]))
            block.append(Spacer(1, _ITEM_GAP))
            story.append(KeepTogether(block))

    # ── Technical Skills ──────────────────────────────────────────────────────
    skills = resume.get("technical_skills") or {}
    skill_cats = [
        ("Languages", skills.get("programming_languages")),
        ("Frameworks & Libraries", skills.get("frameworks_and_libraries")),
        ("Databases", skills.get("databases")),
        ("Cloud & Infrastructure", skills.get("cloud_and_infrastructure")),
        ("DevOps & Tooling", skills.get("devops_and_tools") or skills.get("tools_and_practices")),
        ("Testing", skills.get("testing")),
        ("Methodologies", skills.get("methodologies")),
        ("Soft Skills", skills.get("soft_skills")),
    ]
    skill_rows = [(k, ", ".join(_safe(x) for x in v if _safe(x))) for k, v in skill_cats if v]
    if skill_rows:
        story += _serif_section("Technical Skills", st, p)
        for label, vals in skill_rows:
            if vals:
                story.append(Paragraph(
                    f"<b>{_esc(label)}</b> : {_esc(vals)}", st["skill_line"],
                ))

    # ── Certifications ────────────────────────────────────────────────────────
    certs = resume.get("certifications") or []
    if certs:
        story += _serif_section("Certifications", st, p)
        for c in certs:
            c_name = _safe(c.get("name"))
            c_issuer = _safe(c.get("issuer"))
            c_date = _safe(c.get("date")) or _safe(c.get("year"))
            c_expiry = _safe(c.get("expiry"))
            c_cred_id = _safe(c.get("credential_id"))
            c_url_raw = _safe(c.get("url", ""))
            c_url = _normalize_url(c_url_raw) if c_url_raw else None
            line = f"<b>{_link(c_name, c_url, accent_hex)}</b>"
            if c_issuer:
                line += f" – <i>{_esc(c_issuer)}</i>"
            date_parts = []
            if c_date:
                date_parts.append(f"issued {_esc(c_date)}")
            if c_expiry:
                date_parts.append(f"expires {_esc(c_expiry)}")
            if date_parts:
                line += f"  <font color='{muted_hex}'>({', '.join(date_parts)})</font>"
            if c_cred_id:
                line += f"  <font color='{muted_hex}'>ID: {_esc(c_cred_id)}</font>"
            story.append(Paragraph(line, st["cert"]))
            story.append(Spacer(1, _ITEM_GAP))

    # ── Publications ──────────────────────────────────────────────────────────
    pubs = resume.get("publications") or []
    if pubs:
        story += _serif_section("Publications", st, p)
        for pub in pubs:
            title = _safe(pub.get("title"))
            venue = _safe(pub.get("venue"))
            date_pub = _safe(pub.get("date"))
            pub_type = _safe(pub.get("type", ""))
            url_raw = _safe(pub.get("url", ""))
            url = _normalize_url(url_raw) if url_raw else None
            authors = ", ".join(_safe(a) for a in (pub.get("authors") or []) if _safe(a))
            line = f"<b>{_link(title, url, accent_hex)}</b>"
            if pub_type and f"[{pub_type.lower()}]" not in title.lower():
                line += f"  <font color='{muted_hex}'>[{_esc(pub_type)}]</font>"
            if venue:
                line += f" – <i>{_esc(venue)}</i>"
            if date_pub:
                line += f"  ({_esc(date_pub)})"
            story.append(Paragraph(line, st["cert"]))
            if authors:
                story.append(Paragraph(_esc(authors), st["small"]))
            story.append(Spacer(1, _ITEM_GAP))

    # ── Patents ───────────────────────────────────────────────────────────────
    patents = resume.get("patents") or []
    if patents:
        story += _serif_section("Patents", st, p)
        for pt in patents:
            pt_title = _safe(pt.get("title"))
            pt_url_raw = _safe(pt.get("url", ""))
            pt_url = _normalize_url(pt_url_raw) if pt_url_raw else None
            line = f"<b>{_link(pt_title, pt_url, accent_hex)}</b>"
            num = _safe(pt.get("patent_number"))
            date_pt = _safe(pt.get("date"))
            if num:
                line += f" – {_esc(num)}"
            if date_pt:
                line += f"  ({_esc(date_pt)})"
            story.append(Paragraph(line, st["cert"]))
            desc = _safe(pt.get("description"))
            if desc:
                story.append(Paragraph(_esc(desc), st["small"]))
            story.append(Spacer(1, _ITEM_GAP))

    # ── Awards & Honors ───────────────────────────────────────────────────────
    awards = resume.get("awards_and_honors") or []
    if awards:
        story += _serif_section("Awards & Honors", st, p)
        for a in awards:
            if isinstance(a, dict):
                nm = _safe(a.get("name") or a.get("title"))
                issuer = _safe(a.get("issuer"))
                yr = _safe(a.get("year") or a.get("date"))
                v = nm + (f" – {issuer}" if issuer else "") + (f" ({yr})" if yr else "")
            else:
                v = _safe(a)
            if v:
                story.append(_bullet_row(_esc(v), st))

    # ── Volunteer Experience ──────────────────────────────────────────────────
    volunteer = resume.get("volunteer_experience") or []
    if volunteer:
        story += _serif_section("Volunteer Experience", st, p)
        for v in volunteer:
            org = _safe(v.get("organization"))
            role = _safe(v.get("role"))
            sd, ed = _safe(v.get("start_date")), _safe(v.get("end_date"))
            dates_str = _serif_dates(sd, ed)
            head_left = " – ".join([x for x in (org, role) if x])
            story.append(_serif_hrow(
                Paragraph(f"<b>{_esc(head_left)}</b>", st["head"]),
                dates_str, st["head_right"],
            ))
            desc = _safe(v.get("description"))
            if desc:
                story.append(Paragraph(_esc(desc), st["small"]))
            story.append(Spacer(1, _ITEM_GAP))

    # ── Languages ─────────────────────────────────────────────────────────────
    langs = resume.get("languages") or []
    if langs:
        story += _serif_section("Languages", st, p)
        parts = []
        for l in langs:
            lang = _safe(l.get("language"))
            prof = _safe(l.get("proficiency"))
            if lang:
                parts.append(f"<b>{_esc(lang)}</b>" + (f" ({_esc(prof)})" if prof else ""))
        story.append(Paragraph("  ·  ".join(parts), st["skill_line"]))

    # ── Interests ─────────────────────────────────────────────────────────────
    interests = [_safe(i) for i in (resume.get("interests") or []) if _safe(i)]
    if interests:
        story += _serif_section("Interests", st, p)
        story.append(Paragraph(_esc(", ".join(interests)), st["skill_line"]))

    # ── References ────────────────────────────────────────────────────────────
    references = resume.get("references")
    if references:
        story += _serif_section("References", st, p)
        if isinstance(references, str):
            story.append(Paragraph(_esc(references), st["skill_line"]))
        elif isinstance(references, list):
            for ref in references:
                ref_str = _safe(ref)
                if ref_str:
                    story.append(_bullet_row(_esc(ref_str), st))

    return story


def _render(resume: dict, template: TemplateName, base: float) -> bytes:
    p = PALETTES.get(template, PALETTES["classic_ats"])
    serif = template == "latex_serif"
    st = _serif_styles(p, base) if serif else _styles(p, base)
    buf = io.BytesIO()
    margin_x = _SERIF_MARGIN_X if serif else 0.6 * inch
    margin_top = _SERIF_MARGIN_TOP if serif else 0.55 * inch
    margin_bottom = _SERIF_MARGIN_BOTTOM if serif else 0.55 * inch
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=margin_x, rightMargin=margin_x,
        topMargin=margin_top, bottomMargin=margin_bottom,
        title=_safe(resume.get("personal_info", {}).get("full_name")) or "Resume",
        author=_safe(resume.get("personal_info", {}).get("full_name")) or "",
    )
    story = _build_story_serif(resume, p, st, base) if serif else _build_story(resume, p, st)
    bg_color = p.get("bg")
    if bg_color:
        def _draw_bg(canvas, doc, _c=bg_color):
            canvas.saveState()
            canvas.setFillColor(_c)
            canvas.rect(0, 0, letter[0], letter[1], fill=1, stroke=0)
            canvas.restoreState()
        doc.build(story, onFirstPage=_draw_bg, onLaterPages=_draw_bg)
    else:
        doc.build(story)
    return buf.getvalue()


def _page_count(pdf_bytes: bytes) -> int:
    """Cheap PDF page count without an external dep."""
    return max(1, pdf_bytes.count(b"/Type /Page") - pdf_bytes.count(b"/Type /Pages"))


def generate_pdf(
    resume: dict,
    template: TemplateName = "classic_ats",
    font_size: FontSize = "normal",
    max_pages: MaxPages = "auto",
) -> bytes:
    """Generate an ATS-friendly PDF resume from resume JSON. Returns PDF bytes."""
    from app.documents._normalize import normalize_resume, resolve_base_font_size
    resume = normalize_resume(resume)
    base = resolve_base_font_size(font_size)

    if max_pages in ("1", "2"):
        target = int(max_pages)
        # Try the requested size, then progressively shrink
        for trial in [base, base - 0.5, base - 1.0, base - 1.5, base - 2.0, base - 2.5]:
            data = _render(resume, template, max(8.0, trial))
            if _page_count(data) <= target:
                return data
        return data  # best effort
    return _render(resume, template, base)


# ─── Cover letter ────────────────────────────────────────────────────────────
#
# Layout:
#   - Sender block (top right): name, contact details
#   - Date
#   - Hiring manager / company block
#   - Body — paragraphs, generous leading, justified
#   - Signature


def _cl_styles(p: dict, base: float) -> dict:
    bf, bld = "Helvetica", "Helvetica-Bold"
    return {
        "name": ParagraphStyle(
            "Name", fontName=bld, fontSize=base + 4,
            textColor=p["name"], alignment=TA_RIGHT,
            spaceAfter=2, leading=(base + 4) * 1.15,
        ),
        "sender": ParagraphStyle(
            "Sender", fontName=bf, fontSize=base - 1.5,
            textColor=p["muted"], alignment=TA_RIGHT,
            spaceAfter=1, leading=(base - 1.5) * 1.5,
        ),
        "date": ParagraphStyle(
            "Date", fontName=bf, fontSize=base - 0.5,
            textColor=p["muted"], spaceBefore=18, spaceAfter=14,
        ),
        "to_block": ParagraphStyle(
            "To", fontName=bf, fontSize=base - 0.5,
            textColor=p["body"], spaceAfter=14, leading=(base - 0.5) * 1.45,
        ),
        "salutation": ParagraphStyle(
            "Salutation", fontName=bf, fontSize=base,
            textColor=p["body"], spaceAfter=10,
        ),
        "body": ParagraphStyle(
            "Body", fontName=bf, fontSize=base,
            textColor=p["body"], alignment=TA_JUSTIFY,
            leading=base * 1.55, spaceAfter=10, firstLineIndent=0,
        ),
        "signoff": ParagraphStyle(
            "Signoff", fontName=bf, fontSize=base,
            textColor=p["body"], spaceBefore=10, spaceAfter=4,
        ),
        "signature": ParagraphStyle(
            "Sig", fontName=bld, fontSize=base,
            textColor=p["name"], spaceAfter=0,
        ),
    }


def generate_cover_letter_pdf(
    cover_letter: str,
    resume: dict,
    template: TemplateName = "modern_clean",
    font_size: FontSize = "normal",
    hiring_manager: str | None = None,
    company_name: str | None = None,
    date_str: str | None = None,
) -> bytes:
    """Render a cover letter to a polished one-page PDF."""
    from app.documents._normalize import resolve_base_font_size
    p = PALETTES.get(template, PALETTES["modern_clean"])
    base = resolve_base_font_size(font_size)
    st = _cl_styles(p, base)
    accent_hex = _hex(p["accent"])

    pi = (resume or {}).get("personal_info", {}) or {}
    name = _safe(pi.get("full_name")) or "Your Name"

    contact_lines = []
    for k in ("email", "phone", "location"):
        v = _safe(pi.get(k))
        if v:
            contact_lines.append(_esc(v))
    for k in ("linkedin", "github", "website"):
        v = _safe(pi.get(k))
        if v:
            display = v.replace("https://", "").replace("http://", "").rstrip("/")
            contact_lines.append(_esc(display))

    buf = io.BytesIO()
    margin = 0.85 * inch
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=margin, rightMargin=margin,
        topMargin=0.85 * inch, bottomMargin=0.85 * inch,
        title=f"{name} - Cover Letter",
        author=name,
    )
    story: list = []

    # ── Sender block (right-aligned) ──────────────────────────────────────────
    story.append(Paragraph(_esc(name), st["name"]))
    for line in contact_lines:
        story.append(Paragraph(line, st["sender"]))

    # Subtle accent rule under the sender block (modern + executive only)
    if template != "classic_ats":
        story.append(Spacer(1, 6))
        story.append(HRFlowable(
            width="35%", thickness=1, color=p["accent"],
            spaceBefore=2, spaceAfter=4, hAlign="RIGHT",
        ))

    # ── Date ──────────────────────────────────────────────────────────────────
    display_date = date_str if date_str else date.today().strftime("%B %d, %Y")
    story.append(Paragraph(display_date, st["date"]))

    # ── Recipient ─────────────────────────────────────────────────────────────
    recip_lines = []
    if hiring_manager and hiring_manager.lower() not in ("hiring team", "hiring manager", ""):
        recip_lines.append(_esc(hiring_manager))
    if company_name:
        recip_lines.append(_esc(company_name))
    if recip_lines:
        story.append(Paragraph("<br/>".join(recip_lines), st["to_block"]))

    # ── Salutation ────────────────────────────────────────────────────────────
    salutation = "Dear Hiring Team,"
    if hiring_manager and hiring_manager.lower() not in ("hiring team", ""):
        # Use first name only when it looks like a real name
        first = hiring_manager.strip().split()[0]
        if first and first[0].isalpha():
            salutation = f"Dear {_esc(first)},"
    story.append(Paragraph(salutation, st["salutation"]))

    # ── Body ─────────────────────────────────────────────────────────────────
    # The body has already been normalised by the cover-letter agent
    # (no salutation, no sign-off, no name line) so the in-app preview and
    # this PDF render the IDENTICAL text. We just add letterhead/sign-off.
    text = (cover_letter or "").strip()
    paras = [pp.strip() for pp in text.split("\n\n") if pp.strip()]
    for para in paras:
        chunks = [_esc(c) for c in para.split("\n")]
        story.append(Paragraph("<br/>".join(chunks), st["body"]))

    # ── Signature ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Sincerely,", st["signoff"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(_esc(name), st["signature"]))

    bg_color = p.get("bg")
    if bg_color:
        def _draw_bg(canvas, doc, _c=bg_color):
            canvas.saveState()
            canvas.setFillColor(_c)
            canvas.rect(0, 0, letter[0], letter[1], fill=1, stroke=0)
            canvas.restoreState()
        doc.build(story, onFirstPage=_draw_bg, onLaterPages=_draw_bg)
    else:
        doc.build(story)
    return buf.getvalue()
