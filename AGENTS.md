# AGENTS.md — solid-waffle

## Repo Overview

Multi-app repository for **LangGraph + FastAPI applications**, each demonstrating a different workflow pattern. Each app
is self-contained with its own dependencies, virtual environment, config, and SQLite storage.

```
solid-waffle/
├── research_assistant/       # Sequential: Search → Summarize → Cite
├── customer_support_triage/  # Router + Human-in-the-loop
└── <future_apps>/           # Add new apps here following the same structure
```

---

## Quick Start (per app)

```bash
cd <app_name>
pip install -r requirements.txt
cp .env.example .env          # add required API keys
uvicorn app.main:app --reload --port <port>
```

- UI at `/` (served from `app/static/index.html`)
- Swagger at `/docs`
- Health at `/health` and `/api/health`

---

## Shared Stack & Versions

| Package                | Version |
|------------------------|---------|
| fastapi                | 0.141.1 |
| uvicorn                | 0.52.4  |
| pydantic               | 2.13.5  |
| pydantic-settings      | 2.15.0  |
| langgraph              | 1.2.11  |
| langchain-google-genai | 4.4.0   |
| aiosqlite              | 0.22.1  |
| pytest                 | 9.1.1   |

**App-specific additions** (check each `requirements.txt`):

- `research_assistant`: `ddgs`, `sse-starlette`, `langchain`
- `customer_support_triage`: `langgraph-checkpoint-sqlite`, `sse-starlette`

---

## Required App Structure

Every app **must** follow this layout:

```
<app_name>/
├── requirements.txt
├── .env.example
├── README.md
└── app/
    ├── main.py                 # FastAPI entrypoint, lifespan, CORS, static mount
    ├── api/
    │   ├── __init__.py
    │   └── routes.py           # All endpoints
    ├── graph/
    │   ├── __init__.py
    │   └── builder.py          # build_graph() -> compiled StateGraph
    ├── agents/
    │   ├── __init__.py
    │   ├── nodes.py            # LangGraph node functions
    │   ├── tools.py            # Tool functions (optional)
    │   └── classifiers.py      # LLM classifiers with structured output (optional)
    ├── models/
    │   ├── __init__.py
    │   ├── state.py            # TypedDict State for LangGraph
    │   └── schemas.py          # Pydantic request/response models
    └── core/
        ├── __init__.py
        ├── config.py           # Settings via pydantic-settings + .env
        └── storage.py          # DB init + CRUD (sqlite3 or aiosqlite)
```

---

## Code Conventions

### Graph Builder (`app/graph/builder.py`)

- Export `build_graph(checkpointer=None, interrupt_before=None)` returning compiled graph
- For stateful apps: provide `build_stateful_graph(checkpointer)` helper
- Module docstring: `"""Description. File: app/graph/builder.py:1"""`

### State (`app/models/state.py`)

- Use `TypedDict` with `total=False` for optional fields
- Include all fields the graph reads/writes

### Config (`app/core/config.py`)

- Subclass `pydantic_settings.BaseSettings`
- Load from `.env` via `model_config = SettingsConfigDict(env_file=".env")`
- Expose `has_gemini_key()` helper

### Main (`app/main.py`)

- Use `@asynccontextmanager lifespan` for startup/shutdown
- Call `storage.init_db()` in lifespan startup
- Mount static files at `/static` from `app/static/`
- Include router with `prefix="/api"`

### Agents/Nodes

- Node functions: `async def node_name(state: StateName) -> dict`
- Return partial state updates (only changed fields)
- Use structured output via `with_structured_output(PydanticModel)` for classifiers
- **SOLID — Facade + SRP:** `app/agents/nodes.py` must be a thin re-export facade; each agent lives in its own file
  (`planner.py`, `coder.py`, `tester.py`, `docs_writer.py`, `reviewer.py`, `common.py`). No business logic inside
  `nodes.py`.
- **Imports:** All imports strictly at file top (PEP8 E402). No inline `import` inside functions; inject via factory
  (`get_llm()`) at top. Remove unused imports (`re`, `io`, `os` if unused).
- **Schemas:** `TasksSchema` / structured-output models live in `app/models/schemas.py` (with `TaskItem`), not inside
  node functions. Nodes import from schemas.

### SOLID Standards (applies to all apps)

- **SRP:** One class/file per reason to change. `tools.py` delegates to `tools/filesystem.py` + `tools/python_repl.py`;
  `storage.py` delegates to `repositories/job_repository.py`; per-agent files.
- **OCP:** Extend via registry, not `if/elif` chains. Use `app/core/language_registry.py` (`LANGUAGE_EXT`,
  `get_code_file_name`) and strategy maps for executors. New language/agent requires adding entry, not editing core
  `if`.
- **DIP (Light):** Depend on `app/core/ports.py` Protocols (`FileSystemPort`, `ExecutorPort`, `LLMProvider`) + factory
  `get_llm()` / `get_settings()`. No direct `ChatGoogleGenerativeAI()` inside node without factory; no direct `sqlite3`
  in routes (use repository).
- **ISP:** Worker state segregated: `WorkerState` (task + reducers) separate from `CodeAssistantState` to avoid fat
  interface.
- **Imports & Schemas:** See above — enforced via `ruff check --select F401,I,E402`.

### Core

- `app/core/ports.py` — light DIP Protocols
- `app/core/language_registry.py` — OCP registry for `LANGUAGE_EXT` and file naming (`get_code_file_name`,
  `get_test_file_name`, `get_docs_file_name`)
- `app/core/repositories/job_repository.py` — SRP persistence (called by `storage.py` facade)
- `app/core/config.py` — `SettingsConfigDict` (not legacy `class Config`)

---

## Adding a New Application

1. **Create folder** with app name (snake_case)
2. **Copy structure** from an existing app
3. **Update `requirements.txt`** — keep shared deps aligned; add app-specific ones
4. **Create `.env.example`** with required keys (e.g., `GOOGLE_API_KEY`, `GEMINI_MODEL`)
5. **Implement `build_graph()`** in `app/graph/builder.py`
6. **Wire `app/main.py`** — lifespan, router, static mount
7. **Write `README.md`** with:
    - Stack description
    - Graph diagram (ASCII)
    - Run commands
    - Endpoint list
    - Storage locations
8. **Choose port** not used by other apps (8000, 8001, 8002...)

---

## Testing

- No shared test config — each app runs `pytest` from its folder
- Add `tests/` per app as needed
- Use `httpx.AsyncClient` for FastAPI integration tests

---

## Environment Variables

| Variable             | Required                   | Default               |
|----------------------|----------------------------|-----------------------|
| `GOOGLE_API_KEY`     | Yes (for LLM)              | —                     |
| `GEMINI_MODEL`       | No                         | App-specific          |
| `CHECKPOINT_DB_PATH` | Only if using checkpointer | `data/checkpoints.db` |

**Mock fallbacks** work without API keys (keyword-based classification).

---

## Key Reference Files

- `research_assistant/app/graph/builder.py:7` — sequential linear graph
- `customer_support_triage/app/graph/builder.py:22` — router + conditional edges + checkpointer
- `*/app/core/config.py` — settings pattern
- `customer_support_triage/app/agents/classifiers.py` — structured output classifier

---

## Gotchas

- Each app has its own `.venv` — activate the correct one
- `.env` files are gitignored per app; commit only `.env.example`
- Apps using checkpointer need `langgraph-checkpoint-sqlite` in requirements
- Static UI served from `app/static/` — ensure `index.html` exists
- No root-level tooling config (ruff, mypy, pyproject.toml) — add if standardizing
- SQLite files (`data/*.db`) are gitignored