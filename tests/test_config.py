from __future__ import annotations

from pathlib import Path

import pytest

from locus_md.config import discover_config, load_config
from locus_md.errors import ConfigError
from conftest import write_minimal_workspace


def test_shared_ini_ignores_unrelated_values_and_interpolation(tmp_path: Path) -> None:
    path = write_minimal_workspace(tmp_path, extra_ini="[locus]\nproject = demo\n\n[locus.tasks]\ntoken = ${ENV:DOES_NOT_EXIST}\nprovider = linear\n\n")
    config = load_config(explicit=path, env={})
    assert config.global_config.surfaces == ("docs",)
    normalized = config.normalized(redact=True)
    assert "tasks" not in normalized
    assert "DOES_NOT_EXIST" not in str(normalized)


def test_environment_substitution_is_allowed_inside_namespace(tmp_path: Path) -> None:
    (tmp_path / ".locus").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / ".locus" / "config.ini").write_text(
        """[locus.docs]\nschema = 1\nsurfaces = docs\n\n[locus.docs.surface:docs]\nroot = ${ENV:DOCS_ROOT}\ninclude = **/*.md\n""",
        encoding="utf-8",
    )
    config = load_config(explicit=tmp_path / ".locus" / "config.ini", env={"DOCS_ROOT": "docs"})
    assert config.surfaces["docs"].root == "docs"


def test_cross_section_interpolation_is_rejected(tmp_path: Path) -> None:
    (tmp_path / ".locus").mkdir()
    path = tmp_path / ".locus" / "config.ini"
    path.write_text("""[locus.tasks]\nroot = tasks\n\n[locus.docs]\nschema = 1\nsurfaces = docs\n\n[locus.docs.surface:docs]\nroot = ${locus.tasks:root}\ninclude = **/*.md\n""", encoding="utf-8")
    with pytest.raises(ConfigError, match="CFG-040"):
        load_config(explicit=path)


def test_ambiguous_discovery_is_rejected(tmp_path: Path) -> None:
    (tmp_path / ".locus").mkdir()
    (tmp_path / ".locus" / "config.ini").write_text("[locus.docs]\nschema=1\nsurfaces=docs\n", encoding="utf-8")
    (tmp_path / "locus.ini").write_text("[locus.docs]\nschema=1\nsurfaces=docs\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="CFG-060"):
        discover_config(start=tmp_path)


def test_nested_config_owns_its_workspace_inside_parent_git_repo(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "examples" / "basic"
    path = write_minimal_workspace(nested)

    config = load_config(explicit=path)

    assert config.workspace_root == nested


def test_contract_path_escape_is_rejected(tmp_path: Path) -> None:
    path = write_minimal_workspace(tmp_path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            """
[locus.docs.provider:tasks]
adapter = file-json
path = data/tasks.json

[locus.docs.contract:x]
surface = docs
path = ../outside.md
block_kind = milestone
block_id = tasks
schema = task-table.v1
mode = projection
provider = tasks
renderer = task-table.v1
"""
        )
    with pytest.raises(ConfigError, match="CFG-050"):
        load_config(explicit=path)
