"""Itinerary generate node. File: app/agents/itinerary/generate.py:1"""
from typing import Dict

from app.agents.common import require_gemini_key
from app.agents.tools.travel_data import generate_activities


async def itinerary_generate_node(state: Dict) -> Dict:
    require_gemini_key()
    destination = state.get("destination", "")
    preferences = state.get("preferences", {})
    interests = preferences.get("interests") if isinstance(preferences.get("interests"), list) else None
    activities = await generate_activities(destination, interests)
    return {
        "activities": activities,
        "tool_outputs": [
            {"tool": "generate_activities", "input": f"{destination} interests={interests}", "output": activities}],
        "messages": [
            {"role": "assistant", "content": f"Itinerary generate: {len(activities)} activities for {destination}"}],
    }
