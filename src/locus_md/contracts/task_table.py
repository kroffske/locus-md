from __future__ import annotations

import re
from typing import Any

from ..models import ContractBinding, DocumentRecord, EntityRecord, Finding, ManagedBlock, ProviderQuery, ProviderSnapshot, Severity
from ..providers.common import matches_query

_SEPARATOR_RE = re.compile(r"^:?-{3,}:?$")


def _escape_cell(value: Any) -> str:
    text = " ".join(str(value).replace("\r", " ").replace("\n", " ").split())
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;")


def _select(binding: ContractBinding, snapshot: ProviderSnapshot) -> list[EntityRecord]:
    query = ProviderQuery(kind="task", selector=binding.selector)
    return sorted((record for record in snapshot.records if matches_query(record, query)), key=lambda item: item.entity_id)


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in stripped[1:-1]:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    cells.append("".join(current).strip())
    return cells


def _parse_authored_rows(body: str) -> dict[str, tuple[str, str]]:
    rows: dict[str, tuple[str, str]] = {}
    for line in body.splitlines():
        cells = _split_table_row(line)
        if len(cells) < 3 or cells[0].lower() == "task" or all(_SEPARATOR_RE.fullmatch(cell.replace(" ", "")) for cell in cells[:3]):
            continue
        rows[cells[0]] = (cells[1], cells[2])
    return rows


class TaskTableHandler:
    api_version = "1"
    schema_id = "task-table.v1"
    renderer_ids = frozenset({"task-table.v1"})
    required_capabilities = frozenset({"list"})

    def plan(self, binding: ContractBinding, document: DocumentRecord, block: ManagedBlock) -> list[ProviderQuery]:
        return [ProviderQuery(kind="task", selector=binding.selector, fields=("id", "title", "status", "milestone"))]

    def validate(self, binding: ContractBinding, document: DocumentRecord, block: ManagedBlock, snapshot: ProviderSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        display_path = document.relative_path
        records = _select(binding, snapshot)
        for record in records:
            for field in ("title", "status"):
                if field not in record.fields or record.fields[field] is None:
                    findings.append(Finding(code="CONTRACT-001", message=f"task {record.entity_id!r} has no required field {field!r}",
                                            severity=binding.severity, path=display_path, line=block.start_line, surface=document.surface,
                                            contract_id=binding.name))
        if binding.mode == "authored":
            rows = _parse_authored_rows(document.body(block))
            expected = {record.entity_id: (str(record.fields.get("title", "")), str(record.fields.get("status", ""))) for record in records}
            for entity_id, values in expected.items():
                if entity_id not in rows:
                    findings.append(Finding(code="CONTRACT-010", message=f"authored task table is missing task {entity_id}", severity=binding.severity,
                                            path=display_path, line=block.start_line, surface=document.surface, contract_id=binding.name))
                elif rows[entity_id] != values:
                    findings.append(
                        Finding(code="CONTRACT-011", message=f"authored task row {entity_id} differs from provider facts", severity=binding.severity,
                                path=display_path, line=block.start_line, surface=document.surface, contract_id=binding.name,
                                details={"document": rows[entity_id], "provider": values})
                    )
            for entity_id in sorted(set(rows) - set(expected)):
                findings.append(Finding(code="CONTRACT-012", message=f"authored task table contains unknown task {entity_id}", severity=binding.severity,
                                        path=display_path, line=block.start_line, surface=document.surface, contract_id=binding.name))
        return findings

    def render(self, binding: ContractBinding, snapshot: ProviderSnapshot, newline: str) -> str:
        if binding.renderer not in self.renderer_ids:
            raise ValueError(f"unsupported renderer {binding.renderer!r} for {self.schema_id}")
        lines = ["| Task | Title | Status |", "|---|---|---|"]
        for record in _select(binding, snapshot):
            task = _escape_cell(record.entity_id)
            title = _escape_cell(record.fields.get("title", ""))
            status = _escape_cell(record.fields.get("status", ""))
            lines.append(f"| {task} | {title} | {status} |")
        return newline.join(lines) + newline
