import operator
from typing import Annotated, List, Dict, Literal, TypedDict


class SupportState(TypedDict):
    """Shared state for supervisor routing. File: app/models/state.py:5"""
    messages: Annotated[List[Dict], operator.add]
    user_input: str
    intent: Literal["billing", "technical", "sales"]
    sentiment: Literal["positive", "neutral", "negative"]
    confidence: float
    tool_outputs: Annotated[List[Dict], operator.add]
    final_response: str
    escalated: bool
    thread_id: str
