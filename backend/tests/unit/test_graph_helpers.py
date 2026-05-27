"""Pure-function helpers inside agents/graph.py — these run without LLMs."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ── JSON extraction ───────────────────────────────────────────────────────────

class TestExtractJson:
    def test_plain_json(self):
        from app.agents.graph import _extract_json
        assert _extract_json('{"a": 1}') == {"a": 1}

    def test_json_inside_markdown_fence(self):
        from app.agents.graph import _extract_json
        text = "```json\n{\"a\": 2}\n```"
        assert _extract_json(text) == {"a": 2}

    def test_json_with_trailing_comma(self):
        from app.agents.graph import _extract_json
        # Models sometimes emit `{"a": 1,}` — we should still recover.
        assert _extract_json('{"a": 1,}') == {"a": 1}

    def test_json_with_preamble(self):
        from app.agents.graph import _extract_json
        text = 'Sure! Here is the resume:\n{"a": 3, "b": [1,2,3]}\nLet me know.'
        assert _extract_json(text) == {"a": 3, "b": [1, 2, 3]}

    def test_unrecoverable_raises(self):
        from app.agents.graph import _extract_json
        with pytest.raises(ValueError):
            _extract_json("this is not json at all")


# ── Dash + quote stripper ─────────────────────────────────────────────────────

class TestStripDashes:
    def test_em_dash(self):
        from app.agents.graph import _strip_dashes
        assert _strip_dashes("hi — there") == "hi - there"

    def test_en_dash(self):
        from app.agents.graph import _strip_dashes
        assert _strip_dashes("2019–2022") == "2019-2022"

    def test_curly_quotes(self):
        from app.agents.graph import _strip_dashes
        assert _strip_dashes("“hello” ‘world’") == '"hello" \'world\''

    def test_recurses_into_nested_structures(self):
        from app.agents.graph import _strip_dashes
        nested = {
            "name": "Ada — Lovelace",
            "roles": ["Lead — Eng", {"summary": "“wow”"}],
            "count": 3,
        }
        cleaned = _strip_dashes(nested)
        assert cleaned["name"] == "Ada - Lovelace"
        assert cleaned["roles"][0] == "Lead - Eng"
        assert cleaned["roles"][1]["summary"] == '"wow"'
        assert cleaned["count"] == 3


# ── Quick-intent classifier (no LLM) ──────────────────────────────────────────

class TestQuickIntent:
    @pytest.mark.parametrize("text", [
        "", "  ", "hi", "hey there", "what's up", "bye", "tell me a joke",
    ])
    def test_social_chatter_is_off_topic(self, text):
        from app.agents.graph import _quick_intent
        assert _quick_intent(text, has_existing_resume=False) == "off_topic"

    @pytest.mark.parametrize("text", [
        "Spring Boot dev, 6 years",
        "Senior Java engineer, FAANG career history",
        "Tailor my resume to this JD",
        "Python backend role at a fintech startup",
    ])
    def test_resume_keywords_are_on_topic(self, text):
        from app.agents.graph import _quick_intent
        assert _quick_intent(text, has_existing_resume=False) == "resume_related"

    def test_refinement_verb_with_existing_resume(self):
        from app.agents.graph import _quick_intent
        # "make it shorter" alone is ambiguous, but once we have a resume,
        # we treat refinement verbs as on-topic.
        assert _quick_intent("make it shorter", has_existing_resume=True) == "resume_related"

    def test_short_non_keyword_cold_start(self):
        from app.agents.graph import _quick_intent
        # 3 words, no resume keywords, no resume on file — block it.
        assert _quick_intent("the blue elephant", has_existing_resume=False) == "off_topic"

    def test_ambiguous_returns_none(self):
        from app.agents.graph import _quick_intent
        # Long-ish, not obvious — defer to LLM.
        assert _quick_intent("Could you help me with something later today please", False) is None


# ── format_exc ────────────────────────────────────────────────────────────────

class TestFormatExc:
    def test_includes_type_and_message(self):
        from app.agents.graph import format_exc
        out = format_exc(ValueError("bad json"))
        assert "ValueError" in out
        assert "bad json" in out

    def test_includes_status_code_when_present(self):
        from app.agents.graph import format_exc

        class FakeError(Exception):
            status_code = 429
        out = format_exc(FakeError("rate limited"))
        assert "status_code=429" in out

    def test_pulls_provider_message_from_body(self):
        from app.agents.graph import format_exc

        class FakeError(Exception):
            body = {"error": {"message": "credit balance too low"}}
        out = format_exc(FakeError(""))
        assert "credit balance too low" in out


# ── content_to_text ───────────────────────────────────────────────────────────

class TestContentToText:
    def test_string_passthrough(self):
        from app.agents.graph import _content_to_text
        assert _content_to_text("hello") == "hello"

    def test_none_returns_empty(self):
        from app.agents.graph import _content_to_text
        assert _content_to_text(None) == ""

    def test_list_of_text_blocks(self):
        from app.agents.graph import _content_to_text
        blocks = [{"type": "text", "text": "hello "}, {"type": "text", "text": "world"}]
        assert _content_to_text(blocks) == "hello world"

    def test_list_of_raw_strings(self):
        from app.agents.graph import _content_to_text
        assert _content_to_text(["a", "b"]) == "ab"

    def test_list_of_dicts_without_type(self):
        from app.agents.graph import _content_to_text
        # Some providers emit {"text": "..."} with no type.
        assert _content_to_text([{"text": "x"}, {"text": "y"}]) == "xy"


# ── History formatter ─────────────────────────────────────────────────────────

class TestBuildHistoryText:
    def test_truncates_long_messages(self):
        from app.agents.graph import _build_history_text

        long = "x" * 1000
        out = _build_history_text([{"role": "user", "content": long}])
        # Content is capped at 400 chars per message.
        assert out.startswith("User: ")
        assert len(out) <= 410

    def test_keeps_last_eight_messages(self):
        from app.agents.graph import _build_history_text

        msgs = [{"role": "user", "content": f"msg{i}"} for i in range(20)]
        out = _build_history_text(msgs)
        assert "msg19" in out
        assert "msg0" not in out


# ── JD intensity directive ────────────────────────────────────────────────────

class TestJdIntensity:
    @pytest.mark.parametrize("v, label", [
        (100, "FULL"),
        (90, "FULL"),
        (75, "HEAVY"),
        (50, "MODERATE"),
        (20, "LIGHT"),
        (0, "NONE"),
        (-5, "NONE"),       # clamped
        (200, "FULL"),      # clamped
    ])
    def test_label_buckets(self, v, label):
        from app.agents.graph import _jd_intensity_directive
        out = _jd_intensity_directive(v)
        assert label in out

    def test_none_defaults_to_full(self):
        from app.agents.graph import _jd_intensity_directive
        out = _jd_intensity_directive(None)
        assert "FULL" in out


# ── Memory context formatting ─────────────────────────────────────────────────

class TestMemoryContextStr:
    def test_empty_returns_empty(self):
        from app.agents.graph import _memory_context_str
        assert _memory_context_str(None) == ""
        assert _memory_context_str({}) == ""

    def test_includes_all_known_fields(self):
        from app.agents.graph import _memory_context_str
        mem = {
            "full_name": "Ada", "email": "a@b.com", "phone": "+1",
            "location": "London", "linkedin_url": "li", "github_url": "gh",
            "website": "w", "target_roles": ["Backend"],
            "total_years_experience": 5,
            "companies": [{"name": "C", "title": "T", "from_year": 2020, "to_year": 2024}],
            "education": [{"degree": "BS", "institution": "MIT", "graduation_year": 2018}],
            "always_include_skills": ["Python"],
            "personal_notes": "n",
        }
        out = _memory_context_str(mem)
        assert "Ada" in out and "Backend" in out and "MIT" in out and "Python" in out

    def test_projects_are_included(self):
        """Regression: projects from UserMemory must reach the LLM prompt.

        See _load_memory in api/_pipeline.py — it fetches `projects`
        from the DB; _memory_context_str must surface them in the prompt or
        the field is silently dropped on the way to the model.
        """
        from app.agents.graph import _memory_context_str
        mem = {
            "projects": [
                {
                    "name": "StackResume",
                    "role": "Creator",
                    "description": "AI resume builder",
                    "technologies": ["Python", "FastAPI", "LangGraph"],
                    "url": "https://stackresume.dev",
                    "year": 2025,
                },
                {"name": "MinimalProj"},
            ],
        }
        out = _memory_context_str(mem)
        assert "Project:" in out
        assert "StackResume" in out
        assert "Creator" in out
        assert "AI resume builder" in out
        assert "Python" in out and "FastAPI" in out and "LangGraph" in out
        assert "https://stackresume.dev" in out
        assert "2025" in out
        # Bare-minimum project (only `name`) must still render — no crash on
        # missing optional keys.
        assert "MinimalProj" in out

    def test_certifications_languages_and_extras(self):
        from app.agents.graph import _memory_context_str
        mem = {
            "summary": "Senior backend engineer with payments expertise.",
            "portfolio_url": "https://port.example.com",
            "certifications": [
                {"name": "AWS SAA", "issuer": "Amazon", "year": 2023, "url": "https://aws.example"},
            ],
            "languages_spoken": [
                {"language": "English", "proficiency": "Native"},
                {"language": "Spanish"},
            ],
            "open_to_remote": True,
            "work_authorization": "US Citizen",
            "availability": "2 weeks notice",
        }
        out = _memory_context_str(mem)
        assert "Senior backend engineer" in out
        assert "https://port.example.com" in out
        assert "AWS SAA" in out and "Amazon" in out and "2023" in out
        assert "English (Native)" in out
        assert "Spanish" in out
        assert "Open to remote: yes" in out
        assert "US Citizen" in out
        assert "2 weeks notice" in out

    def test_open_to_remote_false_is_emitted(self):
        """False is meaningful — must not be silently dropped like None."""
        from app.agents.graph import _memory_context_str
        out = _memory_context_str({"open_to_remote": False})
        assert "Open to remote: no" in out

    def test_empty_lists_dont_emit_headers(self):
        """Loader returns `[]` when the column is NULL — don't emit empty
        'Project:' / 'Certification:' lines for empty collections."""
        from app.agents.graph import _memory_context_str
        out = _memory_context_str({
            "projects": [],
            "certifications": [],
            "languages_spoken": [],
        })
        assert out == ""
