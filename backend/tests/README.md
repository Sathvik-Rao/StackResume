# StackResume — Test Suite

A scalable test layout that mirrors the production code, so a contributor can
find (or add) tests by guessing the same path as the source file.

## Layout

```
backend/
├── pytest.ini
├── requirements-dev.txt
└── tests/
    ├── conftest.py              # ← shared fixtures (DB, async_client, fake_llm, sample resumes)
    ├── fixtures/                # ← reusable test data: resumes, file bytes, fake LLM
    │   ├── resumes.py
    │   ├── llm_fakes.py
    │   └── files.py
    ├── unit/                    # ← pure-function tests (no FastAPI, no DB)
    │   ├── test_config.py
    │   ├── test_auth.py
    │   ├── test_runtime_settings.py
    │   ├── test_schemas.py
    │   ├── test_llm_factory.py
    │   ├── test_graph_helpers.py
    │   ├── test_routing.py
    │   ├── test_models.py
    │   ├── test_section_preferences.py
    │   └── test_documents_normalize.py
    ├── api/                     # ← HTTP-level tests against the live FastAPI app
    │   ├── test_health_config.py
    │   ├── test_sessions.py
    │   ├── test_messages.py
    │   ├── test_memory.py
    │   ├── test_document_routes.py
    │   ├── test_settings_routes.py
    │   ├── test_metrics_routes.py
    │   ├── test_upload_routes.py
    │   └── test_auth_flow.py
    ├── agents/                  # ← LangGraph nodes + end-to-end pipeline (LLM faked)
    │   ├── conftest.py          # ← shared `base_state` fixture
    │   ├── test_intent_guard.py
    │   ├── test_parser_and_jd.py
    │   ├── test_generator_reviewer_enhancer.py
    │   ├── test_cover_letter_and_outreach.py
    │   └── test_full_pipeline.py
    └── documents/               # ← PDF / DOCX / ODT generator smoke tests
        ├── test_pdf_generator.py
        ├── test_docx_generator.py
        ├── test_odt_generator.py
        └── test_cover_letter_pdf.py
```

## Running

```bash
cd backend
pip install -r requirements-dev.txt

# Everything (~30s on a modern laptop, fully offline)
pytest

# One layer
pytest tests/unit
pytest tests/api
pytest tests/agents
pytest tests/documents

# By marker
pytest -m unit
pytest -m api
pytest -m agents
pytest -m documents
pytest -m "not slow"

# Coverage
pytest --cov=app --cov-report=term-missing
```

### Docker

```bash
docker compose --profile test up --build --abort-on-container-exit
```

Runs the full suite inside the same Python 3.13 base image the app ships on,
so a green local run guarantees a green CI run.

## How to add a test

1. **Find the corresponding source file** (`app/api/foo.py`).
2. **Open or create the matching test file** under the same sub-tree
   (`tests/api/test_foo.py`).
3. **Use the existing fixtures from `conftest.py`** — don't roll your own
   client or DB session:

   | Fixture          | What you get |
   |------------------|--------------|
   | `async_client`   | `httpx.AsyncClient` bound to the live FastAPI app (no port, no network) |
   | `db_session`     | An `AsyncSession` you can use to seed/inspect rows directly |
   | `fake_llm`       | Patches every `get_llm(...)` call so agents run offline. Returns a `FakeLLM` you can drive with `.set(agent_key, payload)` |
   | `sample_resume`  | Fully-populated resume dict (every section the renderers care about) |
   | `minimal_resume` | Smallest valid resume — use to test degrade-gracefully behaviour |
   | `jd_text`        | A short, realistic job description string |
   | `base_state`     | (agents/ only) A fully-formed `AgentState` you can mutate per test |

4. **Database is wiped before every test** via the autouse `_reset_database`
   fixture in `conftest.py`. No cross-test bleed; no manual cleanup.

## Driving the FakeLLM

The fake is fingerprinted from the **system prompt** so each agent gets its
own payload. Override per-agent:

```python
def test_my_thing(fake_llm, base_state):
    fake_llm.set("reviewer", {"overall_score": 50, "critical_issues": ["x"]})
    fake_llm.set_raw("parser", "not even json — should fall back gracefully")
    fake_llm.fail_with("generator", RuntimeError("provider down"))
    ...
```

Available agent keys: `intent`, `parser`, `jd_analyzer`, `generator`,
`reviewer`, `enhancer`, `cover_letter`, `outreach`.

## Conventions

- **Async tests** are auto-detected (`asyncio_mode = "auto"` in `pytest.ini`);
  no `@pytest.mark.asyncio` decorator needed.
- **Module-level `pytestmark`** sets the marker for every test in the file —
  use it instead of decorating each function.
- **Polling**: API tests that wait for the background pipeline use
  `_poll_until_done` (see `test_messages.py`). 10-second cap.
- **No real provider keys** ever land in the test environment — `conftest.py`
  scrubs them on import.

## CI

The GitHub Actions workflow at `.github/workflows/ci.yml` runs the suite on
Python 3.13 against every push and PR, uploads the coverage XML,
and (on pushes to `main` / `v*` tags) publishes the backend image to Docker
Hub.
