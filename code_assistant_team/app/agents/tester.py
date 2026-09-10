"""Tester agent (SRP). File: app/agents/tester.py:1"""
import datetime

from app.agents.common import _extract_llm_text, _mock_test_content, get_llm
from app.agents.tools import python_repl, write_file
from app.core.language_registry import get_test_file_name
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import has_gemini_key


async def tester_node(state: dict) -> dict:
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
    file_name = get_test_file_name(tid, language)

    code = ""
    exec_res = {"status": "error", "output": "", "error": "not executed"}
    for attempt in range(3):
        if not has_gemini_key():
            code = _mock_test_content(task if isinstance(task, dict) else {"description": str(task)}, language)
            if attempt > 0 and exec_res.get("status") == "error":
                code = code.replace("assert True", "assert 1==1  # retry fix")
        else:
            try:
                llm = get_llm()
                fix_prompt = f". Previous attempt failed: {exec_res.get('error', '')[:500]}. Fix it." if attempt > 0 else ""
                msg = await llm.ainvoke([SystemMessage(content=f"You are expert {language} test writer."),
                                         HumanMessage(content=f"Task: {desc}. Write tests.{fix_prompt}")])
                code = _extract_llm_text(msg.content) or _mock_test_content({"description": desc, "language": language},
                                                                            language)
            except Exception:
                code = _mock_test_content({"description": desc, "language": language}, language)
        write_file(job_id, file_name, code)
        exec_res = python_repl(code, job_id=job_id, language=language)
        if exec_res.get("status") == "ok":
            break

    return {
        "test_artifacts": [{"file": file_name, "content": code, "task_id": tid, "language": language}],
        "agent_status": [{"agent": "tester", "status": "done", "ts": now, "task_id": tid}],
        "exec_results": [
            {"agent": "tester", "task_id": tid, "file": file_name, "language": language, "result": exec_res}],
    }
