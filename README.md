<div align="center">
  <img src="logo/wordmark.svg" alt="StackResume" width="380" />
  <br/><br/>
  <p><strong>Self-hosted, AI-powered resume builder for software developers.</strong><br/>
  One sentence in → polished, ATS-optimised resume out — running entirely on your own machine.</p>

  ![Python](https://img.shields.io/badge/Python-3.13%2B-3776AB?logo=python&logoColor=white)
  ![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)
  ![LangGraph](https://img.shields.io/badge/LangGraph-multi--agent-FF6B35)
  ![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
  ![Self-hosted](https://img.shields.io/badge/self--hosted-yes-8B5CF6)
  ![Open Source](https://img.shields.io/badge/open%20source-GPL--3.0-22C55E)
  ![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)
</div>

---

## Table of contents

1. [What it does](#what-it-does)
2. [Why self-host?](#why-self-host)
3. [Quick start (Docker)](#quick-start-docker)
4. [Build from source](#build-from-source)
5. [Features](#features)
6. [Tech stack](#tech-stack)
7. [Architecture & pipeline](#architecture--pipeline)
8. [Configuration](#configuration)
9. [Running without Docker](#running-without-docker)
10. [Testing](#testing)
11. [Contributing](#contributing)
12. [License](#license)

---

## What it does

StackResume turns minimal input into a polished, interview-ready software-developer resume. The multi-agent pipeline:

- **Parses** your message into structured data, with optional persistent profile memory injected automatically.
- **Generates** a complete resume JSON with STAR-format bullets and quantified metrics.
- **Reviews & enhances** in a loop — a Reviewer agent scores ATS compatibility, writing quality, impact, and completeness (0–100 each), then an Enhancer rewrites weak bullets and injects missing keywords. Loops until the score crosses `MIN_QUALITY_SCORE` (default 82) or hits `MAX_REVIEW_ITERATIONS` (default 3).
- **Tailors** — paste a job description to unlock a cover letter and a library of outreach email templates alongside the resume.
- **Exports** to PDF, Word (`.docx`), or OpenDocument (`.odt`) across four visual templates.

Everything is wrapped in a chat-style web UI with persistent sessions, search, favourites, an application tracker, and a live LLM activity log.

---

## Why self-host?

StackResume is built to live on **your** infrastructure — a laptop, a homelab box, a private VPS, a corporate VM. Nothing is rented, nothing phones home.

- **Your data stays put.** Sessions, profile, master resumes, and uploads sit in a single SQLite file under the bind-mounted `./data` directory. Back it up, encrypt it, move it between machines — it's a flat file.
- **No SaaS, no telemetry, no tracking.** The container talks to one place: whichever LLM provider *you* configure. Nothing else leaves the box.
- **Bring your own key — or skip keys entirely.** Plug in OpenAI / Anthropic / Google Gemini, or point at a local [Ollama](https://ollama.com) install for fully **offline, zero-cost** inference. No vendor lock-in.
- **Open source under GPL-3.0.** Read it, audit it, fork it, patch it. The whole pipeline — agents, prompts, document renderers — is in this repo.
- **One container, anywhere Docker runs.** Multi-arch image (`amd64`, `arm64`, `armv7`) — runs on a Raspberry Pi just as happily as on a bare-metal server.
- **Optional single-user auth.** Flip one env var to put it behind SHA-512 + session-token login if you expose it on a LAN or behind a tunnel.

---

## Quick start (Docker)

No clone needed — pull the pre-built multi-arch image (`amd64` / `arm64` / `armv7`) straight from [Docker Hub](https://hub.docker.com/r/sathvikrao/stackresume).

**Minimal:**

```bash
docker run -d -p 8000:8000 -v ./data:/data sathvikrao/stackresume:latest
```

API keys and provider settings can be configured from the in-app **⚙️ Settings** UI after the container is running.

<details>
<summary><strong>Full docker-compose.yml (all options)</strong></summary>

```yaml
services:
  stackresume:
    image: sathvikrao/stackresume:latest
    container_name: stackresume
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data
    environment:
      # ── LLM Provider ────────────────────────────────────────────────────────
      - LLM_PROVIDER=google           # openai | anthropic | google | ollama | custom
      - LLM_MODEL=gemini-2.5-flash
      - LLM_TEMPERATURE=0.7           # 0 = deterministic, 1 = creative

      # ── API Keys (set the one matching LLM_PROVIDER) ────────────────────────
      - OPENAI_API_KEY=
      - ANTHROPIC_API_KEY=
      - GOOGLE_API_KEY=
      - OPENAI_BASE_URL=              # custom OpenAI-compatible endpoint only

      # ── Ollama (local inference, no key needed) ──────────────────────────────
      - OLLAMA_BASE_URL=http://host.docker.internal:11434

      # ── Pipeline tuning ──────────────────────────────────────────────────────
      - MAX_REVIEW_ITERATIONS=3       # max Reviewer→Enhancer loops
      - MIN_QUALITY_SCORE=82.0        # stop early once score crosses this (0–100)

      # ── Auth (off by default) ────────────────────────────────────────────────
      - AUTH_ENABLED=false
      - AUTH_USERNAME=admin
      - AUTH_PASSWORD=                # must be set when AUTH_ENABLED=true

      # ── LangSmith tracing (optional) ─────────────────────────────────────────
      - LANGSMITH_API_KEY=
      - LANGSMITH_PROJECT=stackresume
      - LANGSMITH_TRACING=false

      # ── Misc ─────────────────────────────────────────────────────────────────
      - CORS_ORIGINS=*                # collapses to same-origin when AUTH_ENABLED=true
      - DATABASE_URL=sqlite+aiosqlite:////data/resume_builder.db
      - DEBUG=false
    extra_hosts:
      - "host.docker.internal:host-gateway"   # needed for Ollama on the host
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s
```

```bash
docker compose up -d
```

</details>

Open <http://localhost:8000> once the container is running.

---

## Build from source

Prefer building the image yourself? Clone the repo, drop in a provider key, and let `docker compose` do the rest.

### 1. Clone and configure

```bash
git clone https://github.com/Sathvik-Rao/StackResume.git
cd StackResume
cp .env.example .env
```

### 2. Set a provider key in `.env`

```bash
# Google Gemini (default — fast and cheap)
LLM_PROVIDER=google
LLM_MODEL=gemini-2.5-flash
GOOGLE_API_KEY=AIza...

# OpenAI
# LLM_PROVIDER=openai
# LLM_MODEL=gpt-4o
# OPENAI_API_KEY=sk-...

# Anthropic Claude
# LLM_PROVIDER=anthropic
# LLM_MODEL=claude-sonnet-4-6
# ANTHROPIC_API_KEY=sk-ant-...

# Local Ollama — no API key needed
# LLM_PROVIDER=ollama
# LLM_MODEL=llama3.1
```

> [!TIP]
> **No API key?** Use `LLM_PROVIDER=ollama` with a local [Ollama](https://ollama.com) install — free, no internet required. Run `ollama pull llama3.1` first.

### 3. Run

```bash
docker compose up --build
```

Open <http://localhost:8000>. The backend serves both the API and the frontend from the same port.

> [!TIP]
> **No Docker?** See [Running without Docker](#running-without-docker).

---

## Features

### Multi-agent pipeline

Nine specialised agents orchestrated with LangGraph — each resume goes through intent guarding, input parsing, optional JD analysis, generation, a Reviewer→Enhancer quality loop, and finalisation. If a job description is attached, a Cover Letter Writer and Outreach Writer run after finalisation.

| Agent | Role |
|---|---|
| **Intent Guard** | Blocks off-topic messages with a polite redirect — regex pre-filter first, LLM fallback only for ambiguous cases. |
| **Input Parser** | Extracts structured data from any free-form input. |
| **JD Analyzer** | *(JD only)* Pulls ATS keywords, required / preferred skills, and seniority from the job description. |
| **Resume Generator** | Produces the full JSON resume with STAR bullets and realistic fill for any missing fields. |
| **Quality Reviewer** | Scores ATS, writing quality, impact, and completeness (0–100 each). |
| **Resume Enhancer** | Rewrites weak bullets, injects missing keywords, fixes every issue the Reviewer flagged. |
| **Finalizer** | Stamps final metadata (iteration count, version, timestamp). |
| **Cover Letter Writer** | *(JD only)* Drafts a tailored cover letter. |
| **Outreach Writer** | *(JD only)* Drafts 2–4 templates — cold-application, LinkedIn, referral, follow-up. |

### Job description tailoring

Click **🎯 Tailor to JD**, paste any JD, and drag the intensity slider (0–100):

| Range | Effect |
|---|---|
| **100** | Full rewrite — every section mirrors the JD. |
| **65–89** | Heavy — summary + competencies tailored, bullets reordered. |
| **35–64** | Moderate — minor adjustments, a few JD keywords surfaced. |
| **10–34** | Light — 1–2 small tweaks. |
| **0–9** | None — JD used as background context only. |

### Persistent profile (My Profile)

Click **🧠 My Profile** to store your identity, work history, projects, education, and target roles across five tabs. Profile data is automatically injected into every pipeline run.

**Import / Export** — download your profile as a portable JSON file and load it back on any install. Invalid files are rejected with a clear error.

### Master resumes

Save any generated resume as a named **master resume** and set one as the default. The sidebar attach button starts a new chat with a specific master pre-loaded — great for keeping a polished base and forking variants per role.

### Manual editor + Re-score

Every resume has an **✏ Edit** tab for inline editing of every section — summary, bullets, skills, education, etc. **💾 Save edits** stamps `metadata.manually_edited=true` so subsequent agent runs preserve your changes. **🎯 Save & Re-score** reruns only the Quality Reviewer — fresh scores in seconds without touching any content.

### Document export

| Format | Notes |
|---|---|
| **PDF** | Universal, print-ready. Recommended for job portals. |
| **Word (`.docx`)** | Editable in Word / Google Docs / Pages. |
| **OpenDocument (`.odt`)** | Editable in LibreOffice / OpenOffice. |

Four templates: **Classic ATS** (max ATS compatibility), **Modern Clean** (blue accents), **Executive** (dark slate), **Dark Theme** (deep navy). Font size (9 / 10 / 11pt) and page cap (auto / 1 / 2) configurable per export. The Export modal includes a **live side-by-side PDF preview** that updates as you change options.

### Application tracker

Each session carries an optional tracker — status, apply URL, account email, masked password, and notes. Status pills appear in the sidebar so you can scan your whole pipeline at a glance.

### Multi-provider support

Switch provider and model at any time from **⚙️ AI Model Settings**. Supported: OpenAI, Anthropic, Google Gemini, Ollama (local), and any OpenAI-compatible custom endpoint.

### Optional authentication

Set `AUTH_ENABLED=true` to require login. Passwords are SHA-512 hashed client-side; the server compares with `secrets.compare_digest` and issues a UUID session token valid for 24 h.

> [!WARNING]
> You must also set `AUTH_PASSWORD`. If it's empty the server returns `503 Server auth misconfigured` on every login attempt.

### Pipeline tuning

Key generation parameters are configurable via `.env` or the in-app settings UI:

| Parameter | Default | Effect |
|---|---|---|
| `LLM_TEMPERATURE` | `0.7` | Controls output creativity — `0` is fully deterministic, `1` is most creative. |
| `MAX_REVIEW_ITERATIONS` | `3` | How many Reviewer→Enhancer loops to allow before accepting the resume. |
| `MIN_QUALITY_SCORE` | `82.0` | Overall score threshold (0–100) at which the loop stops early. |

### LangSmith tracing

Set `LANGSMITH_API_KEY` + `LANGSMITH_TRACING=true` to stream every LLM call to your LangSmith project. A **Test trace** button in Settings verifies the connection end-to-end.

---

## Tech stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI · LangGraph · LangChain · SQLAlchemy (async) · SQLite · aiosqlite |
| **AI providers** | OpenAI / Anthropic / Google Gemini / Ollama via LangChain |
| **Document generation** | ReportLab (PDF) · python-docx (Word) · odfpy (ODT) — pure Python, no headless browser |
| **File parsing** | pypdf + pdfminer.six · python-docx — for the resume upload flow |
| **Frontend** | Vanilla HTML / CSS / JS — single `index.html`, zero build step, zero npm |
| **Deployment** | Docker · docker-compose · GitHub Actions |
| **Observability** | LangSmith (optional) |

---

## Architecture & pipeline

```
                   ┌──────────────┐
                   │ Intent Guard │ ── off-topic ──▶ polite redirect ──▶ END
                   └──────┬───────┘
                          │ resume-related
                          ▼
                   ┌──────────────┐
                   │ Input Parser │
                   └──────┬───────┘
                          │ (jd_text present?)
              ┌───── yes ─┴─ no ─────┐
              ▼                      ▼
       ┌──────────────┐         ┌──────────────────┐
       │ JD Analyzer  │ ───────▶│ Resume Generator │
       └──────────────┘         └────────┬─────────┘
                                          ▼
                                ┌──────────────────┐
                                │ Quality Reviewer │◀─────────┐
                                └────────┬─────────┘          │
                                         │                    │
                          score ≥ MIN_QUALITY_SCORE           │
                          or iter ≥ MAX_REVIEW_ITERATIONS    no
                                         │                    │
                                       yes                    │
                                         ▼                    │
                                  ┌──────────────┐    ┌───────┴──────────┐
                                  │  Finalizer   │    │ Resume Enhancer  │
                                  └──────┬───────┘    └──────────────────┘
                                         │ (jd_analysis present?)
                          ┌──── yes ─────┴───── no ────┐
                          ▼                            ▼
                ┌──────────────────┐                  END
                │ Cover Letter     │
                └──────┬───────────┘
                       ▼
                ┌──────────────────┐
                │ Outreach Writer  │
                └──────┬───────────┘
                       ▼
                      END
```

The graph is compiled once at startup (`RESUME_GRAPH`) and reused across requests. Background execution runs in a thread via `loop.run_in_executor` so LangChain's synchronous streaming doesn't block the FastAPI event loop. Cancellation goes through an in-process `threading.Event` registry keyed by message id.

---

## Configuration

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `google` | `openai` / `anthropic` / `google` / `ollama` / `custom` |
| `LLM_MODEL` | `gemini-2.5-flash` | Model name for the selected provider |
| `LLM_TEMPERATURE` | `0.7` | 0 = deterministic, 1 = creative |
| `OPENAI_API_KEY` | — | OpenAI key |
| `ANTHROPIC_API_KEY` | — | Anthropic key |
| `GOOGLE_API_KEY` | — | Google AI Studio key |
| `OPENAI_BASE_URL` | — | Custom OpenAI-compatible endpoint (`LLM_PROVIDER=custom` only) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Use `http://host.docker.internal:11434` inside Docker |
| `MAX_REVIEW_ITERATIONS` | `3` | Max Reviewer→Enhancer loops |
| `MIN_QUALITY_SCORE` | `82.0` | Stop refining once the resume reaches this score |
| `DATABASE_URL` | `sqlite+aiosqlite:////data/resume_builder.db` | SQLAlchemy async URL |
| `AUTH_ENABLED` | `false` | Require login on every `/api/*` route |
| `AUTH_USERNAME` | `admin` | Admin username |
| `AUTH_PASSWORD` | — | **Must be set** when `AUTH_ENABLED=true` |
| `CORS_ORIGINS` | `*` | Comma-separated origins. Collapses to same-origin automatically when `AUTH_ENABLED=true` and `*` |
| `LANGSMITH_API_KEY` | — | LangSmith tracing key |
| `LANGSMITH_PROJECT` | `stackresume` | LangSmith project name |
| `LANGSMITH_TRACING` | `false` | Enable LangSmith tracing |
| `DEBUG` | `false` | FastAPI debug mode + SQL echo |

### `.env` vs runtime settings

Settings flow through two layers:

1. **Baseline** — `.env` (or shell env) loaded at startup into the `settings` object.
2. **DB overlay** — the `app_settings` table stores live edits from the **🔑 API Keys** / **⚙️ AI Models** modals. Non-empty values here override the baseline; clearing a field falls back to baseline.

`runtime_settings.py` also writes keys like `OPENAI_API_KEY` into `os.environ` so LangChain instrumentation and LangSmith pick up new values without a restart.

---

## Running without Docker

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export LLM_PROVIDER=google
export LLM_MODEL=gemini-2.5-flash
export GOOGLE_API_KEY=AIza...
export DATABASE_URL="sqlite+aiosqlite:///./stackresume.db"

uvicorn app.main:app --reload --port 8000
```

Open <http://localhost:8000>. For the frontend, either rely on FastAPI's static mount or open `frontend/index.html` directly with a local static server behind the same origin.

---

## Testing

The pytest suite covers API routes, LangGraph agent nodes, document generators, and pure helpers. Every LLM call is swapped for a deterministic `FakeLLM` — the full suite runs offline with no provider keys.

```bash
cd backend
pip install -r requirements-dev.txt

pytest                              # everything (~30s)
pytest tests/unit                   # pure functions
pytest tests/api                    # HTTP-level via httpx.AsyncClient
pytest tests/agents                 # LangGraph node + pipeline
pytest tests/documents              # PDF / DOCX / ODT smoke tests
pytest --cov=app --cov-report=term-missing
```

**In Docker:**

```bash
docker compose --profile test up --build --abort-on-container-exit
```

See [`backend/tests/README.md`](backend/tests/README.md) for fixture reference and contribution conventions.

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for branch / test / PR conventions. Short version: open a PR against `main`, `pytest` must be green, and the CI bot will suggest which tests to add based on the changed files.

---

## License

StackResume is free, open-source software released under the **GNU General Public License v3.0** — see [`LICENSE`](LICENSE) for the full text.

You're free to run it, study it, modify it, and redistribute it. Derived works must remain GPL-3.0.
