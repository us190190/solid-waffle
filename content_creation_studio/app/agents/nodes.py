"""LangGraph nodes: Writer -> Critic -> Editor (+ HumanApproval). File: app/agents/nodes.py:1"""
from typing import Dict

from app.agents.classifiers import keyword_critic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import has_gemini_key, settings
from app.models.schemas import CriticScore
from app.models.state import StudioState


def _extract_llm_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        if isinstance(content.get("text"), str):
            return content["text"]
        return str(content)
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                txt = block.get("text")
                if isinstance(txt, str):
                    parts.append(txt)
                elif isinstance(block.get("content"), str):
                    parts.append(block["content"])
            else:
                txt = getattr(block, "text", None)
                if isinstance(txt, str):
                    parts.append(txt)
                elif isinstance(getattr(block, "content", None), str):
                    parts.append(getattr(block, "content"))
        joined = "\n\n".join(p for p in parts if p)
        return joined if joined else str(content)
    return str(content)


async def writer_node(state: StudioState) -> Dict:
    prompt = state.get("prompt", "")
    tone = state.get("tone", "")
    content_type = state.get("content_type", "")
    iteration = state.get("iteration", 0)
    feedback = state.get("feedback", "")
    suggestions = state.get("suggestions", [])
    previous_draft = state.get("draft", "")

    if not has_gemini_key():
        base = f"# Draft v{iteration + 1} — {content_type or 'content'} ({tone or 'default tone'})\n\n"
        base += f"**Brief:** {prompt}\n\n"
        if iteration == 0:
            base += (
                "## Introduction\nThis piece explores the topic with a clear hook and sets up key questions.\n\n"
                "## Main Content\nWe cover the core ideas with examples and explain why they matter. "
                f"For instance, considering '{prompt[:80]}', we outline practical steps and benefits.\n\n"
                "## Conclusion\nKey takeaways and a call to action.\n"
            )
        else:
            base += f"## Introduction (revised after feedback: {feedback[:120]})\nImproved hook that directly addresses the brief.\n\n"
            base += "## Main Content (revised)\n"
            if suggestions:
                base += "Incorporating: " + "; ".join(suggestions[:2]) + ".\n\n"
            base += f"Expanded discussion of '{prompt[:80]}' with 2 concrete examples, clearer structure, and tighter language.\n"
            if tone:
                base += f"Tone adjusted to be more {tone}.\n"
            base += "\n## Conclusion (revised)\nStronger ending with actionable next steps.\n"
            if previous_draft:
                base += f"\n> Previous draft was {len(previous_draft)} chars; this version refines flow and depth.\n"
        new_iteration = iteration + 1
        draft_entry = {"iteration": new_iteration, "draft": base}
        return {"draft": base, "iteration": new_iteration, "drafts": [draft_entry]}

    try:
        llm = ChatGoogleGenerativeAI(model=settings.gemini_model, max_retries=2)
        sys_content = (
            f"You are an expert writer. Create {content_type or 'engaging content'} "
            f"in a {tone or 'professional'} tone. Be concise, structured, with headings and examples."
        )
        if iteration > 0 and feedback:
            sys_content += f" You are REWRITING a previous draft based on editor feedback. Feedback: {feedback}. Suggestions: {', '.join(suggestions[:3])}. Improve significantly."
        human_content = f"Brief: {prompt}\n"
        if previous_draft and iteration > 0:
            human_content += f"\nPrevious draft (to improve):\n{previous_draft[:3000]}\n\nRewrite fully, keeping strengths and fixing critique points."
        else:
            human_content += "\nWrite a complete draft (300-600 words) with intro, body, conclusion."
        human_content += f"\n\n(Iteration {iteration + 1})"

        system = SystemMessage(content=sys_content)
        human = HumanMessage(content=human_content)
        resp = await llm.ainvoke([system, human])
        text = _extract_llm_text(resp.content)
        if not text or len(text.strip()) < 20:
            text = f"# Draft v{iteration + 1}\n\n{prompt}\n\n(Fallback generated draft)"
        new_iteration = iteration + 1
        draft_entry = {"iteration": new_iteration, "draft": text}
        return {"draft": text, "iteration": new_iteration, "drafts": [draft_entry]}
    except Exception as e:
        fallback = f"# Draft v{iteration + 1} (fallback: {str(e)[:200]})\n\nBrief: {prompt}\n\nMock content for iteration {iteration + 1}."
        new_iteration = iteration + 1
        return {"draft": fallback, "iteration": new_iteration,
                "drafts": [{"iteration": new_iteration, "draft": fallback}]}


async def critic_node(state: StudioState) -> Dict:
    draft = state.get("draft", "")
    prompt = state.get("prompt", "")
    tone = state.get("tone", "")
    content_type = state.get("content_type", "")
    iteration = state.get("iteration", 0)

    if not has_gemini_key():
        result = keyword_critic(draft, iteration)
        return {"score": result.score, "feedback": result.feedback, "suggestions": result.suggestions}

    try:
        llm = ChatGoogleGenerativeAI(model=settings.gemini_model, max_retries=2)
        structured = llm.with_structured_output(CriticScore)
        ctx = (
            f"Brief: {prompt}\nTone: {tone or 'default'}\nContent type: {content_type or 'general'}\n"
            f"Iteration: {iteration}\n\nDraft:\n{draft[:4000]}"
        )
        prompt_msg = (
                "You are a strict senior editor. Score draft 1-10 (8+ publishable). "
                "Criteria: clarity, engagement, structure, fidelity to brief, tone. "
                "Return score, one-sentence feedback, and 1-3 suggestions.\n\n" + ctx
        )
        result: CriticScore = await structured.ainvoke(prompt_msg)
        score = max(1, min(10, int(result.score)))
        return {"score": score, "feedback": result.feedback, "suggestions": result.suggestions}
    except Exception as e:
        print(f"Critic LLM failed: {e}")
        fb = keyword_critic(draft, iteration)
        return {"score": fb.score, "feedback": fb.feedback, "suggestions": fb.suggestions}


async def editor_node(state: StudioState) -> Dict:
    draft = state.get("draft", "")
    prompt = state.get("prompt", "")
    score = state.get("score", 0)
    feedback = state.get("feedback", "")

    if not has_gemini_key():
        polished = draft + f"\n\n---\n*Edited for final polish (score {score}/10, feedback: {feedback[:100]})*"
        polished += "\n\n**Final note:** Ready for human approval."
        return {"final_content": polished, "status": "awaiting_approval"}

    try:
        llm = ChatGoogleGenerativeAI(model=settings.gemini_model, max_retries=2)
        system = SystemMessage(
            content="You are a copy editor. Polish grammar, flow, headings, keep tone. Do not add new hallucinations. Output final markdown (300-600 words).")
        human = HumanMessage(
            content=f"Brief: {prompt}\nCritic score {score}/10 feedback: {feedback}\n\nDraft to polish:\n{draft[:4000]}\n\nReturn polished final content.")
        resp = await llm.ainvoke([system, human])
        text = _extract_llm_text(resp.content)
        if not text:
            text = draft
        return {"final_content": text, "status": "awaiting_approval"}
    except Exception as e:
        print(f"Editor LLM failed: {e}")
        return {"final_content": draft, "status": "awaiting_approval"}


def human_approval_node(state: StudioState) -> Dict:
    """Placeholder node for interrupt_before HITL. Actual pause is before this node.
    If resumed, mark completed."""
    final = state.get("final_content") or state.get("draft", "")
    return {"final_content": final, "status": "completed"}
