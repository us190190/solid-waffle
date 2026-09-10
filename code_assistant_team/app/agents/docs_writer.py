"""Docs writer agent (SRP). File: app/agents/docs_writer.py:1"""
import datetime

from app.agents.common import _extract_llm_text, _mock_docs_content, get_llm
from app.agents.tools import write_file
from app.core.language_registry import get_docs_file_name
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import has_gemini_key


async def docs_writer_node(state: dict) -> dict:
    task = state.get("task") or (state.get("tasks") or [{}])[0]
    if isinstance(task, dict) and "description" not in task and "task" in state:
        task = state["task"]
    language = (state.get("language") or task.get("language", "python") or task.get("_language",
                                                                                    "python")) if isinstance(task,
                                                                                                             dict) else "python"
    job_id = (state.get("job_id") or task.get("_job_id") or "default") if isinstance(task, dict) else state.get(
        "job_id", "default")
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    desc = task.get("description", "") if isinstance(task, dict) else str(task)
    tid = task.get("id", "T1") if isinstance(task, dict) else "T1"

    if not has_gemini_key():
        content = _mock_docs_content(task if isinstance(task, dict) else {"description": str(task)}, language)
    else:
        try:
            llm = get_llm()
            msg = await llm.ainvoke([SystemMessage(content="You are tech writer."),
                                     HumanMessage(content=f"Task: {desc} Language: {language}. Write docs.")])
            content = _extract_llm_text(msg.content) or _mock_docs_content({"description": desc, "language": language},
                                                                           language)
        except Exception:
            content = _mock_docs_content({"description": desc, "language": language}, language)

    file_name = get_docs_file_name(tid)
    write_file(job_id, file_name, content)
    return {
        "docs_artifacts": [{"file": file_name, "content": content, "task_id": tid, "language": language}],
        "agent_status": [{"agent": "docs_writer", "status": "done", "ts": now, "task_id": tid}],
        "exec_results": [{"agent": "docs_writer", "task_id": tid, "file": file_name, "language": language,
                          "result": {"status": "ok", "output": "docs generated"}}],
    }
