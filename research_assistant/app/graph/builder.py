"""LangGraph StateGraph: Sequential Research Assistant. File: app/graph/builder.py:1"""
from app.agents.nodes import search_node, summarizer_node, citation_node
from app.models.state import ResearchState
from langgraph.graph import StateGraph, START, END


def build_graph():
    workflow = StateGraph(ResearchState)
    workflow.add_node("search", search_node)
    workflow.add_node("summarize", summarizer_node)
    workflow.add_node("cite", citation_node)

    workflow.add_edge(START, "search")
    workflow.add_edge("search", "summarize")
    workflow.add_edge("summarize", "cite")
    workflow.add_edge("cite", END)

    return workflow.compile()


graph = build_graph()
