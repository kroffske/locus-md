from __future__ import annotations

import subprocess
import json
from importlib.resources import files
from pathlib import Path

import pytest
from jsonschema import validate

from locus_md.cli import main
from locus_md.config import load_config
from locus_md.engine import Engine
from locus_md.errors import GitError
from locus_md.impact import build_impact


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def test_impact_reports_changed_document_and_current_inbound_dependents(tmp_path: Path) -> None:
    (tmp_path / ".locus").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text("---\ndescription: index\n---\n# Index\n[Guide](guide.md)\n", encoding="utf-8")
    (tmp_path / "docs" / "guide.md").write_text("---\ndescription: guide\n---\n# Guide\n", encoding="utf-8")
    (tmp_path / ".locus" / "locus-md.toml").write_text('''[locus-md]
schema = 1
surfaces = ["docs"]

[locus-md.surface.docs]
root = "docs"
include = ["**/*.md"]

[locus-md.document.index]
surface = "docs"
path = "index.md"
description = "Index"

[locus-md.document.guide]
surface = "docs"
path = "guide.md"
description = "Guide"
''', encoding="utf-8")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "base")
    guide = tmp_path / "docs" / "guide.md"
    guide.write_text(guide.read_text(encoding="utf-8") + "Changed.\n", encoding="utf-8")
    config = load_config(explicit=tmp_path / ".locus" / "locus-md.toml")
    scan = Engine(config).scan()
    report = build_impact(config, "HEAD", scan.documents.values())
    row = next(change for change in report.changes if change.path == "docs/guide.md")
    assert row.status == "changed"
    assert row.managed is True
    assert row.dependents == ("docs/index.md",)
    assert report.configuration_changed is False


def _seed_repo(root: Path, *, init_git: bool = True) -> Path:
    (root / ".locus").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "docs" / "index.md").write_text("---\ndescription: index\n---\n# Index\n[Guide](guide.md)\n", encoding="utf-8")
    (root / "docs" / "guide.md").write_text("---\ndescription: guide\n---\n# Guide\n", encoding="utf-8")
    (root / ".locus" / "locus-md.toml").write_text('''[locus-md]
schema = 1
surfaces = ["docs"]

[locus-md.surface.docs]
root = "docs"
include = ["**/*.md"]

[locus-md.document.index]
surface = "docs"
path = "index.md"
description = "Index"

[locus-md.document.guide]
surface = "docs"
path = "guide.md"
description = "Guide"
''', encoding="utf-8")
    if init_git:
        _git(root, "init", "-q")
        _git(root, "add", ".")
        _git(root, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "base")
    return root / ".locus" / "locus-md.toml"


def test_impact_reports_deleted_target_and_keeps_workspace_unchanged(tmp_path: Path) -> None:
    config_path = _seed_repo(tmp_path)
    guide = tmp_path / "docs" / "guide.md"
    guide.unlink()
    before_config = config_path.read_bytes()
    config = load_config(explicit=config_path)
    scan = Engine(config).scan()
    report = build_impact(config, "HEAD", scan.documents.values())
    row = next(change for change in report.changes if change.path == "docs/guide.md")
    assert row.status == "deleted"
    assert row.managed is True
    assert row.dependents == ("docs/index.md",)
    assert config_path.read_bytes() == before_config
    assert not (tmp_path / ".locus" / "docs.lock.json").exists()


def test_impact_reports_rename_old_and_new_paths(tmp_path: Path) -> None:
    config_path = _seed_repo(tmp_path)
    _git(tmp_path, "mv", "docs/guide.md", "docs/howto.md")
    config_path.write_text(config_path.read_text(encoding="utf-8").replace('path = "guide.md"', 'path = "howto.md"'), encoding="utf-8")
    config = load_config(explicit=config_path)
    report = build_impact(config, "HEAD", Engine(config).scan().documents.values())
    row = next(change for change in report.changes if change.status == "renamed")
    assert row.path == "docs/howto.md"
    assert row.old_path == "docs/guide.md"
    assert row.managed is True


