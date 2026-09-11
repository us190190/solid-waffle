"""Flight filter node. File: app/agents/flights/filter.py:1"""
from typing import Dict

from app.agents.common import require_gemini_key
from app.agents.tools.travel_data import filter_flights_by_budget


async def flight_filter_node(state: Dict) -> Dict:
    require_gemini_key()
    budget = state.get("budget", 0)
    flights = state.get("flights", [])
    filtered = filter_flights_by_budget(flights, budget)
    return {
        "filtered_flights": filtered,
        "tool_outputs": [{"tool": "filter_flights", "input": f"budget {budget}", "output": filtered}],
        "messages": [{"role": "assistant", "content": f"Flight filter: {len(filtered)}/{len(flights)} within budget"}],
    }
