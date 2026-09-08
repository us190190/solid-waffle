"""Critic structured output + mock fallback. File: app/agents/classifiers.py:1"""

from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import has_gemini_key, settings
from app.models.schemas import CriticScore


def keyword_critic(draft: str, iteration: int) -> CriticScore:
    """Deterministic mock: score improves with iteration and draft quality heuristics."""
    text = draft or ""
    length = len(text)
    # base: keep first drafts below threshold to demonstrate loop visibly
    if length < 100:
        base = 3
    elif length < 300:
        base = 4
    elif length < 600:
        base = 5
    else:
        base = 5
    # iteration bonus: small for early iterations, larger later to guarantee convergence
    if iteration <= 1:
        iter_bonus = 0
    elif iteration == 2:
        iter_bonus = 2
    else:
        iter_bonus = 3
    # quality heuristics: only modest bonus
    quality_terms = ["example", "introduction", "conclusion", "step", "benefit", "because", "however"]
    hits = sum(1 for w in quality_terms if w in text.lower())
    quality_bonus = 1 if hits >= 3 else 0
    score = min(10, base + iter_bonus + quality_bonus)
    # ensure eventual 8+ by iteration 3 for demo termination
    if iteration >= 3 and score < 8:
        score = 8
    if score < 5:
        feedback = f"Draft too brief or vague (len={length}). Add structure, examples, and clear takeaways."
        suggestions = ["Expand introduction with hook", "Add 2-3 concrete examples", "End with actionable conclusion"]
    elif score < 8:
        feedback = f"Good start (len={length}), needs more depth and polish for publishable quality."
        suggestions = ["Tighten language and remove repetition", "Add supporting detail or data",
                       "Improve flow between sections"]
    else:
        feedback = f"Strong draft (len={length}) — clear, well-structured, meets quality bar."
        suggestions = ["Minor copy edits", "Consider stronger title"]
    return CriticScore(score=score, feedback=feedback, suggestions=suggestions)


async def llm_critic(draft: str, prompt: str, tone: str = "", content_type: str = "") -> CriticScore:
    if not has_gemini_key():
        return keyword_critic(draft, 0)
    try:
        llm = ChatGoogleGenerativeAI(model=settings.gemini_model, max_retries=2)
        structured = llm.with_structured_output(CriticScore)
        ctx = f"Original brief: {prompt}\nTone: {tone or 'default'}\nContent type: {content_type or 'general'}\n\nDraft to score:\n{draft[:4000]}"
        prompt_msg = (
                "You are a senior editor. Score the draft 1-10 where 8+ is publishable.\n"
                "Be strict: only 8+ if draft is clear, engaging, accurate to brief, and well-structured.\n"
                "Return score, one-sentence feedback, and 1-3 suggestions.\n\n" + ctx
        )
        result: CriticScore = await structured.ainvoke(prompt_msg)
        result.score = max(1, min(10, int(result.score)))
        return result
    except Exception as e:
        print(f"LLM critic failed: {e}")
        return keyword_critic(draft, 0)
