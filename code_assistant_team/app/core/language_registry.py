"""Language registry (OCP): extension mapping + file naming. File: app/core/language_registry.py:1"""
from typing import Dict

LANGUAGE_EXT: Dict[str, str] = {
    "python": "py",
    "py": "py",
    "javascript": "js",
    "js": "js",
    "typescript": "ts",
    "ts": "ts",
    "go": "go",
    "java": "java",
    "rust": "rs",
}


def get_file_extension(language: str) -> str:
    return LANGUAGE_EXT.get((language or "python").lower(), "py")


def get_code_file_name(task_id: str, language: str) -> str:
    ext = get_file_extension(language)
    tid = (task_id or "t1").lower()
    if (language or "python").lower() in ("python", "py"):
        return f"{tid}_main.py"
    return f"{tid}_{language.lower()}.{ext}"


def get_test_file_name(task_id: str, language: str) -> str:
    ext = get_file_extension(language)
    return f"{(task_id or 't1').lower()}_test.{ext}"


def get_docs_file_name(task_id: str) -> str:
    return f"{(task_id or 't1').lower()}_README.md"
