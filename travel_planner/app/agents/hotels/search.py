"""Hotel search node. File: app/agents/hotels/search.py:1"""
from typing import Dict

from app.agents.common import require_gemini_key
from app.agents.tools.travel_data import search_hotels


async def hotel_search_node(state: Dict) -> Dict:
    require_gemini_key()
    destination = state.get("destination", "")
    start_date = state.get("start_date", "")
    end_date = state.get("end_date", "")
    hotels = await search_hotels(destination, start_date, end_date)
    return {
        "hotels": hotels,
        "tool_outputs": [
            {"tool": "search_hotels", "input": f"{destination} {start_date}->{end_date}", "output": hotels}],
        "messages": [{"role": "assistant", "content": f"Hotel search: found {len(hotels)} in {destination}"}],
    }
