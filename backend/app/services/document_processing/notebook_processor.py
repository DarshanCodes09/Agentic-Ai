"""
Jupyter Notebook (.ipynb) parser and execution evidence extractor.

Parses notebook structure, preserves ordered cells, extracts markdown explanations,
code cells, execution counts, and saved execution outputs (stdout, stderr, results,
images metadata, and runtime errors). Detects unexecuted, partial, or errored execution.
"""

from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class NotebookCell:
    index: int
    cell_type: str  # "code", "markdown", "raw"
    source: str
    execution_count: int | None = None
    outputs: list[dict[str, Any]] = field(default_factory=list)
    has_error: bool = False
    error_message: str | None = None
    is_executed: bool = False


@dataclass
class NotebookExecutionAudit:
    total_cells: int = 0
    markdown_cells: int = 0
    code_cells: int = 0
    executed_code_cells: int = 0
    unexecuted_code_cells: int = 0
    cells_with_errors: int = 0
    execution_status: str = "UNEXECUTED"  # "COMPLETE", "PARTIAL", "UNEXECUTED", "ERRORED"
    execution_order_anomaly: bool = False
    kernel_language: str = "python"
    kernel_name: str | None = None
    nbformat: int = 4


@dataclass
class ParsedNotebook:
    filename: str
    audit: NotebookExecutionAudit
    cells: list[NotebookCell]
    text_representation: str
    metadata: dict[str, Any] = field(default_factory=dict)
    is_valid: bool = True
    parse_error: str | None = None


