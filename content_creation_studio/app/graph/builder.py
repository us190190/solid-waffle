"""Reflection loop: Writer -> Critic -> Editor with max-iteration guard. File: app/graph/builder.py:1"""
from langgraph.graph import StateGraph, START, END

from app.agents.nodes import writer_node, critic_node, editor_node, human_approval_node
from app.models.state import StudioState


def reflect_router(state: StudioState) -> str:
    iteration = state.get("iteration", 0)
    score = state.get("score", 0)
    max_iter = state.get("max_iterations", 3)
    threshold = state.get("critic_threshold", 8)
    if iteration >= max_iter:
        return "editor"
    if score >= threshold:
        return "editor"
    return "writer"


def build_graph(checkpointer=None, interrupt_before=None):
    workflow = StateGraph(StudioState)
    workflow.add_node("writer", writer_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("editor", editor_node)
    workflow.add_node("human_approval", human_approval_node)

    workflow.add_edge(START, "writer")
    workflow.add_edge("writer", "critic")
    workflow.add_conditional_edges("critic", reflect_router, {"writer": "writer", "editor": "editor"})
    workflow.add_edge("editor", "human_approval")
    workflow.add_edge("human_approval", END)

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
    return build_graph(checkpointer=checkpointer, interrupt_before=["human_approval"])