def test_impact_reports_untracked_managed_addition(tmp_path: Path) -> None:
    config_path = _seed_repo(tmp_path)
    (tmp_path / "docs" / "new.md").write_text("---\ndescription: new\n---\n# New\n", encoding="utf-8")
    config = load_config(explicit=config_path)
    report = build_impact(config, "HEAD", Engine(config).scan().documents.values())
    row = next(change for change in report.changes if change.path == "docs/new.md")
    assert row.status == "added"
    assert row.managed is True


def test_impact_nested_workspace_uses_workspace_relative_coordinates(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    nested = tmp_path / "packages" / "docs"
    config_path = _seed_repo(nested, init_git=False)
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    _git(tmp_path, "add", "packages/docs")
    _git(tmp_path, "add", "outside.md")
    _git(tmp_path, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "nested-base")
    document = nested / "docs" / "guide.md"
    document.write_text(document.read_text(encoding="utf-8") + "Changed.\n", encoding="utf-8")
    outside.write_text("outside changed\n", encoding="utf-8")
    config = load_config(explicit=config_path)
    report = build_impact(config, "HEAD", Engine(config).scan().documents.values())
    row = next(change for change in report.changes if change.path == "docs/guide.md")
    assert row.path != "packages/docs/docs/guide.md"
    assert all("outside.md" not in change.path for change in report.changes)
    assert all(not change.old_path or "outside.md" not in change.old_path for change in report.changes)


def test_impact_cross_boundary_rename_outside_is_projected_as_deletion(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    nested = tmp_path / "packages" / "docs"
    config_path = _seed_repo(nested, init_git=False)
    _git(tmp_path, "add", "packages/docs")
    _git(tmp_path, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "nested-base")
    _git(tmp_path, "mv", "packages/docs/docs/guide.md", "outside-guide.md")

    config = load_config(explicit=config_path)
    report = build_impact(config, "HEAD", Engine(config).scan().documents.values())

    row = next(change for change in report.changes if change.path == "docs/guide.md")
    assert row.status == "deleted"
    assert row.old_path is None
    assert row.managed is True
    assert row.document == "guide"
    assert row.dependents == ("docs/index.md",)
    assert all("outside-guide.md" not in change.path for change in report.changes)


def test_impact_cross_boundary_rename_inside_is_projected_as_addition(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    nested = tmp_path / "packages" / "docs"
    config_path = _seed_repo(nested, init_git=False)
    outside = tmp_path / "outside-guide.md"
    outside.write_text("# Outside guide\n", encoding="utf-8")
    _git(tmp_path, "add", "packages/docs", "outside-guide.md")
    _git(tmp_path, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "nested-base")
    _git(tmp_path, "mv", "outside-guide.md", "packages/docs/docs/from-outside.md")

    config = load_config(explicit=config_path)
    report = build_impact(config, "HEAD", Engine(config).scan().documents.values())

    row = next(change for change in report.changes if change.path == "docs/from-outside.md")
    assert row.status == "added"
    assert row.old_path is None
    assert row.managed is True
    assert row.surface == "docs"
    assert row.document is None
    assert all("outside-guide.md" not in change.path for change in report.changes)


def test_impact_flags_canonical_configuration_change_and_invalid_base_is_typed(tmp_path: Path) -> None:
    config_path = _seed_repo(tmp_path)
    config_path.write_text(config_path.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
    config = load_config(explicit=config_path)
    report = build_impact(config, "HEAD", Engine(config).scan().documents.values())
    assert report.configuration_changed is True
    with pytest.raises(GitError, match="IMPACT-GIT-001"):
        build_impact(config, "does-not-exist", Engine(config).scan().documents.values())


def test_impact_cli_json_matches_packaged_schema(tmp_path: Path, capsys) -> None:
    config_path = _seed_repo(tmp_path)
    original = config_path.read_bytes()
    assert main(["--config", str(config_path), "impact", "--base", "HEAD", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    schema = json.loads(files("locus_md").joinpath("schemas/impact.v1.schema.json").read_text(encoding="utf-8"))
    validate(payload, schema)
    assert config_path.read_bytes() == original
