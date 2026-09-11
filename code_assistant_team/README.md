# Code Assistant Team — Parallel Collaboration

Multi-agent code generation team demonstrating **fan-out/fan-in**, **Send API**, **subgraphs**, **shared state
reducers**, and **tool-bound agents** with **WebSocket + SSE** real-time updates.

## Pattern

```
START → planner ──Send([coder,tester,docs_writer])──► coder subgraph (generate→exec→retry×2) ─┐
                          ├─ tester subgraph (generate→exec→retry×2) ─┼─► reviewer ──interrupt_before──► human_approval → END
                          └─ docs_writer subgraph (generate→lint) ────┘
Reducer: Annotated[List[Dict], operator.add] merges artifacts
Tools: PythonREPLTool + FileSystem (sandbox data/workspace/{job_id})
HITL: interrupt_before human_approval, resume via POST /approve
Realtime: POST /codegen async job + WS /ws/codegen/{job_id} + SSE fallback
```

## Stack

- FastAPI 0.141.1, LangGraph 1.2.11, Gemini via langchain-google-genai 4.4.0
- Checkpoint via langgraph-checkpoint-sqlite
- PythonREPL + FileSystem tools

## Run

```bash
cd code_assistant_team
pip install -r requirements.txt
cp .env.example .env  # add GOOGLE_API_KEY (mock works without)
uvicorn app.main:app --reload --port 8003
```

- UI at `/` (Kanban coder/tester/docs, WS dot)
- Swagger at `/docs`
- Health at `/health` and `/api/health`

## Endpoints

| Method | Path                            | Description                         |
|--------|---------------------------------|-------------------------------------|
| GET    | `/health`, `/api/health`        | Health + checkpointer               |
| POST   | `/api/codegen` 202              | Create job `{user_story, language}` |
| GET    | `/api/codegen/{job_id}`         | Poll job status/artifacts           |
| GET    | `/api/codegen/{job_id}/stream`  | SSE fallback (poll DB 0.5s)         |
| WS     | `/api/ws/codegen/{job_id}`      | Real-time agent status              |
| POST   | `/api/codegen/{job_id}/approve` | HITL resume `{approved, edits?}`    |
| GET    | `/api/codegen/{job_id}/state`   | Checkpointer snapshot               |
| GET    | `/api/codegen/history`          | List jobs                           |
| DELETE | `/api/codegen/history`          | Clear all                           |

## Storage

- `data/code_assistant.db` → `jobs` table
- `data/checkpoints.db` → AsyncSqliteSaver
- `data/workspace/{job_id}/` → sandboxed files

## Concepts Demonstrated

- `Send` API dynamic fan-out (planner → N workers)
- Parallel nodes (coder/tester/docs concurrently)
- `Annotated[list, operator.add]` reducers (code/test/docs/exec_results)
- Subgraphs each with internal retry loop (coder/tester loop on tool error, max 2)
- Tool-bound agents (PythonREPL exec even in mock, FileSystem sandbox)
- WebSocket broadcast via ConnectionManager + SSE polling fallback

## TODO

- Provide download link for code genrated in a zip file or provide better UX for viewing the code content of workspace
- Use sub graphs instead of for loop within coder/tester/docs nodes alongwith a score for each output so that the best
  output is selected
- buttons on UX are not working at approval step
- the UX gets stuck when workkflow is interrupted and then resumed (common pattern whenever vanilla alert of HTML is
  used)
- ensure thread safe connection manager with pooling for WebSocket, SSE, DB, etc.
- eval agent
- langsmith for observation
- UX the scrollable sections are not working properly (e.g. it does not scroll to the bottom when new job is created and
  the content is added on scroll)