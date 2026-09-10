"""Light DIP ports (Protocols) for SOLID. File: app/core/ports.py:1"""
from typing import Dict, Protocol, runtime_checkable


@runtime_checkable
class FileSystemPort(Protocol):
    def write_file(self, job_id: str, file_path: str, content: str) -> Dict: ...

    def read_file(self, job_id: str, file_path: str) -> Dict: ...


@runtime_checkable
class ExecutorPort(Protocol):
    def execute(self, code: str, job_id: str, language: str) -> Dict: ...


@runtime_checkable
class LLMProvider(Protocol):
    async def ainvoke(self, messages) -> object: ...
