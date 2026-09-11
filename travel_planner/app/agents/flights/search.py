"""Flight search node. File: app/agents/flights/search.py:1"""
from typing import Dict

from app.agents.common import require_gemini_key
from app.agents.tools.travel_data import search_flights


async def flight_search_node(state: Dict) -> Dict:
    origin = state.get("origin", "")
    destination = state.get("destination", "")
    start_date = state.get("start_date", "")
    flights = await search_flights(origin, destination, start_date)
    return {
        "flights": flights,
        "tool_outputs": [
            {"tool": "search_flights", "input": f"{origin}->{destination} {start_date}", "output": flights}],
        "messages": [
            {"role": "assistant", "content": f"Flight search: found {len(flights)} options {origin}->{destination}"}],
    }
