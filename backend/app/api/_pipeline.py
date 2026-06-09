"""Shared internals for the API routers: the run/cancellation registry, the
background pipeline runner, and the helpers that build summary / error
messages from final pipeline state.

Underscore prefix to signal "not part of the public API surface" — only the
per-feature route modules in this package should import from here.
"""
import asyncio
import threading
import traceback
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import Session, Message, UserMemory


# ── In-process run registry (cancellation + liveness) ─────────────────────────
# msg_id → threading.Event (set when user cancels)
_CANCEL_EVENTS: dict[str, threading.Event] = {}


def _register_run(msg_id: str) -> threading.Event:
    ev = threading.Event()
    _CANCEL_EVENTS[msg_id] = ev
    return ev


def _release_run(msg_id: str) -> None:
    _CANCEL_EVENTS.pop(msg_id, None)


def get_cancel_event(msg_id: str) -> threading.Event | None:
    return _CANCEL_EVENTS.get(msg_id)


# ── Memory loader ─────────────────────────────────────────────────────────────

async def _load_memory(db: AsyncSession) -> dict | None:
    result = await db.execute(select(UserMemory).limit(1))
    mem = result.scalar_one_or_none()
    if not mem:
        return None
    return {
        "full_name": mem.full_name, "email": mem.email, "phone": mem.phone,
        "location": mem.location, "linkedin_url": mem.linkedin_url,
        "github_url": mem.github_url, "website": mem.website,
        "portfolio_url": getattr(mem, "portfolio_url", None),
        "summary": getattr(mem, "summary", None),
        "target_roles": mem.target_roles or [],
        "total_years_experience": mem.total_years_experience,
        "companies": mem.companies or [],
        "education": mem.education or [],
        "always_include_skills": mem.always_include_skills or [],
        "certifications": getattr(mem, "certifications", None) or [],
        "languages_spoken": getattr(mem, "languages_spoken", None) or [],
        "projects": getattr(mem, "projects", None) or [],
        "open_to_remote": getattr(mem, "open_to_remote", None),
        "work_authorization": getattr(mem, "work_authorization", None),
        "availability": getattr(mem, "availability", None),
        "personal_notes": mem.personal_notes,
    }


# ── Background pipeline ───────────────────────────────────────────────────────

async def _save_progress(msg_id: str, events: list) -> None:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Message).where(Message.id == msg_id))
            msg = result.scalar_one_or_none()
            if msg and msg.status == "processing":
                msg.progress_events = events
                msg.agent_trace = events
                await db.commit()
    except Exception:
        pass


