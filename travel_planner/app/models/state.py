import operator
from typing import Annotated, Dict, List, TypedDict


class FlightState(TypedDict, total=False):
    """Flight subgraph state. File: app/models/state.py:5"""
    origin: str
    destination: str
    start_date: str
    budget: float
    travelers: int
    preferences: Dict
    flights: List[Dict]
    filtered_flights: List[Dict]
    ranked_flights: List[Dict]
    tool_outputs: Annotated[List[Dict], operator.add]


class HotelState(TypedDict, total=False):
    """Hotel subgraph state. File: app/models/state.py:18"""
    destination: str
    start_date: str
    end_date: str
    budget: float
    travelers: int
    preferences: Dict
    hotels: List[Dict]
    filtered_hotels: List[Dict]
    ranked_hotels: List[Dict]
    tool_outputs: Annotated[List[Dict], operator.add]


class ItineraryState(TypedDict, total=False):
    """Itinerary subgraph state. File: app/models/state.py:31"""
    destination: str
    start_date: str
    end_date: str
    budget: float
    preferences: Dict
    activities: List[Dict]
    daily_plan: List[Dict]
    itinerary: Dict
    tool_outputs: Annotated[List[Dict], operator.add]


class TravelPlannerState(TypedDict, total=False):
    """Parent hierarchical state. File: app/models/state.py:43"""
    trip_id: str
    thread_id: str
    origin: str
    destination: str
    start_date: str
    end_date: str
    budget: float
    travelers: int
    preferences: Dict
    messages: Annotated[List[Dict], operator.add]
    flights: List[Dict]
    hotels: List[Dict]
    itinerary: Dict
    tool_outputs: Annotated[List[Dict], operator.add]
    status: str
    final_response: str
