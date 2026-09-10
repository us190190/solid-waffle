"""FastAPI routes: REST + WebSocket + SSE + HITL. File: app/api/routes.py:1"""
import asyncio
import json
import sqlite3
import uuid
from typing import Optional

from app.core.ws_manager import manager
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.core import storage
from app.core.config import has_gemini_key, settings
from app.graph.builder import build_stateful_graph, graph
from app.models.schemas import ApproveRequest, CodegenRequest, HealthResponse
from app.models.state import CodeAssistantState

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", gemini_configured=has_gemini_key(), model=settings.gemini_model,
                          checkpointer="AsyncSqliteSaver")


async def _run_graph_job(job_id: str):
    job = storage.get_job(job_id)
    if not job:
        return
    storage.update_job(job_id, status="running")
    await manager.broadcast(job_id, {"type": "status", "status": "running", "message": "planner started"})
    user_story = job["user_story"]
    language = job.get("language", "python") or "python"

    initial_state: CodeAssistantState = {
        "job_id": job_id,
        "user_story": user_story,
        "language": language,
        "tasks": [],
        "code_artifacts": [],
        "test_artifacts": [],
        "docs_artifacts": [],
        "agent_status": [],
        "exec_results": [],
        "final_output": "",
        "reviewer_notes": "",
        "status": "running",
    }
    config = {"configurable": {"thread_id": job_id}}
    try:
        async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path) as checkpointer:
            g = build_stateful_graph(checkpointer)
            # Stream values
            async for event in g.astream(initial_state, config=config, stream_mode="values"):
                # Persist incremental
                tasks = event.get("tasks", []) or []
                code_artifacts = event.get("code_artifacts", []) or []
                test_artifacts = event.get("test_artifacts", []) or []
                docs_artifacts = event.get("docs_artifacts", []) or []
                agent_status = event.get("agent_status", []) or []
                exec_results = event.get("exec_results", []) or []
                final_output = event.get("final_output", "")
                reviewer_notes = event.get("reviewer_notes", "")
                status_val = event.get("status", "")

                # update db with latest accumulated via reducer semantics
                # need to merge with existing stored values to avoid duplication issues from repeated values stream
                # For artifacts, event contains accumulated list, so overwrite
                db_job = storage.get_job(job_id)
                if db_job is None:
                    break
                # Only update if changed
                updates = {}
                if tasks and len(tasks) != len(db_job.get("tasks", [])):
                    updates["tasks"] = tasks
                    await manager.broadcast(job_id, {"type": "tasks", "tasks": tasks})
                if code_artifacts and len(code_artifacts) != len(db_job.get("code_artifacts", [])):
                    updates["code_artifacts"] = code_artifacts
                    await manager.broadcast(job_id,
                                            {"type": "artifacts", "agent": "coder", "artifacts": code_artifacts})
                if test_artifacts and len(test_artifacts) != len(db_job.get("test_artifacts", [])):
                    updates["test_artifacts"] = test_artifacts
                    await manager.broadcast(job_id,
                                            {"type": "artifacts", "agent": "tester", "artifacts": test_artifacts})
                if docs_artifacts and len(docs_artifacts) != len(db_job.get("docs_artifacts", [])):
                    updates["docs_artifacts"] = docs_artifacts
                    await manager.broadcast(job_id,
                                            {"type": "artifacts", "agent": "docs_writer", "artifacts": docs_artifacts})
                if agent_status and len(agent_status) != len(db_job.get("agent_status", [])):
                    updates["agent_status"] = agent_status
                    # broadcast last status
                    last = agent_status[-1] if agent_status else {}
                    await manager.broadcast(job_id, {"type": "agent_status", "agent_status": last})
                if exec_results and len(exec_results) != len(db_job.get("exec_results", [])):
                    updates["exec_results"] = exec_results
                    await manager.broadcast(job_id,
                                            {"type": "exec", "exec_results": exec_results[-1] if exec_results else {}})
                if final_output and final_output != db_job.get("final_output"):
                    updates["final_output"] = final_output
                    await manager.broadcast(job_id, {"type": "final", "final_output": final_output[:4000]})
                if reviewer_notes and reviewer_notes != db_job.get("reviewer_notes"):
                    updates["reviewer_notes"] = reviewer_notes
                if status_val and status_val != db_job.get("status"):
                    updates["status"] = status_val
                if updates:
                    storage.update_job(job_id, **updates)
                await asyncio.sleep(0)

            # After stream, check checkpoint
            snapshot = await g.aget_state(config)
            if snapshot and snapshot.next:
                # paused before human_approval
                vals = snapshot.values or {}
                final = vals.get("final_output", "") or ""
                notes = vals.get("reviewer_notes", "") or ""
                storage.update_job(job_id, final_output=final, reviewer_notes=notes, status="awaiting_approval")
                await manager.broadcast(job_id, {"type": "awaiting_approval", "final_output": final[:4000]})
            else:
                vals = snapshot.values if snapshot and snapshot.values else {}
                final = vals.get("final_output", "") or storage.get_job(job_id).get("final_output", "")
                notes = vals.get("reviewer_notes", "") or ""
                if final:
                    storage.update_job(job_id, final_output=final, reviewer_notes=notes, status="awaiting_approval")
                    await manager.broadcast(job_id, {"type": "awaiting_approval", "final_output": final[:4000]})
                else:
                    # fallback to direct storage
                    j = storage.get_job(job_id)
                    if j and j.get("status") != "awaiting_approval":
                        storage.update_job(job_id, status="awaiting_approval")

    except Exception as e:
        # Fallback stateless
        try:
            result = await graph.ainvoke(initial_state)
            code_artifacts = result.get("code_artifacts", [])
            test_artifacts = result.get("test_artifacts", [])
            docs_artifacts = result.get("docs_artifacts", [])
            final_output = result.get("final_output", "")
            reviewer_notes = result.get("reviewer_notes", "")
            agent_status = result.get("agent_status", [])
            exec_results = result.get("exec_results", [])
            tasks = result.get("tasks", [])
            storage.update_job(job_id, code_artifacts=code_artifacts, test_artifacts=test_artifacts,
                               docs_artifacts=docs_artifacts, final_output=final_output, reviewer_notes=reviewer_notes,
                               agent_status=agent_status, exec_results=exec_results, tasks=tasks,
                               status="awaiting_approval")
            await manager.broadcast(job_id,
                                    {"type": "final", "final_output": final_output[:4000] if final_output else "",
                                     "status": "awaiting_approval"})
        except Exception as e2:
            storage.update_job(job_id, status="failed")
            await manager.broadcast(job_id, {"type": "error", "error": str(e2)[:1000]})


