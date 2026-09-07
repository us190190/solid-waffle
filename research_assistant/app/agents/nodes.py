"""LangGraph nodes: Search -> Summarize -> Cite. File: app/agents/nodes.py:1"""
from typing import Dict

from ddgs import DDGS
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings, has_gemini_key

# --- Search Node: DuckDuckGo ---
FALLBACK_DOCS = [
    {"title": "LangGraph Documentation", "url": "https://langchain-ai.github.io/langgraph/",
     "content": "LangGraph is a library for building stateful, multi-actor LLM applications. It models agent workflows as graphs with nodes and edges, supports cycles, branching, persistence via checkpointers, and human-in-the-loop. Built on LangChain."},
    {"title": "LangChain vs LangGraph", "url": "https://python.langchain.com/docs/langgraph",
     "content": "LangChain provides chains and agents for single-turn tasks. LangGraph extends this with graph-based orchestration, allowing complex multi-agent collaboration, loops for reflection/critique, and memory. Ideal for research, coding teams, and long-running workflows."},
    {"title": "FastAPI Documentation", "url": "https://fastapi.tiangolo.com/",
     "content": "FastAPI is a modern Python web framework for building APIs with automatic OpenAPI docs, async support, and Pydantic validation. Pairs well with LangGraph for streaming (SSE/WebSocket) and background task execution."},
]


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
                txt = getattr(block, "text", None)
                if isinstance(txt, str):
                    parts.append(txt)
                elif isinstance(getattr(block, "content", None), str):
                    parts.append(getattr(block, "content"))
        joined = "\n\n".join(p for p in parts if p)
        return joined if joined else str(content)
    return str(content)


def _ddg_search(query: str, max_results: int):
    """Try DDGS (new name) then duckduckgo_search (old name). Returns list or []."""
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        print(f"DuckDuckGo results exception: {e}")
        return []


def search_node(state: Dict) -> Dict:
    """Uses DDGS().text() to fetch documents. No API key required. Falls back to curated docs if offline."""
    query = state.get("query", "").strip()
    if not query:
        return {"documents": [{"title": "No query", "url": "", "content": "Empty query provided."}]}
    try:
        results = _ddg_search(query, settings.max_search_results)
        documents = []
        for r in results:
            documents.append({
                "title": r.get("title", "")[:200],
                "url": r.get("href", "") or r.get("url", ""),
                "content": r.get("body", "")[:1500],
            })
        if not documents:
            # Network blocked or no results -> use curated fallback filtered by query keywords
            ql = query.lower()
            if "langgraph" in ql or "langchain" in ql:
                documents = FALLBACK_DOCS[:2]
            elif "fastapi" in ql:
                documents = [FALLBACK_DOCS[2], FALLBACK_DOCS[0]]
            else:
                # generic fallback + echo query
                documents = [
                                {"title": f"Fallback result for: {query}",
                                 "url": "https://duckduckgo.com/?q=" + query.replace(" ", "+"),
                                 "content": f"No live DuckDuckGo results (offline/blocked). Query: '{query}'. Using curated knowledge: LangGraph enables multi-agent graphs, FastAPI serves the workflow."},
                            ] + FALLBACK_DOCS[:2]
        return {"documents": documents}
    except Exception as e:
        return {"documents": [
            {"title": "DuckDuckGo error - fallback", "url": "https://duckduckgo.com",
             "content": f"Search failed: {str(e)[:500]}. Query was: {query}."},
            FALLBACK_DOCS[0],
            FALLBACK_DOCS[1],
        ]}


# --- Summarizer Node: Gemini Flash ---
async def summarizer_node(state: Dict) -> Dict:
    query = state.get("query", "")
    documents = state.get("documents", [])
    docs_text = "\n\n".join(
        [f"[{i + 1}] {d.get('title')} ({d.get('url')}): {d.get('content')}" for i, d in enumerate(documents)])

    if not has_gemini_key():
        # Mock mode: no API key -> deterministic summary without LLM call (demo still works)
        bullets = "\n".join([f"- {d.get('title')}: {d.get('content')[:120]}..." for d in documents[:3]])
        mock_summary = f"**Mock summary (no GOOGLE_API_KEY set)**\nQuery: {query}\n\nKey points:\n{bullets}\n\n(Set GOOGLE_API_KEY in .env to enable Gemini Flash summarization.)"
        return {"summary": mock_summary}

    try:
        llm = ChatGoogleGenerativeAI(model=settings.gemini_model, max_retries=2)
        system = SystemMessage(
            content="You are a concise research summarizer. Synthesize documents into 3-5 bullet points answering the query. Be factual, no hallucination, cite implicitly by preserving facts.")
        human = HumanMessage(
            content=f"Query: {query}\n\nDocuments:\n{docs_text}\n\nProvide 3-5 bullet summary in markdown.")
        resp = await llm.ainvoke([system, human])
        summary = _extract_llm_text(resp.content)
        return {"summary": summary}
    except Exception as e:
        return {"summary": f"**Summarization failed** (Gemini error: {str(e)[:400]}). Fallback summary:\n" + "\n".join(
            [f"- {d.get('content')[:150]}" for d in documents[:3]])}


# --- Citation Node: Gemini Flash ---
async def citation_node(state: Dict) -> Dict:
    query = state.get("query", "")
    summary = state.get("summary", "")
    documents = state.get("documents", [])

    citations = [{"index": i + 1, "title": d.get("title", ""), "url": d.get("url", "")} for i, d in
                 enumerate(documents)]

    if not has_gemini_key():
        # Mock final answer with inline citations
        cite_marks = " ".join([f"[{c['index']}]" for c in citations[:2]])
        mock_answer = f"### Answer (Mock - set GOOGLE_API_KEY for real Gemini Flash)\n\n**Query:** {query}\n\n{summary}\n\n**Sources:** {cite_marks}\n\n" + "\n".join(
            [f"[{c['index']}] {c['title']} - {c['url']}" for c in citations])
        return {"citations": citations, "final_answer": mock_answer}

    try:
        llm = ChatGoogleGenerativeAI(model=settings.gemini_model, max_retries=2)
        docs_context = "\n".join(
            [f"[{i + 1}] {d['title']} | {d['url']} | {d['content'][:600]}" for i, d in enumerate(documents)])
        system = SystemMessage(
            content="You are a research reporter. Produce final markdown answer with inline citations [1][2] matching the provided documents. Every claim should be traceable. End with a References section listing [n] Title - URL.")
        human = HumanMessage(
            content=f"Query: {query}\n\nSummary:\n{summary}\n\nDocuments:\n{docs_context}\n\nWrite final answer (200-350 words) with inline citations like [1] [2]. Then add '### References' with numbered list.")
        resp = await llm.ainvoke([system, human])
        final = _extract_llm_text(resp.content)
        return {"citations": citations, "final_answer": final}
    except Exception as e:
        fallback = f"### Answer (fallback due to Gemini error: {str(e)[:300]})\n\n{summary}\n\n### References\n" + "\n".join(
            [f"[{c['index']}] {c['title']} - {c['url']}" for c in citations])
        return {"citations": citations, "final_answer": fallback}
