from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class CodegenRequest(BaseModel):
    user_story: str = Field(..., min_length=10, max_length=5000, description="User story to implement")
    language: str = Field(default="python", min_length=2, max_length=20, description="Target language")

    model_config = {"json_schema_extra": {
        "example": {"user_story": "As a user I want a FastAPI endpoint that returns hello world",
                    "language": "python"}}}


class Artifact(BaseModel):
    file: str
    content: str
    task_id: Optional[str] = None


class TaskItem(BaseModel):
    id: str
    type: str = Field(..., description="code|test|docs")
    description: str
    language: str = "python"


class TasksSchema(BaseModel):
    """Structured output for planner: list of tasks. File: app/models/schemas.py:25"""
    tasks: List[TaskItem]


class CodegenResponse(BaseModel):
    job_id: str
    status: str
    language: str
    user_story: str


class JobStatus(BaseModel):
    job_id: str
    user_story: str
    language: str
    status: str
    tasks: List[Dict] = []
    code_artifacts: List[Dict] = []
    test_artifacts: List[Dict] = []
    docs_artifacts: List[Dict] = []
    agent_status: List[Dict] = []
    exec_results: List[Dict] = []
    final_output: Optional[str] = None
    reviewer_notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ApproveRequest(BaseModel):
    approved: bool = Field(..., description="True to approve, False to reject")
    edits: Optional[str] = Field(default=None, max_length=20000, description="Optional edits to final output")


class HealthResponse(BaseModel):
    status: str
    gemini_configured: bool
    model: str
    checkpointer: str
