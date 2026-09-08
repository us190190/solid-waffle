"""FastAPI routes: create + SSE stream + HITL approval. File: app/api/routes.py:1"""
import asyncio
import json
import sqlite3
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.core import storage
from app.core.config import has_gemini_key, settings
from app.graph.builder import build_stateful_graph, graph
from app.models.schemas import ApproveRequest, CreateRequest, HealthResponse
from app.models.state import StudioState

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        gemini_configured=has_gemini_key(),
        model=settings.gemini_model,
        checkpointer="AsyncSqliteSaver",
    )


async def _run_graph_job(job_id: str):
    """Background task: runs LangGraph reflection loop and persists intermediate drafts."""
    job = storage.get_job(job_id)
    if not job:
        print(f"Job {job_id} not found for run")
        return
    storage.update_job(job_id, status="running")
    max_iter = job.get("max_iterations", settings.max_iterations)
    threshold = job.get("critic_threshold", settings.critic_threshold)

    initial_state = StudioState(
        job_id=job_id,
        prompt=job["prompt"],
        tone=job.get("tone") or "",
        content_type=job.get("content_type") or "",
        draft="",
        drafts=[],
        score=0,
        feedback="",
        suggestions=[],
        iteration=0,
        final_content="",
        status="running",
        max_iterations=max_iter,
        critic_threshold=threshold,
    )

    try:
        config = {"configurable": {"thread_id": job_id}}
        async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path) as checkpointer:
            g = build_stateful_graph(checkpointer)
            async for event in g.astream(initial_state, config=config, stream_mode="values"):
                drafts = event.get("drafts", [])
                if drafts:
                    stored = storage.get_job(job_id)
                    stored_drafts = stored.get("drafts", []) if stored else []
                    score = event.get("score", 0)
                    feedback = event.get("feedback", "")
                    suggestions = event.get("suggestions", [])
                    curr_iter = event.get("iteration", 0)
                    existing_map = {d.get("iteration"): d for d in stored_drafts}
                    enriched = []
                    for d in drafts:
                        entry = dict(d)
                        it = entry.get("iteration")
                        if it in existing_map and existing_map[it].get("score") is not None:
                            entry["score"] = existing_map[it].get("score")
                            entry["feedback"] = existing_map[it].get("feedback")
                            entry["suggestions"] = existing_map[it].get("suggestions", [])
                        if it == curr_iter and score:
                            entry["score"] = score
                            entry["feedback"] = feedback
                            entry["suggestions"] = suggestions
                        enriched.append(entry)
                    storage.update_job(
                        job_id,
                        drafts=enriched,
                        iteration=curr_iter,
                        score=score if score else None,
                        feedback=feedback if feedback else None,
                        suggestions=suggestions if suggestions else None,
                    )
                    if event.get("final_content"):
                        storage.set_final(job_id, event["final_content"], status="awaiting_approval")
                await asyncio.sleep(0)

            snapshot = await g.aget_state(config)
            if snapshot and snapshot.next:
                vals = snapshot.values
                if vals.get("final_content"):
                    storage.set_final(job_id, vals["final_content"], status="awaiting_approval")
                else:
                    storage.update_job(job_id, status="awaiting_approval")
                return
            final_job = storage.get_job(job_id)
            if snapshot and not snapshot.next:
                vals = snapshot.values if snapshot.values else {}
                fc = vals.get("final_content") or (final_job.get("final_content") if final_job else "")
                if fc:
                    storage.set_final(job_id, fc, status="awaiting_approval")
            else:
                if final_job and final_job.get("final_content"):
                    storage.update_job(job_id, status="awaiting_approval")

    except Exception as e:
        print(f"Stateful run failed ({e}), falling back to stateless")
        try:
            result = await graph.ainvoke(initial_state)
            drafts = result.get("drafts", [])
            enriched = []
            score = result.get("score", 0)
            feedback = result.get("feedback", "")
            suggestions = result.get("suggestions", [])
            for d in drafts:
                entry = dict(d)
                if entry.get("iteration") == result.get("iteration"):
                    entry["score"] = score
                    entry["feedback"] = feedback
                    entry["suggestions"] = suggestions
                enriched.append(entry)
            if enriched and score and "score" not in enriched[-1]:
                enriched[-1]["score"] = score
                enriched[-1]["feedback"] = feedback
                enriched[-1]["suggestions"] = suggestions
            storage.update_job(
                job_id,
                drafts=enriched,
                iteration=result.get("iteration", 0),
                score=score,
                feedback=feedback,
                suggestions=suggestions,
            )
            fc = result.get("final_content") or (drafts[-1].get("draft") if drafts else "")
            if fc:
                storage.set_final(job_id, fc, status="awaiting_approval")
            else:
                storage.update_job(job_id, status="failed")
        except Exception as e2:
            print(f"Stateless fallback failed: {e2}")
            storage.update_job(job_id, status="failed", feedback=str(e2)[:500])


@router.post("/studio/create", status_code=202)
async def create_studio(req: CreateRequest, background_tasks: BackgroundTasks):
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt required")
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    max_iter = req.max_iterations if req.max_iterations is not None else settings.max_iterations
    threshold = req.critic_threshold if req.critic_threshold is not None else settings.critic_threshold
    storage.create_job(job_id, prompt, tone=req.tone or "", content_type=req.content_type or "",
                       max_iterations=max_iter, critic_threshold=threshold)
    background_tasks.add_task(_run_graph_job, job_id)
    return {"job_id": job_id, "status": "pending", "max_iterations": max_iter, "critic_threshold": threshold}


