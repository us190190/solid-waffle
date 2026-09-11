"""Pure travel planning policies: budget filtering, ranking, itinerary optimization. File: app/core/travel_policies.py:1

No I/O, no mock data generation, no API calls — deterministic business rules only.
Replaces legacy mock_data.py (which was a misnomer; never contained mock datasets after live API migration).
"""
from typing import Dict, List


def filter_flights_by_budget(flights: List[Dict], budget: float) -> List[Dict]:
    if not budget or budget <= 0:
        return flights
    # per-flight budget cap: assume 40% of total budget for flights
    cap = budget * 0.4 if budget > 5000 else budget
    filtered = [f for f in flights if f["price"] <= cap]
    return filtered if filtered else flights


def rank_flights(flights: List[Dict], preferences: Dict) -> List[Dict]:
    pref = preferences or {}
    prefer_nonstop = pref.get("prefer_nonstop", True)
    prefer_cheap = pref.get("prefer_cheap", False)

    def score(f: Dict) -> float:
        s = 0
        if prefer_nonstop and f["stops"] == 0:
            s += 10
        if prefer_cheap:
            s -= f["price"] / 1000
        else:
            s -= f["duration_min"] / 60
            s -= f["price"] / 5000
        s += f.get("rating", 0) * 0.5
        return s

    return sorted(flights, key=score, reverse=True)


def filter_hotels_by_budget(hotels: List[Dict], budget: float, nights: int = 2) -> List[Dict]:
    if not budget or budget <= 0:
        return hotels
    # hotel budget cap: 50% of total
    cap_total = budget * 0.5
    cap_per_night = cap_total / max(nights, 1)
    filtered = [h for h in hotels if h["price_per_night"] <= cap_per_night]
    return filtered if filtered else hotels


def rank_hotels(hotels: List[Dict], preferences: Dict) -> List[Dict]:
    pref = preferences or {}
    prefer_luxury = pref.get("prefer_luxury", False)

    def score(h: Dict) -> float:
        s = h["rating"] * 2
        if prefer_luxury:
            s += h["rating"]
        else:
            s -= h["price_per_night"] / 2000
        return s

    return sorted(hotels, key=score, reverse=True)


def optimize_itinerary(activities: List[Dict], days: int, budget: float) -> Dict:
    per_day = max(1, len(activities) // max(days, 1))
    daily_plan = []
    idx = 0
    total_cost = 0
    for day in range(1, days + 1):
        day_acts = activities[idx: idx + per_day] if idx < len(activities) else []
        # if last day, take remainder
        if day == days and idx + per_day < len(activities):
            day_acts += activities[idx + per_day:]
        cost = sum(a["cost"] for a in day_acts)
        total_cost += cost
        daily_plan.append({"day": day, "activities": day_acts, "day_cost": cost})
        idx += per_day
        if idx >= len(activities):
            # fill remaining days empty if needed
            continue
    # budget validation
    budget_ok = (budget <= 0) or (total_cost <= budget * 0.3 + 5000)
    return {"daily_plan": daily_plan, "total_activities_cost": total_cost, "budget_ok": budget_ok, "days": days}
