from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

import pytest
from jsonschema import validate

from locus_md.cli import main
from locus_md.config import discover_config, load_config
from locus_md.errors import ConfigError
from conftest import write_minimal_workspace


def _normalized_schema() -> dict:
    schema = files("locus_md").joinpath("schemas/config-normalized.v1.schema.json")
    return json.loads(schema.read_text(encoding="utf-8"))


def test_dedicated_namespace_rejects_unrelated_values(tmp_path: Path) -> None:
    path = write_minimal_workspace(tmp_path)
    path.write_text("[other]\nvalue = \"ignored\"\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="CFG-062"):
        load_config(explicit=path)


def test_environment_substitution_is_recursive_and_preserves_strings(tmp_path: Path) -> None:
    path = write_minimal_workspace(tmp_path)
    path.write_text("""[locus.md]
schema = 1
surfaces = ["docs"]

[locus.md.surface.docs]
root = "${ENV:DOCS_ROOT}"
include = ["**/*.md", "${ENV:EXTRA_GLOB}"]
""", encoding="utf-8")
    config = load_config(explicit=path, env={"DOCS_ROOT": "docs", "EXTRA_GLOB": "README.md"})
    assert config.surfaces["docs"].root == "docs"
    assert config.surfaces["docs"].include == ("**/*.md", "README.md")


def test_cross_section_interpolation_is_rejected(tmp_path: Path) -> None:
    path = write_minimal_workspace(tmp_path)
    path.write_text("""[locus.md]
schema = 1
surfaces = ["docs"]

[locus.md.surface.docs]
root = "${locus.tasks.root}"
include = ["**/*.md"]
""", encoding="utf-8")
    with pytest.raises(ConfigError, match="CFG-040"):
        load_config(explicit=path)


def test_duplicate_toml_keys_have_stable_config_error(tmp_path: Path) -> None:
    path = write_minimal_workspace(tmp_path)
    path.write_text("[locus.md]\nschema = 1\nschema = 1\nsurfaces = [\"docs\"]\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="CFG-002"):
        load_config(explicit=path)


def test_discovery_uses_only_canonical_name_and_rejects_legacy(tmp_path: Path) -> None:
    (tmp_path / ".locus").mkdir()
    (tmp_path / ".locus" / "config.ini").write_text("[locus.docs]\nschema=1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="CFG-061"):
        discover_config(start=tmp_path)


def test_discovery_precedence_is_explicit_then_environment_then_upward(tmp_path: Path) -> None:
    discovered = write_minimal_workspace(tmp_path)
    override_root = tmp_path / "override"
    override = write_minimal_workspace(override_root)
    explicit_root = tmp_path / "explicit"
    explicit = write_minimal_workspace(explicit_root)
    assert discover_config(start=tmp_path / "nested", env={"LOCUS_MD_CONFIG": str(override)}) == override.resolve()
    assert discover_config(explicit=explicit, start=tmp_path, env={"LOCUS_MD_CONFIG": str(override)}) == explicit.resolve()
    assert discover_config(start=tmp_path / "nested") == discovered.resolve()


def test_generic_environment_alias_is_not_read(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[locus.md]\nschema = 1\nsurfaces = [\"docs\"]\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="CFG-001"):
        discover_config(start=tmp_path / "nested", env={"LOCUS_CONFIG": str(path)})


def test_nested_config_owns_its_workspace_inside_parent_git_repo(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "examples" / "basic"
    path = write_minimal_workspace(nested)
    config = load_config(explicit=path)
    assert config.workspace_root == nested


def test_explicit_ini_path_gets_migration_guidance_without_reading(tmp_path: Path) -> None:
    path = tmp_path / "config.ini"
    path.write_text("not toml", encoding="utf-8")
    with pytest.raises(ConfigError, match="CFG-061"):
        load_config(explicit=path)
    assert path.read_text(encoding="utf-8") == "not toml"


def test_contract_path_escape_is_rejected(tmp_path: Path) -> None:
    path = write_minimal_workspace(tmp_path)
    path.write_text("""[locus.md]
schema = 1
surfaces = ["docs"]

[locus.md.surface.docs]
root = "docs"
include = ["**/*.md"]

[locus.md.provider.tasks]
adapter = "file-json"
path = "data/tasks.json"

[locus.md.contract.x]
surface = "docs"
path = "../outside.md"
block_kind = "milestone"
block_id = "tasks"
schema = "task-table.v1"
mode = "projection"
provider = "tasks"
renderer = "task-table.v1"
""", encoding="utf-8")
    with pytest.raises(ConfigError, match="CFG-050"):
        load_config(explicit=path)


def test_packaged_schema_validates_real_normalized_config_without_rules(example_workspace: Path) -> None:
    config = load_config(explicit=example_workspace / ".locus" / "locus.md.toml")
    validate(instance=config.normalized(), schema=_normalized_schema())


def test_packaged_schema_validates_real_normalized_config_with_rule(tmp_path: Path) -> None:
    config_path = write_minimal_workspace(tmp_path)
    config_path.write_text(config_path.read_text(encoding="utf-8") + """
[locus.md.rule.policy]
adapter = "policy"
phase = "verify"
surface = "docs"
severity = "warning"
options = { registry = "docs/policies.json" }
""", encoding="utf-8")
    config = load_config(explicit=config_path)
    validate(instance=config.normalized(), schema=_normalized_schema())


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_rule_options_reject_non_finite_toml_values_before_plugin_validation(tmp_path: Path, value: str) -> None:
    config_path = write_minimal_workspace(tmp_path)
    config_path.write_text(config_path.read_text(encoding="utf-8") + f"""
[locus.md.rule.policy]
adapter = "policy"
phase = "verify"
surface = "docs"
options = {{ value = {value} }}
""", encoding="utf-8")
    with pytest.raises(ConfigError, match="CFG-036"):
        load_config(explicit=config_path)


@pytest.mark.parametrize("key,value", [("schema", "true"), ("surfaces", "\"docs\""), ("strict", "\"true\"")])
def test_native_toml_types_are_strict(tmp_path: Path, key: str, value: str) -> None:
    config_path = write_minimal_workspace(tmp_path)
    text = config_path.read_text(encoding="utf-8").replace("schema = 1", f"{key} = {value}", 1)
    config_path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(explicit=config_path)


def test_provider_options_must_be_strings(tmp_path: Path) -> None:
    config_path = write_minimal_workspace(tmp_path)
    config_path.write_text(config_path.read_text(encoding="utf-8") + """
[locus.md.provider.tasks]
adapter = "file-json"
custom = true
""", encoding="utf-8")
    with pytest.raises(ConfigError, match="CFG-004"):
        load_config(explicit=config_path)


def test_init_is_create_only_and_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    path = tmp_path / ".locus" / "locus.md.toml"
    first = path.read_text(encoding="utf-8")
    assert main(["init"]) == 0
    assert path.read_text(encoding="utf-8") == first


def test_init_rejects_invalid_existing_and_legacy_without_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / ".locus" / "locus.md.toml"
    target.parent.mkdir()
    target.write_text("[wrong]\nvalue = 1\n", encoding="utf-8")
    before = target.read_bytes()
    assert main(["init"]) == 2
    assert target.read_bytes() == before

    target.unlink()
    legacy = target.parent / "config.ini"
    legacy.write_text("[locus.docs]\nschema=1\n", encoding="utf-8")
    before = legacy.read_bytes()
    assert main(["init"]) == 2
    assert legacy.read_bytes() == before


def test_init_print_rejects_explicit_non_toml_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    legacy = tmp_path / "legacy.ini"
    legacy.write_text("[locus.docs]\nschema=1\n", encoding="utf-8")
    assert main(["init", "--config", str(legacy), "--print"]) == 2
    assert "CFG-061" in capsys.readouterr().err
    assert legacy.read_text(encoding="utf-8") == "[locus.docs]\nschema=1\n"
