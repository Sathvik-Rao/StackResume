"""LangGraph routing predicates — pure functions over state dicts."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_route_after_intent():
    from app.agents.graph import route_after_intent

    assert route_after_intent({"is_off_topic": True}) == "off_topic"
    assert route_after_intent({"is_off_topic": False}) == "parse"
    assert route_after_intent({}) == "parse"


def test_route_after_parse():
    from app.agents.graph import route_after_parse

    assert route_after_parse({"jd_text": "Senior role"}) == "jd_analyze"
    assert route_after_parse({"jd_text": "   "}) == "generate"
    assert route_after_parse({}) == "generate"


def test_should_enhance_on_error():
    from app.agents.graph import should_enhance

    # Error and no resume → straight to finalize, do not loop forever.
    assert should_enhance({"error": "x", "resume": None}) == "finalize"


def test_should_enhance_under_threshold(monkeypatch):
    from app.agents import graph
    monkeypatch.setattr(graph.settings, "max_review_iterations", 3, raising=False)
    monkeypatch.setattr(graph.settings, "min_quality_score", 82, raising=False)

    state = {"iteration": 1, "review": {"overall_score": 60}, "resume": {"x": 1}}
    assert graph.should_enhance(state) == "enhance"


def test_should_enhance_above_threshold(monkeypatch):
    from app.agents import graph
    monkeypatch.setattr(graph.settings, "min_quality_score", 82, raising=False)

    state = {"iteration": 1, "review": {"overall_score": 95}, "resume": {"x": 1}}
    assert graph.should_enhance(state) == "finalize"


def test_should_enhance_iteration_cap(monkeypatch):
    from app.agents import graph
    monkeypatch.setattr(graph.settings, "max_review_iterations", 3, raising=False)
    monkeypatch.setattr(graph.settings, "min_quality_score", 82, raising=False)

    # Even with low score, the cap kicks in.
    state = {"iteration": 3, "review": {"overall_score": 10}, "resume": {"x": 1}}
    assert graph.should_enhance(state) == "finalize"


def test_route_after_finalize():
    from app.agents.graph import route_after_finalize

    assert route_after_finalize({"resume": {"a": 1}, "jd_analysis": {"k": 1}}) == "cover_letter"
    assert route_after_finalize({"resume": {"a": 1}, "jd_analysis": None}) == "end"
    assert route_after_finalize({"resume": None}) == "end"
