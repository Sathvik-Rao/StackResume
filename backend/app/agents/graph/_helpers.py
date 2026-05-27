"""Shared helpers used by every agent node — JSON extraction, dash sanitization,
LLM call timing/retry wrapper, conversation-history formatting, memory-context
string builder, and the JD-intensity-to-instructions translator.
"""
import json
import os
import re
import time
from datetime import datetime, timezone

from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_core.messages import SystemMessage, HumanMessage


def _now_epoch_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _trace_event(agent: str, status: str, notes: str, llm_event: dict | None = None) -> dict:
    return {
        "agent": agent,
        "status": status,
        "notes": notes,
        "timestamp": _now_epoch_ms(),
        "llm_event": llm_event,
    }


def format_exc(e: BaseException) -> str:
    """Human-readable single-line description of an LLM/SDK exception.

    `str(e)` on provider SDK errors (anthropic.BadRequestError, openai.RateLimitError, …)
    drops the type name. Tenacity's RetryError repr is even worse — opaque.
    We attach the type name and bubble up status_code / request_id when the
    SDK exposes them so the chat-side error has the same detail you'd see in
    LangSmith or the server logs.
    """
    typ = type(e).__name__
    msg = (str(e) or "").strip()
    extras = []
    for attr in ("status_code", "code", "request_id"):
        v = getattr(e, attr, None)
        if v and not callable(v):
            extras.append(f"{attr}={v}")
    body = getattr(e, "body", None)
    if isinstance(body, dict):
        provider_msg = (body.get("error") or {}).get("message") if isinstance(body.get("error"), dict) else None
        if provider_msg and provider_msg not in msg:
            msg = f"{msg} — {provider_msg}" if msg else provider_msg
    base = f"{typ}: {msg}" if msg else typ
    return base + (f"  [{' '.join(extras)}]" if extras else "")


def _extract_json(text: str) -> dict:
    """Robust JSON extraction with multiple fallbacks."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE)
    text = text.strip()

    def _try(s: str) -> dict | None:
        try:
            return json.loads(s)
        except (json.JSONDecodeError, ValueError):
            return None

    r = _try(text)
    if r is not None:
        return r

    cleaned = re.sub(r",\s*([\]}])", r"\1", text)
    r = _try(cleaned)
    if r is not None:
        return r

    start = text.find("{")
    if start != -1:
        depth, end = 0, -1
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end > start:
            candidate = re.sub(r",\s*([\]}])", r"\1", text[start:end])
            r = _try(candidate)
            if r is not None:
                return r

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        r = _try(re.sub(r",\s*([\]}])", r"\1", match.group()))
        if r is not None:
            return r

    raise ValueError(f"Could not parse JSON: {text[:300]}")


def _strip_dashes(value):
    """Recursively replace em/en dashes with regular hyphens, and curly quotes with straight ones.

    Belt-and-braces: even when the prompt forbids them, some models still slip them in.
    This sanitises the final JSON so what reaches the user is consistent.
    """
    if isinstance(value, str):
        return (value
                .replace("—", "-")    # em dash
                .replace("–", "-")    # en dash
                .replace("−", "-")    # minus
                .replace("‘", "'").replace("’", "'")
                .replace("“", '"').replace("”", '"'))
    if isinstance(value, list):
        return [_strip_dashes(v) for v in value]
    if isinstance(value, dict):
        return {k: _strip_dashes(v) for k, v in value.items()}
    return value


def _build_history_text(history: list[dict]) -> str:
    lines = []
    for m in history[-8:]:
        role = "User" if m["role"] == "user" else "Assistant"
        content = m["content"][:400] if len(m["content"]) > 400 else m["content"]
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _build_callbacks(agent_name: str) -> list:
    """Attach a fresh LangChainTracer when LangSmith tracing is enabled.

    We construct it lazily on each call so settings changed in the UI take
    effect on the next request without any restart.
    """
    from app.config import settings as _s
    if not (_s.langsmith_tracing and _s.langsmith_api_key):
        return []
    try:
        from langchain_core.tracers.langchain import LangChainTracer
        from langsmith import Client
        client = Client(
            api_url=os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
            api_key=_s.langsmith_api_key,
        )
        return [LangChainTracer(
            project_name=_s.langsmith_project or "stackresume",
            client=client,
        )]
    except Exception:
        return []


def _content_to_text(content) -> str:
    """Normalize a LangChain message `content` to a plain string.

    In langchain-core 1.x, `AIMessage.content` may be a string OR a list of
    content blocks (dicts like `{"type": "text", "text": "..."}` or raw strings).
    Older providers still return a plain string. Collapse both shapes so the
    rest of the pipeline can call `.strip()` etc. safely.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                # Standard text block — keep only its text payload.
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    parts.append(block["text"])
                # Some providers surface a bare {"text": "..."} without a type.
                elif "text" in block and isinstance(block["text"], str):
                    parts.append(block["text"])
        return "".join(parts)
    return str(content)


