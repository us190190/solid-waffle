"""Hotel filter node. File: app/agents/hotels/filter.py:1"""
from datetime import datetime
from typing import Dict

from app.agents.common import require_gemini_key
from app.agents.tools.travel_data import filter_hotels_by_budget, search_hotels


def _nights(state: Dict) -> int:
    try:
        s = datetime.fromisoformat(state.get("start_date", "2026-10-01"))
        e = datetime.fromisoformat(state.get("end_date", "2026-10-03"))
        d = (e - s).days
        return max(1, d)
    except Exception:
        return 2


async def hotel_filter_node(state: Dict) -> Dict:
    require_gemini_key()
    budget = state.get("budget", 0)
    hotels = state.get("hotels", [])
    if not hotels:
        hotels = await search_hotels(state.get("destination", ""), state.get("start_date", ""),
                                     state.get("end_date", ""))
    filtered = filter_hotels_by_budget(hotels, budget, nights=_nights(state))
    return {
        "filtered_hotels": filtered,
        "tool_outputs": [
            {"tool": "filter_hotels", "input": f"budget {budget} nights {_nights(state)}", "output": filtered}],
        "messages": [{"role": "assistant", "content": f"Hotel filter: {len(filtered)}/{len(hotels)} within budget"}],
    }
