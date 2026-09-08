"""LangGraph nodes: Supervisor -> Specialists -> Responder -> HumanHandoff. File: app/agents/nodes.py:1"""
import re
from typing import Dict

from app.agents.classifiers import llm_classify
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core import mock_db
from app.core.config import has_gemini_key, settings
from app.models.state import SupportState


async def supervisor_node(state: SupportState) -> Dict:
    user_input = state.get("user_input", "")
    messages = state.get("messages", [])
    history = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages] if messages else []
    result = await llm_classify(user_input, history)
    return {
        "intent": result.intent,
        "sentiment": result.sentiment,
        "confidence": result.confidence,
        "escalated": result.sentiment == "negative" and result.confidence >= 0.7,
        "messages": [{"role": "user", "content": user_input}],
    }


def _extract_invoice_id(text: str) -> str | None:
    m = re.search(r"INV-\d+", text.upper())
    return m.group(0) if m else None


def _extract_ticket_id(text: str) -> str | None:
    m = re.search(r"TICK-\d+", text.upper())
    return m.group(0) if m else None


def _extract_sku(text: str) -> str | None:
    m = re.search(r"PROD-[A-Z]+", text.upper())
    return m.group(0) if m else None


def _extract_llm_text(content) -> str:
    """Normalize LLM response content to plain text.

    Gemini via langchain-google-genai can return:
      - str
      - list[str]
      - list[dict] like [{"type": "text", "text": "...", "extras": {"signature": "..."}}]
    The previous code did `str(content)` for non-str, which leaked the
    JSON/signature structure to the client. This extracts only the `text` values.
    """
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
                # Handle objects like langchain TextContent with .text attribute
                txt = getattr(block, "text", None)
                if isinstance(txt, str):
                    parts.append(txt)
                elif isinstance(getattr(block, "content", None), str):
                    parts.append(getattr(block, "content"))
                elif isinstance(block, dict) and isinstance(block.get("text"), str):
                    parts.append(block["text"])
        joined = "\n\n".join(p for p in parts if p)
        return joined if joined else str(content)
    return str(content)


# Specialist nodes use mock DB/API tools

def billing_node(state: SupportState) -> Dict:
    user_input = state.get("user_input", "")
    outputs = []
    invoice_id = _extract_invoice_id(user_input)
    if invoice_id:
        res = mock_db.lookup_invoice(invoice_id)
        outputs.append({"tool": "lookup_invoice", "input": invoice_id, "output": res})
        refund = mock_db.check_refund_status(invoice_id)
        outputs.append({"tool": "check_refund_status", "input": invoice_id, "output": refund})
    else:
        # try default invoice
        # demonstrate tool call even without id
        sample = mock_db.lookup_invoice("INV-002")
        outputs.append({"tool": "lookup_invoice", "input": "INV-002 (default demo)", "output": sample})

    summary = f"Billing specialist checked {len(outputs)} tool(s) for query: '{user_input[:120]}'"
    return {"tool_outputs": outputs, "messages": [{"role": "assistant", "content": summary}]}


def technical_node(state: SupportState) -> Dict:
    user_input = state.get("user_input", "")
    outputs = []
    ticket_id = _extract_ticket_id(user_input)
    if ticket_id:
        res = mock_db.lookup_ticket(ticket_id)
        outputs.append({"tool": "lookup_ticket", "input": ticket_id, "output": res})
    else:
        status = mock_db.check_system_status("api")
        outputs.append({"tool": "check_system_status", "input": "api", "output": status})
        if "down" in user_input.lower() or "dashboard" in user_input.lower():
            dash = mock_db.check_system_status("dashboard")
            outputs.append({"tool": "check_system_status", "input": "dashboard", "output": dash})

    summary = f"Technical specialist checked {len(outputs)} tool(s) for query: '{user_input[:120]}'"
    return {"tool_outputs": outputs, "messages": [{"role": "assistant", "content": summary}]}


