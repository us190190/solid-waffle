"""Tools: PythonREPL + FileSystem (sandboxed). File: app/agents/tools.py:1"""
import ast
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Dict

from langchain_core.tools import tool as lc_tool

from app.core.config import DATA_DIR


def _workspace(job_id: str) -> Path:
    ws = DATA_DIR / "workspace" / job_id
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def _safe_path(job_id: str, file_path: str) -> Path:
    ws = _workspace(job_id)
    # prevent traversal
    target = (ws / file_path).resolve()
    ws_resolved = ws.resolve()
    if not str(target).startswith(str(ws_resolved)):
        raise ValueError("path traversal not allowed")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def write_file(job_id: str, file_path: str, content: str) -> Dict:
    """Write file to sandboxed workspace."""
    try:
        fp = _safe_path(job_id, file_path)
        fp.write_text(content, encoding="utf-8")
        return {"file": file_path, "status": "written", "size": len(content)}
    except Exception as e:
        return {"file": file_path, "status": "error", "error": str(e)}


def read_file(job_id: str, file_path: str) -> Dict:
    try:
        fp = _safe_path(job_id, file_path)
        if not fp.exists():
            return {"file": file_path, "status": "not_found"}
        return {"file": file_path, "content": fp.read_text(encoding="utf-8")}
    except Exception as e:
        return {"file": file_path, "status": "error", "error": str(e)}


def list_files(job_id: str) -> Dict:
    try:
        ws = _workspace(job_id)
        files = []
        for p in ws.rglob("*"):
            if p.is_file():
                files.append(str(p.relative_to(ws)))
        return {"files": files, "count": len(files)}
    except Exception as e:
        return {"files": [], "error": str(e)}


def python_repl(code: str, job_id: str = "default", language: str = "python", timeout: int = 5) -> Dict:
    """Execute code in sandbox. Works in mock mode too (no API key). Supports multi-language stub."""
    lang = (language or "python").lower()
    # For non-python languages, run stub validation
    if lang in ("javascript", "js", "typescript", "ts"):
        # minimal JS lint: check balanced braces
        try:
            # try node --check if available, else heuristic
            tmp = _safe_path(job_id, f"_tmp.{'js' if lang in ('js', 'javascript') else 'ts'}")
            tmp.write_text(code, encoding="utf-8")
            try:
                result = subprocess.run(["node", "--check", str(tmp)], capture_output=True, text=True, timeout=timeout)
                if result.returncode == 0:
                    return {"language": lang, "status": "ok", "output": "JS syntax OK (node --check)", "error": ""}
                return {"language": lang, "status": "error", "output": result.stderr[:1000] or result.stdout[:1000],
                        "error": result.stderr[:1000]}
            except FileNotFoundError:
                # node not available, heuristic
                if code.count("{") != code.count("}"):
                    return {"language": lang, "status": "error", "output": "unbalanced braces",
                            "error": "unbalanced braces"}
                return {"language": lang, "status": "ok", "output": "heuristic JS OK", "error": ""}
        except Exception as e:
            return {"language": lang, "status": "error", "output": str(e), "error": str(e)}
    if lang not in ("python", "py"):
        # generic language: heuristic length check
        if len(code.strip()) < 10:
            return {"language": lang, "status": "error", "output": "code too short", "error": "code too short"}
        return {"language": lang, "status": "ok", "output": f"mock exec for {lang}: {len(code)} chars", "error": ""}

    # Python execution with timeout and capture
    # First syntax check via ast
    try:
        ast.parse(code)
    except SyntaxError as se:
        return {"language": "python", "status": "error", "output": f"SyntaxError: {se}",
                "error": f"SyntaxError: {se.msg} line {se.lineno}"}

    # Execute in subprocess for safety
    tmp = _safe_path(job_id, "_repl_exec.py")
    try:
        tmp.write_text(code, encoding="utf-8")
        result = subprocess.run([sys.executable, str(tmp)], capture_output=True, text=True, timeout=timeout,
                                cwd=str(_workspace(job_id)))
        output = (result.stdout or "")[:4000]
        error = (result.stderr or "")[:4000]
        status = "ok" if result.returncode == 0 else "error"
        return {"language": "python", "status": status, "output": output or ("executed" if status == "ok" else ""),
                "error": error}
    except subprocess.TimeoutExpired:
        return {"language": "python", "status": "error", "output": "timeout", "error": "execution timed out"}
    except Exception as e:
        return {"language": "python", "status": "error", "output": traceback.format_exc()[:2000], "error": str(e)}


@lc_tool
def python_repl_tool(code: str) -> str:
    """Execute python code and return output."""
    r = python_repl(code)
    return r.get("output", "") + ("\nERROR: " + r["error"] if r.get("error") else "")


@lc_tool
def write_file_tool(file_path: str, content: str) -> str:
    """Write content to file."""
    return str(write_file("default", file_path, content))