async def _run_pipeline_background(msg_id: str, session_id: str, initial_state: dict,
                                   run_meta: dict | None = None):
    # Imported lazily so the test harness can stub the graph without forcing a
    # heavy import chain at app startup.
    from app.agents.graph import RESUME_GRAPH

    cancel_ev = _register_run(msg_id)
    loop = asyncio.get_running_loop()

    def _push_progress(events: list) -> None:
        """Schedule a DB write back on the main loop from the worker thread."""
        try:
            asyncio.run_coroutine_threadsafe(_save_progress(msg_id, list(events)), loop)
        except Exception:
            pass

    final_state_holder: dict = {"final": initial_state, "cancelled": False}

    def _sync_stream():
        last_state = initial_state
        try:
            for chunk in RESUME_GRAPH.stream(initial_state):
                if cancel_ev.is_set():
                    final_state_holder["cancelled"] = True
                    return
                node_state = next(iter(chunk.values()))
                last_state = node_state
                _push_progress(node_state.get("agent_trace", []))
        finally:
            final_state_holder["final"] = last_state

    try:
        await loop.run_in_executor(None, _sync_stream)

        if final_state_holder["cancelled"]:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Message).where(Message.id == msg_id))
                msg = result.scalar_one_or_none()
                if msg and msg.status == "processing":
                    msg.status = "cancelled"
                    msg.content = "⏹ Generation stopped."
                    await db.commit()
            return

        final_state = final_state_holder["final"]

        if final_state.get("is_off_topic"):
            reply = final_state.get("off_topic_response", "I can only help with resume-related tasks.")
            trace = final_state.get("agent_trace", [])
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Message).where(Message.id == msg_id))
                msg = result.scalar_one_or_none()
                if msg:
                    msg.status = "complete"
                    msg.content = reply
                    msg.agent_trace = trace
                    msg.progress_events = trace
                    await db.commit()
            return

        resume = final_state.get("resume")
        trace = final_state.get("agent_trace", [])
        iteration = final_state.get("iteration", 1)
        # Coerce defensively — LLMs occasionally emit `"high"` or `null` and the
        # Float column would otherwise reject the value at commit time.
        score = _safe_score((resume.get("metadata") or {}).get("overall_score", 0)) if resume else 0.0
        cover_letter = final_state.get("cover_letter")
        outreach_emails = final_state.get("outreach_emails")

        # If the pipeline finished without exception but never produced a resume,
        # an agent failed silently (LLM auth, malformed JSON, etc.). Surface the
        # actual error from state + agent_trace instead of a generic message,
        # and mark the message failed so the UI renders it as an error.
        if not resume:
            status_str = "failed"
            summary = _build_no_resume_error(
                final_state, provider=initial_state.get("llm_provider"),
                model=initial_state.get("llm_model"),
            )
        else:
            status_str = "complete"
            meta_info = run_meta or {}
            summary = _build_summary(
                resume, has_cover=bool(cover_letter), n_emails=len(outreach_emails or []),
                used_memory=bool(meta_info.get("used_memory")),
                from_master_name=meta_info.get("from_master_name"),
            )

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Message).where(Message.id == msg_id))
            msg = result.scalar_one_or_none()
            if msg:
                msg.status = status_str
                msg.content = summary
                msg.resume_json = resume
                msg.cover_letter = cover_letter
                msg.outreach_emails = outreach_emails
                msg.agent_trace = trace
                msg.progress_events = trace
                msg.iteration_count = iteration
                msg.final_score = score
                await db.commit()

            if resume:
                name = resume.get("personal_info", {}).get("full_name", "")
                role_title = resume.get("personal_info", {}).get("professional_title", "")
                if name:
                    new_title = f"{name} — {role_title}" if role_title else name
                    result2 = await db.execute(select(Session).where(Session.id == session_id))
                    sess = result2.scalar_one_or_none()
                    if sess and (not sess.title or sess.title in ("New Resume", "")):
                        sess.title = new_title[:255]
                        sess.updated_at = datetime.now(timezone.utc)
                        await db.commit()

    except Exception as e:
        traceback.print_exc()
        from app.agents.graph import format_exc as _fmt_exc
        existing_trace = list(final_state_holder["final"].get("agent_trace") or [])
        existing_trace.append({
            "agent": "Pipeline", "status": "error", "notes": _fmt_exc(e),
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
        })
        last_agent = _last_running_agent(existing_trace) or "Pipeline"
        provider = initial_state.get("llm_provider") or "?"
        model = initial_state.get("llm_model") or "?"
        tb_text = traceback.format_exc()
        body = [
            f"⚠️ **Pipeline error** — failed in **{last_agent}**",
            f"**Provider:** `{provider}` · **Model:** `{model}`",
            "",
            f"**{_fmt_exc(e)}**",
        ]
        failing_agents = [t for t in existing_trace if t.get("status") == "error"]
        if len(failing_agents) > 1:
            body.append("")
            body.append("**Agent errors during this run:**")
            for t in failing_agents[-5:]:
                body.append(f"- `{t.get('agent','?')}`: {t.get('notes','(no detail)')}")
        # Sentinel — the frontend splits on this and renders the trailing
        # block in a collapsible <details> with a copy button.
        msg_content = "\n".join(body)
        if tb_text:
            msg_content += f"\n\n@@TRACEBACK@@\n{tb_text.strip()}"
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Message).where(Message.id == msg_id))
            msg = result.scalar_one_or_none()
            if msg:
                msg.status = "failed"
                msg.content = msg_content
                msg.agent_trace = existing_trace
                msg.progress_events = existing_trace
                await db.commit()
    finally:
        _release_run(msg_id)


# ── Failure-message builders ──────────────────────────────────────────────────

def _last_running_agent(trace: list) -> str | None:
    """Most recent agent that errored or was still running — what to blame."""
    for entry in reversed(trace or []):
        if entry.get("status") in ("error", "running"):
            return entry.get("agent")
    return (trace[-1].get("agent") if trace else None)


