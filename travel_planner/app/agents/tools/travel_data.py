"""Live travel data facade - no mock fallback. File: app/agents/tools/travel_data.py:1"""
from typing import Dict, List, Optional

from app.core.api_clients.activities_client import search_activities_api
from app.core.api_clients.flights_client import search_flights_api
from app.core.api_clients.hotels_client import search_hotels_api
# Re-export pure planning policies (no I/O, no mock search)
from app.core.travel_policies import (
    filter_flights_by_budget,
    filter_hotels_by_budget,
    optimize_itinerary,
    rank_flights,
    rank_hotels,
)


async def search_flights(origin: str, destination: str, date: str = "") -> List[Dict]:
    return await search_flights_api(origin, destination, date)


async def search_hotels(destination: str, check_in: str = "", check_out: str = "") -> List[Dict]:
    return await search_hotels_api(destination, check_in, check_out)


async def generate_activities(destination: str, interests: Optional[List[str]] = None) -> List[Dict]:
    return await search_activities_api(destination, interests)
