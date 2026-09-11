# Travel Planner — Hierarchical Teams

Supervisor `TripManager` delegates via `Command` to three sub-graphs: **Flight (Search→Filter→Rank)**, **Hotel (
Search→Filter→Rank)**, **Itinerary (Generate→Optimize→Validate)**. Each subgraph is its own `StateGraph`. Demonstrates
state nesting, `InMemoryStore` for user preferences, and checkpoint resumption with `thread_id`.

## Stack

- `FastAPI 0.141.1 + LangGraph 1.2.11 + langchain-google-genai 4.4.0`
- `AsyncSqliteSaver` (`langgraph-checkpoint-sqlite`) + `InMemoryStore` (Memory)
- `GOOGLE_API_KEY` required — no mock fallback, error 500 if missing (per spec)

## Graph

```
START -> trip_manager (Command goto flight_subgraph)
  flight_subgraph:  START -> flight_search -> flight_filter -> flight_rank -> END
  hotel_subgraph:   START -> hotel_search  -> hotel_filter  -> hotel_rank  -> END
  itinerary_sub:    START -> itinerary_generate -> itinerary_optimize -> itinerary_validate -> END
  flight_subgraph -> hotel_subgraph -> itinerary_subgraph -> summarize (interrupt_before) -> END
```

`build_graph(checkpointer, store, interrupt_before)` in `app/graph/builder.py:1`, helper
`build_stateful_graph(checkpointer, store)` with `interrupt_before=["summarize"]`. Parent uses `Command` delegation;
`InMemoryStore.put((thread_id,), "preferences", prefs)` in `trip_manager`.

## Run

```bash
cd travel_planner
pip install -r requirements.txt
cp .env.example .env   # set GOOGLE_API_KEY
uvicorn app.main:app --reload --port 8004
# UI at http://localhost:8004/  Swagger at /docs  Health at /health and /api/health
```

## Endpoints

| Method   | Path                                   | Description                                                                                                                                                                  |
|----------|----------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `GET`    | `/health`, `/api/health`               | Health + `gemini_configured`                                                                                                                                                 |
| `POST`   | `/api/trips`                           | Create trip — invokes hierarchical graph with `thread_id`, persists via `trips` table + checkpoint `data/checkpoints.db`                                                     |
| `GET`    | `/api/trips?limit=&offset=&thread_id=` | History                                                                                                                                                                      |
| `GET`    | `/api/trips/{id}`                      | Fetch one                                                                                                                                                                    |
| `DELETE` | `/api/trips/{id}`, `DELETE /api/trips` | Delete                                                                                                                                                                       |
| `POST`   | `/api/trips/{id}/refine`               | **Checkpoint resumption** — cheap Filter+Rank only with updated `budget`/`preferences`/`refinement_query`; if paused before `summarize`, resumes via `ainvoke(None, config)` |
| `POST`   | `/api/trips/{id}/resume?thread_id=`    | Resume paused thread                                                                                                                                                         |
| `GET`    | `/api/trips/{id}/state/{thread_id}`    | `aget_state` snapshot (`values`, `next`)                                                                                                                                     |

## Storage

- `data/travel.db` — `trips` table (facade `app/core/storage.py:1` → `app/core/repositories/trip_repository.py:1`)
- `data/checkpoints.db` — `AsyncSqliteSaver`
- `InMemoryStore` — user preferences per `thread_id`

## SOLID

- `agents/nodes.py` facade only; per-file nodes (`trip_manager.py`, `flights/search.py` etc.)
- `core/ports.py` Protocols, `core/repositories/trip_repository.py` SRP, `core/travel_policies.py` pure planning rules
  (filter/rank/optimize), `core/mock_data.py` deprecated shim

## Verify

```bash
pytest  # add httpx.AsyncClient tests
curl -X POST http://localhost:8004/api/trips -H "Content-Type: application/json" -d '{"origin":"DEL","destination":"GOA","start_date":"2026-10-01","end_date":"2026-10-05","budget":20000,"travelers":2}'
curl -X POST http://localhost:8004/api/trips/1/refine -H "Content-Type: application/json" -d '{"budget":12000,"preferences":{"prefer_cheap":true}}'
```
