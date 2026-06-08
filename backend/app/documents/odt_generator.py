"""ODT resume + cover-letter generators using odfpy.

Visual parity with the PDF + DOCX renderers so the same resume looks consistent
across all three formats: classic_ats / modern_clean / executive_dark.
"""
from __future__ import annotations

import io
import os
import re
import zipfile
from datetime import date
from typing import Literal

from odf.opendocument import OpenDocumentText
from odf.style import (
    Style, TextProperties, ParagraphProperties, TableColumnProperties,
    TableProperties, TableCellProperties, TabStop, TabStops, GraphicProperties,
)
from odf.text import P, Span, A, Tab, S
from odf.table import Table, TableColumn, TableRow, TableCell
from odf.draw import Frame, Image as DrawImage


TemplateName = Literal[
    "classic_ats", "modern_clean", "executive_dark", "dark_theme", "latex_serif"
]
FontSize = Literal["small", "normal", "large"]


PALETTES_HEX = {
    "classic_ats": {
        "name": "#000000", "title": "#222222", "header": "#000000",
        "rule": "#000000", "body": "#1a1a1a", "muted": "#555555", "accent": "#000000",
    },
    "modern_clean": {
        "name": "#0b1437", "title": "#3b4dc8", "header": "#0b1437",
        "rule": "#3b4dc8", "body": "#1f2540", "muted": "#5a6079", "accent": "#3b4dc8",
    },
    "executive_dark": {
        "name": "#0f172a", "title": "#475569", "header": "#0f172a",
        "rule": "#94a3b8", "body": "#1e293b", "muted": "#64748b", "accent": "#334155",
    },
    "dark_theme": {
        "bg": "#0d0f1a",
        "name": "#e8eaf2", "title": "#a4a8ff", "header": "#e8eaf2",
        "rule": "#7c83ff", "body": "#d0d4e8", "muted": "#9098b3", "accent": "#a4a8ff",
    },
    # latex_serif is a PDF-only serif layout; for ODT we fall back to a clean
    # all-black light palette so the same selection still exports sensibly.
    "latex_serif": {
        "name": "#000000", "title": "#1a1a1a", "header": "#000000",
        "rule": "#000000", "body": "#111111", "muted": "#333333", "accent": "#000000",
    },
}

FONT_SIZES = {"small": 9.5, "normal": 10.5, "large": 11.5}

# Matches `_ITEM_GAP` in pdf/generator/_story.py — the vertical breathing room
# between two consecutive items inside a section. Same constant across all
# three renderers so a resume looks identical in PDF/DOCX/ODT.
_ITEM_GAP_PT = 4


def _safe(v) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        # Defensive: undo upstream `list(<string>)` that turned a sentence into
        # ["A","c","t","i","v","i","t","i","e","s",...].
        if len(v) >= 4 and all(isinstance(x, str) for x in v):
            singles = sum(1 for s in v if len(s) <= 1)
            if singles / len(v) >= 0.8:
                joined = "".join(v).strip()
                if joined:
                    return joined
        return ", ".join(_safe(x) for x in v if _safe(x))
    if isinstance(v, dict):
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


