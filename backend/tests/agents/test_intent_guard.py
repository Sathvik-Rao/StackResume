"""Intent guard node — fast path + LLM fallback + error handling."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.agents


def test_off_topic_short_circuits_no_llm(base_state, fake_llm):
    from app.agents.graph import intent_check_node

    base_state["current_input"] = "hi"
    out = intent_check_node(base_state)
    assert out["is_off_topic"] is True
    assert out["off_topic_response"]
    # Fast path — no LLM invocation.
    assert fake_llm.invocations == []


def test_resume_keyword_short_circuits_no_llm(base_state, fake_llm):
    from app.agents.graph import intent_check_node

    base_state["current_input"] = "Senior Python developer, 8 years"
    out = intent_check_node(base_state)
    assert out["is_off_topic"] is False
    assert fake_llm.invocations == []


def test_ambiguous_message_invokes_llm(base_state, fake_llm):
    """A long, keyword-free phrase falls through to the LLM classifier."""
    from app.agents.graph import intent_check_node

    base_state["current_input"] = "could you please help me figure this thing out today"
    fake_llm.set("intent", {"intent": "off_topic", "suggested_reply": "go away nicely"})
    out = intent_check_node(base_state)
    assert out["is_off_topic"] is True
    assert "go away" in out["off_topic_response"]
    assert any(k == "intent" for k, _ in fake_llm.invocations)


def test_llm_error_falls_back_to_on_topic(base_state, fake_llm):
    """If the LLM raises, we default to letting the request through rather
    than blocking the user."""
    from app.agents.graph import intent_check_node

    base_state["current_input"] = "could you please help me figure this thing out today"
    fake_llm.fail_with("intent", RuntimeError("nope"))
    out = intent_check_node(base_state)
    assert out["is_off_topic"] is False


def test_refinement_verb_with_existing_resume(base_state, fake_llm):
    from app.agents.graph import intent_check_node

    base_state["current_input"] = "make it shorter"
    base_state["existing_resume"] = {"personal_info": {"full_name": "x"}}
    out = intent_check_node(base_state)
    assert out["is_off_topic"] is False
    assert fake_llm.invocations == []
