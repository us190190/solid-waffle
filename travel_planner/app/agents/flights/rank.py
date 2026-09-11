"""Flight rank node. File: app/agents/flights/rank.py:1"""
from typing import Dict

from app.agents.common import require_gemini_key
from app.core.travel_policies import rank_flights


async def flight_rank_node(state: Dict) -> Dict:
    flights = state.get("filtered_flights") or state.get("flights", [])
    preferences = state.get("preferences", {})
    ranked = rank_flights(flights, preferences)
    return {
        "ranked_flights": ranked,
        "flights": ranked,  # propagate to parent as flights
        "tool_outputs": [{"tool": "rank_flights", "input": str(preferences), "output": ranked[:3]}],
        "messages": [{"role": "assistant",
                      "content": f"Flight rank: top {ranked[0]['flight_id'] if ranked else 'none'} price {ranked[0]['price'] if ranked else '-'} "}],
    }
