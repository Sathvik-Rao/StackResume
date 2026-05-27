"""Wire the agent nodes into the LangGraph state machine.

Calling ``build_graph()`` returns a freshly compiled graph; the module-level
``RESUME_GRAPH`` is the singleton used throughout the app.
"""
from langgraph.graph import StateGraph, END

from app.agents.state import AgentState

from ._intent import intent_check_node, off_topic_node
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


def build_graph():
    g = StateGraph(AgentState)

    g.add_node("intent_check", intent_check_node)
    g.add_node("off_topic", off_topic_node)
    g.add_node("parse_input", parse_input_node)
    g.add_node("jd_analyze", jd_analyze_node)
    g.add_node("generate_resume", generate_resume_node)
    g.add_node("review_resume", review_resume_node)
    g.add_node("enhance_resume", enhance_resume_node)
    g.add_node("finalize", finalize_node)
    g.add_node("write_cover_letter", cover_letter_node)
    g.add_node("write_outreach", outreach_node)

    g.set_entry_point("intent_check")
    g.add_conditional_edges("intent_check", route_after_intent, {
        "off_topic": "off_topic",
        "parse": "parse_input",
    })
    g.add_edge("off_topic", END)
    g.add_conditional_edges("parse_input", route_after_parse, {
        "jd_analyze": "jd_analyze",
        "generate": "generate_resume",
    })
    g.add_edge("jd_analyze", "generate_resume")
    g.add_edge("generate_resume", "review_resume")
    g.add_conditional_edges("review_resume", should_enhance, {
        "enhance": "enhance_resume",
        "finalize": "finalize",
    })
    g.add_edge("enhance_resume", "review_resume")
    g.add_conditional_edges("finalize", route_after_finalize, {
        "cover_letter": "write_cover_letter",
        "end": END,
    })
    g.add_edge("write_cover_letter", "write_outreach")
    g.add_edge("write_outreach", END)

    return g.compile()


RESUME_GRAPH = build_graph()
