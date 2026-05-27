"""Per-user resume section/field enable map.

Stored on AppSettings.section_preferences as JSON of shape:
    {
      "sections": {"<section_key>": bool, ...},
      "fields":   {"<section_key>.<field_key>": bool, ...}
    }

A missing entry means "enabled" — so the absence of the row, an empty dict,
or no override for a given section all leave the schema fully on.

This module is the single source of truth for:
- The canonical schema (sections + their toggleable fields) the UI renders.
- The post-generation `apply_to_resume()` filter that strips disabled keys.
- The `build_prompt_directive()` text injected into the generator/enhancer
  prompts so the LLM doesn't waste tokens producing sections the user has
  already chosen to drop.
"""
from __future__ import annotations

from typing import Any


# Ordered for stable UI rendering. Each entry:
#   key: matches the resume_json top-level key
#   label: human-readable section name
#   fields: optional list of {key, label} subfields that can be toggled off
#           individually (only meaningful when the section itself is enabled).
SECTION_SCHEMA: list[dict[str, Any]] = [
    {
        "key": "personal_info",
        "label": "Personal Info",
        "required": True,  # cannot disable the section itself
        "fields": [
            {"key": "professional_title", "label": "Professional title"},
            {"key": "email", "label": "Email"},
            {"key": "phone", "label": "Phone"},
            {"key": "location", "label": "Location"},
            {"key": "linkedin", "label": "LinkedIn"},
            {"key": "github", "label": "GitHub"},
            {"key": "website", "label": "Website"},
            {"key": "portfolio", "label": "Portfolio"},
        ],
    },
    {"key": "professional_summary", "label": "Professional Summary", "fields": []},
    {"key": "core_competencies", "label": "Core Competencies", "fields": []},
    {
        "key": "experience",
        "label": "Professional Experience",
        "fields": [
            {"key": "location", "label": "Location"},
            {"key": "employment_type", "label": "Employment type"},
            {"key": "team_size", "label": "Team size"},
            {"key": "technologies", "label": "Technologies"},
            {"key": "achievements", "label": "Achievements"},
        ],
    },
    {
        "key": "technical_skills",
        "label": "Technical Skills",
        "fields": [
            {"key": "programming_languages", "label": "Programming languages"},
            {"key": "frameworks_and_libraries", "label": "Frameworks & libraries"},
            {"key": "databases", "label": "Databases"},
            {"key": "cloud_and_infrastructure", "label": "Cloud & infrastructure"},
            {"key": "devops_and_tools", "label": "DevOps & tools"},
            {"key": "testing", "label": "Testing"},
            {"key": "methodologies", "label": "Methodologies"},
            {"key": "soft_skills", "label": "Soft skills"},
        ],
    },
    {
        "key": "projects",
        "label": "Projects",
        "fields": [
            {"key": "url", "label": "URL"},
            {"key": "github", "label": "GitHub"},
            {"key": "technologies", "label": "Technologies"},
            {"key": "highlights", "label": "Highlights"},
        ],
    },
    {
        "key": "education",
        "label": "Education",
        "fields": [
            {"key": "location", "label": "Location"},
            {"key": "gpa", "label": "GPA"},
            {"key": "honors", "label": "Honors"},
            {"key": "relevant_coursework", "label": "Relevant coursework"},
            {"key": "activities", "label": "Activities"},
        ],
    },
    {
        "key": "certifications",
        "label": "Certifications",
        "fields": [
            {"key": "credential_id", "label": "Credential ID"},
            {"key": "url", "label": "URL"},
            {"key": "expiry", "label": "Expiry"},
        ],
    },
    {
        "key": "open_source_contributions",
        "label": "Open Source Contributions",
        "fields": [
            {"key": "stars", "label": "Stars"},
            {"key": "language", "label": "Language"},
        ],
    },
    {"key": "publications", "label": "Publications", "fields": []},
    {"key": "patents", "label": "Patents", "fields": []},
    {"key": "awards_and_honors", "label": "Awards & Honors", "fields": []},
    {"key": "volunteer_experience", "label": "Volunteer Experience", "fields": []},
    {"key": "languages", "label": "Spoken Languages", "fields": []},
    {"key": "interests", "label": "Interests", "fields": []},
    {"key": "references", "label": "References line", "fields": []},
]


