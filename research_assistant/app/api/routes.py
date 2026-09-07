"""FastAPI routes: research + storage + streaming. File: app/api/routes.py:1"""
import asyncio
import json
import sqlite3

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core import storage
from app.core.config import settings, has_gemini_key
from app.graph.builder import graph
from app.models.schemas import ResearchRequest, ResearchResponse, HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", gemini_configured=has_gemini_key(), model=settings.gemini_model)


@router.post("/research", response_model=ResearchResponse)
async def research(req: ResearchRequest):
    query = req.query.strip()
    # Run LangGraph sequentially
    result = await graph.ainvoke({"query": query, "documents": [], "summary": "", "citations": [], "final_answer": ""})
    documents = result.get("documents", [])
    summary = result.get("summary", "")
    final_answer = result.get("final_answer", "")
    citations = result.get("citations", [])

    # Persist every question
    rid = storage.save_research(query, summary, final_answer, citations, documents)
    # Retrieve to get created_at
    saved = storage.get_by_id(rid)
    return ResearchResponse(
        id=saved["id"],
        query=saved["query"],
        summary=saved["summary"],
        final_answer=saved["final_answer"],
        citations=[{"index": c["index"], "title": c["title"], "url": c["url"]} for c in saved["citations"]],
        documents=saved["documents"],
        created_at=saved["created_at"],
    )


@router.get("/research/stream")
async def research_stream(q: str = Query(..., min_length=3, max_length=500)):
    """SSE streaming: yields events as graph progresses through nodes."""

    async def gen():
        try:
            async for event in graph.astream(
                    {"query": q, "documents": [], "summary": "", "citations": [], "final_answer": ""},
                    stream_mode="values"):
                payload = json.dumps(event, ensure_ascii=False, default=str)
                yield f"data: {payload}\n\n"
                await asyncio.sleep(0)
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/history")
async def history(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    items = storage.get_history(limit=limit, offset=offset)
    total = storage.count_all()
    return {"total": total, "items": items}


@router.get("/history/{item_id}")
async def history_item(item_id: int):
    item = storage.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return item


@router.delete("/history/{item_id}")
async def history_delete(item_id: int):
    ok = storage.delete_by_id(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": item_id}


@router.delete("/history")
async def history_clear():
    # delete all via direct conn
    conn = sqlite3.connect(settings.db_path)
    conn.execute("DELETE FROM researches")
    conn.commit()
    conn.close()
    return {"cleared": True}
