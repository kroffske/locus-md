from __future__ import annotations

import json
from pathlib import Path

from locus_md.config import load_config
from locus_md.engine import Engine
from locus_md.models import RunState


def test_explicit_and_inherited_providers_validate_in_one_document(tmp_path: Path) -> None:
    (tmp_path / ".locus").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "docs" / "index.md").write_text("# Index\n\n[Plan](plan.md)\n", encoding="utf-8")
    (tmp_path / "docs" / "plan.md").write_text(
        """# Plan

## Local

<!-- locus:milestone local begin -->
| Task | Title | Status |
|---|---|---|
| L-1 | Local work | done |
<!-- locus:milestone local end -->

## Linear projection

<!-- locus:milestone linear begin -->
| Task | Title | Status |
|---|---|---|
| LIN-1 | Remote work | doing |
<!-- locus:milestone linear end -->
""",
        encoding="utf-8",
    )
    local = {
        "schema": "locus-md.entities.v1",
        "records": [
            {"kind": "task", "id": "L-1", "revision": "1", "fields": {"title": "Local work", "status": "done", "milestone": "local"}, "url": None}
        ],
    }
    linear = {
        "schema": "locus-md.entities.v1",
        "records": [
            {"kind": "task", "id": "LIN-1", "revision": "1", "fields": {"title": "Remote work", "status": "doing", "milestone": "remote"}, "url": None}
        ],
    }
    (tmp_path / "data" / "local.json").write_text(json.dumps(local), encoding="utf-8")
    (tmp_path / "data" / "linear.json").write_text(json.dumps(linear), encoding="utf-8")
    (tmp_path / ".locus" / "locus.md.toml").write_text(
        """[locus.md]
schema = 1
surfaces = ["docs"]
strict = false

[locus.md.surface.docs]
root = "docs"
include = ["**/*.md"]
index = ["index.md"]
require_reachable = true
default_provider = "linear-tasks"
[locus.md.provider.local-tasks]
adapter = "file-json"
path = "data/local.json"
[locus.md.provider.linear-tasks]
adapter = "file-json"
path = "data/linear.json"
[locus.md.contract.local]
surface = "docs"
path = "plan.md"
block_kind = "milestone"
block_id = "local"
schema = "task-table.v1"
mode = "projection"
provider = "local-tasks"
selector = { milestone = "local" }
renderer = "task-table.v1"
[locus.md.contract.linear]
surface = "docs"
path = "plan.md"
block_kind = "milestone"
block_id = "linear"
schema = "task-table.v1"
mode = "projection"
provider = "inherit"
selector = { milestone = "remote" }
renderer = "task-table.v1"
""",
        encoding="utf-8",
    )
    report = Engine(load_config(explicit=tmp_path / ".locus" / "locus.md.toml")).verify(offline=True)
    assert report.state == RunState.PASSED
    override = [finding for finding in report.findings if finding.code == "DOC-BLOCK-030"]
    assert len(override) == 1
    assert override[0].contract_id == "local"
    assert set(report.snapshots) == {"local-tasks", "linear-tasks"}
