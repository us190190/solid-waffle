"""Classifier for planner tasks. File: app/agents/classifiers.py:1"""
from typing import Dict, List

from pydantic import BaseModel, Field


class TasksResult(BaseModel):
    tasks: List[Dict] = Field(..., description="List of tasks with id, type, description, language")


def keyword_tasks(user_story: str, language: str = "python") -> List[Dict]:
    """Mock fallback: break user story into code/test/docs tasks."""
    story = user_story.lower()
    lang = (language or "python").lower()
    tasks = []
    tid = 1

    def add(t: str, desc: str):
        nonlocal tid
        tasks.append({"id": f"T{tid}", "type": t, "description": desc, "language": lang})
        tid += 1

    # Code tasks
    if any(k in story for k in ("api", "endpoint", "route", "server")):
        add("code", f"Implement REST API endpoint ({lang}) for: {user_story[:120]}")
        add("code", f"Add error handling and validation ({lang})")
    elif any(k in story for k in ("function", "class", "algorithm", "parse")):
        add("code", f"Implement core function/class ({lang}): {user_story[:120]}")
        add("code", f"Implement helper utilities ({lang})")
    else:
        add("code", f"Implement main feature ({lang}): {user_story[:120]}")
        add("code", f"Implement edge case handling ({lang})")

    # Test tasks
    add("test", f"Write unit tests for main feature ({lang}) using pytest/unittest")
    add("test", f"Write integration tests for API/edge cases ({lang})")

    # Docs tasks
    add("docs", f"Write README with usage examples ({lang})")
    add("docs", f"Write API docstring and inline documentation")

    return tasks
