from typing import List, Literal, Optional, Dict

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"] = Field(..., examples=["user"])
    content: str = Field(..., min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="Latest user message",
                         examples=["I was charged twice for INV-002"])
    history: List[ChatMessage] = Field(default_factory=list,
                                       description="Conversation history for stateless invocation")
    thread_id: Optional[str] = Field(None, description="Thread id for stateful invocation")


class ClassificationResult(BaseModel):
    intent: Literal["billing", "technical", "sales"] = Field(..., description="Classified intent")
    sentiment: Literal["positive", "neutral", "negative"] = Field(..., description="Sentiment")
    confidence: float = Field(..., ge=0, le=1)
    reasoning: str = Field(..., description="Brief reasoning")


class ChatResponse(BaseModel):
    thread_id: str
    intent: Literal["billing", "technical", "sales"]
    sentiment: Literal["positive", "neutral", "negative"]
    confidence: float
    escalated: bool
    response: str
    tool_outputs: List[Dict]
    history: List[ChatMessage] = []


class HealthResponse(BaseModel):
    status: str
    gemini_configured: bool
    model: str
    checkpointer: str


class HistoryItem(BaseModel):
    id: int
    thread_id: str
    user_input: str
    intent: str
    sentiment: str
    response: str
    tool_outputs: List[Dict]
    escalated: bool
    created_at: str
