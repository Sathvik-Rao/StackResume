"""Agent system prompts. Each prompt lives in its own module under
this package; this `__init__` re-exports them so callers can keep
doing `from app.agents.prompts import INTENT_SYSTEM, ...`."""

from .intent import INTENT_SYSTEM
from .parser import PARSER_SYSTEM
from .jd_analyzer import JD_ANALYZER_SYSTEM
from .generator import GENERATOR_SYSTEM
from .reviewer import REVIEWER_SYSTEM
from .enhancer import ENHANCER_SYSTEM
from .cover_letter import COVER_LETTER_SYSTEM
from .outreach import OUTREACH_SYSTEM
from .jd_tailor_enhancer import JD_TAILOR_ENHANCER_SYSTEM

__all__ = [
    "INTENT_SYSTEM",
    "PARSER_SYSTEM",
    "JD_ANALYZER_SYSTEM",
    "GENERATOR_SYSTEM",
    "REVIEWER_SYSTEM",
    "ENHANCER_SYSTEM",
    "COVER_LETTER_SYSTEM",
    "OUTREACH_SYSTEM",
    "JD_TAILOR_ENHANCER_SYSTEM",
]
