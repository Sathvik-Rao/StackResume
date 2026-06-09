"""Contact-icon glyph contract — shared across the PDF / DOCX / ODT exporters.

Regression guard for the location pin: it must be Font Awesome ``location-dot``
(U+F3C5 — a pin with a hollow centre), NOT ``location-pin`` (U+F041 — a solid
black teardrop that reads as an ink blob). All three exporters must agree so a
résumé's contact line looks identical whichever format it's downloaded in.
"""
from __future__ import annotations

import importlib

import pytest

pytestmark = pytest.mark.documents

LOCATION_DOT = ""   # what we want — pin with a hollow centre
LOCATION_PIN = ""   # the old solid blob — must never come back

_GENERATORS = [
    "app.documents.pdf_generator",
    "app.documents.docx_generator",
    "app.documents.odt_generator",
]


@pytest.mark.parametrize("module_path", _GENERATORS)
def test_location_icon_is_location_dot_not_blob(module_path):
    mod = importlib.import_module(module_path)
    _face, glyph = mod._FA_ICONS["location"]
    assert glyph == LOCATION_DOT, (
        f"{module_path} location glyph is U+{ord(glyph):04X}, expected U+F3C5 (location-dot)"
    )
    assert glyph != LOCATION_PIN, f"{module_path} regressed to the solid blob U+F041"


def test_all_exporters_agree_on_location_glyph():
    glyphs = {importlib.import_module(p)._FA_ICONS["location"][1] for p in _GENERATORS}
    assert glyphs == {LOCATION_DOT}, f"exporters disagree on the location glyph: {glyphs}"


def test_location_dot_glyph_exists_in_bundled_font():
    """The chosen glyph must actually exist in fa-solid-900.ttf, otherwise the
    pin silently renders as blank/tofu instead of an icon."""
    ttLib = pytest.importorskip("fontTools.ttLib")
    import os
    from app.documents.pdf_generator import _FONTS_DIR

    font = ttLib.TTFont(os.path.join(_FONTS_DIR, "fa-solid-900.ttf"))
    cmap = font.getBestCmap()
    assert ord(LOCATION_DOT) in cmap, "location-dot (U+F3C5) missing from fa-solid-900.ttf"
    assert cmap[ord(LOCATION_DOT)] == "location-dot"