@router.get("/studio/history")
async def history(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), status: str = Query(None)):
    items = storage.get_history(limit=limit, offset=offset, status=status)
    total = storage.count_all(status=status)
    return {"total": total, "items": items}


@router.get("/studio/history/{job_id}")
async def history_item(job_id: str):
    job = storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Not found")
    return job


@router.delete("/studio/history/{job_id}")
async def history_delete(job_id: str):
    ok = storage.delete_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": job_id}


@router.delete("/studio/history")
async def history_clear():
    conn = sqlite3.connect(settings.db_path)
    conn.execute("DELETE FROM jobs")
    conn.commit()
    conn.close()
    return {"cleared": True}


@router.get("/studio/{job_id}")
async def get_job(job_id: str):
    job = storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/studio/{job_id}/stream")
async def stream_job(job_id: str):
    job = storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def gen():
        last_sent = -1
        last_status = None
        for _ in range(300):
            cur = storage.get_job(job_id)
            if not cur:
                yield f"data: {json.dumps({'error': 'job not found'})}\n\n"
                break
            drafts = cur.get("drafts", []) or []
            status = cur.get("status", "")
            for idx, d in enumerate(drafts):
                if idx > last_sent:
                    payload = {
                        "type": "critic" if d.get("score") is not None else "draft",
                        "iteration": d.get("iteration"),
                        "draft": d.get("draft", "")[:4000],
                        "score": d.get("score"),
                        "feedback": d.get("feedback"),
                        "suggestions": d.get("suggestions", []),
                    }
                    yield f"event: draft\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    last_sent = idx
            if status != last_status:
                if status == "awaiting_approval" and cur.get("final_content"):
                    payload = {
                        "type": "final",
                        "final_content": cur.get("final_content", "")[:5000],
                        "iteration": cur.get("iteration"),
                        "score": cur.get("score"),
                    }
                    yield f"event: final\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                elif status == "completed" and cur.get("final_content"):
                    payload = {"type": "completed", "final_content": cur.get("final_content", "")[:5000]}
                    yield f"event: completed\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                elif status == "failed":
                    yield f"event: error\ndata: {json.dumps({'type': 'error', 'feedback': cur.get('feedback')})}\n\n"
                last_status = status

            if status in ("completed", "failed"):
                yield "data: [DONE]\n\n"
                break
            if status == "awaiting_approval" and last_sent >= len(drafts) - 1:
                await asyncio.sleep(0.5)
                continue
            await asyncio.sleep(0.5)
        else:
            yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/studio/{job_id}/approve")
async def approve_job(job_id: str, req: ApproveRequest):
    job = storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] not in ("awaiting_approval", "running"):
        raise HTTPException(status_code=400, detail=f"Job not in awaiting_approval (current: {job['status']})")

    if not req.approved:
        storage.update_job(job_id, status="failed", feedback="Rejected by user")
        return {"job_id": job_id, "status": "failed", "message": "Rejected"}

    final = req.edits.strip() if req.edits and req.edits.strip() else job.get("final_content") or ""
    if not final:
        raise HTTPException(status_code=400, detail="No final content to approve")

    config = {"configurable": {"thread_id": job_id}}
    try:
        async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path) as checkpointer:
            g = build_stateful_graph(checkpointer)
            snapshot = await g.aget_state(config)
            if snapshot and snapshot.next:
                if req.edits and req.edits.strip():
                    await g.aupdate_state(config, {"final_content": final, "status": "completed"})
                result = await g.ainvoke(None, config=config)
                vals = (await g.aget_state(config)).values if (await g.aget_state(config)) else result
                fc = vals.get("final_content", final) if vals else final
                storage.set_final(job_id, fc, status="completed")
                return {"job_id": job_id, "status": "completed", "final_content": fc}
    except Exception as e:
        print(f"Approve resume warning: {e}")

    storage.set_final(job_id, final, status="completed")
    return {"job_id": job_id, "status": "completed", "final_content": final}


@router.post("/studio/{job_id}/edit")
async def edit_job(job_id: str, req: ApproveRequest):
    """Alias for approve with edits."""
    return await approve_job(job_id, req)


@router.get("/studio/{job_id}/state")
async def get_state(job_id: str):
    config = {"configurable": {"thread_id": job_id}}
    try:
        async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path) as checkpointer:
            g = build_stateful_graph(checkpointer)
            snapshot = await g.aget_state(config)
            if not snapshot or not snapshot.values:
                job = storage.get_job(job_id)
                if not job:
                    raise HTTPException(status_code=404, detail="No state for job_id")
                return {"job_id": job_id, "values": job, "next": [], "checkpoint": "db-fallback"}
            return {
                "job_id": job_id,
                "values": snapshot.values,
                "next": snapshot.next,
                "created_at": str(snapshot.created_at) if snapshot.created_at else None,
            }
    except HTTPException:
        raise
    except Exception as e:
        job = storage.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="No state")
        return {"job_id": job_id, "values": job, "next": [], "error": str(e)[:300]}