@router.post("/codegen", status_code=202)
async def codegen(req: CodegenRequest, background_tasks: BackgroundTasks):
    user_story = req.user_story.strip()
    if not user_story or len(user_story) < 10:
        raise HTTPException(status_code=400, detail="user_story required >=10 chars")
    language = (req.language or "python").strip().lower()
    job_id = f"code-{uuid.uuid4().hex[:8]}"
    storage.create_job(job_id, user_story, language)
    background_tasks.add_task(_run_graph_job, job_id)
    return {"job_id": job_id, "status": "pending", "language": language, "user_story": user_story}


@router.get("/codegen/history")
async def history(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), status: Optional[str] = None):
    items = storage.get_history(limit=limit, offset=offset, status=status)
    total = storage.count_all(status=status)
    return {"total": total, "items": items}


@router.get("/codegen/{job_id}")
async def get_job(job_id: str):
    job = storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@router.get("/codegen/{job_id}/state")
async def get_state(job_id: str):
    config = {"configurable": {"thread_id": job_id}}
    try:
        async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path) as cp:
            g = build_stateful_graph(cp)
            snap = await g.aget_state(config)
            if not snap:
                # fallback to db
                job = storage.get_job(job_id)
                if not job:
                    raise HTTPException(status_code=404, detail="No state for job_id")
                return {"job_id": job_id, "values": job, "next": [], "created_at": job.get("updated_at"),
                        "checkpoint": "db-fallback"}
            return {"job_id": job_id, "values": snap.values, "next": list(snap.next) if snap.next else [],
                    "created_at": str(snap.created_at) if snap.created_at else None}
    except HTTPException:
        raise
    except Exception as e:
        job = storage.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="No state")
        return {"job_id": job_id, "values": job, "next": [], "created_at": job.get("updated_at"),
                "checkpoint": f"error-fallback: {e}"}


