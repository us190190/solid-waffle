import operator
from typing import Annotated, Dict, List, TypedDict

from app.models.schemas import TaskItem


class CodeAssistantState(TypedDict, total=False):
    """Shared state for Code Assistant Team. File: app/models/state.py:5"""
    job_id: str
    user_story: str
    language: str
    tasks: List[Dict]
    # Reducers: fan-in from parallel workers
    code_artifacts: Annotated[List[Dict], operator.add]
    test_artifacts: Annotated[List[Dict], operator.add]
    docs_artifacts: Annotated[List[Dict], operator.add]
    agent_status: Annotated[List[Dict], operator.add]
    exec_results: Annotated[List[Dict], operator.add]
    final_output: str
    reviewer_notes: str
    status: str


class WorkerState(TypedDict, total=False):
    """State for worker subgraphs (isolated from parent to avoid concurrent channel writes)."""
    task: TaskItem
    job_id: str
    language: str
    user_story: str
    code_artifacts: Annotated[List[Dict], operator.add]
    test_artifacts: Annotated[List[Dict], operator.add]
    docs_artifacts: Annotated[List[Dict], operator.add]
    agent_status: Annotated[List[Dict], operator.add]
    exec_results: Annotated[List[Dict], operator.add]
