# Customer Support Triage — Router + Human Handoff

**Stack:** LangGraph + FastAPI + Gemini 2.0 Flash (structured output) + AsyncSqliteSaver + SQLite history + minimal UI
This project demonstrates branching.

## Graph

```
START -> supervisor (with_structured_output intent+billing/technical/sales + sentiment)
      --add_conditional_edges(router)--> billing | technical | sales --|
                                      (each specialist calls mock DB/API tools)
                                      └-> responder --add_conditional_edges(escalation)--> END  (or)  human_handoff -> END
                                                      interrupt_before=["human_handoff"] with AsyncSqliteSaver
```

## Concepts Demonstrated

- `with_structured_output(ClassificationResult)` for supervisor (vs freeform prompts in research)
- `add_conditional_edges` Router pattern (billing/technical/sales)
- Specialist tool use (mock invoices/tickets/pricing)
- Stateless vs Stateful invocation
- Sentiment-based escalation → `HumanHandoffNode` with `interrupt_before` + `AsyncSqliteSaver`

## Run

```bash
pip install -r requirements.txt
# .env already has GOOGLE_API_KEY; without key, mock keyword classifier still works
uvicorn app.main:app --reload --port 8001
```

Open http://localhost:8001 → UI, http://localhost:8001/docs → Swagger.

Without key: keyword fallback classifies intent/sentiment deterministically.

## Endpoints

- `POST /api/support/chat` — stateless: body `{message, history: [{role,content}], thread_id?}` returns
  `{intent, sentiment, escalated, response, tool_outputs}`
- `POST /api/support/chat/stateful?thread_id=` — stateful via `AsyncSqliteSaver` (persists checkpoint to
  `data/checkpoints.db`)
- `POST /api/support/chat/stateful/resume?thread_id=` — resume after `interrupt_before` human_handoff
- `GET /api/support/chat/state/{thread_id}` — inspect checkpoint `values` + `next`
- `GET /api/support/history` / `/{id}` / `DELETE`
- `GET /api/health`, `GET /health`

## Stateless vs Stateful

- Stateless: client sends `history` array every turn; server has no memory (`graph.ainvoke` without checkpointer).
- Stateful: client sends only `thread_id`+`message`; server loads state via `AsyncSqliteSaver`
  (`config={"configurable":{"thread_id"}}`). Second message can omit history and still retain prior intent/tools.
  Interrupt pauses before `human_handoff`.

Example:

```bash
# stateless
curl -X POST http://localhost:8001/api/support/chat -H "Content-Type: application/json" -d '{"message":"I was charged twice for INV-002","history":[]}'

# stateful
curl -X POST "http://localhost:8001/api/support/chat/stateful?thread_id=demo1" -H "Content-Type: application/json" -d '{"message":"I was charged twice for INV-002","history":[]}'
curl -X POST "http://localhost:8001/api/support/chat/stateful?thread_id=demo1" -H "Content-Type: application/json" -d '{"message":"I am furious, need human","history":[]}'
curl http://localhost:8001/api/support/chat/state/demo1
curl -X POST "http://localhost:8001/api/support/chat/stateful/resume?thread_id=demo1"
```

## Stretch: Sentiment Escalation

Supervisor returns `sentiment=negative` (keyword `angry|furious|escalate` or LLM). Router `escalation_router` triggers
`human_handoff` when `escalated==True` (negative + confidence>=0.7). Stateful graph compiled with
`interrupt_before=["human_handoff"]` so `ainvoke` pauses; client calls `/resume` to complete.

## Storage

- Conversations: `data/support_history.db`
- Checkpoints: `data/checkpoints.db` (AsyncSqliteSaver)

## Mock Tools (app/core/mock_db.py)

- billing: `lookup_invoice`, `check_refund_status`
- technical: `check_system_status`, `lookup_ticket`
- sales: `lookup_pricing`, `check_inventory`, `create_lead`
