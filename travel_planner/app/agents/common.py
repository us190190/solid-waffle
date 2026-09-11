"""Shared helpers. File: app/agents/common.py:1"""
from app.core.config import has_gemini_key


def require_gemini_key():
    if not has_gemini_key():
        raise RuntimeError("GOOGLE_API_KEY is not configured. Set it in .env to use Travel Planner.")


def extract_llm_text(content) -> str:
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
