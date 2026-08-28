from __future__ import annotations

import pytest

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
