from __future__ import annotations

import json
from pathlib import Path

from locus_md.config import load_config
from locus_md.engine import Engine


def test_frontmatter_schema_is_applied_without_timestamp_coercion(example_workspace: Path) -> None:
    report = Engine(load_config(explicit=example_workspace / ".locus" / "locus-md.toml")).lint()
    assert not any(finding.code == "DOC-ENV-010" for finding in report.findings)


def test_external_json_schema_refs_are_rejected(tmp_path: Path) -> None:
    (tmp_path / ".locus").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "doc.json").write_text(json.dumps({"$schema": "https://json-schema.org/draft/2020-12/schema", "$ref": "https://example.invalid/schema.json"}), encoding="utf-8")
    (tmp_path / "docs" / "index.md").write_text("---\ntitle: Index\n---\n# Index\n", encoding="utf-8")
    (tmp_path / ".locus" / "locus-md.toml").write_text(
        """[locus-md]
schema = 1
surfaces = ["docs"]

[locus-md.surface.docs]
root = "docs"
include = ["**/*.md"]
index = ["index.md"]
frontmatter = "required"
frontmatter_schema = "schemas/doc.json"
""",
        encoding="utf-8",
    )
    report = Engine(load_config(explicit=tmp_path / ".locus" / "locus-md.toml")).lint()
    assert any(finding.code == "CFG-014" for finding in report.findings)
