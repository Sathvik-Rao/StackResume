"""Defensive normalization for resume dicts before rendering.

The LLM (or an upstream coercion step) sometimes turns a sentence into an
array of single characters — e.g. ``"activities": ["A","c","t","i","v",...]``.
That array travels through ``_safe()`` and gets joined as
``"A, c, t, i, v, ..."`` in the PDF/DOCX/ODT output.

It also sometimes emits a *string* at a field the schema says is a list —
``"activities": "Graduate Research Assistant, CS Department"`` — and the
generators then iterate the raw string, producing the same char-split
artifact (this time without the rescue path in ``_safe(list)``).

Story builders iterate per element, so a fix in ``_safe(list)`` alone doesn't
help. This module walks the whole resume dict once, reconstructs every
char-split list, AND coerces known list-fields from string → list, so all
three generators see clean data.

Idempotent — safe to call repeatedly.
"""
from __future__ import annotations

import copy
import re

_SPLIT_RE = re.compile(r"[,;\n]")

# Fields the resume schema declares as lists. If the LLM emits a string at one
# of these, split it on commas/semicolons before the generators iterate it.
_LIST_KEYS = frozenset({
    "activities", "interests", "relevant_coursework",
    "technologies", "highlights",
    "responsibilities", "achievements", "contributions",
    "authors", "core_competencies",
    "programming_languages", "frameworks_and_libraries",
    "databases", "cloud_and_infrastructure", "devops_and_tools",
    "testing", "methodologies", "soft_skills",
})

_FONT_PRESETS = {"small": 9.5, "normal": 10.5, "large": 11.5}
_FONT_MIN, _FONT_MAX = 8.0, 13.0


def _looks_char_split(seq: list) -> bool:
    """True when at least 80% of >=4 string entries are length <= 1."""
    if len(seq) < 4:
        return False
    if not all(isinstance(x, str) for x in seq):
        return False
    singles = sum(1 for s in seq if len(s) <= 1)
    return singles / len(seq) >= 0.8


def _strip_label(s: str) -> str:
    """Drop a leading "Activities:" / "Interests:" label echo so it doesn't
    double up with the section header."""
    return re.sub(r"^\s*[A-Z][A-Za-z ]{0,30}:\s*", "", s)


def _rebuild(seq: list) -> list:
    """Join a char-split list back into a string, then split on common delimiters."""
    joined = "".join(seq).strip()
    if not joined:
        return []
    joined = _strip_label(joined)
    parts = [p.strip() for p in _SPLIT_RE.split(joined) if p.strip()]
    return parts or [joined]


def _split_string(s: str) -> list:
    s = s.strip()
    if not s:
        return []
    s = _strip_label(s)
    parts = [p.strip() for p in _SPLIT_RE.split(s) if p.strip()]
    return parts or [s]


def _walk(v):
    if isinstance(v, list):
        if _looks_char_split(v):
            return _rebuild(v)
        return [_walk(x) for x in v]
    if isinstance(v, dict):
        out = {}
        for k, val in v.items():
            if k in _LIST_KEYS and isinstance(val, str):
                val = _split_string(val)
            out[k] = _walk(val)
        return out
    return v


def normalize_resume(resume: dict) -> dict:
    """Return a deep-copied resume with every char-split list reconstructed."""
    if not isinstance(resume, dict):
        return resume
    return _walk(copy.deepcopy(resume))


def resolve_base_font_size(font_size) -> float:
    """Map a font_size request (preset name or numeric pt value) to a base size.

    Accepts: "small"/"normal"/"large" presets, a numeric string like "10.5",
    or a raw int/float. Out-of-range values are clamped to [8.0, 13.0].
    Falls back to 10.5 for anything unparseable.
    """
    if isinstance(font_size, bool):
        return 10.5
    if isinstance(font_size, (int, float)):
        return max(_FONT_MIN, min(_FONT_MAX, float(font_size)))
    s = (font_size or "").strip().lower() if isinstance(font_size, str) else ""
    if s in _FONT_PRESETS:
        return _FONT_PRESETS[s]
    try:
        return max(_FONT_MIN, min(_FONT_MAX, float(s)))
    except (ValueError, TypeError):
        return 10.5


def is_valid_font_size(font_size) -> bool:
    """True iff resolve_base_font_size would accept this value as-given."""
    if isinstance(font_size, (int, float)) and not isinstance(font_size, bool):
        return _FONT_MIN <= float(font_size) <= _FONT_MAX
    if not isinstance(font_size, str):
        return False
    s = font_size.strip().lower()
    if s in _FONT_PRESETS:
        return True
    try:
        v = float(s)
    except ValueError:
        return False
    return _FONT_MIN <= v <= _FONT_MAX
