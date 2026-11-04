"""
Static-only code execution service and sandboxed extension factory.

Enforces system security policy:
- Does NOT execute untrusted student code or notebooks directly inside the FastAPI server.
- Prioritizes static code inspection, notebook structure, and verified saved outputs.
- Acts as a clean plug-in point for future Docker/microVM isolated execution workers.
"""

import logging
from pathlib import Path
from typing import Any

from app.services.code_execution.base import BaseCodeExecutionService, CodeExecutionResult

logger = logging.getLogger(__name__)


class StaticOnlyExecutionService(BaseCodeExecutionService):
    """
    Default safe execution service.
    Rejects server-side untrusted execution to protect the application server.
    """

    async def execute_code(
        self,
        code: str,
        language: str = "python",
        timeout_seconds: int = 15,
    ) -> CodeExecutionResult:
        logger.info("Server-side execution skipped: static inspection mode active.")
        return CodeExecutionResult(
            status="SKIPPED_STATIC_ONLY",
            is_sandboxed=False,
            message="Server-side untrusted code execution is disabled for security. Evaluation relies on static syntax inspection and student-submitted verified outputs.",
        )

    async def execute_notebook(
        self,
        notebook_path: Path,
        timeout_seconds: int = 30,
    ) -> CodeExecutionResult:
        logger.info("Notebook server-side re-execution skipped: inspecting saved outputs.")
        return CodeExecutionResult(
            status="SKIPPED_STATIC_ONLY",
            is_sandboxed=False,
            message="Notebook cell re-execution is skipped inside application server. Parser extracts and evaluates saved outputs and cell execution counts.",
        )

    async def run_tests(
        self,
        project_dir: Path,
        test_command: str = "pytest",
        timeout_seconds: int = 30,
    ) -> CodeExecutionResult:
        logger.info("Project tests server-side execution skipped.")
        return CodeExecutionResult(
            status="SKIPPED_STATIC_ONLY",
            is_sandboxed=False,
            message="Project tests execution skipped inside application server. Test files are analyzed statically for coverage and assertions.",
        )


_execution_service: BaseCodeExecutionService | None = None


def get_code_execution_service() -> BaseCodeExecutionService:
    """Dependency / accessor for the active code execution service."""
    global _execution_service
    if _execution_service is None:
        _execution_service = StaticOnlyExecutionService()
    return _execution_service