class NotebookProcessor:
    """Parser and evidence extractor for Jupyter Notebooks."""

    def __init__(
        self,
        max_output_chars: int | None = None,
        max_cells: int | None = None,
    ) -> None:
        settings = get_settings()
        self.max_output_chars = max_output_chars or settings.max_notebook_cell_output_chars
        self.max_cells = max_cells or settings.max_notebook_cells

    def parse_file(self, file_path: str | Path, filename: str | None = None) -> ParsedNotebook:
        """Parse a notebook file on disk."""
        path = Path(file_path)
        name = filename or path.name
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            return self.parse_content(content, filename=name)
        except Exception as exc:
            logger.warning("Failed to read notebook file %s: %s", path, exc)
            return ParsedNotebook(
                filename=name,
                audit=NotebookExecutionAudit(),
                cells=[],
                text_representation=f"[ERROR: Malformed or unreadable notebook file: {exc}]",
                is_valid=False,
                parse_error=str(exc),
            )

    def parse_content(self, raw_content: str, filename: str = "notebook.ipynb") -> ParsedNotebook:
        """Parse raw JSON notebook content."""
        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            return ParsedNotebook(
                filename=filename,
                audit=NotebookExecutionAudit(),
                cells=[],
                text_representation=f"[ERROR: Malformed notebook - Invalid JSON syntax at line {exc.lineno}: {exc.msg}]",
                is_valid=False,
                parse_error=f"Invalid JSON: {exc.msg}",
            )

        if not isinstance(data, dict):
            return ParsedNotebook(
                filename=filename,
                audit=NotebookExecutionAudit(),
                cells=[],
                text_representation="[ERROR: Malformed notebook - Root must be a JSON object]",
                is_valid=False,
                parse_error="Root is not a JSON object",
            )

        nbformat = data.get("nbformat", 4)
        metadata = data.get("metadata", {})
        language_info = metadata.get("language_info", {})
        language = language_info.get("name") or metadata.get("kernelspec", {}).get("language", "python")
        kernel_name = metadata.get("kernelspec", {}).get("display_name") or metadata.get("kernelspec", {}).get("name")

        raw_cells = data.get("cells", [])
        if not isinstance(raw_cells, list):
            raw_cells = []

        parsed_cells: list[NotebookCell] = []
        code_cells_count = 0
        executed_cells_count = 0
        cells_with_errors = 0
        markdown_cells_count = 0
        execution_counts: list[int] = []

        for idx, cell in enumerate(raw_cells, start=1):
            if not isinstance(cell, dict):
                continue
            cell_type = str(cell.get("cell_type", "raw"))
            source_raw = cell.get("source", "")
            source = "".join(source_raw) if isinstance(source_raw, list) else str(source_raw)

            if cell_type == "markdown":
                markdown_cells_count += 1
                parsed_cells.append(
                    NotebookCell(
                        index=idx,
                        cell_type="markdown",
                        source=source,
                        is_executed=True,
                    )
                )
            elif cell_type == "code":
                code_cells_count += 1
                exec_count = cell.get("execution_count")
                if isinstance(exec_count, int):
                    execution_counts.append(exec_count)

                outputs = cell.get("outputs", [])
                extracted_outputs: list[dict[str, Any]] = []
                has_error = False
                error_msg: str | None = None

                if isinstance(outputs, list):
                    for out in outputs:
                        if not isinstance(out, dict):
                            continue
                        out_type = out.get("output_type", "")
                        if out_type == "stream":
                            text_raw = out.get("text", "")
                            text = "".join(text_raw) if isinstance(text_raw, list) else str(text_raw)
                            extracted_outputs.append({
                                "type": "stream",
                                "name": out.get("name", "stdout"),
                                "text": self._truncate_output(text),
                            })
                        elif out_type in ("execute_result", "display_data"):
                            data_dict = out.get("data", {})
                            text_val = ""
                            image_info = None
                            if isinstance(data_dict, dict):
                                if "text/plain" in data_dict:
                                    t = data_dict["text/plain"]
                                    text_val = "".join(t) if isinstance(t, list) else str(t)
                                for mime_key in data_dict.keys():
                                    if mime_key.startswith("image/"):
                                        img_bytes_len = len(str(data_dict[mime_key]))
                                        image_info = f"[Saved Figure/Plot: {mime_key}, ~{img_bytes_len} bytes]"
                                        break
                            extracted_outputs.append({
                                "type": out_type,
                                "text": self._truncate_output(text_val) if text_val else None,
                                "image_info": image_info,
                            })
                        elif out_type == "error":
                            has_error = True
                            cells_with_errors += 1
                            ename = out.get("ename", "Error")
                            evalue = out.get("evalue", "")
                            tb = out.get("traceback", [])
                            tb_text = "\n".join(tb) if isinstance(tb, list) else str(tb)
                            error_msg = f"{ename}: {evalue}"
                            extracted_outputs.append({
                                "type": "error",
                                "ename": ename,
                                "evalue": evalue,
                                "traceback": self._truncate_output(tb_text, max_len=1500),
                            })

                is_executed = (exec_count is not None) or (len(extracted_outputs) > 0)
                if is_executed:
                    executed_cells_count += 1

                parsed_cells.append(
                    NotebookCell(
                        index=idx,
                        cell_type="code",
                        source=source,
                        execution_count=exec_count if isinstance(exec_count, int) else None,
                        outputs=extracted_outputs,
                        has_error=has_error,
                        error_message=error_msg,
                        is_executed=is_executed,
                    )
                )
            else:
                parsed_cells.append(
                    NotebookCell(
                        index=idx,
                        cell_type=cell_type,
                        source=source,
                        is_executed=True,
                    )
                )

        unexecuted_code = code_cells_count - executed_cells_count
        order_anomaly = False
        if len(execution_counts) > 1:
            if execution_counts != sorted(execution_counts):
                order_anomaly = True

        if code_cells_count == 0:
            status = "COMPLETE" if markdown_cells_count > 0 else "UNEXECUTED"
        elif cells_with_errors > 0:
            status = "ERRORED"
        elif executed_cells_count == 0:
            status = "UNEXECUTED"
        elif unexecuted_code > 0:
            status = "PARTIAL"
        else:
            status = "COMPLETE"

        audit = NotebookExecutionAudit(
            total_cells=len(parsed_cells),
            markdown_cells=markdown_cells_count,
            code_cells=code_cells_count,
            executed_code_cells=executed_cells_count,
            unexecuted_code_cells=unexecuted_code,
            cells_with_errors=cells_with_errors,
            execution_status=status,
            execution_order_anomaly=order_anomaly,
            kernel_language=str(language),
            kernel_name=str(kernel_name) if kernel_name else None,
            nbformat=nbformat,
        )

        text_rep = self._render_text_representation(filename, audit, parsed_cells)

        return ParsedNotebook(
            filename=filename,
            audit=audit,
            cells=parsed_cells,
            text_representation=text_rep,
            metadata=metadata,
            is_valid=True,
        )

    def _truncate_output(self, text: str, max_len: int | None = None) -> str:
        limit = max_len or self.max_output_chars
        if len(text) > limit:
            return text[:limit] + f"\n... [Output truncated; {len(text) - limit} characters omitted] ..."
        return text

    def _render_text_representation(
        self, filename: str, audit: NotebookExecutionAudit, cells: list[NotebookCell]
    ) -> str:
        """Render a readable text evidence package for LLM and faculty review."""
        lines: list[str] = [
            f"=== JUPYTER NOTEBOOK: {filename} ===",
            f"Execution Audit: {audit.execution_status} | Code Cells: {audit.code_cells} total, "
            f"{audit.executed_code_cells} executed, {audit.unexecuted_code_cells} unexecuted | "
            f"Errors: {audit.cells_with_errors} | Language: {audit.kernel_language}",
        ]
        if audit.execution_order_anomaly:
            lines.append("Notice: Execution count order anomaly detected (cells executed non-sequentially).")
        if audit.unexecuted_code_cells > 0:
            lines.append(f"Notice: {audit.unexecuted_code_cells} code cell(s) contain code but lack saved execution outputs.")
        if audit.cells_with_errors > 0:
            lines.append(f"Warning: {audit.cells_with_errors} cell(s) threw execution runtime errors.")

        lines.append("\n--- NOTEBOOK CONTENT & SAVED EVIDENCE ---\n")

        selected_cells = cells
        if len(cells) > self.max_cells:
            priority_indices = set()
            for c in cells:
                if c.has_error:
                    priority_indices.add(c.index)
                elif c.cell_type == "markdown" and any(line.strip().startswith("#") for line in c.source.splitlines()):
                    priority_indices.add(c.index)
                elif c.cell_type == "code" and c.is_executed and c.outputs:
                    priority_indices.add(c.index)

            for c in cells[:8]:
                priority_indices.add(c.index)
            for c in cells[-8:]:
                priority_indices.add(c.index)

            if len(priority_indices) > self.max_cells:
                def cell_rank(c: NotebookCell) -> int:
                    if c.has_error:
                        return 0
                    if c.cell_type == "markdown" and "#" in c.source:
                        return 1
                    if c.outputs:
                        return 2
                    return 3
                sorted_by_rank = sorted([c for c in cells if c.index in priority_indices], key=cell_rank)
                final_indices = {c.index for c in sorted_by_rank[:self.max_cells]}
            else:
                final_indices = set(priority_indices)
                for c in cells:
                    if len(final_indices) >= self.max_cells:
                        break
                    final_indices.add(c.index)

            selected_cells = [c for c in cells if c.index in final_indices]
            omitted_count = len(cells) - len(selected_cells)
            lines.append(
                f"Notice: Notebook contains {len(cells)} cells. Displaying {len(selected_cells)} key cells "
                f"(prioritizing errors, headings, and execution results); {omitted_count} intermediate cells omitted to fit assessment limits."
            )

        for c in selected_cells:
            if c.cell_type == "markdown":
                lines.append(f"[Cell {c.index}: Markdown]")
                lines.append(c.source.strip())
                lines.append("")
            elif c.cell_type == "code":
                exec_tag = f"Execution #{c.execution_count}" if c.execution_count is not None else "NOT EXECUTED / NO COUNT"
                lines.append(f"[Cell {c.index}: Code ({exec_tag})]")
                lines.append(">>> CODE:")
                code_src = c.source if c.source.strip() else "(empty cell)"
                if len(code_src) > 4000:
                    code_src = code_src[:4000] + f"\n... [Cell source truncated; {len(code_src) - 4000} chars omitted] ..."
                lines.append(code_src)

                if c.outputs:
                    lines.append("<<< SAVED OUTPUTS:")
                    for out in c.outputs:
                        otype = out.get("type")
                        if otype == "stream":
                            stream_name = out.get("name", "stdout")
                            lines.append(f"  [{stream_name}]:")
                            lines.append(f"  {out.get('text', '').strip()}")
                        elif otype in ("execute_result", "display_data"):
                            if out.get("text"):
                                lines.append(f"  [result]: {out.get('text', '').strip()}")
                            if out.get("image_info"):
                                lines.append(f"  {out.get('image_info')}")
                        elif otype == "error":
                            lines.append(f"  [RUNTIME ERROR]: {out.get('ename')}: {out.get('evalue')}")
                            if out.get("traceback"):
                                lines.append(f"  Traceback snippet:\n  {out.get('traceback').strip()}")
                else:
                    lines.append("<<< (No saved execution output recorded for this cell)")
                lines.append("")

        return "\n".join(lines)


_notebook_processor: NotebookProcessor | None = None


def get_notebook_processor() -> NotebookProcessor:
    global _notebook_processor
    if _notebook_processor is None:
        _notebook_processor = NotebookProcessor()
    return _notebook_processor
