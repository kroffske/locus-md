from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, Sequence

from ..models import Finding, Severity


def readonly_value(value: object) -> object:
    """Return an immutable projection of JSON/YAML-compatible data."""

    if isinstance(value, Mapping):
        return MappingProxyType({key: readonly_value(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(readonly_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(readonly_value(item) for item in value)
    return value


def readonly_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    projected = readonly_value(value)
    if not isinstance(projected, Mapping):  # pragma: no cover - guarded by the public type
        raise TypeError("expected a mapping")
    return projected


@dataclass(frozen=True, slots=True)
class RuleContext:
    workspace_root: Path
    rule_name: str
    phase: Literal["verify"]
    surface: str | None
    severity: Severity


@dataclass(frozen=True, slots=True)
class RuleLink:
    target: str
    line: int
    column: int = 1
    image: bool = False


@dataclass(frozen=True, slots=True)
class RuleDocument:
    surface: str
    relative_path: str
    display_path: str
    text: str
    frontmatter: Mapping[str, object] | None
    links: tuple[RuleLink, ...]


class RulePlugin(Protocol):
    api_version: str
    plugin_id: str
    plugin_version: str

    def validate_config(self, options: Mapping[str, object]) -> None: ...

    def check(
        self,
        context: RuleContext,
        document: RuleDocument,
        options: Mapping[str, object],
    ) -> Sequence[Finding]: ...
