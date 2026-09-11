"""Hotel rank node. File: app/agents/hotels/rank.py:1"""
from typing import Dict

from app.agents.common import require_gemini_key
from app.agents.tools.travel_data import rank_hotels


async def hotel_rank_node(state: Dict) -> Dict:
    require_gemini_key()
    hotels = state.get("filtered_hotels") or state.get("hotels", [])
    preferences = state.get("preferences", {})
    ranked = rank_hotels(hotels, preferences)
    return {
        "ranked_hotels": ranked,
        "hotels": ranked,
        "tool_outputs": [{"tool": "rank_hotels", "input": str(preferences), "output": ranked[:3]}],
        "messages": [{"role": "assistant",
                      "content": f"Hotel rank: top {ranked[0]['name'] if ranked else 'none'} rating {ranked[0]['rating'] if ranked else '-'} "}],
    }