def sales_node(state: SupportState) -> Dict:
    user_input = state.get("user_input", "")
    outputs = []
    sku = _extract_sku(user_input)
    if sku:
        pricing = mock_db.lookup_pricing(sku)
        outputs.append({"tool": "lookup_pricing", "input": sku, "output": pricing})
        inv = mock_db.check_inventory(sku)
        outputs.append({"tool": "check_inventory", "input": sku, "output": inv})
    else:
        # default product check + lead creation demo
        pricing = mock_db.lookup_pricing("PROD-A")
        outputs.append({"tool": "lookup_pricing", "input": "PROD-A (default)", "output": pricing})
        if "demo" in user_input.lower() or "lead" in user_input.lower() or "contact" in user_input.lower():
            # extract email if present
            m = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", user_input)
            email = m.group(0) if m else "demo@example.com"
            lead = mock_db.create_lead(email, user_input[:80])
            outputs.append({"tool": "create_lead", "input": email, "output": lead})

    summary = f"Sales specialist checked {len(outputs)} tool(s) for query: '{user_input[:120]}'"
    return {"tool_outputs": outputs, "messages": [{"role": "assistant", "content": summary}]}


async def responder_node(state: SupportState) -> Dict:
    intent = state.get("intent", "technical")
    sentiment = state.get("sentiment", "neutral")
    tool_outputs = state.get("tool_outputs", [])
    user_input = state.get("user_input", "")

    # Build deterministic responder; use LLM if key present
    tool_summary = "\n".join([f"- {t['tool']}({t['input']}): {str(t['output'])[:300]}" for t in tool_outputs[-4:]])

    if not has_gemini_key():
        # Mock responder
        if intent == "billing":
            body = f"**Billing Support**\n\nFor your query: \"{user_input}\"\n\nI checked your invoice details:\n{tool_summary}\n\nNext steps: If you need a refund for an overdue invoice, reply with the invoice ID. For payment updates, provide customer ID."
        elif intent == "technical":
            body = f"**Technical Support**\n\nFor your query: \"{user_input}\"\n\nSystem check results:\n{tool_summary}\n\nWe have logged your issue. If this is urgent, mention 'escalate' to reach a human."
        else:
            body = f"**Sales Support**\n\nFor your query: \"{user_input}\"\n\nProduct info:\n{tool_summary}\n\nWant a demo? Share your email and we'll create a lead. Current inventory shown above."

        if sentiment == "negative":
            body += "\n\n> I sense frustration — I can escalate you to a human agent if you'd like."

        return {"final_response": body, "messages": [{"role": "assistant", "content": body}]}

    try:
        llm = ChatGoogleGenerativeAI(model=settings.gemini_model, max_retries=2)
        system = SystemMessage(
            content=f"You are a {intent} support specialist. Be concise, helpful, use tool outputs as facts. Sentiment is {sentiment}. If sentiment negative, offer human escalation. End with next-step question.")
        human = HumanMessage(
            content=f"User: {user_input}\n\nTool outputs:\n{tool_summary}\n\nWrite final markdown response (150-250 words).")
        resp = await llm.ainvoke([system, human])
        text = _extract_llm_text(resp.content)
        return {"final_response": text, "messages": [{"role": "assistant", "content": text}]}
    except Exception as e:
        fallback = f"**{intent.title()} Support (fallback)**\n\nTool outputs:\n{tool_summary}\n\nError: {str(e)[:300]}"
        return {"final_response": fallback, "messages": [{"role": "assistant", "content": fallback}]}


def human_handoff_node(state: SupportState) -> Dict:
    intent = state.get("intent", "unknown")
    user_input = state.get("user_input", "")
    msg = (
        f"**Human Handoff Triggered**\n\n"
        f"Your request has been escalated to a human agent.\n\n"
        f"- Intent: `{intent}`\n"
        f"- Sentiment: `negative` (frustration detected)\n"
        f"- Original message: \"{user_input}\"\n\n"
        f"A human will review within 2 minutes. Meanwhile, your tool outputs and classification are preserved in the thread state.\n\n"
        f"*(This node used `interrupt_before` - the graph paused before executing this node until resumed.)*"
    )
    return {"final_response": msg, "escalated": True, "messages": [{"role": "assistant", "content": msg}]}
