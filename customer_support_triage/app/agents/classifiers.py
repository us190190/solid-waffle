"""Intent + sentiment classifier with structured output. File: app/agents/classifiers.py:1"""
from typing import Dict, List

from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings, has_gemini_key
from app.models.schemas import ClassificationResult

# Keyword fallback lists (used when no GOOGLE_API_KEY)
BILLING_KW = ["invoice", "charge", "charged", "refund", "payment", "billing", "pay", "overdue", "receipt"]
TECHNICAL_KW = ["error", "bug", "crash", "fail", "500", "login", "slow", "not working", "down", "issue", "ticket",
                "restart"]
SALES_KW = ["pricing", "price", "plan", "buy", "purchase", "demo", "enterprise", "quote", "discount", "subscribe"]
NEGATIVE_KW = ["angry", "furious", "terrible", "awful", "frustrated", "escalate", "human", "manager", "worst", "hate",
               "unacceptable"]
POSITIVE_KW = ["thanks", "thank you", "great", "awesome", "love", "happy", "excellent"]


def keyword_classify(user_input: str, history: List[Dict] | None = None) -> ClassificationResult:
    text = (user_input or "").lower()
    scores = {"billing": 0, "technical": 0, "sales": 0}
    for kw in BILLING_KW:
        if kw in text:
            scores["billing"] += 1
    for kw in TECHNICAL_KW:
        if kw in text:
            scores["technical"] += 1
    for kw in SALES_KW:
        if kw in text:
            scores["sales"] += 1
    # do NOT pollute intent with history to keep stateless/stateful consistent; history only used for LLM path

    intent = max(scores, key=lambda k: scores[k])
    if all(v == 0 for v in scores.values()):
        intent = "technical"  # default fallback
    total = sum(scores.values()) or 1
    confidence = max(0.55, min(0.95, 0.55 + (scores[intent] / total) * 0.4))

    neg = any(kw in text for kw in NEGATIVE_KW)
    pos = any(kw in text for kw in POSITIVE_KW)
    if neg:
        sentiment = "negative"
        confidence = max(confidence, 0.85)
    elif pos:
        sentiment = "positive"
    else:
        sentiment = "neutral"

    reasoning = f"keyword scores {scores}, matched text: '{user_input[:120]}'"
    return ClassificationResult(intent=intent, sentiment=sentiment, confidence=round(confidence, 2),
                                reasoning=reasoning)


async def llm_classify(user_input: str, history: List[Dict] | None = None) -> ClassificationResult:
    if not has_gemini_key():
        return keyword_classify(user_input, history)

    try:
        llm = ChatGoogleGenerativeAI(model=settings.gemini_model, max_retries=2)
        structured_llm = llm.with_structured_output(ClassificationResult)
        history_text = ""
        if history:
            history_text = "\n".join([f"{m.get('role')}: {m.get('content')}" for m in history[-5:]])
        prompt = f"""Classify customer support intent and sentiment.

Conversation history:
{history_text}

Latest user message: "{user_input}"

Rules:
- intent: billing (invoices, charges, refunds, payments) / technical (errors, bugs, outages, tickets) / sales (pricing, plans, demos, purchase)
- sentiment: positive / neutral / negative (negative if angry/frustrated/escalation)
- confidence 0-1
- reasoning: one sentence."""
        result: ClassificationResult = await structured_llm.ainvoke(prompt)
        # clamp confidence
        result.confidence = max(0.0, min(1.0, result.confidence))
        # Guard: if LLM says negative but user_input has no explicit NEGATIVE_KW nor strong escalation phrase, downgrade to neutral to avoid false escalation
        lowered = user_input.lower()
        has_negative_signal = any(kw in lowered for kw in NEGATIVE_KW)
        if result.sentiment == "negative" and not has_negative_signal:
            result.sentiment = "neutral"
            result.confidence = min(result.confidence, 0.65)
            result.reasoning += " [corrected: no explicit negative keyword, downgraded to neutral]"
        return result
    except Exception as e:
        # fallback on LLM error
        print(f"LLM classify failed: {e}")
        return keyword_classify(user_input, history)
