from __future__ import annotations

from pathlib import Path

from locus_md.config import load_config
from locus_md.engine import Engine
from conftest import write_minimal_workspace


def test_broken_link_and_orphan_are_detected(tmp_path: Path) -> None:
    path = write_minimal_workspace(tmp_path)
    (tmp_path / "docs" / "index.md").write_text("# Index\n\n[Known](known.md)\n[Missing](missing.md)\n", encoding="utf-8")
    (tmp_path / "docs" / "known.md").write_text("# Known\n", encoding="utf-8")
    (tmp_path / "docs" / "orphan.md").write_text("# Orphan\n", encoding="utf-8")
    report = Engine(load_config(explicit=path)).lint()
    codes = {finding.code for finding in report.findings}
    assert "DOC-LINK-001" in codes
    assert "DOC-LINK-020" in codes


def test_reference_style_links_participate_in_graph(tmp_path: Path) -> None:
    path = write_minimal_workspace(tmp_path)
    (tmp_path / "docs" / "index.md").write_text("# Index\n\n[Child][child]\n\n[child]: child.md\n", encoding="utf-8")
    (tmp_path / "docs" / "child.md").write_text("# Child\n", encoding="utf-8")
    report = Engine(load_config(explicit=path)).lint()
    assert not any(finding.code == "DOC-LINK-020" for finding in report.findings)
