# Research Assistant — (Sequential)

**Stack:** LangGraph + FastAPI + Gemini 1.5 Flash + DuckDuckGo + SQLite history + minimal UI

## Graph

`START -> search (DuckDuckGo) -> summarize (Gemini Flash) -> cite (Gemini Flash) -> END`

## Run

```bash
pip install -r requirements.txt
# set key
echo GOOGLE_API_KEY=your_key > .env
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 → UI, http://localhost:8000/docs → Swagger.

Without key: mock mode still works (search real, summarize/cite mocked).

## Endpoints

- POST /api/research
- GET /api/research/stream?q=...
- GET /api/history
- GET /api/history/{id}
- DELETE /api/history/{id}
- GET /api/health

## Storage

SQLite at `data/history.db` — every question saved with summary, answer, citations, docs, timestamp.
