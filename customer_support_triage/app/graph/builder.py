"""LangGraph Router: Supervisor -> conditional -> specialists -> responder -> conditional -> handoff. File: app/graph/builder.py:1"""
from langgraph.graph import StateGraph, START, END

from app.agents.nodes import supervisor_node, billing_node, technical_node, sales_node, responder_node, \
    human_handoff_node
from app.models.state import SupportState


def intent_router(state: dict) -> str:
    return state.get("intent", "technical")


def escalation_router(state: dict) -> str:
    if state.get("escalated"):
        return "handoff"
    # also route if sentiment negative and intent requires human
    if state.get("sentiment") == "negative" and state.get("confidence", 0) >= 0.7:
        return "handoff"
    return "end"


def build_graph(checkpointer=None, interrupt_before=None):
    workflow = StateGraph(SupportState)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("billing", billing_node)
    workflow.add_node("technical", technical_node)
    workflow.add_node("sales", sales_node)
    workflow.add_node("responder", responder_node)
    workflow.add_node("human_handoff", human_handoff_node)

    workflow.add_edge(START, "supervisor")
    workflow.add_conditional_edges("supervisor", intent_router,
                                   {"billing": "billing", "technical": "technical", "sales": "sales"})
    workflow.add_edge("billing", "responder")
    workflow.add_edge("technical", "responder")
    workflow.add_edge("sales", "responder")
    workflow.add_conditional_edges("responder", escalation_router, {"handoff": "human_handoff", "end": END})
    workflow.add_edge("human_handoff", END)

    kwargs = {}
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer
    if interrupt_before is not None:
        kwargs["interrupt_before"] = interrupt_before
    return workflow.compile(**kwargs)


# Stateless compiled graph (no checkpointer, no interrupt)
graph = build_graph()


# Helper for stateful graph - caller must provide checkpointer instance
def build_stateful_graph(checkpointer):
    return build_graph(checkpointer=checkpointer, interrupt_before=["human_handoff"])
