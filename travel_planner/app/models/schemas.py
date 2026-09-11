from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class TripCreateRequest(BaseModel):
    origin: str = Field(..., min_length=2, max_length=20, description="Origin code e.g. DEL", examples=["DEL"])
    destination: str = Field(..., min_length=2, max_length=20, description="Destination code e.g. GOA",
                             examples=["GOA"])
    start_date: str = Field(..., description="Start date YYYY-MM-DD", examples=["2026-10-01"])
    end_date: str = Field(..., description="End date YYYY-MM-DD", examples=["2026-10-05"])
    budget: float = Field(..., gt=0, description="Total budget", examples=[20000])
    travelers: int = Field(default=1, ge=1, le=20)
    preferences: Dict = Field(default_factory=dict, description="User preferences e.g. {'prefer_nonstop': true}")
    thread_id: Optional[str] = Field(None, description="Thread id for checkpoint resumption")


class TripRefineRequest(BaseModel):
    budget: Optional[float] = Field(None, gt=0, description="Updated budget")
    preferences: Optional[Dict] = Field(None, description="Updated preferences patch")
    refinement_query: Optional[str] = Field(None, min_length=1, max_length=500, description="Free-text refinement")


class TripResponse(BaseModel):
    id: int
    thread_id: str
    origin: str
    destination: str
    start_date: str
    end_date: str
    budget: float
    travelers: int
    preferences: Dict
    flights: List[Dict]
    hotels: List[Dict]
    itinerary: Dict
    status: str
    final_response: str
    created_at: str
    updated_at: str


class HealthResponse(BaseModel):
    status: str
    gemini_configured: bool
    model: str
    checkpointer: str
    store: str
