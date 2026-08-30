from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from locus_md.config import load_config
from locus_md.engine import Engine
from locus_md.errors import ConfigError
from locus_md.models import Finding, RunState
from locus_md.plugins import PluginRegistry


class DummyProvider:
    api_version = "1"


class OldProvider:
    api_version = "0"


class DummyRule:
    api_version = "1"
    plugin_id = "dummy-rule"
    plugin_version = "1.0"

    def validate_config(self, options) -> None:
        return None

    def check(self, context, document, options):
        return ()


class OldRule(DummyRule):
    api_version = "0"


class InvalidMetadataRule(DummyRule):
    plugin_id = object()


class MutatingMetadataRule(DummyRule):
    plugin_id = "mutating"

    def __init__(self) -> None:
        self.version_reads = 0
        self.current_version = 1

    @property
    def plugin_version(self) -> str:
        self.version_reads += 1
        return str(self.current_version)

    def validate_config(self, options) -> None:
        return None

    def check(self, context, document, options):
        self.current_version += 1
        return (
            Finding(
                code="external.rule.changed",
                message="metadata changed during execution",
                state=RunState.FAILED,
                details={"plugin_version": str(self.current_version)},
            ),
        )


def test_host_can_inject_provider_adapter() -> None:
    registry = PluginRegistry(discover=False)
    provider = DummyProvider()
    registry.register_provider("host", provider)
    assert registry.provider("host") is provider
    with pytest.raises(ConfigError, match="PLUGIN-002"):
        registry.register_provider("host", provider)
    with pytest.raises(ConfigError, match="PLUGIN-001"):
        registry.register_provider("old", OldProvider())


def test_rule_plugins_fail_closed_when_adapter_is_unknown(tmp_path: Path) -> None:
    (tmp_path / ".locus").mkdir()
    (tmp_path / "docs").mkdir()
    config_path = tmp_path / ".locus" / "locus.md.toml"
    config_path.write_text(
        """[locus.md]
schema = 1
surfaces = ["docs"]

[locus.md.surface.docs]
root = "docs"
include = ["**/*.md"]

[locus.md.rule.policy-coverage]
adapter = "policy-coverage"
phase = "verify"
surface = "docs"
""",
        encoding="utf-8",
    )
    workspace = load_config(explicit=config_path)

    with pytest.raises(ConfigError) as raised:
        PluginRegistry(discover=False).validate_references(workspace)

    error = raised.value
    assert error.code == "CFG-037"
    assert "policy-coverage" in error.message
    assert "v0.1" not in error.message
    assert "v0.2.0" not in error.message


def test_host_can_inject_rule_adapter() -> None:
    registry = PluginRegistry(discover=False)
    plugin = DummyRule()

    registry.register_rule("dummy", plugin)

    assert registry.rule("dummy") is plugin
    with pytest.raises(ConfigError, match="PLUGIN-002"):
        registry.register_rule("dummy", plugin)
    with pytest.raises(ConfigError, match="PLUGIN-001"):
        registry.register_rule("old", OldRule())
    with pytest.raises(ConfigError, match="PLUGIN-003"):
        registry.register_rule("bad-metadata", InvalidMetadataRule())


def test_rule_entry_point_is_discovered(monkeypatch) -> None:
    plugin_class = DummyRule

    class FakeEntryPoints:
        def select(self, *, group: str):
            if group != "locus_md.rules":
                return ()
            return (SimpleNamespace(name="dummy", load=lambda: plugin_class),)

    monkeypatch.setattr("locus_md.plugins.metadata.entry_points", lambda: FakeEntryPoints())

    registry = PluginRegistry()

    assert isinstance(registry.rule("dummy"), DummyRule)


def test_incompatible_rule_entry_point_fails_when_referenced(monkeypatch) -> None:
    class FakeEntryPoints:
        def select(self, *, group: str):
            if group != "locus_md.rules":
                return ()
            return (SimpleNamespace(name="old", load=lambda: OldRule),)

    monkeypatch.setattr("locus_md.plugins.metadata.entry_points", lambda: FakeEntryPoints())

    registry = PluginRegistry()

    with pytest.raises(ConfigError, match="unsupported API version") as raised:
        registry.rule("old")
    assert raised.value.code == "PLUGIN-001"


def test_rule_metadata_is_one_command_snapshot_for_shared_adapter(tmp_path: Path) -> None:
    (tmp_path / ".locus").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text("# Index\n", encoding="utf-8")
    (tmp_path / "docs" / "second.md").write_text("# Second\n", encoding="utf-8")
    config_path = tmp_path / ".locus" / "locus.md.toml"
    config_path.write_text(
        """[locus.md]
schema = 1
surfaces = ["docs"]

[locus.md.surface.docs]
root = "docs"
include = ["**/*.md"]

[locus.md.rule.alpha]
adapter = "mutating"
phase = "verify"
surface = "docs"
[locus.md.rule.beta]
adapter = "mutating"
phase = "verify"
surface = "docs"
""",
        encoding="utf-8",
    )
    plugin = MutatingMetadataRule()
    registry = PluginRegistry(discover=False)
    registry.register_rule("mutating", plugin)
    engine = Engine(load_config(explicit=config_path), registry=registry)
    reads_before = plugin.version_reads

    report = engine.verify(offline=True)

    assert plugin.version_reads - reads_before == 1
    assert len(report.findings) == 4
    assert {finding.details["plugin_version"] for finding in report.findings} == {"1"}
    assert [item["rule"] for item in report.metadata["rules"]] == ["alpha", "beta"]
    assert {item["plugin_version"] for item in report.metadata["rules"]} == {"1"}
    assert {item["invocation_count"] for item in report.metadata["rules"]} == {2}
