"""Hotel subgraph: Search -> Filter -> Rank. File: app/graph/subgraphs/hotel.py:1"""
from app.agents.hotels.filter import hotel_filter_node
from app.agents.hotels.rank import hotel_rank_node
from app.agents.hotels.search import hotel_search_node
from langgraph.graph import END, START, StateGraph

from app.models.state import HotelState


def build_hotel_subgraph():
    workflow = StateGraph(HotelState)
    workflow.add_node("hotel_search", hotel_search_node)
    workflow.add_node("hotel_filter", hotel_filter_node)
    workflow.add_node("hotel_rank", hotel_rank_node)
    workflow.add_edge(START, "hotel_search")
    workflow.add_edge("hotel_search", "hotel_filter")
    workflow.add_edge("hotel_filter", "hotel_rank")
    workflow.add_edge("hotel_rank", END)
    return workflow.compile()
