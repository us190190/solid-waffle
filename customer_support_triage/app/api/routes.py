"""FastAPI routes: stateless + stateful. File: app/api/routes.py:1"""
import sqlite3
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.core import storage
from app.core.config import settings, has_gemini_key
from app.graph.builder import graph, build_stateful_graph
from app.models.schemas import ChatRequest, ChatResponse, HealthResponse
from app.models.state import SupportState

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        gemini_configured=has_gemini_key(),
        model=settings.gemini_model,
        checkpointer="AsyncSqliteSaver",
    )


def _history_to_messages(history):
    return [{"role": m.role, "content": m.content} for m in history]


@router.post("/support/chat", response_model=ChatResponse)
async def support_chat(req: ChatRequest):
    """Stateless invocation: caller sends full history each time."""
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message required")
    thread_id = req.thread_id or f"stateless-{uuid.uuid4().hex[:8]}"
    history_msgs = _history_to_messages(req.history)

    # Build state for stateless graph
    initial_state = SupportState(messages=history_msgs, user_input=message, intent="technical",
                                 sentiment="neutral", confidence=0.0, tool_outputs=[],
                                 final_response="", escalated=False, thread_id=thread_id)
    result = await graph.ainvoke(initial_state)

    intent = result.get("intent", "technical")
    sentiment = result.get("sentiment", "neutral")
    escalated = bool(result.get("escalated", False))
    response_text = result.get("final_response", "")
    tool_outputs = result.get("tool_outputs", [])
    messages = result.get("messages", []) or history_msgs + [{"role": "user", "content": message},
                                                             {"role": "assistant", "content": response_text}]

    # Persist
    storage.save_conversation(thread_id, message, intent, sentiment, response_text, tool_outputs, escalated)

    # Convert messages to ChatMessage shape for response
    history_out = []
    for m in messages:
        role = m.get("role", "assistant")
        if role in ("user", "assistant"):
            history_out.append({"role": role, "content": m.get("content", "")})

    return ChatResponse(
        thread_id=thread_id,
        intent=intent,
        sentiment=sentiment,
        confidence=float(result.get("confidence", 0.0)),
        escalated=escalated,
        response=response_text,
        tool_outputs=tool_outputs,
        history=history_out,
    )


@router.post("/support/chat/stateful", response_model=ChatResponse)
async def support_chat_stateful(req: ChatRequest):
    """Stateful invocation: uses AsyncSqliteSaver + thread_id, demonstrates checkpoint persistence."""
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message required")
    thread_id = req.thread_id or f"thread-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    history_msgs = _history_to_messages(req.history)
    # For stateful, history is ideally loaded from checkpointer, but we accept supplied history for first turn

    initial_state = SupportState(messages=history_msgs, user_input=message, intent="technical",
                                 sentiment="neutral", confidence=0.0, tool_outputs=[],
                                 final_response="", escalated=False, thread_id=thread_id)

    async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path) as checkpointer:
        graph_stateful = build_stateful_graph(checkpointer)
        result = await graph_stateful.ainvoke(initial_state, config=config)

        # Handle interrupt_before human_handoff: result will contain __interrupt__ in newer langgraph
        # If interrupted, retrieve pending state and complete manually via resume logic
        if "__interrupt__" in result:
            # Graph paused before human_handoff; save partial and return interrupt payload
            # need to fetch current snapshot to get intent/sentiment
            snapshot = await graph_stateful.aget_state(config)
            vals = snapshot.values if snapshot else result
            tool_outputs = vals.get("tool_outputs", [])
            storage.save_conversation(thread_id, message, vals.get("intent", "technical"),
                                      vals.get("sentiment", "negative"),
                                      vals.get("final_response") or "Paused for human handoff", tool_outputs, True)
            return ChatResponse(
                thread_id=thread_id,
                intent=vals.get("intent", "technical"),
                sentiment=vals.get("sentiment", "negative"),
                confidence=float(vals.get("confidence", 0.85)),
                escalated=True,
                response="Escalated: paused before human_handoff (interrupt_before). Call POST /api/support/chat/stateful/resume to continue.",
                tool_outputs=tool_outputs,
                history=[],
            )

        intent = result.get("intent", "technical")
        sentiment = result.get("sentiment", "neutral")
        # escalated may be True from router OR after node
        escalated = bool(result.get("escalated", False)) or (
                    sentiment == "negative" and float(result.get("confidence", 0)) >= settings.handoff_threshold)
        response_text = result.get("final_response", "")
        tool_outputs = result.get("tool_outputs", [])

        # If escalated but interrupt did not trigger (fallback path where node executed directly), keep escalated
        storage.save_conversation(thread_id, message, intent, sentiment, response_text, tool_outputs, escalated)

        messages = result.get("messages", [])
        history_out = []
        for m in messages:
            if m.get("role") in ("user", "assistant"):
                history_out.append({"role": m["role"], "content": m.get("content", "")})

        return ChatResponse(
            thread_id=thread_id,
            intent=intent,
            sentiment=sentiment,
            confidence=float(result.get("confidence", 0.0)),
            escalated=escalated,
            response=response_text,
            tool_outputs=tool_outputs,
            history=history_out,
        )


