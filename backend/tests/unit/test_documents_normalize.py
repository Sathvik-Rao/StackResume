"""Resume normalization helpers — char-split rescue + font size parsing."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ── normalize_resume ──────────────────────────────────────────────────────────


def test_normalize_rebuilds_char_split_list():
    """LLMs sometimes ``list("phrase")`` a field — rebuild the original string."""
    from app.documents._normalize import normalize_resume

    bad = {
        "education": [{
            "institution": "MIT",
            "activities": list("Graduate Research Assistant, CS Department"),
        }],
    }
    out = normalize_resume(bad)
    acts = out["education"][0]["activities"]
    # Reconstructed and split on the comma — no single-char fragments left.
    assert acts == ["Graduate Research Assistant", "CS Department"]


def test_normalize_strips_leading_label_echo():
    from app.documents._normalize import normalize_resume

    bad = {"experience": [{"responsibilities": list("Responsibilities: Built systems")}]}
    out = normalize_resume(bad)
    # The "Responsibilities:" prefix should be dropped before splitting.
    assert out["experience"][0]["responsibilities"] == ["Built systems"]


def test_normalize_coerces_string_to_list_for_known_keys():
    """When the schema says list[str] but the LLM emits a string, split it."""
    from app.documents._normalize import normalize_resume

    bad = {
        "education": [{
            "relevant_coursework": "Algorithms, Distributed Systems; ML",
        }],
    }
    out = normalize_resume(bad)
    assert out["education"][0]["relevant_coursework"] == [
        "Algorithms", "Distributed Systems", "ML",
    ]


def test_normalize_idempotent():
    from app.documents._normalize import normalize_resume

    clean = {
        "personal_info": {"full_name": "Ada"},
        "experience": [{"company": "Acme", "technologies": ["Python", "Go"]}],
    }
    once = normalize_resume(clean)
    twice = normalize_resume(once)
    assert once == twice == clean


def test_normalize_does_not_mutate_input():
    from app.documents._normalize import normalize_resume

    bad = {"interests": list("Coffee, Sailing")}
    snapshot = {"interests": list("Coffee, Sailing")}
    normalize_resume(bad)
    assert bad == snapshot


def test_normalize_non_dict_passes_through():
    from app.documents._normalize import normalize_resume

    assert normalize_resume("nope") == "nope"  # type: ignore[arg-type]


# ── resolve_base_font_size + is_valid_font_size ───────────────────────────────


@pytest.mark.parametrize("preset, expected", [
    ("small", 9.5),
    ("normal", 10.5),
    ("large", 11.5),
])
def test_resolve_base_font_size_presets(preset, expected):
    from app.documents._normalize import resolve_base_font_size

    assert resolve_base_font_size(preset) == expected


def test_resolve_base_font_size_numeric_string():
    from app.documents._normalize import resolve_base_font_size

    assert resolve_base_font_size("10.3") == 10.3


def test_resolve_base_font_size_clamps_out_of_range():
    from app.documents._normalize import resolve_base_font_size

    assert resolve_base_font_size(50.0) == 13.0
    assert resolve_base_font_size("5.0") == 8.0


def test_resolve_base_font_size_falls_back_for_garbage():
    from app.documents._normalize import resolve_base_font_size

    assert resolve_base_font_size("huge") == 10.5
    assert resolve_base_font_size(None) == 10.5


def test_is_valid_font_size_accepts_presets_and_in_range_numbers():
    from app.documents._normalize import is_valid_font_size

    assert is_valid_font_size("small")
    assert is_valid_font_size("normal")
    assert is_valid_font_size("large")
    assert is_valid_font_size("10")
    assert is_valid_font_size("8.0")
    assert is_valid_font_size("13.0")
    assert is_valid_font_size(10.5)


def test_is_valid_font_size_rejects_out_of_range_and_garbage():
    from app.documents._normalize import is_valid_font_size

    assert not is_valid_font_size("huge")
    assert not is_valid_font_size("7.9")
    assert not is_valid_font_size("13.1")
    assert not is_valid_font_size(True)
    assert not is_valid_font_size(None)