# reraise=True: when all attempts fail, surface the real underlying exception
# (e.g. anthropic.BadRequestError with the "credit balance too low" message and
# request_id) instead of tenacity's opaque RetryError wrapper.
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
def _call_llm_timed(llm, system: str, human: str, agent_name: str) -> tuple[str, dict]:
    """Call the LLM and return (response_text, llm_event_dict) with timing."""
    t0 = time.monotonic()
    messages = [SystemMessage(content=system), HumanMessage(content=human)]
    callbacks = _build_callbacks(agent_name)
    config = {"callbacks": callbacks, "run_name": f"StackResume · {agent_name}"} if callbacks else {"run_name": f"StackResume · {agent_name}"}
    response = llm.invoke(messages, config=config)
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    # Try to extract token usage. LangChain UsageMetadata is a TypedDict (dict),
    # not a class — use .get() not getattr().
    usage = {}
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        u = response.usage_metadata
        _g = u.get if isinstance(u, dict) else lambda k: getattr(u, k, None)
        usage = {
            "input_tokens": _g("input_tokens"),
            "output_tokens": _g("output_tokens"),
        }
    if not any(usage.values()) and hasattr(response, "response_metadata"):
        meta = response.response_metadata or {}
        # OpenAI / Anthropic
        tu = meta.get("token_usage") or meta.get("usage") or {}
        # Gemini stores it under usage_metadata inside response_metadata
        if not tu:
            um = meta.get("usage_metadata") or {}
            tu = {
                "input_tokens": um.get("prompt_token_count"),
                "output_tokens": um.get("candidates_token_count"),
            }
        usage = {
            "input_tokens": tu.get("prompt_tokens") or tu.get("input_tokens"),
            "output_tokens": tu.get("completion_tokens") or tu.get("output_tokens"),
        }

    llm_event = {
        "agent": agent_name,
        "model": getattr(llm, "model_name", getattr(llm, "model", "unknown")),
        "duration_ms": elapsed_ms,
        "system_prompt": system,
        "user_prompt": human,
        **usage,
    }
    return _content_to_text(response.content), llm_event


