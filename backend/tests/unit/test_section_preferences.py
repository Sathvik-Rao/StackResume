"""Per-user section/field toggle map — prompt directive + post-render scrubber."""
from __future__ import annotations

import copy

import pytest

pytestmark = pytest.mark.unit


def test_apply_to_resume_no_prefs_is_identity():
    from app.section_preferences import apply_to_resume

    resume = {"personal_info": {"full_name": "x"}, "experience": [{"company": "Acme"}]}
    out = apply_to_resume(resume, None)
    assert out is resume
    out2 = apply_to_resume(resume, {})
    assert out2 is resume


def test_apply_to_resume_drops_disabled_section():
    from app.section_preferences import apply_to_resume

    resume = {
        "metadata": {"version": "1"},
        "personal_info": {"full_name": "x"},
        "languages": [{"language": "English"}],
        "interests": ["coffee"],
    }
    prefs = {"sections": {"languages": False}}
    out = apply_to_resume(resume, prefs)
    assert "languages" not in out
    # Other sections survive
    assert out["interests"] == ["coffee"]
    # Metadata + personal_info are never wholesale-dropped
    assert "personal_info" in out
    assert "metadata" in out


def test_apply_to_resume_strips_disabled_fields_in_personal_info():
    from app.section_preferences import apply_to_resume

    resume = {
        "personal_info": {
            "full_name": "x", "email": "e@x", "website": "https://w",
            "portfolio": "https://p",
        },
    }
    prefs = {"fields": {"personal_info.website": False, "personal_info.portfolio": False}}
    out = apply_to_resume(resume, prefs)
    pi = out["personal_info"]
    assert "website" not in pi and "portfolio" not in pi
    assert pi["full_name"] == "x" and pi["email"] == "e@x"


def test_apply_to_resume_strips_fields_inside_list_sections():
    from app.section_preferences import apply_to_resume

    resume = {
        "personal_info": {"full_name": "x"},
        "experience": [
            {"company": "Acme", "title": "Eng", "location": "NYC", "technologies": ["Py"]},
            {"company": "Beta", "title": "Sr", "location": "SF", "technologies": ["Go"]},
        ],
    }
    prefs = {"fields": {"experience.location": False, "experience.technologies": False}}
    out = apply_to_resume(resume, prefs)
    for entry in out["experience"]:
        assert "location" not in entry and "technologies" not in entry
        # Untouched keys remain
        assert "company" in entry and "title" in entry


def test_apply_to_resume_is_side_effect_free():
    from app.section_preferences import apply_to_resume

    resume = {
        "personal_info": {"full_name": "x", "website": "https://w"},
        "languages": [{"language": "English"}],
    }
    snapshot = copy.deepcopy(resume)
    apply_to_resume(resume, {
        "sections": {"languages": False},
        "fields": {"personal_info.website": False},
    })
    assert resume == snapshot


def test_apply_to_resume_handles_non_dict_input():
    from app.section_preferences import apply_to_resume

    # Defensive: non-dict input passes through.
    assert apply_to_resume("nope", {"sections": {"x": False}}) == "nope"  # type: ignore[arg-type]


def test_build_prompt_directive_empty_when_no_overrides():
    from app.section_preferences import build_prompt_directive

    assert build_prompt_directive(None) == ""
    assert build_prompt_directive({}) == ""
    assert build_prompt_directive({"sections": {}, "fields": {}}) == ""


def test_build_prompt_directive_lists_disabled_sections_and_fields():
    from app.section_preferences import build_prompt_directive

    out = build_prompt_directive({
        "sections": {"languages": False, "interests": False, "publications": True},
        "fields": {"personal_info.website": False, "experience.location": False},
    })
    # Mentions disabled sections (sorted), not enabled ones.
    assert "languages" in out and "interests" in out
    assert "publications" not in out
    assert "personal_info.website" in out and "experience.location" in out


def test_is_section_enabled_default_true_when_missing():
    from app.section_preferences import is_section_enabled, is_field_enabled

    assert is_section_enabled(None, "experience") is True
    assert is_section_enabled({}, "experience") is True
    assert is_section_enabled({"sections": {"experience": False}}, "experience") is False
    # Field default also enabled
    assert is_field_enabled(None, "experience", "location") is True
    assert is_field_enabled(
        {"fields": {"experience.location": False}}, "experience", "location"
    ) is False
