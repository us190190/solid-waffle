"""Reviewer agent (SRP). File: app/agents/reviewer.py:1"""
import datetime

from app.agents.common import _extract_llm_text, get_llm
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import has_gemini_key


async def reviewer_node(state: dict) -> dict:
    code_artifacts = state.get("code_artifacts", []) or []
    test_artifacts = state.get("test_artifacts", []) or []
    docs_artifacts = state.get("docs_artifacts", []) or []
    language = state.get("language", "python")
    user_story = state.get("user_story", "")
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if not has_gemini_key():
        notes = f"Reviewed {len(code_artifacts)} code, {len(test_artifacts)} tests, {len(docs_artifacts)} docs for '{user_story[:80]}' ({language}). All artifacts present."
        final = f"# Code Assistant Team - Review\n\n**Story:** {user_story}\n**Language:** {language}\n\n## Code ({len(code_artifacts)})\n"
        for a in code_artifacts:
            final += f"\n### {a.get('file', '')}\n```{language}\n{a.get('content', '')[:2500]}\n```\n"
        final += f"\n## Tests ({len(test_artifacts)})\n"
        for a in test_artifacts:
            final += f"\n### {a.get('file', '')}\n```{language}\n{a.get('content', '')[:1500]}\n```\n"
        final += f"\n## Docs ({len(docs_artifacts)})\n"
        for a in docs_artifacts:
            final += f"\n### {a.get('file', '')}\n{a.get('content', '')[:2000]}\n"
        final += f"\n---\n**Reviewer notes:** {notes}\n"
        return {
            "final_output": final,
            "reviewer_notes": notes,
            "agent_status": [{"agent": "reviewer", "status": "done", "ts": now}],
            "status": "awaiting_approval",
        }

    try:
        llm = get_llm()
        code_summary = "\n".join([f"{a.get('file')}: {a.get('content', '')[:500]}" for a in code_artifacts])
        test_summary = "\n".join([f"{a.get('file')}: {a.get('content', '')[:300]}" for a in test_artifacts])
        docs_summary = "\n".join([f"{a.get('file')}: {a.get('content', '')[:300]}" for a in docs_artifacts])
        prompt = f"Review this code assistant output for story '{user_story}' lang {language}.\nCode:\n{code_summary}\nTests:\n{test_summary}\nDocs:\n{docs_summary}\nReturn final markdown with Code/Tests/Docs sections and reviewer notes."
        msg = await llm.ainvoke([SystemMessage(content="You are senior reviewer."), HumanMessage(content=prompt)])
        text = _extract_llm_text(msg.content)
        if not text or len(text) < 50:
            raise ValueError("short")
        return {"final_output": text, "reviewer_notes": "LLM reviewed",
                "agent_status": [{"agent": "reviewer", "status": "done", "ts": now}], "status": "awaiting_approval"}
    except Exception:
        notes = f"Reviewed {len(code_artifacts)} code, {len(test_artifacts)} tests, {len(docs_artifacts)} docs."
        final = f"# Review\nStory: {user_story}\n\nCode files: {len(code_artifacts)}\nTests: {len(test_artifacts)}\nDocs: {len(docs_artifacts)}"
        return {"final_output": final, "reviewer_notes": notes,
                "agent_status": [{"agent": "reviewer", "status": "done", "ts": now}], "status": "awaiting_approval"}


async def human_approval_node(state: dict) -> dict:
    """HITL node - paused before via interrupt_before."""
    final = state.get("final_output", "")
    return {"final_output": final, "status": "completed", "agent_status": [
        {"agent": "human_approval", "status": "done", "ts": datetime.datetime.now(datetime.timezone.utc).isoformat()}]}
