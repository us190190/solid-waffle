"""Itinerary subgraph: Generate -> Optimize -> Validate. File: app/graph/subgraphs/itinerary.py:1"""
from app.agents.itinerary.generate import itinerary_generate_node
from app.agents.itinerary.optimize import itinerary_optimize_node
from app.agents.itinerary.validate import itinerary_validate_node
from langgraph.graph import END, START, StateGraph

from app.models.state import ItineraryState


def build_itinerary_subgraph():
    workflow = StateGraph(ItineraryState)
    workflow.add_node("itinerary_generate", itinerary_generate_node)
    workflow.add_node("itinerary_optimize", itinerary_optimize_node)
    workflow.add_node("itinerary_validate", itinerary_validate_node)
    workflow.add_edge(START, "itinerary_generate")
    workflow.add_edge("itinerary_generate", "itinerary_optimize")
    workflow.add_edge("itinerary_optimize", "itinerary_validate")
    workflow.add_edge("itinerary_validate", END)
    return workflow.compile()
