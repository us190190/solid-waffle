"""Parallel collab: Planner -> Send fan-out -> Coder/Tester/DocsWriter -> Reviewer. File: app/graph/builder.py:1"""
from typing import List

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.agents.nodes import coder_node, docs_writer_node, human_approval_node, planner_node, reviewer_node, tester_node
from app.models.state import CodeAssistantState, WorkerState


def fanout(state: CodeAssistantState) -> List[Send]:
    tasks = state.get("tasks", []) or []
    job_id = state.get("job_id", "")
    language = state.get("language", "python")
    user_story = state.get("user_story", "")
    sends: List[Send] = []
    for t in tasks:
        ttype = t.get("type", "code")
        initial_state = WorkerState(task=t, job_id=job_id, language=language or t.get("language", "python"),
                                    user_story=user_story)
        if ttype == "code":
            sends.append(Send("coder", initial_state))
        elif ttype == "test":
            sends.append(Send("tester", initial_state))
        elif ttype == "docs":
            sends.append(Send("docs_writer", initial_state))
    return sends


def build_coder_subgraph():
    # Subgraph uses WorkerState isolated to avoid parent concurrent writes; demonstrates subgraph composition
    sg = StateGraph(WorkerState)
    sg.add_node("coder", coder_node)
    sg.add_edge(START, "coder")
    sg.add_edge("coder", END)
    return sg.compile()


def build_tester_subgraph():
    sg = StateGraph(WorkerState)
    sg.add_node("tester", tester_node)
    sg.add_edge(START, "tester")
    sg.add_edge("tester", END)
    return sg.compile()


def build_docs_subgraph():
    sg = StateGraph(WorkerState)
    sg.add_node("docs_writer", docs_writer_node)
    sg.add_edge(START, "docs_writer")
    sg.add_edge("docs_writer", END)
    return sg.compile()


# Keep subgraphs for demo but use direct nodes for parallel to avoid parent job_id concurrent merge
# Subgraphs are used internally by reviewer (composition example) and also available
coder_subgraph = build_coder_subgraph()
tester_subgraph = build_tester_subgraph()
docs_subgraph = build_docs_subgraph()


# For parallel execution, use direct nodes (Send to direct node avoids subgraph merge conflict)
# Subgraph demonstration is retained via reviewer_subgraph composition
def build_reviewer_subgraph():
    sg = StateGraph(CodeAssistantState)
    sg.add_node("reviewer", reviewer_node)
    sg.add_node("human_approval", human_approval_node)
    sg.add_edge(START, "reviewer")
    sg.add_edge("reviewer", "human_approval")
    sg.add_edge("human_approval", END)
    return sg.compile()


reviewer_subgraph = build_reviewer_subgraph()


def build_graph(checkpointer=None, interrupt_before=None):
    workflow = StateGraph(CodeAssistantState)
    workflow.add_node("planner", planner_node)
    # Use direct nodes for parallel workers to allow clean Send fan-out
    workflow.add_node("coder", coder_node)
    workflow.add_node("tester", tester_node)
    workflow.add_node("docs_writer", docs_writer_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("human_approval", human_approval_node)

    workflow.add_edge(START, "planner")
    workflow.add_conditional_edges("planner", fanout, ["coder", "tester", "docs_writer"])
    workflow.add_edge("coder", "reviewer")
    workflow.add_edge("tester", "reviewer")
    workflow.add_edge("docs_writer", "reviewer")
    workflow.add_edge("reviewer", "human_approval")
    workflow.add_edge("human_approval", END)

    kwargs = {}
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer
    if interrupt_before is not None:
        kwargs["interrupt_before"] = interrupt_before
    return workflow.compile(**kwargs)


graph = build_graph()


def build_stateful_graph(checkpointer):
    return build_graph(checkpointer=checkpointer, interrupt_before=["human_approval"])
