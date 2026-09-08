import operator
from typing import Annotated, List, Dict, TypedDict


class StudioState(TypedDict, total=False):
    """Shared state for Content Creation Studio reflection loop. File: app/models/state.py:5"""
    job_id: str
    prompt: str
    tone: str
    content_type: str
    draft: str
    drafts: Annotated[List[Dict], operator.add]
    score: int
    feedback: str
    suggestions: List[str]
    iteration: int
    final_content: str
    status: str
    max_iterations: int
    critic_threshold: int
