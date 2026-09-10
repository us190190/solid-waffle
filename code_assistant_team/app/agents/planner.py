"""Planner agent (SRP). File: app/agents/planner.py:1"""
import datetime
from typing import Dict, List

from app.agents.classifiers import keyword_tasks
from app.agents.common import _extract_llm_text, get_llm
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import has_gemini_key
from app.models.schemas import TasksSchema, TaskItem


async def planner_node(state: dict) -> dict:
    """Break user_story into tasks. Fan-out source."""
    user_story = state.get("user_story", "").strip()
    language = state.get("language", "python") or "python"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    agent_status = [{"agent": "planner", "status": "running", "ts": now}]

    if not has_gemini_key():
        tasks = keyword_tasks(user_story, language)
        return {
            "tasks": tasks,
            "agent_status": agent_status + [{"agent": "planner", "status": "done", "ts": now}],
            "status": "planning_done",
        }

    try:
        llm = get_llm()
        structured = llm.with_structured_output(TasksSchema)
        prompt = f"Break this user story into 6 tasks (2 code, 2 test, 2 docs) for language {language}. User story: {user_story}"
        result = await structured.ainvoke(
            [SystemMessage(content="You are a planner. Always return tasks."), HumanMessage(content=prompt)])
        tasks_raw = result.tasks if hasattr(result, "tasks") else []
        norm: List[Dict] = []
        for i, t in enumerate(tasks_raw[:6], 1):
            if isinstance(t, TaskItem):
                norm.append({"id": t.get("id", f"T{i}"),
                             "type": t.get("type", "code") if t.get("type") in ("code", "test", "docs") else "code",
                             "description": t.get("description", str(t))[:400],
                             "language": t.get("language", language)})
            elif hasattr(t, "model_dump"):
                d = t.model_dump()
                norm.append({"id": d.get("id", f"T{i}"),
                             "type": d.get("type", "code") if d.get("type") in ("code", "test", "docs") else "code",
                             "description": d.get("description", str(t))[:400],
                             "language": d.get("language", language)})
            else:
                norm.append(
                    {"id": f"T{i}", "type": "code", "description": _extract_llm_text(t)[:400], "language": language})
        if len(norm) < 3:
            raise ValueError("too few tasks")
        return {"tasks": norm, "agent_status": agent_status + [{"agent": "planner", "status": "done", "ts": now}],
                "status": "planning_done"}
    except Exception:
        tasks = keyword_tasks(user_story, language)
        return {"tasks": tasks, "agent_status": agent_status + [{"agent": "planner", "status": "done", "ts": now}],
                "status": "planning_done"}