def _memory_context_str(memory: dict | None) -> str:
    if not memory:
        return ""
    parts = []
    if memory.get("full_name"):
        parts.append(f"Name: {memory['full_name']}")
    if memory.get("email"):
        parts.append(f"Email: {memory['email']}")
    if memory.get("phone"):
        parts.append(f"Phone: {memory['phone']}")
    if memory.get("location"):
        parts.append(f"Location: {memory['location']}")
    if memory.get("linkedin_url"):
        parts.append(f"LinkedIn: {memory['linkedin_url']}")
    if memory.get("github_url"):
        parts.append(f"GitHub: {memory['github_url']}")
    if memory.get("website"):
        parts.append(f"Website: {memory['website']}")
    if memory.get("portfolio_url"):
        parts.append(f"Portfolio: {memory['portfolio_url']}")
    if memory.get("summary"):
        parts.append(f"Summary: {memory['summary']}")
    if memory.get("target_roles"):
        parts.append(f"Target roles: {', '.join(memory['target_roles'])}")
    if memory.get("total_years_experience"):
        parts.append(f"Total years experience: {memory['total_years_experience']}")
    if memory.get("companies"):
        def _fmt_ym(year, month):
            if not year:
                return None
            return f"{year}/{month:02d}" if month else str(year)
        for c in memory["companies"]:
            from_str = _fmt_ym(c.get("from_year"), c.get("from_month")) or ""
            to_str = _fmt_ym(c.get("to_year"), c.get("to_month")) or "present"
            line = f"Company: {c.get('name')} | {c.get('title')} | {from_str}-{to_str}"
            if c.get("employment_type"):
                line += f" | {c['employment_type']}"
            if c.get("location"):
                line += f" | {c['location']}"
            if c.get("description"):
                line += f" | {c['description'].replace(chr(10), ' ').strip()}"
            parts.append(line)
    if memory.get("education"):
        for e in memory["education"]:
            degree = e.get("degree") or ""
            if e.get("field_of_study"):
                degree = f"{degree} in {e['field_of_study']}" if degree else e["field_of_study"]
            start = e.get("start_year")
            grad = e.get("graduation_year")
            years = f"{start}-{grad}" if start and grad else (str(grad) if grad else (str(start) if start else ""))
            line = f"Education: {degree} from {e.get('institution')}" + (f" ({years})" if years else "")
            extras = []
            if e.get("gpa"):
                extras.append(f"GPA: {e['gpa']}")
            if e.get("honors"):
                extras.append(e["honors"])
            if extras:
                line += f" | {', '.join(extras)}"
            parts.append(line)
    if memory.get("always_include_skills"):
        parts.append(f"Always include skills: {', '.join(memory['always_include_skills'])}")
    if memory.get("certifications"):
        for c in memory["certifications"]:
            bits = [c.get("name")]
            if c.get("issuer"):
                bits.append(f"by {c['issuer']}")
            if c.get("year"):
                bits.append(f"({c['year']})")
            if c.get("url"):
                bits.append(c["url"])
            parts.append("Certification: " + " ".join(b for b in bits if b))
    if memory.get("languages_spoken"):
        langs = []
        for lang in memory["languages_spoken"]:
            name = lang.get("language")
            if not name:
                continue
            prof = lang.get("proficiency")
            langs.append(f"{name} ({prof})" if prof else name)
        if langs:
            parts.append(f"Languages spoken: {', '.join(langs)}")
    if memory.get("projects"):
        for p in memory["projects"]:
            bits = [p.get("name")]
            if p.get("role"):
                bits.append(f"as {p['role']}")
            if p.get("year"):
                bits.append(f"({p['year']})")
            if p.get("technologies"):
                bits.append(f"[{', '.join(p['technologies'])}]")
            if p.get("description"):
                bits.append(f"- {p['description']}")
            if p.get("url"):
                bits.append(p["url"])
            parts.append("Project: " + " ".join(b for b in bits if b))
    if memory.get("open_to_remote") is not None:
        parts.append(f"Open to remote: {'yes' if memory['open_to_remote'] else 'no'}")
    if memory.get("work_authorization"):
        parts.append(f"Work authorization: {memory['work_authorization']}")
    if memory.get("availability"):
        parts.append(f"Availability: {memory['availability']}")
    if memory.get("personal_notes"):
        parts.append(f"Notes: {memory['personal_notes']}")
    return "\n".join(parts) if parts else ""


def _jd_intensity_directive(intensity: int | None) -> str:
    """Translate the 0–100 JD-tailoring slider into concrete instructions for
    the LLM. 100 = full rewrite; lower values progressively constrain how much
    of the existing resume the model is allowed to touch."""
    if intensity is None:
        intensity = 100
    intensity = max(0, min(100, int(intensity)))
    if intensity >= 90:
        return (
            f"JD TAILORING INTENSITY: {intensity}/100 — FULL.\n"
            "Tailor every section to the job description. Rewrite the summary, "
            "reorder experience bullets, mirror JD keywords and phrasing throughout, "
            "and rebuild core_competencies around the JD's required + preferred skills."
        )
    if intensity >= 65:
        return (
            f"JD TAILORING INTENSITY: {intensity}/100 — HEAVY but conservative.\n"
            "Tailor the professional summary and core_competencies to the JD, "
            "reorder bullets so the most JD-relevant ones surface first, and inject "
            "the top JD keywords where they fit. Keep the candidate's original "
            "wording on bullets that don't directly map to the JD."
        )
    if intensity >= 35:
        return (
            f"JD TAILORING INTENSITY: {intensity}/100 — MODERATE.\n"
            "Make targeted adjustments only: tweak the professional summary so it "
            "acknowledges the role, surface 2–4 of the most relevant JD keywords in "
            "the most relevant experience bullets, and add any obvious missing skills "
            "to core_competencies. Leave the rest of the resume's wording, bullet "
            "order, and structure UNCHANGED."
        )
    if intensity >= 10:
        return (
            f"JD TAILORING INTENSITY: {intensity}/100 — LIGHT TOUCH.\n"
            "Make at most 1–2 small adjustments aligning the resume to the JD — "
            "e.g. nudge the summary or add a single keyword to one bullet. Do NOT "
            "rewrite bullets, reorder sections, or restructure core_competencies. "
            "Preserve the candidate's original resume almost verbatim."
        )
    return (
        f"JD TAILORING INTENSITY: {intensity}/100 — NONE.\n"
        "Do NOT tailor the resume to the job description. Treat the JD as background "
        "context only; preserve the candidate's resume content, wording, ordering, "
        "and structure exactly as provided."
    )
