# Contributing to StackResume

Thanks for taking the time to contribute. StackResume is a single-binary
FastAPI backend + a zero-build vanilla frontend, so the contribution loop is
intentionally short.

## TL;DR

```bash
git clone <repo>
cd stackresume/backend
pip install -r requirements-dev.txt   # includes runtime deps + pytest
pytest                                # full suite, ~30s, fully offline
```

Open a PR. CI runs the suite on Python 3.13.

## Project layout

```
stackresume/
├── frontend/index.html       ← single-file vanilla JS UI
├── backend/
│   ├── app/                  ← FastAPI + LangGraph pipeline + PDF/DOCX/ODT renderers
│   ├── tests/                ← pytest suite (mirrors app/ — see tests/README.md)
│   ├── requirements.txt      ← runtime
│   ├── requirements-dev.txt  ← runtime + pytest + coverage + httpx
│   ├── Dockerfile            ← production image
│   └── Dockerfile.test       ← test image (used by `docker compose --profile test`)
├── docker-compose.yml
└── .github/workflows/        ← CI
```

## Test-driven workflow

Every change should have a test. The suite is organised so the file you edit
maps one-to-one with the test file you should touch:

| Touching… | Add tests under… |
|---|---|
| `app/api/*.py`        | `tests/api/test_*.py` |
| `app/agents/*.py`     | `tests/agents/test_*.py` (LLMs are auto-faked) |
| `app/documents/*.py`  | `tests/documents/test_*.py` |
| `app/config.py`, `auth.py`, `schemas.py`, `runtime_settings.py`, `database.py` | `tests/unit/test_*.py` |

Shared fixtures live in `backend/tests/conftest.py` — use them rather than
rolling your own:

- `async_client` — live FastAPI app over `httpx.AsyncClient` (no port binding)
- `db_session`   — async SQLAlchemy session
- `fake_llm`     — deterministic LLM stand-in; `.set("reviewer", payload)` etc.
- `sample_resume` / `minimal_resume` — ready-to-go resume dicts
- `jd_text`      — a short, realistic job description
- `base_state`   — (agent tests only) a fully populated `AgentState`

The DB is wiped between every test — don't worry about cleanup.

See [`backend/tests/README.md`](backend/tests/README.md) for the full
fixtures reference and FakeLLM cheat-sheet.

## What we expect on a PR

1. **Tests pass locally** — `cd backend && pytest`.
2. **New behaviour comes with new tests** in the matching sub-folder.
3. **No new runtime dependencies** without a one-line justification in the PR.
   (`requirements.txt` ships in the prod image — keep it lean.)
4. **No emojis / cosmetic README rewrites** unless they're part of a UX
   change the PR is actually shipping.
5. **No real provider keys in tests.** The fixtures hard-blank them on
   import; if you find yourself needing one, mock the LLM instead.

## Style

- Python: keep it readable. The codebase favours explicit `if/elif` over
  clever metaprogramming.
- Comments: explain *why*, not *what*. The code already shows what.
- Commits: one logical change per commit. Squash trivia before opening a PR.

## Running the app

```bash
docker compose up --build          # full app at http://localhost:8000
docker compose --profile test up   # run the test suite in Docker
```

Or without Docker, see the "Running without Docker" section of the README.

## Where to ask questions

Open an issue. Tag `question` for design discussions, `bug` for repro
reports, `enhancement` for feature requests.

Happy shipping.
