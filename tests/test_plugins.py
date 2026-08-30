from __future__ import annotations

from pathlib import Path

import pytest

from locus_md.config import load_config
from locus_md.errors import ConfigError
from locus_md.plugins import PluginRegistry


class DummyProvider:
    api_version = "1"


class OldProvider:
    api_version = "0"


def test_host_can_inject_provider_adapter() -> None:
    registry = PluginRegistry(discover=False)
    provider = DummyProvider()
    registry.register_provider("host", provider)
    assert registry.provider("host") is provider
    with pytest.raises(ConfigError, match="PLUGIN-002"):
        registry.register_provider("host", provider)
    with pytest.raises(ConfigError, match="PLUGIN-001"):
        registry.register_provider("old", OldProvider())


def test_rule_plugins_fail_closed_with_version_neutral_message(tmp_path: Path) -> None:
    (tmp_path / ".locus").mkdir()
    (tmp_path / "docs").mkdir()
    config_path = tmp_path / ".locus" / "config.ini"
    config_path.write_text(
        """[locus.docs]
schema = 1
surfaces = docs

[locus.docs.surface:docs]
root = docs
include = **/*.md

[locus.docs.rule:policy-coverage]
adapter = policy-coverage
surface = docs
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
