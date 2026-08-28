from __future__ import annotations

from pathlib import Path

from locus_md.contracts.task_table import TaskTableHandler
from locus_md.models import ContractBinding, EntityRecord, ProviderSnapshot, Severity


def test_task_table_renderer_is_sorted_and_escaped() -> None:
    snapshot = ProviderSnapshot(
        provider="tasks",
        adapter="test",
        adapter_version="1",
        revision="r1",
        consistency="local",
        captured_at="2026-01-01T00:00:00Z",
        records=(
            EntityRecord(kind="task", entity_id="T-2", revision=None, fields={"title": "B | C", "status": "doing"}),
            EntityRecord(kind="task", entity_id="T-1", revision=None, fields={"title": "A\nline", "status": "done"}),
        ),
        content_digest="sha256:test",
    )
    binding = ContractBinding(
        name="x", surface="docs", path="a.md", block_kind="milestone", block_id="tasks", schema="task-table.v1", mode="projection",
        provider="tasks", selector={}, renderer="task-table.v1", severity=Severity.ERROR,
    )
    rendered = TaskTableHandler().render(binding, snapshot, "\n")
    assert rendered.index("T-1") < rendered.index("T-2")
    assert "B \\| C" in rendered
    assert "A line" in rendered
