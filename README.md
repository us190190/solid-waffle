# solid-waffle

Multi-app repository of **LangGraph + FastAPI applications**, each demonstrating a different workflow pattern.

## Applications

| App                                                | Pattern                    | Port | Description                                                                                     |
|----------------------------------------------------|----------------------------|------|-------------------------------------------------------------------------------------------------|
| [research_assistant](research_assistant)           | Sequential chain           | 8000 | Search (DuckDuckGo) → Summarize (Gemini) → Cite (Gemini) + SQLite history                       |
| [customer_support_triage](customer_support_triage) | Router + Human-in-the-loop | 8001 | Supervisor (structured output) → Specialist → Responder → Escalation/Handoff with checkpoints   |
| [content_creation_studio](content_creation_studio) | Reflection Loop (Cycle)    | 8002 | Writer → Critic (score <8 loop max 3) → Editor → Human Approval (interrupt_before) + SSE stream |

## Quick Start

Each app is self-contained with its own virtual environment and dependencies.

### research_assistant

```bash
cd research_assistant
pip install -r requirements.txt
cp .env.example .env  # add GOOGLE_API_KEY
uvicorn app.main:app --reload --port 8000
```

### customer_support_triage

```bash
cd customer_support_triage
pip install -r requirements.txt
cp .env.example .env  # add GOOGLE_API_KEY (mock fallback works without)
uvicorn app.main:app --reload --port 8001
```

### content_creation_studio

```bash
cd content_creation_studio
pip install -r requirements.txt
cp .env.example .env  # add GOOGLE_API_KEY (mock fallback works without)
uvicorn app.main:app --reload --port 8002
```

Open `http://localhost:<port>/` for UI, `/docs` for Swagger.

## Shared Stack

- **FastAPI** 0.141.1
- **LangGraph** 1.2.11
- **Gemini** via `langchain-google-genai` 4.4.0
- **Pydantic** 2.13.5 / `pydantic-settings` 2.15.0
- **SQLite** via `aiosqlite` 0.22.1 (async) or `sqlite3` (sync)
- **Testing**: pytest 9.1.1 + httpx

See [AGENTS.md](AGENTS.md) for architecture conventions, adding new apps, and development guidelines.

## Adding a New App

1. Create folder with snake_case name
2. Copy structure from existing app (see AGENTS.md)
3. Update `requirements.txt` with shared + app-specific deps
4. Implement `app/graph/builder.py` with `build_graph()`
5. Wire `app/main.py` (lifespan, router, static mount)
6. Document in `README.md` with run commands and endpoints
7. Pick unused port (8002, 8003...)

## Repository Structure

```
solid-waffle/
├── AGENTS.md                    # Agent instructions & conventions
├── README.md                    # This file
├── research_assistant/          # Sequential workflow app
│   ├── requirements.txt
│   ├── .env.example
│   ├── README.md
│   └── app/
├── customer_support_triage/     # Router + human handoff app
│   ├── requirements.txt
│   ├── .env.example
│   ├── README.md
│   └── app/
└── content_creation_studio/     # Reflection loop app
    ├── requirements.txt
    ├── .env.example
    ├── README.md
    └── app/
```

## License

MIT