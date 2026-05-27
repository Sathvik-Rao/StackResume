"""Shared helpers for agent-node tests.

Each agent node accepts a single ``state`` dict (the ``AgentState`` TypedDict)
and returns a new dict. ``base_state`` gives every test a fully-populated
starting state — individual tests override just the fields they care about.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def base_state() -> dict:
    return {
        "session_id": "sess-1",
        "current_input": "Senior Python backend engineer, 8 years.",
        "conversation_history": [],
        "existing_resume": None,
        "llm_provider": "fake",
        "llm_model": "fake-test",
        "memory_context": None,
        "is_off_topic": False,
        "off_topic_response": None,
        "jd_text": "",
        "jd_analysis": None,
        "jd_intensity": 100,
        "parsed_data": None,
        "request_type": "create",
        "resume": None,
        "review": None,
        "cover_letter": None,
        "outreach_emails": None,
        "iteration": 0,
        "agent_trace": [],
        "error": None,
    }
