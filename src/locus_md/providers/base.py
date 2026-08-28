from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol, Sequence

from ..models import Finding, ProviderQuery, ProviderSnapshot


@dataclass(frozen=True, slots=True)
class ProviderContext:
    workspace_root: Path
    provider_name: str
    offline: bool
    network_allowed: bool


class ProviderSession(Protocol):
    capabilities: frozenset[str]

    def capture(self, queries: Sequence[ProviderQuery]) -> ProviderSnapshot: ...

    def close(self) -> None: ...


class ProviderPlugin(Protocol):
    api_version: str
    plugin_id: str
    plugin_version: str

    def validate_config(self, options: Mapping[str, str]) -> list[Finding]: ...

    def open(self, context: ProviderContext, options: Mapping[str, str]) -> ProviderSession: ...
