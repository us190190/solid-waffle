"""Itinerary optimize node. File: app/agents/itinerary/optimize.py:1"""
from datetime import datetime
from typing import Dict

from app.agents.common import require_gemini_key
from app.agents.tools.travel_data import generate_activities, optimize_itinerary


def _days(state: Dict) -> int:
    try:
        s = datetime.fromisoformat(state.get("start_date", "2026-10-01"))
        e = datetime.fromisoformat(state.get("end_date", "2026-10-03"))
        d = (e - s).days
        return max(1, d)
    except Exception:
        return 2


async def itinerary_optimize_node(state: Dict) -> Dict:
    require_gemini_key()
    activities = state.get("activities", [])
    if not activities:
        activities = await generate_activities(state.get("destination", ""), None)
    budget = state.get("budget", 0)
    days = _days(state)
    opt = optimize_itinerary(activities, days, budget)
    return {
        "daily_plan": opt["daily_plan"],
        "itinerary": opt,
        "tool_outputs": [{"tool": "optimize_itinerary", "input": f"days {days} budget {budget}", "output": opt}],
        "messages": [
            {"role": "assistant", "content": f"Itinerary optimize: {days} days, cost {opt['total_activities_cost']}"}],
    }
