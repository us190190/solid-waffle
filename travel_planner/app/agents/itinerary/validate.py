"""Itinerary validate node. File: app/agents/itinerary/validate.py:1"""
from typing import Dict

from app.agents.common import require_gemini_key


async def itinerary_validate_node(state: Dict) -> Dict:
    require_gemini_key()
    itinerary = state.get("itinerary", {})
    budget_ok = itinerary.get("budget_ok", True)
    msg = "Itinerary validated: budget OK" if budget_ok else "Itinerary warning: activities cost exceeds budget slice"
    return {
        "itinerary": itinerary,
        "tool_outputs": [{"tool": "validate_itinerary", "input": str(itinerary.get("total_activities_cost", 0)),
                          "output": {"budget_ok": budget_ok}}],
        "messages": [{"role": "assistant", "content": msg}],
    }
