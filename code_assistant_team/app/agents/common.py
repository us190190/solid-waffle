"""Shared helpers for agents (SRP). File: app/agents/common.py:1"""
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import has_gemini_key, settings


def get_llm():
    """Factory (DIP): returns LLM or None for mock mode."""
    if not has_gemini_key():
        return None
    return ChatGoogleGenerativeAI(model=settings.gemini_model, max_retries=2)


def _extract_llm_text(content: Any) -> str:
    """Normalize Gemini response to plain text (handles str|dict|list)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        for k in ("text", "content", "output"):
            v = content.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return str(content).strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                t = item.get("text") or item.get("content") or ""
                if isinstance(t, str) and t.strip():
                    parts.append(t.strip())
                elif isinstance(t, list):
                    for x in t:
                        if isinstance(x, dict) and x.get("text"):
                            parts.append(str(x["text"]))
            elif hasattr(item, "text"):
                try:
                    parts.append(str(item.text))
                except Exception:
                    pass
        return "\n".join([p for p in parts if p.strip()]).strip()
    return str(content).strip()


def _mock_code_content(task: dict, language: str, attempt: int = 1) -> str:
    lang = (language or task.get("language") or "python").lower()
    desc = task.get("description", "")[:200]
    if lang in ("python", "py"):
        if "api" in desc.lower() or "endpoint" in desc.lower():
            return f'''from fastapi import FastAPI
app = FastAPI()

@app.get("/hello")
def hello():
    """{desc}"""
    return {{"message": "hello world"}}

if __name__ == "__main__":
    print("hello world")
'''
        return f'''# {desc}
def main():
    """{desc}"""
    print("feature implemented: {desc[:60]}")

if __name__ == "__main__":
    main()
'''
    elif lang in ("javascript", "js"):
        return f'''// {desc}
function main() {{
  console.log("feature: {desc[:60]}");
}}
main();
'''
    elif lang in ("typescript", "ts"):
        return f'''// {desc} (TypeScript)
function main(): void {{
  console.log("feature: {desc[:60]}");
}}
main();
'''
    else:
        return f'''# {desc} ({lang})
# Feature: {desc[:80]}
print("hello from {lang}")
'''


def _mock_test_content(task: dict, language: str) -> str:
    lang = (language or "python").lower()
    desc = task.get("description", "")[:200]
    if lang in ("python", "py"):
        return f'''import pytest

def test_main():
    """{desc}"""
    assert True

def test_edge():
    """edge for {desc[:60]}"""
    assert 1 + 1 == 2
'''
    if lang in ("javascript", "js", "typescript", "ts"):
        return f'''// {desc}
test("main", () => {{ expect(true).toBe(true); }});
'''
    return f'''# test for {lang}: {desc[:80]}
assert True
'''


def _mock_docs_content(task: dict, language: str) -> str:
    return f"""# {task.get('description', 'Documentation')}

## Overview
{task.get('description', '')}

Language: {language}

## Usage
```{language}
# example
print("usage")
```

## Notes
Auto-generated docs for: {task.get('description', '')[:200]}
"""
