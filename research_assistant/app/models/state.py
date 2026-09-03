import operator
from typing import TypedDict, Annotated, List, Dict


class ResearchState(TypedDict):
    """Shared state across LangGraph nodes. File: app/models/state.py:5"""
    query: str
    documents: Annotated[List[Dict], operator.add]
    summary: str
    citations: List[Dict]
    final_answer: str
