# AGENTS.md

Guidance for AI coding assistants (Claude Code, Cursor, Codex, Aider, Copilot,
Gemini, Windsurf, …) working on **StackResume**.

This file follows the open [agents.md](https://agents.md) spec — most modern
coding agents read it automatically. For agents that prefer their own filename,
create symlinks instead of duplicating content (see the bottom of this file).

- **Humans** → read [`CONTRIBUTING.md`](CONTRIBUTING.md) first.
- **AI agents** → read `CONTRIBUTING.md` *and* the rules below.

---

## Project shape

| Layer | Where | What |
|---|---|---|
| Backend | `backend/app/` | FastAPI + LangGraph + async SQLAlchemy/SQLite |
| Frontend | `frontend/` | Vanilla HTML/CSS/JS — single `index.html`, no build step, no npm |
| Tests | `backend/tests/` | pytest, mirrors `app/` 1:1; runs fully offline |
| Pipeline | `backend/app/agents/graph/` | Multi-agent LangGraph; one file per node under `nodes/` |
| Docs | `README.md`, `CONTRIBUTING.md`, `backend/tests/README.md` | Authoritative |

Read `CONTRIBUTING.md` for the test ↔ code mapping and branch/PR conventions.

---

## Hard rules

1. **No new runtime dependencies** in `backend/requirements.txt` without a
   one-line justification in the PR. The prod image ships this file — keep it lean.
2. **Tests are mandatory.** Every change to `backend/app/**.py` needs a
   matching test under `backend/tests/**.py`. The full suite must pass:
   `cd backend && pytest` (~30 s, offline).
3. **LLMs in tests = the `fake_llm` fixture.** Never call a real provider.
   See `backend/tests/fixtures/llm_fakes.py`. Drive responses with
   `fake_llm.set("agent_key", payload)`; force errors with `fake_llm.fail_with(...)`.
4. **Don't break the offline guarantee.** `backend/tests/conftest.py` scrubs
   `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` / `LANGSMITH_API_KEY`
   at import time. Don't read live env vars in tests.
5. **No new `*.md` docs** unless explicitly requested. Don't auto-generate
   READMEs, CHANGELOGs, design docs, or planning notes.
6. **No emojis in code or comments** unless the user explicitly asks. UI text
   (sidebar labels, toasts, agent step descriptions) is the only exception.
7. **No `--no-verify`, `--force-push`, or destructive `git reset --hard`**
   without explicit user approval — even if the user pre-approved a similar
   action earlier in the session.

---

## Code style — match what's already here

- **Comments explain *why*, not *what*.** The identifiers already say what.
  Write a comment only when the *why* is non-obvious: a hidden constraint, a
  subtle invariant, a workaround for a specific bug, behavior that would
  surprise a future reader.
- **Python:** explicit `if`/`elif`, no clever metaprogramming. Type hints on
  signatures where they help readers. Keep pure functions pure; isolate I/O.
- **One concern per file.** When a module passes ~250 lines, split it the way
  this codebase already does (see "Splitting patterns" below).
- **Validate at boundaries only** (HTTP request bodies, file uploads, JSON
  parsed back from the LLM). Internal callers don't need defensive checks
  for shapes the type system already guarantees.
- **Names match the existing vocabulary.** `_extract_json`, `_strip_dashes`,
  `_call_llm_timed`, `_safe_score`, "Intent Guard", "Resume Generator",
  "JD Tailoring", `sessionProcessing`, `inFlightSends`. Don't rename
  established concepts.
- **Finish what you start.** No TODO comments for the next session, no
  half-wired feature flags, no dead branches.
- **Three similar lines is better than a premature abstraction.** Wait for a
  real third use case before extracting a helper.

---

## Splitting / decoupling patterns the codebase already uses

When a file you're editing has grown too big, the accepted moves are:

- **Per-feature router files** — `app/api/sessions_routes.py`,
  `messages_routes.py`, `document_routes.py`, … (not one giant `routes.py`).
  Shared internals live in `app/api/_pipeline.py`. The underscore prefix
  signals *package-internal*.
- **Per-node agent files** — `app/agents/graph/nodes/parse.py`,
  `generate.py`, `review.py`, … Re-exported from `app/agents/graph/__init__.py`
  so importers keep using `from app.agents.graph import generate_resume_node`.
- **Per-prompt files** — `app/agents/prompts/<role>.py`, re-exported from
  the prompts `__init__.py`.
- **Shared graph helpers under `_*.py`** — `_helpers.py`, `_intent.py`,
  `_routing.py`, `_builder.py`. Underscore = "not part of the public API surface."

Follow the same shape when you create new modules.

---

## Architectural patterns to follow

- **Two-tier settings.** `.env` baseline → `app_settings` DB overlay
  (`app/runtime_settings.py`). To add a new tunable:
  1. Add the field to `Settings` in `app/config.py` (with a default).
  2. Add the column to `AppSettings` in `app/models.py`.
  3. Append an `ALTER TABLE` entry to `_MIGRATIONS` in `app/database.py`.
  4. Add the field to `AppSettingsUpsert` in `app/api/settings_routes.py`.
  5. Surface it in the Settings UI (`frontend/js/section-prefs.js` /
     `settings.js` / `keys.js`).
- **LangGraph nodes** have the signature `def fn(state: AgentState) -> AgentState`.
  Append a `_trace_event(...)` for every meaningful step. Wrap LLM calls
  with `_call_llm_timed`. Parse the response with `_extract_json` — it
  handles fenced blocks, trailing commas, and preamble text robustly.
- **Defensive normalization at the boundary.** `app/documents/_normalize.py`
  rescues char-split lists (`list("phrase")` artifacts) and coerces
  string-where-list-was-expected for known list fields. The PDF/DOCX/ODT
  generators rely on it — call it before rendering.
- **Background work.** API route → `BackgroundTasks` →
  `_run_pipeline_background` → `loop.run_in_executor` (LangGraph's
  `.stream()` is synchronous). Cancellation goes through the in-process
  `_CANCEL_EVENTS` registry keyed by message id.
- **Frontend state.** Module-globals in `frontend/js/state.js`. Per-message
  state lives in `messageStates[msgId]`. Persisted user prefs go in
  `localStorage` with the `sr_*` prefix (e.g. `sr_p`, `sr_m`, `sr_theme`).
  Auth tokens go in `sessionStorage` (`sr_auth`).
- **Frontend `index.html`** loads scripts in a deliberate order at the
  bottom of the file. `state.js` must load before anything that touches
  globals; `bootstrap.js` runs last and calls `init()`. Don't reorder
  without verifying.

---

## Writing tests

- **Path mirroring.** A change in `app/api/foo.py` needs tests in
  `tests/api/test_foo.py`. A change in `app/agents/graph/nodes/bar.py`
  needs tests in `tests/agents/test_bar*.py` or `test_*pipeline*.py`.
- **Use the existing fixtures** from `tests/conftest.py` —
  `async_client`, `db_session`, `fake_llm`, `sample_resume`,
  `minimal_resume`, `jd_text`, `base_state`. Never roll your own DB
  setup; the autouse `_reset_database` fixture wipes between tests.
- **Mark intent** with `pytestmark = pytest.mark.unit` (or `api` /
  `agents` / `documents`) at module top.
- **Cover happy path + at least one failure / edge case.** Most
  regressions in this repo come from un-tested error branches.
- **Async tests are auto-detected** (`asyncio_mode = auto` in `pytest.ini`).
  Just use `async def test_...`.

---

## What NOT to touch without an explicit ask

- `tests/conftest.py` env-scrubbing block (runs before app import — order matters).
- The `_MIGRATIONS` list in `app/database.py` — **append only**, never reorder
  or delete; each entry is idempotent and historical.
- Script load order at the bottom of `frontend/index.html`.
- `metadata.json` — read by Docker Hub and release tooling.
- `.github/workflows/ci.yml` — controls release tagging + Docker publish.

---

## Risky actions — always confirm

The user's previous approval applies to **that one action only**.
Re-confirm for the next:

- `git push --force` / `--force-with-lease`
- `git reset --hard`, `git clean -fd`, `git checkout .`
- `gh pr merge`, `gh pr close`, `gh issue close` (esp. in bulk)
- Deleting branches, tags, or releases
- `rm -rf` on anything outside `.pytest_cache/` / `__pycache__/` / build output
- Editing CI secrets or `settings.json` permissions

When you encounter unexpected files / branches / lock-files, **investigate
before deleting** — they may represent the user's in-progress work.

---

## Sister-tool config files

Most agents read their own filename. Keep one source of truth by
symlinking — don't copy-paste:

```bash
# Run once at the repo root:
ln -s AGENTS.md CLAUDE.md                                # Claude Code
ln -s AGENTS.md .cursorrules                             # Cursor
ln -s AGENTS.md GEMINI.md                                # Gemini CLI
ln -s AGENTS.md .windsurfrules                           # Windsurf
mkdir -p .github && ln -s ../AGENTS.md .github/copilot-instructions.md
```

Symlinks survive `git` cleanly on macOS/Linux. On Windows, prefer a
one-line pointer file (`See AGENTS.md`) over a symlink.
