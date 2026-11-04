"""
Base interface and dataclasses for code execution and testing.
Provides a clean extension point for isolated, sandboxed execution workers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CodeExecutionResult:
    status: str  # "SKIPPED_STATIC_ONLY", "SUCCESS", "TIMEOUT", "ERROR", "BLOCKED"
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    execution_time_seconds: float = 0.0
    is_sandboxed: bool = False
    message: str = ""
    test_results: dict[str, Any] = field(default_factory=dict)


class BaseCodeExecutionService(ABC):
    """Abstract interface for student code and notebook execution."""

    @abstractmethod
    async def execute_code(
        self,
        code: str,
        language: str = "python",
        timeout_seconds: int = 15,
    ) -> CodeExecutionResult:
        """Execute a snippet of code in an isolated environment."""
        pass

    @abstractmethod
    async def execute_notebook(
        self,
        notebook_path: Path,
        timeout_seconds: int = 30,
    ) -> CodeExecutionResult:
        """Execute a Jupyter notebook end-to-end and capture new cell outputs."""
        pass

    @abstractmethod
    async def run_tests(
        self,
        project_dir: Path,
        test_command: str = "pytest",
        timeout_seconds: int = 30,
    ) -> CodeExecutionResult:
        """Run project tests in an isolated sandbox."""
        pass
