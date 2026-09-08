# Content Creation Studio — Reflection Loop

**Stack:** LangGraph + FastAPI + Gemini 3.5 Flash (structured output) + AsyncSqliteSaver + SQLite + SSE +
BackgroundTasks

Demonstrates **LangGraph cycles** — the core differentiator vs plain chains.

## Graph

```
START -> writer -> critic --reflect_router--> writer  (if score < threshold && iteration < max_iterations)  ↻
                   |                              ^
                   | score ≥ threshold             | cycle edge (conditional loop)
                   |  OR iteration ≥ max           |
                   └──────────────────────────────┘
                              |
                              ▼
                           editor -> human_approval (interrupt_before) -> END
```

* `add_conditional_edges("critic", reflect_router, {"writer":"writer","editor":"editor"})` creates the **cycle**.
* `max_iterations=3` (configurable per-request 1-5) + `critic_threshold=8` (1-10) guard prevents infinite loops.
* `human_approval` uses `interrupt_before=["human_approval"]` + `AsyncSqliteSaver` — graph pauses at
  `awaiting_approval`, client calls `POST /approve` to resume.

## Concepts Demonstrated

- **Cycles / Conditional Looping** vs sequential chain
- **Evaluation Node** (`critic` with `with_structured_output(CriticScore)`)
- **Max-iteration guard** (`reflect_router`)
- **Streaming intermediate drafts** via SSE polling + `BackgroundTasks`
- **Human-in-the-loop** stretch via `interrupt_before` + checkpoint

## Run

```bash
cd content_creation_studio
pip install -r requirements.txt
cp .env.example .env  # add GOOGLE_API_KEY (mock fallback works without)
uvicorn app.main:app --reload --port 8002
```

Open http://localhost:8002 → UI, http://localhost:8002/docs → Swagger.

Without `GOOGLE_API_KEY`: writer produces deterministic improving drafts, critic uses `keyword_critic` that forces
`score=8` at iteration ≥2.

## Endpoints

- `POST /api/studio/create` **202** `{prompt, tone?, content_type?, max_iterations?, critic_threshold?}` →
  `{job_id, status:"pending"}` (BackgroundTasks)
- `GET /api/studio/{job_id}` → job status + `drafts[]` + `final_content`
- `GET /api/studio/{job_id}/stream` → `text/event-stream` (polls DB every 0.5s, emits `draft`/`critic`/`final`/
  `completed`)
- `POST /api/studio/{job_id}/approve` `{approved:bool, edits?:string}` → resume HITL or reject
- `POST /api/studio/{job_id}/edit` — alias for approve with edits
- `GET /api/studio/{job_id}/state` → checkpoint snapshot (`values` + `next`)
- `GET /api/studio/history?limit=&offset=&status=` → paginated jobs
- `DELETE /api/studio/history/{job_id}` / `DELETE /api/studio/history`
- `GET /api/health`, `GET /health`

## Example

```bash
curl -X POST http://localhost:8002/api/studio/create -H "Content-Type: application/json" \
  -d '{"prompt":"Write a blog about LangGraph reflection loops","tone":"professional","content_type":"blog","max_iterations":3,"critic_threshold":8}'

curl -N http://localhost:8002/api/studio/job-abc12345/stream
curl http://localhost:8002/api/studio/job-abc12345
curl -X POST http://localhost:8002/api/studio/job-abc12345/approve -H "Content-Type: application/json" \
  -d '{"approved":true}'
```

## Storage

- Jobs: `data/studio.db`
- Checkpoints: `data/checkpoints.db` (AsyncSqliteSaver)

## Ports

- `research_assistant` 8000 (sequential)
- `customer_support_triage` 8001 (router + handoff)
- `content_creation_studio` **8002** (reflection loop)