def _build_no_resume_error(state: dict, provider: str | None, model: str | None) -> str:
    """Detailed message for the case where the pipeline finished cleanly but
    produced no resume (an agent caught its exception and returned without
    setting state['resume'])."""
    trace = state.get("agent_trace") or []
    err = state.get("error")
    failing = [e for e in trace if e.get("status") == "error"]
    last_agent = (failing[-1].get("agent") if failing else None) or _last_running_agent(trace) or "Resume Generator"
    last_notes = (failing[-1].get("notes") if failing else None) or err or "No specific error was recorded."

    lines = [
        f"⚠️ **Couldn't generate a resume** — `{last_agent}` did not return a usable result.",
        f"**Provider:** `{provider or '?'}` · **Model:** `{model or '?'}`",
        "",
        f"**Details:** {last_notes}",
    ]
    if len(failing) > 1:
        lines.append("")
        lines.append("**Other agent errors:**")
        for e in failing[:-1][-3:]:
            lines.append(f"- `{e.get('agent','?')}`: {e.get('notes','(no detail)')}")
    lines.append("")
    lines.append("Try again, or check **🔑 API Keys** — a missing key or wrong model name is the most common cause.")

    # Build a pseudo-traceback block from the full agent_trace timeline so the
    # collapsible details panel has substance even though the underlying
    # exception was swallowed inside an agent.
    if trace:
        report = []
        report.append(f"Agent timeline ({len(trace)} step{'s' if len(trace) != 1 else ''}):")
        for e in trace:
            ts = e.get("timestamp")
            ts_str = ""
            if ts:
                try:
                    ts_str = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z"
                    ts_str = f"[{ts_str}] "
                except Exception:
                    ts_str = ""
            report.append(f"{ts_str}{e.get('agent','?'):<22}  {e.get('status','?'):<8}  {(e.get('notes') or '').strip()}")
            ev = e.get("llm_event") or {}
            if ev:
                in_t = ev.get("input_tokens"); out_t = ev.get("output_tokens"); dur = ev.get("duration_ms")
                tok = f"{in_t}->{out_t}tk" if in_t else ""
                dur_str = f"{dur}ms" if dur else ""
                meta = " · ".join(x for x in [ev.get("model",""), tok, dur_str] if x)
                if meta:
                    report.append(f"{' ' * (len(ts_str) + 24)}↳ {meta}")
        return "\n".join(lines) + "\n\n@@TRACEBACK@@\n" + "\n".join(report)
    return "\n".join(lines)


def _safe_score(v) -> float:
    """Coerce any LLM-emitted score to a float. Bad payloads ('high', None, …)
    would otherwise blow up `f"{score:.0f}"` and take the whole summary down."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _build_summary(resume: dict | None, has_cover: bool = False, n_emails: int = 0,
                   used_memory: bool = False, from_master_name: str | None = None) -> str:
    if not resume:
        return "I encountered an issue generating your resume. Please try again."
    meta = resume.get("metadata", {})
    name = resume.get("personal_info", {}).get("full_name", "your profile")
    title = resume.get("personal_info", {}).get("professional_title", "Software Developer")
    score = _safe_score(meta.get("overall_score", 0))
    iterations = meta.get("iteration_count", 1)
    review_notes = meta.get("review_notes", "")
    jd_score_raw = meta.get("jd_match_score")
    jd_score = _safe_score(jd_score_raw) if jd_score_raw else None
    jd_role = meta.get("jd_role")

    lines = [
        f"✅ Resume generated for **{name}** ({title})",
        f"📊 Quality Score: **{score:.0f}/100**" + (f" · JD Match: **{jd_score:.0f}/100**" if jd_score else ""),
        f"🔄 Refinement passes: {iterations}",
    ]
    if jd_role:
        lines.append(f"🎯 Tailored for: **{jd_role}**")
    if has_cover or n_emails:
        bonus = []
        if has_cover:
            bonus.append("a tailored **cover letter**")
        if n_emails:
            bonus.append(f"**{n_emails} outreach email templates**")
        lines.append(f"📨 Also generated: {' and '.join(bonus)} — see the tabs above.")
    if review_notes:
        lines.append(f"\n💡 {review_notes}")

    improvements = meta.get("improvement_suggestions", [])
    if improvements:
        lines.append("\n**Suggestions for further improvement:**")
        for s in improvements[:3]:
            lines.append(f"• {s}")

    # Provenance note — records what fed this generation so it's clear on a later
    # read whether the master resume and/or profile memory were applied.
    sources = []
    if from_master_name:
        sources.append(f'master resume **{from_master_name}**')
    if used_memory:
        sources.append("your **profile memory**")
    if sources:
        lines.append(f"\n📎 Generated using {' and '.join(sources)}.")

    lines.append("")
    lines.append("Tip: ask me to refine sections, raise seniority, target a company, add certifications, or paste a JD to tailor.")
    return "\n".join(lines)