@router.post("/support/chat/stateful/resume", response_model=ChatResponse)
async def resume_stateful(thread_id: str = Query(..., description="Thread to resume after interrupt")):
    """Resume a paused stateful thread (after interrupt_before human_handoff)."""
    config = {"configurable": {"thread_id": thread_id}}
    async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path) as checkpointer:
        graph_stateful = build_stateful_graph(checkpointer)
        snapshot = await graph_stateful.aget_state(config)
        if not snapshot or not snapshot.next:
            raise HTTPException(status_code=404, detail="No paused thread found for this thread_id")
        # Resume by invoking with None (continues from interrupt)
        result = await graph_stateful.ainvoke(None, config=config)
        snapshot2 = await graph_stateful.aget_state(config)
        vals = snapshot2.values if snapshot2 and snapshot2.values else result
        response_text = vals.get("final_response", result.get("final_response", ""))
        tool_outputs = vals.get("tool_outputs", result.get("tool_outputs", []))
        intent = vals.get("intent", result.get("intent", "technical"))
        sentiment = vals.get("sentiment", result.get("sentiment", "negative"))
        escalated = True
        storage.save_conversation(thread_id, "[resume human_handoff]", intent, sentiment, response_text, tool_outputs,
                                  escalated)
        return ChatResponse(
            thread_id=thread_id,
            intent=intent,
            sentiment=sentiment,
            confidence=float(vals.get("confidence", result.get("confidence", 0.85))),
            escalated=escalated,
            response=response_text,
            tool_outputs=tool_outputs,
            history=[],
        )


@router.get("/support/chat/state/{thread_id}")
async def get_state(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path) as checkpointer:
        graph_stateful = build_stateful_graph(checkpointer)
        snapshot = await graph_stateful.aget_state(config)
        if not snapshot:
            raise HTTPException(status_code=404, detail="No state for thread_id")
        return {
            "thread_id": thread_id,
            "values": snapshot.values,
            "next": snapshot.next,
            "created_at": str(snapshot.created_at) if snapshot.created_at else None,
        }


@router.get("/support/history")
async def support_history(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                          thread_id: Optional[str] = None):
    items = storage.get_history(limit=limit, offset=offset, thread_id=thread_id)
    total = storage.count_all(thread_id=thread_id)
    return {"total": total, "items": items}


@router.get("/support/history/{item_id}")
async def support_history_item(item_id: int):
    item = storage.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return item


@router.delete("/support/history/{item_id}")
async def support_history_delete(item_id: int):
    ok = storage.delete_by_id(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": item_id}


@router.delete("/support/history")
async def support_history_clear():
    conn = sqlite3.connect(settings.db_path)
    conn.execute("DELETE FROM conversations")
    conn.commit()
    conn.close()
    return {"cleared": True}
