"""Flight subgraph: Search -> Filter -> Rank. File: app/graph/subgraphs/flight.py:1"""
from app.agents.flights.filter import flight_filter_node
from app.agents.flights.rank import flight_rank_node
from app.agents.flights.search import flight_search_node
from langgraph.graph import END, START, StateGraph

from app.models.state import FlightState


def build_flight_subgraph():
    workflow = StateGraph(FlightState)
    workflow.add_node("flight_search", flight_search_node)
    workflow.add_node("flight_filter", flight_filter_node)
    workflow.add_node("flight_rank", flight_rank_node)
    workflow.add_edge(START, "flight_search")
    workflow.add_edge("flight_search", "flight_filter")
    workflow.add_edge("flight_filter", "flight_rank")
    workflow.add_edge("flight_rank", END)
    return workflow.compile()
