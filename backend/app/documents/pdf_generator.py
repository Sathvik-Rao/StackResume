"""PDF resume + cover-letter generators using ReportLab.

Templates: classic_ats | modern_clean | executive_dark | dark_theme

Design notes (2026 era, not 1990):
- Generous whitespace and clear typographic hierarchy.
- Name set large; role on its own line beneath.
- Contact rendered as one tidy inline list with bullet separators and live links.
- Section headers UPPERCASE with a hairline underline rule.
- Bullets use a true hanging indent and tight leading.
- Skills rendered as a clean 'Label : values' line block.
- For max_pages=1|2 the resume generator transparently shrinks the body until it fits.
"""
from __future__ import annotations
import io
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


TemplateName = Literal["classic_ats", "modern_clean", "executive_dark", "dark_theme"]
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


_CONTENT_W = letter[0] - 2 * (0.6 * inch)  # 525.6pt for letter + 0.6in margins
_BULLET_COL = 11  # pt: visual indent from bullet to text (consistent at all font sizes)
_TEXT_COL = _CONTENT_W - _BULLET_COL


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


def _bullet_row(text_markup: str, st: dict) -> Table:
    """Two-cell table bullet: col-0=•, col-1=text.
    Continuation lines align perfectly because they're in their own column.
    """
    t = Table(
        [[Paragraph("•", st["bullet_mark"]), Paragraph(text_markup, st["bullet_body"])]],
        colWidths=[_BULLET_COL, _TEXT_COL],
    )
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
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


def _render(resume: dict, template: TemplateName, base: float) -> bytes:
    p = PALETTES.get(template, PALETTES["classic_ats"])
    st = _styles(p, base)
    buf = io.BytesIO()
    margin = 0.6 * inch
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=margin, rightMargin=margin,
        topMargin=0.55 * inch, bottomMargin=0.55 * inch,
        title=_safe(resume.get("personal_info", {}).get("full_name")) or "Resume",
        author=_safe(resume.get("personal_info", {}).get("full_name")) or "",
    )
    story = _build_story(resume, p, st)
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
