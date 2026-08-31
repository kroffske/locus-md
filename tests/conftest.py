from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def example_workspace(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[1] / "examples" / "basic"
    target = tmp_path / "workspace"
    shutil.copytree(source, target)
    return target


def write_minimal_workspace(root: Path, *, extra_ini: str = "") -> Path:
    (root / ".locus").mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "index.md").write_text("# Index\n", encoding="utf-8")
    config = """[locus-md]
schema = 1
surfaces = ["docs"]

[locus-md.surface.docs]
root = "docs"
include = ["**/*.md"]
index = ["index.md"]
frontmatter = "optional"
require_reachable = true
"""
    path = root / ".locus" / "locus-md.toml"
    path.write_text(config, encoding="utf-8")
    return path


def write_tasks(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema": "locus-md.entities.v1", "records": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
