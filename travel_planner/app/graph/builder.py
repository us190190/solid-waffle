"""Hierarchical Teams: TripManager -> Flight/Hotel/Itinerary subgraphs -> Summarize. File: app/graph/builder.py:1"""
from app.agents.trip_manager import summarize_node, trip_manager_node
from app.graph.subgraphs.flight import build_flight_subgraph
from app.graph.subgraphs.hotel import build_hotel_subgraph
from app.graph.subgraphs.itinerary import build_itinerary_subgraph
from langgraph.graph import END, START, StateGraph
from langgraph.store.memory import InMemoryStore

from app.models.state import TravelPlannerState


def build_graph(checkpointer=None, store=None, interrupt_before=None):
    flight_sg = build_flight_subgraph()
    hotel_sg = build_hotel_subgraph()
    itinerary_sg = build_itinerary_subgraph()

    workflow = StateGraph(TravelPlannerState)
    workflow.add_node("trip_manager", trip_manager_node)
    workflow.add_node("flight_subgraph", flight_sg)
    workflow.add_node("hotel_subgraph", hotel_sg)
    workflow.add_node("itinerary_subgraph", itinerary_sg)
    workflow.add_node("summarize", summarize_node)

    workflow.add_edge(START, "trip_manager")
    workflow.add_edge("flight_subgraph", "hotel_subgraph")
    workflow.add_edge("hotel_subgraph", "itinerary_subgraph")
    workflow.add_edge("itinerary_subgraph", "summarize")
    workflow.add_edge("summarize", END)

    kwargs = {}
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer
    if store is not None:
        kwargs["store"] = store
    if interrupt_before is not None:
        kwargs["interrupt_before"] = interrupt_before
    return workflow.compile(**kwargs)


# Stateless graph (no checkpointer, no interrupt)
graph = build_graph()


def build_stateful_graph(checkpointer, store=None):
    if store is None:
        store = InMemoryStore()
    return build_graph(checkpointer=checkpointer, store=store, interrupt_before=["summarize"])
