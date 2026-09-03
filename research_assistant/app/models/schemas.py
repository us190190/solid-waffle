from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500, description="Research question",
                       examples=["What is LangGraph and how does it differ from LangChain?"])


class Citation(BaseModel):
    index: int
    title: str
    url: str


class ResearchResponse(BaseModel):
    id: int
    query: str
    summary: str
    final_answer: str
    citations: List[Citation]
    documents: List[Dict]
    created_at: str


class HistoryItem(BaseModel):
    id: int
    query: str
    summary: str
    final_answer: str
    citations: List[Dict]
    created_at: str
    documents_count: int = 0


class HealthResponse(BaseModel):
    status: str
    gemini_configured: bool
    model: str
