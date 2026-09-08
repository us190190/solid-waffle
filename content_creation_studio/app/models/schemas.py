from typing import List, Optional, Dict

from pydantic import BaseModel, Field


class CreateRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=5000, description="Free-form creation brief",
                        examples=["Write a blog post about LangGraph reflection loops for AI engineers"])
    tone: Optional[str] = Field(None, max_length=100,
                                description="Free-form tone e.g. professional, casual, witty, dramatic",
                                examples=["professional"])
    content_type: Optional[str] = Field(None, max_length=100,
                                        description="Free-form content type e.g. blog, tweet, story, email",
                                        examples=["blog"])
    max_iterations: Optional[int] = Field(None, ge=1, le=5, description="Override max Writer->Critic loops (default 3)")
    critic_threshold: Optional[int] = Field(None, ge=1, le=10, description="Score threshold to exit loop (default 8)")


class DraftEntry(BaseModel):
    iteration: int
    draft: str
    score: Optional[int] = None
    feedback: Optional[str] = None
    suggestions: List[str] = []


class CreateResponse(BaseModel):
    job_id: str
    status: str


class JobStatus(BaseModel):
    job_id: str
    prompt: str
    tone: str = ""
    content_type: str = ""
    status: str
    iteration: int
    score: Optional[int] = None
    feedback: Optional[str] = None
    suggestions: List[str] = []
    drafts: List[Dict] = []
    final_content: Optional[str] = None
    max_iterations: int = 3
    critic_threshold: int = 8
    created_at: str
    updated_at: str


class ApproveRequest(BaseModel):
    approved: bool = Field(..., description="Approve drafted final content")
    edits: Optional[str] = Field(None, max_length=10000, description="Optional edited final content to replace draft")


class HealthResponse(BaseModel):
    status: str
    gemini_configured: bool
    model: str
    checkpointer: str = "AsyncSqliteSaver"


class CriticScore(BaseModel):
    score: int = Field(..., ge=1, le=10, description="Quality score 1-10")
    feedback: str = Field(..., description="Brief critique")
    suggestions: List[str] = Field(default_factory=list, description="Improvement suggestions")