def _normalize_url(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    if s.startswith("http://") or s.startswith("https://") or s.startswith("mailto:"):
        return s
    if "@" in s and "://" not in s:
        return f"mailto:{s}"
    return f"https://{s}"


class _Styles:
    """Registers reusable text/paragraph styles. Created once per document."""

    def __init__(self, doc: OpenDocumentText, palette: dict, base: float):
        self.doc = doc
        self.palette = palette
        self.base = base
        self._counter = 0
        self._cache: dict[str, str] = {}
        self._icon_frame_style = None

    def _next(self) -> str:
        self._counter += 1
        return f"AutoStyle{self._counter}"

    def text(self, *, size: float, color: str, bold: bool = False, italic: bool = False,
             font: str = "Helvetica", small_caps: bool = False) -> str:
        key = f"t/{size}/{color}/{int(bold)}/{int(italic)}/{font}/{int(small_caps)}"
        if key in self._cache:
            return self._cache[key]
        name = self._next()
        s = Style(name=name, family="text")
        tp_kwargs = dict(
            fontname=font,
            fontsize=f"{size}pt",
            color=color,
            fontweight="bold" if bold else "normal",
            fontstyle="italic" if italic else "normal",
        )
        if small_caps:
            tp_kwargs["fontvariant"] = "small-caps"
        s.addElement(TextProperties(**tp_kwargs))
        self.doc.automaticstyles.addElement(s)
        self._cache[key] = name
        return name

    def hyperlink(self, color: str, size: float, font: str = "Helvetica",
                  bold: bool = False, underline: bool = True) -> str:
        key = f"hl/{color}/{size}/{font}/{int(bold)}/{int(underline)}"
        if key in self._cache:
            return self._cache[key]
        name = self._next()
        s = Style(name=name, family="text")
        tp_kwargs = dict(
            fontname=font,
            fontsize=f"{size}pt",
            color=color,
            fontweight="bold" if bold else "normal",
        )
        if underline:
            tp_kwargs["textunderlinetype"] = "single"
            tp_kwargs["textunderlinestyle"] = "solid"
        s.addElement(TextProperties(**tp_kwargs))
        self.doc.automaticstyles.addElement(s)
        self._cache[key] = name
        return name

    def icon_frame(self):
        """Graphic Style object for an inline icon image (odfpy's Frame needs the
        Style object, not its name): centred on the text line, no border, inline."""
        if self._icon_frame_style is None:
            s = Style(name=self._next(), family="graphic")
            # For an as-char frame only the vertical alignment matters; setting
            # horizontal pos/wrap turns it into a floating frame and spawns blank
            # pages, so keep it minimal.
            s.addElement(GraphicProperties(
                verticalrel="text", verticalpos="middle",
                border="none", padding="0cm",
            ))
            self.doc.automaticstyles.addElement(s)
            self._icon_frame_style = s
        return self._icon_frame_style

    def para(
        self,
        *,
        align: str = "left",
        space_before: float = 0,
        space_after: float = 0,
        line_height: float | None = None,
        bottom_border: str | None = None,
        left_indent: float = 0,
        first_line_indent: float = 0,
        right_tab_cm: float | None = None,
        border_weight: str = "0.5pt",
    ) -> str:
        key = (f"p/{align}/{space_before}/{space_after}/{line_height}/{bottom_border}/"
               f"{left_indent}/{first_line_indent}/{right_tab_cm}/{border_weight}")
        if key in self._cache:
            return self._cache[key]
        name = self._next()
        s = Style(name=name, family="paragraph")
        attrs = {
            "textalign": align,
            "marginbottom": f"{space_after}pt",
            "margintop": f"{space_before}pt",
        }
        if line_height:
            attrs["lineheight"] = f"{int(line_height * 100)}%"
        if bottom_border:
            attrs["borderbottom"] = f"{border_weight} solid {bottom_border}"
            attrs["paddingbottom"] = "1pt"
        if left_indent:
            attrs["marginleft"] = f"{left_indent}pt"
        if first_line_indent:
            attrs["textindent"] = f"{first_line_indent}pt"
        pp = ParagraphProperties(**attrs)
        if right_tab_cm is not None:
            # Right-aligned tab at the text-area edge → LaTeX \hfill behaviour.
            ts = TabStops()
            ts.addElement(TabStop(position=f"{right_tab_cm}cm", type="right"))
            pp.addElement(ts)
        elif left_indent and first_line_indent and first_line_indent < 0:
            # Tab stop at the indent so "•\t" aligns continuation lines exactly.
            ts = TabStops()
            ts.addElement(TabStop(position=f"{left_indent}pt", type="left"))
            pp.addElement(ts)
        s.addElement(pp)
        self.doc.automaticstyles.addElement(s)
        self._cache[key] = name
        return name


def _run(p: P, styles: _Styles, text: str, *, size: float, color: str,
         bold: bool = False, italic: bool = False):
    span = Span(stylename=styles.text(size=size, color=color, bold=bold, italic=italic))
    span.addText(text)
    p.addElement(span)


def _link(p: P, styles: _Styles, text: str, url: str, color: str, size: float):
    a = A(href=url, type="simple")
    span = Span(stylename=styles.hyperlink(color, size))
    span.addText(text)
    a.addElement(span)
    p.addElement(a)


def _section(doc: OpenDocumentText, styles: _Styles, title: str):
    p_style = styles.para(
        align="left",
        space_before=10,
        space_after=4,
        line_height=1.15,
        bottom_border=styles.palette["rule"],
    )
    p = P(stylename=p_style)
    _run(p, styles, title.upper(), size=styles.base + 0.5,
         color=styles.palette["header"], bold=True)
    doc.text.addElement(p)


def _add_para(doc: OpenDocumentText, p: P):
    doc.text.addElement(p)


def _item_gap(doc: OpenDocumentText, styles: "_Styles"):
    """Vertical gap between two list-section items (matches PDF Spacer)."""
    p = P(stylename=styles.para(space_after=0, line_height=1.0))
    _run(p, styles, "", size=_ITEM_GAP_PT, color="#ffffff")
    _add_para(doc, p)


def _bullet(doc: OpenDocumentText, styles: _Styles, text: str):
    p_style = styles.para(
        align="justify",
        space_after=2,
        line_height=1.45,
        left_indent=11,
        first_line_indent=-11,
    )
    p = P(stylename=p_style)
    _run(p, styles, "•", size=styles.base - 0.5, color=styles.palette["body"])
    p.addElement(Tab())
    _run(p, styles, text, size=styles.base - 0.5, color=styles.palette["body"])
    _add_para(doc, p)


def _two_col_row_custom(doc: OpenDocumentText, styles: "_Styles",
                        fill_left, fill_right):
    """Borderless 2-col row where each cell is populated by a callback.

    Mirrors :func:`docx_generator._two_col_row_custom` — use when the left
    side needs more than a single styled run (e.g. a hyperlinked project name
    plus a muted tech list).
    """
    table_name = f"two_col_c_{styles._next()}"
    col_style_l = Style(name=f"{table_name}_l", family="table-column")
    col_style_l.addElement(TableColumnProperties(columnwidth="11.5cm"))
    col_style_r = Style(name=f"{table_name}_r", family="table-column")
    col_style_r.addElement(TableColumnProperties(columnwidth="6cm"))
    cell_style = Style(name=f"{table_name}_cell", family="table-cell")
    cell_style.addElement(TableCellProperties(
        padding="0pt",
        bordertop="none", borderbottom="none",
        borderleft="none", borderright="none",
    ))
    table_style = Style(name=table_name, family="table")
    table_style.addElement(TableProperties(width="17.5cm", align="left"))
    for s in (col_style_l, col_style_r, cell_style, table_style):
        styles.doc.automaticstyles.addElement(s)

    tbl = Table(stylename=table_name)
    tbl.addElement(TableColumn(stylename=col_style_l))
    tbl.addElement(TableColumn(stylename=col_style_r))
    row = TableRow()
    lcell = TableCell(stylename=cell_style)
    rcell = TableCell(stylename=cell_style)

    lp = P(stylename=styles.para(align="left", line_height=1.2))
    fill_left(lp)
    lcell.addElement(lp)

    rp = P(stylename=styles.para(align="right", line_height=1.3))
    fill_right(rp)
    rcell.addElement(rp)

    row.addElement(lcell)
    row.addElement(rcell)
    tbl.addElement(row)
    doc.text.addElement(tbl)


def _two_col_row(doc: OpenDocumentText, styles: _Styles,
                 left_text: str, right_text: str,
                 left_size: float, left_color: str, left_bold: bool,
                 right_size: float, right_color: str):
    table_name = f"two_col_{styles._next()}"
    col_style_l = Style(name=f"{table_name}_l", family="table-column")
    col_style_l.addElement(TableColumnProperties(columnwidth="11.5cm"))
    col_style_r = Style(name=f"{table_name}_r", family="table-column")
    col_style_r.addElement(TableColumnProperties(columnwidth="6cm"))
    cell_style = Style(name=f"{table_name}_cell", family="table-cell")
    # Explicitly zero every border so LibreOffice doesn't draw the default
    # 0.5pt cell outline.
    cell_style.addElement(TableCellProperties(
        padding="0pt",
        bordertop="none", borderbottom="none",
        borderleft="none", borderright="none",
    ))
    table_style = Style(name=table_name, family="table")
    table_style.addElement(TableProperties(width="17.5cm", align="left"))
    for s in (col_style_l, col_style_r, cell_style, table_style):
        styles.doc.automaticstyles.addElement(s)

    tbl = Table(stylename=table_name)
    tbl.addElement(TableColumn(stylename=col_style_l))
    tbl.addElement(TableColumn(stylename=col_style_r))
    row = TableRow()
    lcell = TableCell(stylename=cell_style)
    rcell = TableCell(stylename=cell_style)

    lp = P(stylename=styles.para(align="left", line_height=1.2))
    _run(lp, styles, left_text, size=left_size, color=left_color, bold=left_bold)
    lcell.addElement(lp)

    rp = P(stylename=styles.para(align="right", line_height=1.3))
    _run(rp, styles, right_text, size=right_size, color=right_color)
    rcell.addElement(rp)

    row.addElement(lcell)
    row.addElement(rcell)
    tbl.addElement(row)
    doc.text.addElement(tbl)


def _make_doc(*, side_cm: float, vert_cm: float, bg_color: str | None = None) -> OpenDocumentText:
    doc = OpenDocumentText()
    from odf.style import PageLayout, PageLayoutProperties, MasterPage
    pl = PageLayout(name="StdLayout")
    props_kwargs: dict = dict(
        pagewidth="21cm",
        pageheight="29.7cm",
        marginleft=f"{side_cm}cm",
        marginright=f"{side_cm}cm",
        margintop=f"{vert_cm}cm",
        marginbottom=f"{vert_cm}cm",
        printorientation="portrait",
    )
    if bg_color:
        props_kwargs["backgroundcolor"] = bg_color
    pl.addElement(PageLayoutProperties(**props_kwargs))
    doc.automaticstyles.addElement(pl)
    mp = MasterPage(name="Standard", pagelayoutname="StdLayout")
    doc.masterstyles.addElement(mp)
    return doc


# ═══════════════════════════════════════════════════════════════════════════
# latex_serif — ODT twin of the PDF's LaTeX layout (Computer Modern + Font
# Awesome icons embedded, small-caps name, Title-Case ruled headers, hfill rows,
# italic technologies line, itemize-indented bullets).
# ═══════════════════════════════════════════════════════════════════════════

_FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")
_CMU = "CMU Serif"
_FA_SOLID = "SR FA Solid"
_FA_BRANDS = "SR FA Brands"
_FA_ICONS = {
    "phone":    (_FA_SOLID, ""),   # faPhone
    "email":    (_FA_SOLID, ""),   # faEnvelope
    "location": (_FA_SOLID, ""),   # faMapMarker
    "linkedin": (_FA_BRANDS, ""),  # faLinkedin
    "github":   (_FA_BRANDS, ""),  # faGithub
    "web":      (_FA_SOLID, ""),   # faGlobe
}
_SERIF_CONTENT_CM = (8.5 - 2 * 0.4) * 2.54   # 19.558cm (Letter, 0.4in margins)
_SERIF_BULLET_POS_PT = 14
_SERIF_BULLET_TEXT_PT = 25

# Embedded font-face declarations (LibreOffice "loext" weight/style mapping).
# Only the Computer Modern text faces are embedded here — LibreOffice does NOT
# render embedded *icon* fonts in ODT, so contact icons are inlined as PNGs
# (rasterised from the same Font Awesome glyphs) instead.
_LOEXT_NS = "urn:org:documentfoundation:names:experimental:office:xmlns:loext:1.0"
_EMBED_ODT_FONTS = [
    ("CMUSerif-Roman.ttf",      _CMU, "normal", "normal", "roman"),
    ("CMUSerif-Bold.ttf",       _CMU, "normal", "bold",   "roman"),
    ("CMUSerif-Italic.ttf",     _CMU, "italic", "normal", "roman"),
    ("CMUSerif-BoldItalic.ttf", _CMU, "italic", "bold",   "roman"),
]
_FA_FILES = {_FA_SOLID: "fa-solid-900.ttf", _FA_BRANDS: "fa-brands-400.ttf"}
_ICON_PNG_CACHE: dict[str, tuple[bytes, float]] = {}


def _fa_icon_png(kind: str, color_hex: str, px: int = 72) -> tuple[bytes, float] | None:
    """Rasterise a Font Awesome glyph to a transparent PNG (cached). Returns
    (png_bytes, width/height aspect) or None if Pillow/the font is unavailable."""
    key = f"{kind}/{color_hex}"
    if key in _ICON_PNG_CACHE:
        return _ICON_PNG_CACHE[key]
    spec = _FA_ICONS.get(kind)
    if not spec:
        return None
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None
    face, glyph = spec
    h = color_hex.lstrip("#")
    rgb = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
    font = ImageFont.truetype(os.path.join(_FONTS_DIR, _FA_FILES[face]), px)
    probe = ImageDraw.Draw(Image.new("RGBA", (px * 2, px * 2)))
    bbox = probe.textbbox((0, 0), glyph, font=font)
    w, ht = bbox[2] - bbox[0], bbox[3] - bbox[1]
    img = Image.new("RGBA", (w + 4, ht + 4), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((-bbox[0] + 2, -bbox[1] + 2), glyph, font=font, fill=rgb)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    out = (buf.getvalue(), img.width / img.height)
    _ICON_PNG_CACHE[key] = out
    return out


def _serif_dates(start: str, end: str) -> str:
    if start and end:
        return f"{start} – {end}"
    return end or start or ""


def _srun(p: P, styles: "_Styles", text: str, size: float, color: str,
          *, bold=False, italic=False, font=_CMU, small_caps=False):
    span = Span(stylename=styles.text(size=size, color=color, bold=bold,
                                      italic=italic, font=font, small_caps=small_caps))
    span.addText(text)
    p.addElement(span)


def _slink(p: P, styles: "_Styles", text: str, url: str, color: str, size: float,
           *, bold=False, underline=True):
    a = A(href=url, type="simple")
    span = Span(stylename=styles.hyperlink(color, size, font=_CMU, bold=bold, underline=underline))
    span.addText(text)
    a.addElement(span)
    p.addElement(a)


def _sicon(p: P, styles: "_Styles", kind: str, color: str, size: float):
    """Inline a Font Awesome icon as a PNG image (LibreOffice won't render an
    embedded icon font in ODT, but inline images always render)."""
    out = _fa_icon_png(kind, color)
    if not out:
        return
    png, aspect = out
    href = styles.doc.addPictureFromString(png, "image/png")
    h_in = (size * 0.95) / 72.0
    w_in = h_in * aspect
    frame = Frame(
        stylename=styles.icon_frame(),
        width=f"{w_in:.3f}in", height=f"{h_in:.3f}in",
        anchortype="as-char",
    )
    frame.addElement(DrawImage(href=href, type="simple", show="embed", actuate="onLoad"))
    p.addElement(frame)
    p.addElement(S(c=1))  # real space (ODF collapses literal spaces)


def _ssection(doc: OpenDocumentText, styles: "_Styles", title: str):
    p = P(stylename=styles.para(align="left", space_before=6, space_after=3,
                                line_height=1.05, bottom_border=styles.palette["rule"],
                                border_weight="0.6pt"))
    _srun(p, styles, title, styles.base + 2.5, styles.palette["header"], bold=True)
    doc.text.addElement(p)


def _serif_gap(doc: OpenDocumentText, styles: "_Styles"):
    p = P(stylename=styles.para(space_after=0, line_height=1.0))
    _srun(p, styles, "", 3, "#ffffff")
    doc.text.addElement(p)


def _shrow(doc: OpenDocumentText, styles: "_Styles", fill_left, right_text: str,
           right_size: float, right_color: str, *, right_bold=True,
           right_italic=False, space_after=0):
    p = P(stylename=styles.para(align="left", space_after=space_after,
                                line_height=1.12, right_tab_cm=_SERIF_CONTENT_CM))
    fill_left(p)
    if right_text:
        p.addElement(Tab())
        _srun(p, styles, right_text, right_size, right_color,
              bold=right_bold, italic=right_italic)
    doc.text.addElement(p)


def _sbullet(doc: OpenDocumentText, styles: "_Styles", text: str):
    p = P(stylename=styles.para(
        align="justify", space_after=1, line_height=1.18,
        left_indent=_SERIF_BULLET_TEXT_PT,
        first_line_indent=-(_SERIF_BULLET_TEXT_PT - _SERIF_BULLET_POS_PT)))
    _srun(p, styles, "•", styles.base - 0.5, styles.palette["body"])
    p.addElement(Tab())
    _srun(p, styles, text, styles.base - 0.5, styles.palette["body"])
    doc.text.addElement(p)


def _embed_fonts_odt(odt_bytes: bytes) -> bytes:
    """Embed CMU Serif + Font Awesome into the .odt (ODF font embedding) so the
    LaTeX look renders without the fonts installed."""
    zin = zipfile.ZipFile(io.BytesIO(odt_bytes))
    items: dict[str, bytes] = {n: zin.read(n) for n in zin.namelist()}

    # 1) Font binaries (ODF stores them unobfuscated).
    for fn, *_ in _EMBED_ODT_FONTS:
        items[f"Fonts/{fn}"] = open(os.path.join(_FONTS_DIR, fn), "rb").read()

    # 2) manifest entries.
    man = items["META-INF/manifest.xml"].decode()
    seen = set()
    entries = ""
    for fn, *_ in _EMBED_ODT_FONTS:
        if fn in seen:
            continue
        seen.add(fn)
        entries += (f'<manifest:file-entry manifest:full-path="Fonts/{fn}" '
                    f'manifest:media-type="application/x-font-ttf"/>')
    man = man.replace("</manifest:manifest>", entries + "</manifest:manifest>")
    items["META-INF/manifest.xml"] = man.encode()

    # 3) font-face-decls with embedded src, grouped per family.
    by_family: dict[str, list] = {}
    generic: dict[str, str] = {}
    for fn, fam, style, weight, gen in _EMBED_ODT_FONTS:
        by_family.setdefault(fam, []).append((fn, style, weight))
        generic[fam] = gen
    faces = ""
    for fam, srcs in by_family.items():
        gen_attr = f' style:font-family-generic="{generic[fam]}"' if generic[fam] != "system" else ""
        faces += (f'<style:font-face style:name="{fam}" svg:font-family="{fam}"'
                  f'{gen_attr} style:font-pitch="variable"><svg:font-face-src>')
        for fn, style, weight in srcs:
            faces += (f'<svg:font-face-uri xlink:href="Fonts/{fn}" xlink:type="simple" '
                      f'loext:font-style="{style}" loext:font-weight="{weight}">'
                      f'<svg:font-face-format svg:string="truetype"/></svg:font-face-uri>')
        faces += "</svg:font-face-src></style:font-face>"
    decls = f"<office:font-face-decls>{faces}</office:font-face-decls>"

    # Inject the embedded font-face-decls into BOTH content.xml and styles.xml —
    # LibreOffice reads embedded fonts from the styles part.
    for part, root, anchor in (
        ("content.xml", "office:document-content", "<office:automatic-styles"),
        ("styles.xml", "office:document-styles", "<office:styles"),
    ):
        if part not in items:
            continue
        x = items[part].decode()
        if "xmlns:loext" not in x:
            x = x.replace(f"<{root} ", f'<{root} xmlns:loext="{_LOEXT_NS}" ', 1)
        if "<office:font-face-decls>" in x:
            # lambda replacement avoids re.sub interpreting backslashes/\g in decls
            x = re.sub(r"<office:font-face-decls>.*?</office:font-face-decls>",
                       lambda _m: decls, x, count=1, flags=re.S)
        elif "<office:font-face-decls/>" in x:
            x = x.replace("<office:font-face-decls/>", decls, 1)
        elif anchor in x:
            x = x.replace(anchor, decls + anchor, 1)
        items[part] = x.encode()

    # 4) settings.xml with EmbedFonts=true — REQUIRED for LibreOffice to actually
    #    use the embedded fonts on open (odfpy writes no settings.xml).
    items["settings.xml"] = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<office:document-settings '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0">'
        '<office:settings><config:config-item-set '
        'config:name="ooo:configuration-settings">'
        '<config:config-item config:name="EmbedFonts" config:type="boolean">true'
        '</config:config-item></config:config-item-set></office:settings>'
        '</office:document-settings>'
    ).encode()
    man = items["META-INF/manifest.xml"].decode()
    if "settings.xml" not in man:
        man = man.replace("</manifest:manifest>",
            '<manifest:file-entry manifest:full-path="settings.xml" '
            'manifest:media-type="text/xml"/></manifest:manifest>')
        items["META-INF/manifest.xml"] = man.encode()

    # 5) Re-zip — mimetype MUST be first and stored uncompressed.
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        if "mimetype" in items:
            zi = zipfile.ZipInfo("mimetype")
            zi.compress_type = zipfile.ZIP_STORED
            zout.writestr(zi, items.pop("mimetype"))
        for n, d in items.items():
            zout.writestr(n, d)
    return out.getvalue()


def _build_resume_doc_serif(resume: dict, base: float) -> OpenDocumentText:
    """LaTeX-style ODT (Computer Modern + Font Awesome) matching the PDF."""
    palette = PALETTES_HEX["latex_serif"]
    body, muted, accent = palette["body"], palette["muted"], palette["accent"]
    doc = _make_doc(side_cm=0.4 * 2.54, vert_cm=0.36 * 2.54)
    styles = _Styles(doc, palette, base)
    pi = resume.get("personal_info", {}) or {}

    # ── Header: small-caps name, optional title, icon contact line ──────────
    name = _safe(pi.get("full_name")) or "Your Name"
    p = P(stylename=styles.para(align="center", space_after=1, line_height=1.0))
    _srun(p, styles, name, base + 12, palette["name"], bold=True, small_caps=True)
    doc.text.addElement(p)

    role = _safe(pi.get("professional_title"))
    if role:
        p = P(stylename=styles.para(align="center", space_after=2, line_height=1.2))
        _srun(p, styles, role, base + 0.5, muted, italic=True)
        doc.text.addElement(p)

    contact = [(k, _safe(pi.get(k))) for k in
               ("phone", "email", "location", "linkedin", "github", "website", "portfolio")]
    contact = [(k, v) for k, v in contact if v]
    if contact:
        cp = P(stylename=styles.para(align="center", space_after=2, line_height=1.3))
        csize = base - 0.5
        first = True
        for key, v in contact:
            if not first:
                cp.addElement(S(c=4))  # gap between contact items
            first = False
            kind = {"website": "web", "portfolio": "web"}.get(key, key)
            _sicon(cp, styles, kind, body, csize)
            if key in ("phone", "location"):
                _srun(cp, styles, v, csize, body)
            elif key == "email":
                _slink(cp, styles, v, _normalize_url(v), accent, csize)
            else:
                disp = v.replace("https://", "").replace("http://", "").rstrip("/")
                _slink(cp, styles, disp, _normalize_url(v), accent, csize)
        doc.text.addElement(cp)

    # ── Summary ─────────────────────────────────────────────────────────────
    summary = _safe(resume.get("professional_summary", ""))
    if summary:
        _ssection(doc, styles, "Summary")
        p = P(stylename=styles.para(align="justify", space_after=1, line_height=1.2))
        _srun(p, styles, summary, base, body)
        doc.text.addElement(p)

    # ── Core Competencies ───────────────────────────────────────────────────
    competencies = [_safe(c) for c in (resume.get("core_competencies") or []) if _safe(c)]
    if competencies:
        _ssection(doc, styles, "Core Competencies")
        cols = 3
        rows = (len(competencies) + cols - 1) // cols
        tname = f"scomp_{styles._next()}"
        col = Style(name=f"{tname}_c", family="table-column")
        col.addElement(TableColumnProperties(columnwidth="6.5cm"))
        cell = Style(name=f"{tname}_cell", family="table-cell")
        cell.addElement(TableCellProperties(padding="0pt", bordertop="none",
                        borderbottom="none", borderleft="none", borderright="none"))
        ts = Style(name=tname, family="table")
        ts.addElement(TableProperties(width=f"{_SERIF_CONTENT_CM}cm", align="left"))
        for s in (col, cell, ts):
            doc.automaticstyles.addElement(s)
        tbl = Table(stylename=tname)
        for _ in range(cols):
            tbl.addElement(TableColumn(stylename=col))
        for r in range(rows):
            tr = TableRow()
            for c in range(cols):
                idx = c * rows + r
                tc = TableCell(stylename=cell)
                if idx < len(competencies):
                    pp = P(stylename=styles.para(space_after=1.5, line_height=1.2))
                    _srun(pp, styles, f"•  {competencies[idx]}", base - 0.5, body)
                    tc.addElement(pp)
                else:
                    tc.addElement(P())
                tr.addElement(tc)
            tbl.addElement(tr)
        doc.text.addElement(tbl)

    # ── Professional Experience ─────────────────────────────────────────────
    experience = resume.get("experience") or []
    if experience:
        _ssection(doc, styles, "Professional Experience")
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
            _shrow(doc, styles,
                   lambda p, t=head_left: _srun(p, styles, t, base, body, bold=True),
                   _serif_dates(start, end), base, body, right_bold=True)

            techs = [_safe(t) for t in (exp.get("technologies") or []) if _safe(t)]
            team = _safe(exp.get("team_size"))
            if techs or team or loc_str:
                def _tech(p, _techs=techs, _team=team):
                    if _techs:
                        _srun(p, styles, "Technologies", base - 0.5, body, bold=True, italic=True)
                        _srun(p, styles, f": {', '.join(_techs)}", base - 0.5, body, italic=True)
                        if _team:
                            _srun(p, styles, f"  ·  Team: {_team}", base - 0.5, body, italic=True)
                    elif _team:
                        _srun(p, styles, f"Team: {_team}", base - 0.5, body, italic=True)
                _shrow(doc, styles, _tech, loc_str, base - 0.5, body,
                       right_bold=False, right_italic=True)

            bullets = list(exp.get("responsibilities") or []) + list(exp.get("achievements") or [])
            seen: set[str] = set()
            for b in bullets:
                bs = _safe(b)
                if bs and bs.lower() not in seen:
                    seen.add(bs.lower())
                    _sbullet(doc, styles, bs)
            _serif_gap(doc, styles)

    # ── Projects ────────────────────────────────────────────────────────────
    projects = resume.get("projects") or []
    if projects:
        _ssection(doc, styles, "Projects")
        for proj in projects:
            p_name = _safe(proj.get("name"))
            url_raw = _safe(proj.get("url") or proj.get("github") or "")
            url = _normalize_url(url_raw) if url_raw else None
            tech = ", ".join(_safe(t) for t in (proj.get("technologies") or []) if _safe(t))
            descriptor = next((d for d in (_safe(proj.get("role")), _safe(proj.get("type")))
                               if d and d.lower() not in p_name.lower()), "")
            dates_str = _serif_dates(_safe(proj.get("start_date")), _safe(proj.get("end_date")))

            def _phead(p, _n=p_name, _u=url, _d=descriptor, _t=tech):
                if _u:
                    _slink(p, styles, _n, _u, body, base, bold=True, underline=False)
                else:
                    _srun(p, styles, _n, base, body, bold=True)
                if _d:
                    _srun(p, styles, f" ({_d})", base, body, bold=True)
                if _t:
                    _srun(p, styles, " | ", base, body)
                    _srun(p, styles, _t, base - 0.5, body, italic=True)
            _shrow(doc, styles, _phead, dates_str, base, body, right_bold=True)
            desc = _safe(proj.get("description"))
            if desc:
                _sbullet(doc, styles, desc)
            for h in (proj.get("highlights") or []):
                if _safe(h):
                    _sbullet(doc, styles, _safe(h))
            _serif_gap(doc, styles)

    # ── Education ───────────────────────────────────────────────────────────
    education = resume.get("education") or []
    if education:
        _ssection(doc, styles, "Education")
        for edu in education:
            deg = _safe(edu.get("degree"))
            field = _safe(edu.get("field_of_study"))
            inst = _safe(edu.get("institution"))
            loc = _safe(edu.get("location"))
            start = _safe(edu.get("start_date"))
            end = _safe(edu.get("end_date")) or _safe(edu.get("graduation_year"))
            deg_line = deg
            if field and field.lower() not in deg.lower():
                deg_line = f"{deg} in {field}" if deg else field
            _shrow(doc, styles,
                   lambda p, t=inst: _srun(p, styles, t, base, body, bold=True),
                   _serif_dates(start, end), base, body, right_bold=True)
            if deg_line or loc:
                _shrow(doc, styles,
                       lambda p, t=deg_line: _srun(p, styles, t, base - 0.5, body, italic=True),
                       loc, base - 0.5, body, right_bold=False, right_italic=True)
            extras = []
            if _safe(edu.get("gpa")):
                extras.append(f"GPA: {_safe(edu.get('gpa'))}")
            if _safe(edu.get("honors")):
                extras.append(_safe(edu.get("honors")))
            cw = ", ".join(_safe(c) for c in (edu.get("relevant_coursework") or []) if _safe(c))
            if cw:
                extras.append(f"Coursework: {cw}")
            if extras:
                p = P(stylename=styles.para(space_after=0, line_height=1.2))
                _srun(p, styles, "  ·  ".join(extras), base - 1.5, muted, italic=True)
                doc.text.addElement(p)
            _serif_gap(doc, styles)

    # ── Technical Skills ────────────────────────────────────────────────────
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
        _ssection(doc, styles, "Technical Skills")
        for label, vals in skill_rows:
            if not vals:
                continue
            p = P(stylename=styles.para(space_after=1.5, line_height=1.2))
            _srun(p, styles, label, base - 0.5, body, bold=True)
            _srun(p, styles, f" : {vals}", base - 0.5, body)
            doc.text.addElement(p)

    _serif_tail_sections(doc, styles, resume)
    return doc


def _serif_tail_sections(doc: OpenDocumentText, styles: "_Styles", resume: dict):
    """Open Source · Certifications · Publications · Patents · Awards · Volunteer
    · Languages · Interests · References — serif-styled to match the PDF."""
    base = styles.base
    body, muted = styles.palette["body"], styles.palette["muted"]

    oss = resume.get("open_source_contributions") or []
    if oss:
        _ssection(doc, styles, "Open Source")
        for o in oss:
            proj = _safe(o.get("project")); role = _safe(o.get("role"))
            url_raw = _safe(o.get("url", "")); url = _normalize_url(url_raw) if url_raw else None
            p = P(stylename=styles.para(space_after=0, line_height=1.18))
            if url:
                _slink(p, styles, proj, url, body, base, bold=True, underline=False)
            else:
                _srun(p, styles, proj, base, body, bold=True)
            if role:
                _srun(p, styles, f" – {role}", base, body, italic=True)
            doc.text.addElement(p)
            o_desc = _safe(o.get("description", "")) or _safe(o.get("contribution", ""))
            if o_desc:
                pd = P(stylename=styles.para(space_after=0, line_height=1.2))
                _srun(pd, styles, o_desc, base - 1.5, muted, italic=True)
                doc.text.addElement(pd)
            for c in (o.get("contributions") or []):
                if _safe(c):
                    _sbullet(doc, styles, _safe(c))
            _serif_gap(doc, styles)

    certs = resume.get("certifications") or []
    if certs:
        _ssection(doc, styles, "Certifications")
        for c in certs:
            url_raw = _safe(c.get("url", "")); url = _normalize_url(url_raw) if url_raw else None
            p = P(stylename=styles.para(space_after=1, line_height=1.2))
            if url:
                _slink(p, styles, _safe(c.get("name")), url, body, base - 0.5, bold=True, underline=False)
            else:
                _srun(p, styles, _safe(c.get("name")), base - 0.5, body, bold=True)
            if _safe(c.get("issuer")):
                _srun(p, styles, f" – {_safe(c.get('issuer'))}", base - 0.5, body, italic=True)
            dp = []
            if _safe(c.get("date")) or _safe(c.get("year")):
                dp.append(f"issued {_safe(c.get('date')) or _safe(c.get('year'))}")
            if _safe(c.get("expiry")):
                dp.append(f"expires {_safe(c.get('expiry'))}")
            if dp:
                _srun(p, styles, f"  ({', '.join(dp)})", base - 0.5, muted)
            doc.text.addElement(p)
            _serif_gap(doc, styles)

    pubs = resume.get("publications") or []
    if pubs:
        _ssection(doc, styles, "Publications")
        for pub in pubs:
            url_raw = _safe(pub.get("url", "")); url = _normalize_url(url_raw) if url_raw else None
            p = P(stylename=styles.para(space_after=1, line_height=1.2))
            if url:
                _slink(p, styles, _safe(pub.get("title")), url, body, base - 0.5, bold=True, underline=False)
            else:
                _srun(p, styles, _safe(pub.get("title")), base - 0.5, body, bold=True)
            if _safe(pub.get("venue")):
                _srun(p, styles, f" – {_safe(pub.get('venue'))}", base - 0.5, body, italic=True)
            if _safe(pub.get("date")):
                _srun(p, styles, f"  ({_safe(pub.get('date'))})", base - 0.5, muted)
            doc.text.addElement(p)
            _serif_gap(doc, styles)

    patents = resume.get("patents") or []
    if patents:
        _ssection(doc, styles, "Patents")
        for pt in patents:
            p = P(stylename=styles.para(space_after=1, line_height=1.2))
            _srun(p, styles, _safe(pt.get("title")), base - 0.5, body, bold=True)
            if _safe(pt.get("patent_number")):
                _srun(p, styles, f" – {_safe(pt.get('patent_number'))}", base - 0.5, body)
            if _safe(pt.get("date")):
                _srun(p, styles, f"  ({_safe(pt.get('date'))})", base - 0.5, muted)
            doc.text.addElement(p)
            _serif_gap(doc, styles)

    awards = resume.get("awards_and_honors") or []
    if awards:
        _ssection(doc, styles, "Awards & Honors")
        for a in awards:
            if isinstance(a, dict):
                nm = _safe(a.get("name") or a.get("title"))
                issuer = _safe(a.get("issuer")); yr = _safe(a.get("year") or a.get("date"))
                v = nm + (f" – {issuer}" if issuer else "") + (f" ({yr})" if yr else "")
            else:
                v = _safe(a)
            if v:
                _sbullet(doc, styles, v)

    vols = resume.get("volunteer_experience") or []
    if vols:
        _ssection(doc, styles, "Volunteer Experience")
        for v in vols:
            org = _safe(v.get("organization")); role = _safe(v.get("role"))
            head_left = " – ".join([x for x in (org, role) if x])
            _shrow(doc, styles,
                   lambda p, t=head_left: _srun(p, styles, t, base, body, bold=True),
                   _serif_dates(_safe(v.get("start_date")), _safe(v.get("end_date"))),
                   base, body, right_bold=True)
            if _safe(v.get("description")):
                pd = P(stylename=styles.para(space_after=0, line_height=1.2))
                _srun(pd, styles, _safe(v.get("description")), base - 1.5, muted, italic=True)
                doc.text.addElement(pd)
            _serif_gap(doc, styles)

    langs = resume.get("languages") or []
    if langs:
        _ssection(doc, styles, "Languages")
        p = P(stylename=styles.para(space_after=1.5, line_height=1.2))
        for i, l in enumerate(langs):
            lang = _safe(l.get("language")); prof = _safe(l.get("proficiency"))
            if not lang:
                continue
            if i > 0:
                _srun(p, styles, "  ·  ", base - 0.5, body)
            _srun(p, styles, lang, base - 0.5, body, bold=True)
            if prof:
                _srun(p, styles, f" ({prof})", base - 0.5, body)
        doc.text.addElement(p)

    interests = [_safe(i) for i in (resume.get("interests") or []) if _safe(i)]
    if interests:
        _ssection(doc, styles, "Interests")
        p = P(stylename=styles.para(space_after=1.5, line_height=1.2))
        _srun(p, styles, ", ".join(interests), base - 0.5, body)
        doc.text.addElement(p)

    references = resume.get("references")
    if references:
        _ssection(doc, styles, "References")
        if isinstance(references, str):
            p = P(stylename=styles.para(space_after=1.5, line_height=1.2))
            _srun(p, styles, _safe(references), base - 0.5, body)
            doc.text.addElement(p)
        elif isinstance(references, list):
            for ref in references:
                if _safe(ref):
                    _sbullet(doc, styles, _safe(ref))


def _build_resume_doc(resume: dict, template: TemplateName, base: float) -> OpenDocumentText:
    palette = PALETTES_HEX.get(template, PALETTES_HEX["classic_ats"])
    # Match the PDF generator: 0.6in side, 0.55in top/bottom.
    doc = _make_doc(side_cm=1.524, vert_cm=1.397, bg_color=palette.get("bg"))
    styles = _Styles(doc, palette, base)

    pi = resume.get("personal_info", {}) or {}
    name = _safe(pi.get("full_name")) or "Your Name"

    # ── Header ────────────────────────────────────────────────────────────
    p = P(stylename=styles.para(align="center", space_after=1, line_height=1.05))
    _run(p, styles, name, size=base + 11.5, color=palette["name"], bold=True)
    _add_para(doc, p)

    role = _safe(pi.get("professional_title"))
    if role:
        p = P(stylename=styles.para(align="center", space_after=4, line_height=1.3))
        _run(p, styles, role, size=base + 1, color=palette["title"])
        _add_para(doc, p)

    contact_bits: list[tuple[str, str | None]] = []
    for key in ("email", "phone", "location"):
        v = _safe(pi.get(key))
        if v:
            contact_bits.append((v, None))
    for key in ("linkedin", "github", "website", "portfolio"):
        v = _safe(pi.get(key))
        if v:
            display = v.replace("https://", "").replace("http://", "").rstrip("/")
            contact_bits.append((display, _normalize_url(v)))
    if contact_bits:
        p = P(stylename=styles.para(align="center", space_after=2, line_height=1.4))
        # See docx_generator: Word/LibreOffice render system Helvetica wider
        # than ReportLab's embedded Helvetica, so size down to keep the line
        # from wrapping.
        csize = base - 2.0
        for i, (text, url) in enumerate(contact_bits):
            if i > 0:
                _run(p, styles, "  ·  ", size=csize, color="#9aa0b4")
            if url:
                _link(p, styles, text, url, palette["accent"], csize)
            else:
                _run(p, styles, text, size=csize, color=palette["muted"])
        _add_para(doc, p)

    # ── Summary ───────────────────────────────────────────────────────────
    summary = _safe(resume.get("professional_summary", ""))
    if summary:
        _section(doc, styles, "Summary")
        p = P(stylename=styles.para(align="justify", space_after=2, line_height=1.45))
        _run(p, styles, summary, size=base - 0.5, color=palette["body"])
        _add_para(doc, p)

    # ── Core Competencies ────────────────────────────────────────────────
    competencies = [_safe(c) for c in (resume.get("core_competencies") or []) if _safe(c)]
    if competencies:
        _section(doc, styles, "Core Competencies")
        cols = 3
        rows = (len(competencies) + cols - 1) // cols
        # Three equal columns
        ts_name = f"comp_{styles._next()}"
        col = Style(name=f"{ts_name}_c", family="table-column")
        col.addElement(TableColumnProperties(columnwidth="5.8cm"))
        cell = Style(name=f"{ts_name}_cell", family="table-cell")
        cell.addElement(TableCellProperties(
            padding="0pt",
            bordertop="none", borderbottom="none",
            borderleft="none", borderright="none",
        ))
        ts = Style(name=ts_name, family="table")
        ts.addElement(TableProperties(width="17.5cm", align="left"))
        for s in (col, cell, ts):
            doc.automaticstyles.addElement(s)
        tbl = Table(stylename=ts_name)
        for _ in range(cols):
            tbl.addElement(TableColumn(stylename=col))
        for r in range(rows):
            tr = TableRow()
            for c in range(cols):
                idx = c * rows + r
                tc = TableCell(stylename=cell)
                if idx < len(competencies):
                    pp = P(stylename=styles.para(space_after=1.5, line_height=1.4))
                    _run(pp, styles, f"•  {competencies[idx]}",
                         size=base - 0.5, color=palette["body"])
                    tc.addElement(pp)
                else:
                    tc.addElement(P())
                tr.addElement(tc)
            tbl.addElement(tr)
        doc.text.addElement(tbl)

    # ── Experience ────────────────────────────────────────────────────────
    experience = resume.get("experience") or []
    if experience:
        _section(doc, styles, "Professional Experience")
        for exp in experience:
            title_str = _safe(exp.get("title"))
            company_str = _safe(exp.get("company"))
            loc_str = _safe(exp.get("location"))
            start = _safe(exp.get("start_date"))
            end = _safe(exp.get("end_date")) or ("Present" if exp.get("current") else "Present")
            emp_type = _safe(exp.get("employment_type", ""))

            _two_col_row(
                doc, styles, title_str, f"{start}  -  {end}",
                base, palette["body"], True,
                base - 1.5, palette["muted"],
            )
            company_inline = company_str
            if emp_type and emp_type.lower() not in ("full-time", "fulltime", ""):
                company_inline = f"{company_str} ({emp_type})" if company_str else emp_type
            if company_inline or loc_str:
                _two_col_row(
                    doc, styles, company_inline, loc_str,
                    base - 0.5, palette["accent"], False,
                    base - 1.5, palette["muted"],
                )

            bullets = list(exp.get("responsibilities") or []) + list(exp.get("achievements") or [])
            seen: set[str] = set()
            for b in bullets:
                b_str = _safe(b)
                if not b_str or b_str.lower() in seen:
                    continue
                seen.add(b_str.lower())
                _bullet(doc, styles, b_str)

            team_size = _safe(exp.get("team_size"))
            techs = [_safe(t) for t in (exp.get("technologies") or []) if _safe(t)]
            meta_parts = []
            if team_size:
                meta_parts.append(f"Team: {team_size}")
            if techs:
                meta_parts.append(f"Tech: {', '.join(techs)}")
            if meta_parts:
                p = P(stylename=styles.para(space_after=0, line_height=1.4))
                _run(p, styles, "  ·  ".join(meta_parts),
                     size=base - 1.5, color=palette["muted"], italic=True)
                _add_para(doc, p)
            _item_gap(doc, styles)

    # ── Technical Skills ──────────────────────────────────────────────────
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
        _section(doc, styles, "Technical Skills")
        for label, vals in skill_rows:
            if not vals:
                continue
            p = P(stylename=styles.para(space_after=2, line_height=1.4))
            _run(p, styles, f"{label}:  ",
                 size=base - 0.5, color=palette["body"], bold=True)
            _run(p, styles, vals, size=base - 0.5, color=palette["body"])
            _add_para(doc, p)

    # ── Projects ──────────────────────────────────────────────────────────
    projects = resume.get("projects") or []
    if projects:
        _section(doc, styles, "Projects")
        for proj in projects:
            p_name = _safe(proj.get("name"))
            url_raw = _safe(proj.get("url") or proj.get("github") or "")
            url = _normalize_url(url_raw) if url_raw else None
            tech = ", ".join(_safe(t) for t in (proj.get("technologies") or []) if _safe(t))
            proj_role = _safe(proj.get("role"))
            proj_type = _safe(proj.get("type"))
            p_start = _safe(proj.get("start_date"))
            p_end = _safe(proj.get("end_date"))
            name_lc = p_name.lower()
            sub_parts = []
            if proj_role and proj_role.lower() not in name_lc:
                sub_parts.append(proj_role)
            if proj_type and proj_type.lower() not in name_lc:
                sub_parts.append(proj_type)
            if tech:
                sub_parts.append(tech)
            dates_str = ""
            if p_start or p_end:
                dates_str = (
                    f"{p_start}  -  {p_end}".strip(" -")
                    if (p_start and p_end) else (p_start or p_end)
                )

            # Same layout as Experience/Education: title left, dates right on
            # the same row, instead of stacking dates on a separate line.
            def _fill_left(lp, _name=p_name, _url=url, _sub=sub_parts):
                if _url:
                    _link(lp, styles, _name, _url, palette["accent"], base)
                else:
                    _run(lp, styles, _name, size=base, color=palette["body"], bold=True)
                if _sub:
                    _run(lp, styles, f"   -   {'  ·  '.join(_sub)}",
                         size=base - 1, color=palette["muted"])

            def _fill_right(rp, _dates=dates_str):
                if _dates:
                    _run(rp, styles, _dates, size=base - 1.5, color=palette["muted"])

            _two_col_row_custom(doc, styles, _fill_left, _fill_right)
            desc = _safe(proj.get("description"))
            if desc:
                _bullet(doc, styles, desc)
            for h in (proj.get("highlights") or []):
                h_str = _safe(h)
                if h_str:
                    _bullet(doc, styles, h_str)
            _item_gap(doc, styles)

    # ── Open Source ───────────────────────────────────────────────────────
    oss = resume.get("open_source_contributions") or []
    if oss:
        _section(doc, styles, "Open Source")
        for o in oss:
            name_o = _safe(o.get("project"))
            role = _safe(o.get("role"))
            url_raw = _safe(o.get("url", ""))
            url = _normalize_url(url_raw) if url_raw else None
            stars = _safe(o.get("stars", ""))
            o_lang = _safe(o.get("language", ""))
            o_desc = _safe(o.get("description", ""))
            p = P(stylename=styles.para(line_height=1.2))
            if url:
                _link(p, styles, name_o, url, palette["accent"], base)
            else:
                _run(p, styles, name_o, size=base, color=palette["body"], bold=True)
            if role:
                _run(p, styles, f"   -   {role}", size=base - 0.5, color=palette["body"])
            if o_lang:
                _run(p, styles, f"  {o_lang}", size=base - 0.5, color=palette["muted"])
            if stars:
                _run(p, styles, f"  ★ {stars}", size=base - 0.5, color=palette["muted"])
            _add_para(doc, p)
            if o_desc:
                pd = P(stylename=styles.para(space_after=0, line_height=1.4))
                _run(pd, styles, o_desc, size=base - 1.5, color=palette["muted"])
                _add_para(doc, pd)
            for contrib in (o.get("contributions") or []):
                c_str = _safe(contrib)
                if c_str:
                    _bullet(doc, styles, c_str)
            _item_gap(doc, styles)

    # ── Education ─────────────────────────────────────────────────────────
    education = resume.get("education") or []
    if education:
        _section(doc, styles, "Education")
        for edu in education:
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
            _two_col_row(
                doc, styles, deg_line, dates,
                base, palette["body"], True,
                base - 1.5, palette["muted"],
            )
            if inst or loc:
                _two_col_row(
                    doc, styles, inst, loc,
                    base - 0.5, palette["accent"], False,
                    base - 1.5, palette["muted"],
                )
            extras = []
            if gpa:
                extras.append(f"GPA: {gpa}")
            if honors:
                extras.append(honors)
            cw = ", ".join(_safe(c) for c in (edu.get("relevant_coursework") or []) if _safe(c))
            if cw:
                extras.append(f"Coursework: {cw}")
            if extras:
                p = P(stylename=styles.para(space_after=0, line_height=1.4))
                _run(p, styles, "  ·  ".join(extras), size=base - 1.5, color=palette["muted"])
                _add_para(doc, p)
            acts = ", ".join(_safe(a) for a in (edu.get("activities") or []) if _safe(a))
            if acts:
                pa = P(stylename=styles.para(space_after=0, line_height=1.4))
                _run(pa, styles, f"Activities: {acts}", size=base - 1.5, color=palette["muted"])
                _add_para(doc, pa)
            _item_gap(doc, styles)

    # ── Certifications ────────────────────────────────────────────────────
    certs = resume.get("certifications") or []
    if certs:
        _section(doc, styles, "Certifications")
        for c in certs:
            c_name = _safe(c.get("name"))
            c_issuer = _safe(c.get("issuer"))
            c_date = _safe(c.get("date"))
            c_expiry = _safe(c.get("expiry"))
            c_cred_id = _safe(c.get("credential_id"))
            c_url_raw = _safe(c.get("url", ""))
            c_url = _normalize_url(c_url_raw) if c_url_raw else None
            p = P(stylename=styles.para(space_after=2, line_height=1.4))
            if c_url:
                _link(p, styles, c_name, c_url, palette["accent"], base - 0.5)
            else:
                _run(p, styles, c_name, size=base - 0.5, color=palette["body"], bold=True)
            if c_issuer:
                _run(p, styles, f"   -   {c_issuer}", size=base - 0.5, color=palette["body"])
            date_parts = []
            if c_date:
                date_parts.append(f"issued {c_date}")
            if c_expiry:
                date_parts.append(f"expires {c_expiry}")
            if date_parts:
                _run(p, styles, f"  ({', '.join(date_parts)})", size=base - 0.5, color=palette["muted"])
            if c_cred_id:
                _run(p, styles, f"  ID: {c_cred_id}", size=base - 0.5, color=palette["muted"])
            _add_para(doc, p)
            _item_gap(doc, styles)

    # ── Publications ──────────────────────────────────────────────────────
    pubs = resume.get("publications") or []
    if pubs:
        _section(doc, styles, "Publications")
        for pub in pubs:
            title = _safe(pub.get("title"))
            venue = _safe(pub.get("venue"))
            d = _safe(pub.get("date"))
            pub_type = _safe(pub.get("type", ""))
            url_raw = _safe(pub.get("url", ""))
            url = _normalize_url(url_raw) if url_raw else None
            authors = ", ".join(_safe(a) for a in (pub.get("authors") or []) if _safe(a))
            p = P(stylename=styles.para(space_after=2, line_height=1.4))
            if url:
                _link(p, styles, title, url, palette["accent"], base - 0.5)
            else:
                _run(p, styles, title, size=base - 0.5, color=palette["body"], bold=True)
            if pub_type and f"[{pub_type.lower()}]" not in title.lower():
                _run(p, styles, f"  [{pub_type}]", size=base - 0.5, color=palette["muted"])
            if venue:
                _run(p, styles, f"   -   {venue}",
                     size=base - 0.5, color=palette["body"], italic=True)
            if d:
                _run(p, styles, f"  ({d})", size=base - 0.5, color=palette["muted"])
            _add_para(doc, p)
            if authors:
                pa = P(stylename=styles.para(space_after=0, line_height=1.4))
                _run(pa, styles, authors, size=base - 1.5, color=palette["muted"])
                _add_para(doc, pa)
            _item_gap(doc, styles)

    # ── Patents ───────────────────────────────────────────────────────────
    patents = resume.get("patents") or []
    if patents:
        _section(doc, styles, "Patents")
        for pt in patents:
            pt_title = _safe(pt.get("title"))
            pt_url_raw = _safe(pt.get("url", ""))
            pt_url = _normalize_url(pt_url_raw) if pt_url_raw else None
            p = P(stylename=styles.para(space_after=2, line_height=1.4))
            if pt_url:
                _link(p, styles, pt_title, pt_url, palette["accent"], base - 0.5)
            else:
                _run(p, styles, pt_title, size=base - 0.5, color=palette["body"], bold=True)
            num = _safe(pt.get("patent_number"))
            d = _safe(pt.get("date"))
            if num:
                _run(p, styles, f"   -   {num}", size=base - 0.5, color=palette["body"])
            if d:
                _run(p, styles, f"  ({d})", size=base - 0.5, color=palette["muted"])
            _add_para(doc, p)
            desc = _safe(pt.get("description"))
            if desc:
                p2 = P(stylename=styles.para(space_after=0, line_height=1.4))
                _run(p2, styles, desc, size=base - 1.5, color=palette["muted"])
                _add_para(doc, p2)
            _item_gap(doc, styles)

    # ── Awards ────────────────────────────────────────────────────────────
    awards = resume.get("awards_and_honors") or []
    if awards:
        _section(doc, styles, "Awards & Honors")
        for a in awards:
            v = _safe(a) if not isinstance(a, dict) else _safe(a.get("name") or a.get("title"))
            if v:
                _bullet(doc, styles, v)

    # ── Volunteer ────────────────────────────────────────────────────────
    vols = resume.get("volunteer_experience") or []
    if vols:
        _section(doc, styles, "Volunteer Experience")
        for v in vols:
            org = _safe(v.get("organization"))
            role = _safe(v.get("role"))
            sd, ed = _safe(v.get("start_date")), _safe(v.get("end_date"))
            dates_str = f"{sd}  -  {ed}".strip(" -") if (sd or ed) else ""

            # Mirror Experience / Education in the other formats: title +
            # dates share the same row via the two-column table helper.
            _two_col_row(
                doc, styles,
                role + (f"   -   {org}" if org else ""),
                dates_str,
                base, palette["body"], True,
                base - 1.5, palette["muted"],
            )
            desc = _safe(v.get("description"))
            if desc:
                p3 = P(stylename=styles.para(space_after=0, line_height=1.4))
                _run(p3, styles, desc, size=base - 1.5, color=palette["muted"])
                _add_para(doc, p3)
            _item_gap(doc, styles)

    # ── Languages ────────────────────────────────────────────────────────
    langs = resume.get("languages") or []
    if langs and len(langs) > 1:
        _section(doc, styles, "Languages")
        p = P(stylename=styles.para(space_after=2, line_height=1.4))
        for i, l in enumerate(langs):
            if i > 0:
                _run(p, styles, "  ·  ", size=base - 0.5, color=palette["muted"])
            lang = _safe(l.get("language"))
            prof = _safe(l.get("proficiency"))
            _run(p, styles, lang, size=base - 0.5, color=palette["body"], bold=True)
            if prof:
                _run(p, styles, f" ({prof})", size=base - 0.5, color=palette["muted"])
        _add_para(doc, p)

    # ── Interests ────────────────────────────────────────────────────────
    interests = [_safe(i) for i in (resume.get("interests") or []) if _safe(i)]
    if interests:
        _section(doc, styles, "Interests")
        p = P(stylename=styles.para(space_after=2, line_height=1.4))
        _run(p, styles, ", ".join(interests), size=base - 0.5, color=palette["body"])
        _add_para(doc, p)

    # ── References ───────────────────────────────────────────────────────
    references = resume.get("references")
    if references:
        _section(doc, styles, "References")
        if isinstance(references, str):
            p = P(stylename=styles.para(space_after=2, line_height=1.4))
            _run(p, styles, _safe(references), size=base - 0.5, color=palette["body"])
            _add_para(doc, p)
        elif isinstance(references, list):
            for ref in references:
                ref_str = _safe(ref)
                if ref_str:
                    _bullet(doc, styles, ref_str)

    return doc



def generate_odt_resume(
    resume: dict,
    template: TemplateName = "classic_ats",
    font_size: FontSize = "normal",
) -> bytes:
    from app.documents._normalize import normalize_resume, resolve_base_font_size
    resume = normalize_resume(resume)
    base = resolve_base_font_size(font_size)

    if template == "latex_serif":
        doc = _build_resume_doc_serif(resume, base)
        buf = io.BytesIO()
        doc.write(buf)
        try:
            return _embed_fonts_odt(buf.getvalue())
        except Exception:
            return buf.getvalue()  # font-name-only fallback if embedding fails

    doc = _build_resume_doc(resume, template, base)
    buf = io.BytesIO()
    doc.write(buf)
    return buf.getvalue()


def generate_odt_cover_letter(
    cover_letter: str,
    resume: dict,
    template: TemplateName = "modern_clean",
    font_size: FontSize = "normal",
    hiring_manager: str | None = None,
    company_name: str | None = None,
    date_str: str | None = None,
) -> bytes:
    from app.documents._normalize import resolve_base_font_size
    palette = PALETTES_HEX.get(template, PALETTES_HEX["modern_clean"])
    base = resolve_base_font_size(font_size)
    pi = (resume or {}).get("personal_info", {}) or {}
    name = _safe(pi.get("full_name")) or "Your Name"

    # Match the PDF cover-letter generator: 0.85in all sides.
    doc = _make_doc(side_cm=2.159, vert_cm=2.159, bg_color=palette.get("bg"))
    styles = _Styles(doc, palette, base)

    # ── Sender block ─────────────────────────────────────────────────────
    p = P(stylename=styles.para(align="right", space_after=2, line_height=1.15))
    _run(p, styles, name, size=base + 4, color=palette["name"], bold=True)
    _add_para(doc, p)

    for key in ("email", "phone", "location", "linkedin", "github", "website", "portfolio"):
        v = _safe(pi.get(key))
        if not v:
            continue
        display = v.replace("https://", "").replace("http://", "").rstrip("/") if key in ("linkedin", "github", "website", "portfolio") else v
        sp = P(stylename=styles.para(align="right", space_after=1, line_height=1.5))
        _run(sp, styles, display, size=base - 1.5, color=palette["muted"])
        _add_para(doc, sp)

    if template != "classic_ats":
        rule_p = P(stylename=styles.para(
            align="right", space_before=4, space_after=4,
            bottom_border=palette["accent"],
        ))
        _add_para(doc, rule_p)

    # ── Date ─────────────────────────────────────────────────────────────
    display_date = date_str if date_str else date.today().strftime("%B %d, %Y")
    p = P(stylename=styles.para(space_before=18, space_after=14))
    _run(p, styles, display_date, size=base - 0.5, color=palette["muted"])
    _add_para(doc, p)

    # ── Recipient ────────────────────────────────────────────────────────
    recip_lines = []
    if hiring_manager and hiring_manager.lower() not in ("hiring team", "hiring manager", ""):
        recip_lines.append(hiring_manager)
    if company_name:
        recip_lines.append(company_name)
    for line in recip_lines:
        p = P(stylename=styles.para(space_after=2, line_height=1.45))
        _run(p, styles, line, size=base - 0.5, color=palette["body"])
        _add_para(doc, p)
    if recip_lines:
        _add_para(doc, P())

    # ── Salutation ───────────────────────────────────────────────────────
    salutation = "Dear Hiring Team,"
    if hiring_manager and hiring_manager.lower() not in ("hiring team", ""):
        first = hiring_manager.strip().split()[0]
        if first and first[0].isalpha():
            salutation = f"Dear {first},"
    p = P(stylename=styles.para(space_after=10))
    _run(p, styles, salutation, size=base, color=palette["body"])
    _add_para(doc, p)

    # ── Body ─────────────────────────────────────────────────────────────
    from odf.text import LineBreak
    text = (cover_letter or "").strip()
    paras = [pp.strip() for pp in text.split("\n\n") if pp.strip()]
    for para in paras:
        p = P(stylename=styles.para(align="justify", space_after=10, line_height=1.55))
        for i, chunk in enumerate(para.split("\n")):
            if i > 0:
                p.addElement(LineBreak())
            _run(p, styles, chunk, size=base, color=palette["body"])
        _add_para(doc, p)

    # ── Signature ────────────────────────────────────────────────────────
    p = P(stylename=styles.para(space_before=10, space_after=4))
    _run(p, styles, "Sincerely,", size=base, color=palette["body"])
    _add_para(doc, p)

    _add_para(doc, P())  # gap

    p = P()
    _run(p, styles, name, size=base, color=palette["name"], bold=True)
    _add_para(doc, p)

    buf = io.BytesIO()
    doc.write(buf)
    return buf.getvalue()