@router.get("/codegen/{job_id}/stream")
async def stream(job_id: str):
    """SSE fallback polling DB (like content_creation_studio)."""
    job = storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")

    async def gen():
        last_code = 0
        last_test = 0
        last_docs = 0
        last_status = ""
        for _ in range(300):
            cur = storage.get_job(job_id)
            if not cur:
                yield f"event: error\ndata: {json.dumps({'error': 'job not found'})}\n\n"
                break
            # emit incremental artifacts
            ca = cur.get("code_artifacts", [])
            ta = cur.get("test_artifacts", [])
            da = cur.get("docs_artifacts", [])
            status = cur.get("status", "")
            if len(ca) > last_code:
                for art in ca[last_code:]:
                    yield f"event: coder\ndata: {json.dumps({'file': art.get('file'), 'content': art.get('content', '')[:4000]}, ensure_ascii=False)}\n\n"
                last_code = len(ca)
            if len(ta) > last_test:
                for art in ta[last_test:]:
                    yield f"event: tester\ndata: {json.dumps({'file': art.get('file'), 'content': art.get('content', '')[:4000]}, ensure_ascii=False)}\n\n"
                last_test = len(ta)
            if len(da) > last_docs:
                for art in da[last_docs:]:
                    yield f"event: docs_writer\ndata: {json.dumps({'file': art.get('file'), 'content': art.get('content', '')[:4000]}, ensure_ascii=False)}\n\n"
                last_docs = len(da)
            if status != last_status:
                yield f"event: status\ndata: {json.dumps({'status': status}, ensure_ascii=False)}\n\n"
                last_status = status
            if status in ("awaiting_approval", "completed"):
                final = cur.get("final_output", "")
                if final:
                    yield f"event: final\ndata: {json.dumps({'final_output': final[:5000]}, ensure_ascii=False)}\n\n"
                if status == "completed":
                    yield f"event: completed\ndata: {json.dumps({'job_id': job_id}, ensure_ascii=False)}\n\n"
                    break
                if status == "awaiting_approval":
                    # keep streaming until approved but break after sending final to avoid endless
                    # continue polling for completed
                    pass
            if status == "failed":
                yield f"event: error\ndata: {json.dumps({'error': 'failed'}, ensure_ascii=False)}\n\n"
                break
            await asyncio.sleep(0.5)
        yield f"event: done\ndata: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                                      "Connection": "keep-alive"})


@router.post("/codegen/{job_id}/approve")
async def approve(job_id: str, req: ApproveRequest):
    job = storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    if job.get("status") not in ("awaiting_approval", "running"):
        # allow approve even if still running? require awaiting_approval
        if job.get("status") != "awaiting_approval":
            raise HTTPException(status_code=400,
                                detail=f"job not awaiting approval, current status {job.get('status')}")
    if not req.approved:
        storage.update_job(job_id, status="failed", reviewer_notes="rejected by human")
        await manager.broadcast(job_id, {"type": "rejected", "status": "failed"})
        return {"job_id": job_id, "status": "failed", "approved": False}
    final = req.edits if req.edits else job.get("final_output", "")
    config = {"configurable": {"thread_id": job_id}}
    try:
        async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path) as cp:
            g = build_stateful_graph(cp)
            snap = await g.aget_state(config)
            if snap and snap.next:
                if req.edits:
                    await g.aupdate_state(config, {"final_output": final, "status": "completed"})
                result = await g.ainvoke(None, config=config)
                snap2 = await g.aget_state(config)
                vals = snap2.values if snap2 and snap2.values else result
                final2 = vals.get("final_output", final)
                storage.set_final(job_id, final2, status="completed")
                await manager.broadcast(job_id, {"type": "completed", "final_output": final2[:4000]})
                return {"job_id": job_id, "status": "completed", "approved": True, "final_output": final2}
            else:
                storage.set_final(job_id, final, status="completed")
                await manager.broadcast(job_id, {"type": "completed", "final_output": final[:4000]})
                return {"job_id": job_id, "status": "completed", "approved": True, "final_output": final}
    except Exception as e:
        # fallback
        storage.set_final(job_id, final, status="completed")
        return {"job_id": job_id, "status": "completed", "approved": True, "final_output": final,
                "warning": str(e)[:500]}


@router.post("/codegen/{job_id}/edit")
async def edit_job(job_id: str, req: ApproveRequest):
    # alias to approve with edits
    return await approve(job_id, req)


@router.websocket("/ws/codegen/{job_id}")
async def ws_codegen(websocket: WebSocket, job_id: str):
    job = storage.get_job(job_id)
    if not job:
        await websocket.close(code=1008)
        return
    await manager.connect(job_id, websocket)
    # send initial state
    cur = storage.get_job(job_id)
    await websocket.send_text(json.dumps({"type": "init", "job": cur}, ensure_ascii=False))
    try:
        while True:
            # heartbeat / client ping
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # echo or handle client keepalive
                try:
                    payload = json.loads(data)
                    if payload.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}, ensure_ascii=False))
                except Exception:
                    pass
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "heartbeat",
                                                      "status": storage.get_job(job_id).get("status",
                                                                                            "") if storage.get_job(
                                                          job_id) else ""}, ensure_ascii=False))
    except WebSocketDisconnect:
        await manager.disconnect(job_id, websocket)
    except Exception:
        await manager.disconnect(job_id, websocket)


@router.get("/codegen/history/{item_id}")
async def history_item_unused(item_id: str):
    # compatibility: treat as job_id lookup
    job = storage.get_job(item_id)
    if not job:
        raise HTTPException(status_code=404, detail="Not found")
    return job


@router.delete("/codegen/history/{job_id}")
async def delete_history(job_id: str):
    ok = storage.delete_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": job_id}


@router.delete("/codegen/history")
async def clear_history():
    conn = sqlite3.connect(settings.db_path)
    conn.execute("DELETE FROM jobs")
    conn.commit()
    conn.close()
    return {"cleared": True}
