"""LLM classifiers - no mock fallback. File: app/agents/classifiers.py:1"""
from typing import Dict

from app.agents.common import extract_llm_text, require_gemini_key
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.core.config import settings


class TripIntent(BaseModel):
    origin: str = Field(..., description="Origin code")
    destination: str = Field(..., description="Destination code")
    trip_type: str = Field(..., description="leisure/business/adventure")
    reasoning: str = Field(..., description="Brief reasoning")


async def classify_trip(origin: str, destination: str, preferences: Dict) -> TripIntent:
    require_gemini_key()
    llm = ChatGoogleGenerativeAI(model=settings.gemini_model, max_retries=2)
    structured = llm.with_structured_output(TripIntent)
    system = SystemMessage(
        content="You are a travel intent classifier. Normalize origin/destination to uppercase codes and classify trip_type.")
    human = HumanMessage(
        content=f"Origin: {origin}, Destination: {destination}, Preferences: {preferences}. Return TripIntent.")
    result = await structured.ainvoke([system, human])
    return result


async def generate_trip_summary(state: Dict) -> str:
    require_gemini_key()
    llm = ChatGoogleGenerativeAI(model=settings.gemini_model, max_retries=2)
    system = SystemMessage(
        content="You are a travel planner. Summarize the trip with flights, hotels, itinerary in markdown 150-250 words.")
    flights = state.get("flights", [])[:3]
    hotels = state.get("hotels", [])[:3]
    itinerary = state.get("itinerary", {})
    human = HumanMessage(
        content=f"Destination {state.get('destination')} origin {state.get('origin')} budget {state.get('budget')} flights {flights} hotels {hotels} itinerary {itinerary}. Write final summary.")
    resp = await llm.ainvoke([system, human])
    return extract_llm_text(resp.content)