def _split_prefs(prefs: dict | None) -> tuple[dict, dict]:
    """Return (sections_map, fields_map) — both defaulting to empty."""
    if not isinstance(prefs, dict):
        return {}, {}
    sec = prefs.get("sections") or {}
    fld = prefs.get("fields") or {}
    if not isinstance(sec, dict):
        sec = {}
    if not isinstance(fld, dict):
        fld = {}
    return sec, fld


def is_section_enabled(prefs: dict | None, section_key: str) -> bool:
    sec, _ = _split_prefs(prefs)
    return sec.get(section_key, True) is not False


def is_field_enabled(prefs: dict | None, section_key: str, field_key: str) -> bool:
    _, fld = _split_prefs(prefs)
    return fld.get(f"{section_key}.{field_key}", True) is not False


def _scrub_section_fields(section_key: str, payload: Any, fld: dict) -> Any:
    """Strip disabled fields from a section payload.

    Sections can be a dict (e.g. personal_info), a list of dicts (e.g. experience),
    or a primitive — we only walk dicts/lists-of-dicts.
    """
    # Fast path: nothing disabled for this section.
    prefix = section_key + "."
    disabled_fields = {
        k.split(".", 1)[1] for k, v in fld.items()
        if k.startswith(prefix) and v is False
    }
    if not disabled_fields:
        return payload

    def _scrub_obj(obj: dict) -> dict:
        return {k: v for k, v in obj.items() if k not in disabled_fields}

    if isinstance(payload, dict):
        return _scrub_obj(payload)
    if isinstance(payload, list):
        return [_scrub_obj(x) if isinstance(x, dict) else x for x in payload]
    return payload


def apply_to_resume(resume: dict, prefs: dict | None) -> dict:
    """Return resume with disabled sections dropped and disabled fields scrubbed.

    Always preserves `metadata` and `personal_info` (those can't be removed
    wholesale — a resume without contact info isn't a resume). Personal-info
    *sub-fields* can still be toggled off.

    Idempotent and side-effect free — does not mutate the input.
    """
    if not isinstance(resume, dict):
        return resume
    if not prefs:
        return resume
    sec, fld = _split_prefs(prefs)
    if not sec and not fld:
        return resume

    out: dict = {}
    for k, v in resume.items():
        if k in ("metadata", "personal_info"):
            out[k] = _scrub_section_fields(k, v, fld) if k == "personal_info" else v
            continue
        # Section disabled → drop it entirely.
        if sec.get(k, True) is False:
            continue
        out[k] = _scrub_section_fields(k, v, fld)
    return out


def build_prompt_directive(prefs: dict | None) -> str:
    """Render a directive describing what the LLM must not produce.

    Returns an empty string when no overrides are set, so callers can just
    f-string it into the prompt unconditionally.
    """
    if not prefs:
        return ""
    sec, fld = _split_prefs(prefs)
    disabled_sections = [k for k, v in sec.items() if v is False]
    disabled_fields = [k for k, v in fld.items() if v is False]
    if not disabled_sections and not disabled_fields:
        return ""

    lines = ["USER SECTION PREFERENCES (strict):"]
    if disabled_sections:
        lines.append(
            "- Do NOT include these top-level sections (omit the keys from the JSON, "
            "leave them out entirely — not empty arrays): "
            + ", ".join(sorted(disabled_sections))
        )
    if disabled_fields:
        lines.append(
            "- Do NOT populate these subfields (omit the keys): "
            + ", ".join(sorted(disabled_fields))
        )
    lines.append("- Everything else in the schema remains required.")
    return "\n".join(lines)
