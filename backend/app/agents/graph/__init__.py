"""Resume-generation LangGraph pipeline.

Everything that tests or routers import from ``app.agents.graph`` is
re-exported here from the per-node submodules.
"""
# Re-export get_llm so ``monkeypatch.setattr(graph, "get_llm", …)`` in tests
# resolves to a real attribute on this package. Per-node modules import
# get_llm directly from llm_factory, so install_fake() patches both.
from app.agents.llm_factory import get_llm
# Re-export the live settings singleton so tests that mutate
# ``graph.settings.max_review_iterations`` still hit the same object the
# routers read from.
from app.config import settings

from ._helpers import (
    _now_epoch_ms, _trace_event, format_exc, _extract_json, _strip_dashes,
    _build_history_text, _build_callbacks, _content_to_text,
    _call_llm_timed, _memory_context_str, _jd_intensity_directive,
)
from ._intent import (
    _RESUME_KEYWORDS, _SOCIAL_ONLY, _REFINEMENT_VERBS,
    _quick_intent, intent_check_node, off_topic_node,
)
from .nodes.parse import parse_input_node
from .nodes.jd import jd_analyze_node
from .nodes.generate import generate_resume_node
from .nodes.review import review_resume_node
from .nodes.enhance import enhance_resume_node
from .nodes.finalize import finalize_node
from .nodes.cover_letter import cover_letter_node
from .nodes.outreach import outreach_node
from ._routing import (
    route_after_intent, route_after_parse, should_enhance, route_after_finalize,
)
from ._builder import build_graph, RESUME_GRAPH


__all__ = [
    # Helpers — underscore-prefixed names are imported by the test suite.
    "get_llm", "settings",
    "_now_epoch_ms", "_trace_event", "format_exc", "_extract_json",
    "_strip_dashes", "_build_history_text", "_build_callbacks",
    "_content_to_text", "_call_llm_timed", "_memory_context_str",
    "_jd_intensity_directive",
    # Intent + nodes
    "_quick_intent", "intent_check_node", "off_topic_node",
    "parse_input_node", "jd_analyze_node",
    "generate_resume_node", "review_resume_node", "enhance_resume_node",
    "finalize_node", "cover_letter_node", "outreach_node",
    # Routing + builder + compiled singleton
    "route_after_intent", "route_after_parse", "should_enhance",
    "route_after_finalize",
    "build_graph", "RESUME_GRAPH",
]
