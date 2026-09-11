"""Supervisor TripManager - delegates via Command. File: app/agents/trip_manager.py:1"""
from typing import Dict

from app.agents.common import require_gemini_key
from langgraph.types import Command
from typing_extensions import Literal

from app.agents.classifiers import generate_trip_summary
from app.models.state import TravelPlannerState


async def trip_manager_node(state: TravelPlannerState, config=None, store=None) -> Command[
    Literal["flight_subgraph", "__end__"]]:
    require_gemini_key()
    # Persist preferences in InMemoryStore for stretch
    thread_id = state.get("thread_id", "")
    prefs = state.get("preferences", {})
    if store is not None and thread_id:
        try:
            # store.put(namespace, key, value)
            store.put((thread_id,), "preferences", prefs)
        except Exception:
            pass
    # Validate core fields
    origin = state.get("origin", "")
    destination = state.get("destination", "")
    if not origin or not destination:
        raise ValueError("origin and destination required")
    # Delegate sequentially - first to flight_subgraph
    # Using Command to demonstrate hierarchical delegation
    return Command(
        goto="flight_subgraph",
        update={
            "messages": [
                {"role": "assistant", "content": f"TripManager: delegating {origin}->{destination} to FlightSubgraph"}],
            "status": "planning",
        },
    )


async def summarize_node(state: TravelPlannerState, config=None, store=None) -> Dict:
    text = await generate_trip_summary(state)
    return {
        "final_response": text,
        "messages": [{"role": "assistant", "content": text}],
        "status": "completed",
    }
