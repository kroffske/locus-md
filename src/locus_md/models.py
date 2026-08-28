from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping, Sequence

from .utils import digest_json, digest_text


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


class RunState(StrEnum):
    PASSED = "passed"
    UNVERIFIED = "unverified"
    FAILED = "failed"
    CONFIGURATION_ERROR = "configuration-error"
    INTERNAL_ERROR = "internal-error"


_SEVERITY_ORDER = {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2, Severity.FATAL: 3}


@dataclass(frozen=True, slots=True)
class Remediation:
    kind: str
    value: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "value": self.value}


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    message: str
    severity: Severity = Severity.ERROR
    path: str | None = None
    line: int | None = None
    column: int | None = None
    surface: str | None = None
    contract_id: str | None = None
    state: RunState | None = None
    details: Mapping[str, Any] = field(default_factory=dict)
    remediation: Remediation | None = None

    def sort_key(self) -> tuple[Any, ...]:
        return (self.surface or "", self.path or "", self.line or 0, self.column or 0, self.code, self.message)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"code": self.code, "message": self.message, "severity": self.severity.value}
        for key, value in (("path", self.path), ("line", self.line), ("column", self.column), ("surface", self.surface), ("contract_id", self.contract_id)):
            if value is not None:
                result[key] = value
        if self.state is not None:
            result["state"] = self.state.value
        if self.details:
            result["details"] = dict(self.details)
        if self.remediation:
            result["remediation"] = self.remediation.to_dict()
        return result


@dataclass(frozen=True, slots=True)
class GlobalConfig:
    schema: int
    surfaces: tuple[str, ...]
    strict: bool = False
    lock_file: str = ".locus/docs.lock.json"
    cache_dir: str = ".locus/cache/locus-md"
    report_dir: str | None = None
    default_output: str = "human"
    network: str = "explicit"
    unverified: str = "fail"


@dataclass(frozen=True, slots=True)
class SurfaceConfig:
    name: str
    root: str
    include: tuple[str, ...]
    exclude: tuple[str, ...] = ()
    indexes: tuple[str, ...] = ()
    frontmatter: str = "optional"
    frontmatter_schema: str | None = None
    require_reachable: bool = False
    allow_external_links: bool = True
    follow_symlinks: bool = False
    default_provider: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    name: str
    adapter: str
    required: bool = True
    network: bool = False
    snapshot_file: str | None = None
    cache_ttl: int | None = None
    options: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ContractBinding:
    name: str
    surface: str
    path: str
    block_kind: str
    block_id: str
    schema: str
    mode: str
    provider: str | None
    selector: Mapping[str, Any]
    renderer: str | None
    provider_explicit: bool = True
    severity: Severity = Severity.ERROR
    required: bool = True

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.surface, self.path, self.block_kind, self.block_id)


@dataclass(frozen=True, slots=True)
class RuleConfig:
    name: str
    adapter: str
    surface: str | None
    severity: Severity
    options: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class WorkspaceConfig:
    config_path: Path
    workspace_root: Path
    global_config: GlobalConfig
    surfaces: Mapping[str, SurfaceConfig]
    providers: Mapping[str, ProviderConfig]
    contracts: Mapping[str, ContractBinding]
    rules: Mapping[str, RuleConfig]
    config_digest: str

    def normalized(self, *, redact: bool = False) -> dict[str, Any]:
        providers: dict[str, Any] = {}
        for name, provider in sorted(self.providers.items()):
            options = dict(provider.options)
            if redact:
                from .utils import redact_mapping

                options = redact_mapping(options)
            providers[name] = {"adapter": provider.adapter, "required": provider.required, "network": provider.network,
                               "snapshot_file": provider.snapshot_file, "cache_ttl": provider.cache_ttl, "options": options}
        return {
            "schema": "locus-md.config.normalized.v1",
            "config_path": str(self.config_path),
            "workspace_root": str(self.workspace_root),
            "global": {
                "schema": self.global_config.schema,
                "surfaces": list(self.global_config.surfaces),
                "strict": self.global_config.strict,
                "lock_file": self.global_config.lock_file,
                "cache_dir": self.global_config.cache_dir,
                "report_dir": self.global_config.report_dir,
                "default_output": self.global_config.default_output,
                "network": self.global_config.network,
                "unverified": self.global_config.unverified,
            },
            "surfaces": {
                name: {
                    "root": surface.root,
                    "include": list(surface.include),
                    "exclude": list(surface.exclude),
                    "indexes": list(surface.indexes),
                    "frontmatter": surface.frontmatter,
                    "frontmatter_schema": surface.frontmatter_schema,
                    "require_reachable": surface.require_reachable,
                    "allow_external_links": surface.allow_external_links,
                    "follow_symlinks": surface.follow_symlinks,
                    "default_provider": surface.default_provider,
                }
                for name, surface in sorted(self.surfaces.items())
            },
            "providers": providers,
            "contracts": {
                name: {
                    "surface": binding.surface,
                    "path": binding.path,
                    "block_kind": binding.block_kind,
                    "block_id": binding.block_id,
                    "schema": binding.schema,
                    "mode": binding.mode,
                    "provider": binding.provider,
                    "provider_explicit": binding.provider_explicit,
                    "selector": dict(binding.selector),
                    "renderer": binding.renderer,
                    "severity": binding.severity.value,
                    "required": binding.required,
                }
                for name, binding in sorted(self.contracts.items())
            },
            "rules": {
                name: {"adapter": rule.adapter, "surface": rule.surface, "severity": rule.severity.value, "options": dict(rule.options)} for name, rule in sorted(self.rules.items())
            },
            "config_digest": self.config_digest,
        }


@dataclass(frozen=True, slots=True)
class FrontmatterRecord:
    data: Mapping[str, Any] | None
    span_start: int | None = None
    span_end: int | None = None


@dataclass(frozen=True, slots=True)
class LinkRecord:
    target: str
    line: int
    column: int = 1
    image: bool = False


@dataclass(frozen=True, slots=True)
class ManagedBlock:
    kind: str
    block_id: str
    start_marker_start: int
    start_marker_end: int
    body_start: int
    body_end: int
    end_marker_start: int
    end_marker_end: int
    start_line: int
    end_line: int

    @property
    def key(self) -> tuple[str, str]:
        return (self.kind, self.block_id)


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    surface: str
    relative_path: str
    absolute_path: Path
    text: str
    source_digest: str
    newline: str
    bom: bool
    frontmatter: FrontmatterRecord
    links: tuple[LinkRecord, ...]
    blocks: tuple[ManagedBlock, ...]

    @property
    def key(self) -> tuple[str, str]:
        return (self.surface, self.relative_path)

    def body(self, block: ManagedBlock) -> str:
        return self.text[block.body_start:block.body_end]

    def encode(self, text: str | None = None) -> bytes:
        payload = (self.text if text is None else text).encode("utf-8")
        return (b"\xef\xbb\xbf" + payload) if self.bom else payload


@dataclass(frozen=True, slots=True)
class ProviderQuery:
    kind: str
    selector: Mapping[str, Any]
    fields: tuple[str, ...] = ()

    def canonical(self) -> dict[str, Any]:
        return {"kind": self.kind, "selector": dict(sorted(self.selector.items())), "fields": sorted(set(self.fields))}

    @property
    def digest(self) -> str:
        return digest_json(self.canonical())


@dataclass(frozen=True, slots=True)
class EntityRecord:
    kind: str
    entity_id: str
    revision: str | None
    fields: Mapping[str, Any]
    url: str | None = None

    def canonical(self) -> dict[str, Any]:
        return {"kind": self.kind, "id": self.entity_id, "revision": self.revision, "fields": dict(sorted(self.fields.items())), "url": self.url}


@dataclass(frozen=True, slots=True)
class ProviderSnapshot:
    provider: str
    adapter: str
    adapter_version: str
    revision: str
    consistency: str
    captured_at: str
    records: tuple[EntityRecord, ...]
    content_digest: str

    def metadata(self) -> dict[str, Any]:
        return {"adapter": self.adapter, "adapter_version": self.adapter_version, "revision": self.revision, "consistency": self.consistency,
                "captured_at": self.captured_at, "content_digest": self.content_digest, "record_count": len(self.records)}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "locus-md.snapshot.v1", "provider": self.provider, "adapter": self.adapter, "adapter_version": self.adapter_version,
            "revision": self.revision, "consistency": self.consistency, "captured_at": self.captured_at,
            "records": [record.canonical() for record in self.records], "content_digest": self.content_digest,
        }


@dataclass(frozen=True, slots=True)
class Patch:
    path: str
    absolute_path: Path
    start: int
    end: int
    old_text: str
    replacement: str
    original_digest: str
    contract_id: str | None = None
    description: str | None = None
    diff: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "start": self.start,
            "end": self.end,
            "original_digest": self.original_digest,
            "replacement_digest": digest_text(self.replacement),
            "contract_id": self.contract_id,
            "description": self.description,
            "diff": self.diff,
        }


@dataclass(frozen=True, slots=True)
class LockEntry:
    surface: str
    path: str
    block_kind: str
    block_id: str
    contract_schema: str
    renderer: str | None
    provider: str
    provider_revision: str
    snapshot_digest: str
    body_digest: str
    synced_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface": self.surface,
            "path": self.path,
            "block_kind": self.block_kind,
            "block_id": self.block_id,
            "contract_schema": self.contract_schema,
            "renderer": self.renderer,
            "provider": self.provider,
            "provider_revision": self.provider_revision,
            "snapshot_digest": self.snapshot_digest,
            "body_digest": self.body_digest,
            "synced_at": self.synced_at,
        }


@dataclass(frozen=True, slots=True)
class LockState:
    entries: Mapping[str, LockEntry]
    source_text: str = ""
    source_digest: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "locus-md.lock.v1", "contracts": {name: entry.to_dict() for name, entry in sorted(self.entries.items())}}


@dataclass(slots=True)
class Report:
    run_id: str
    mode: str
    state: RunState
    config_digest: str
    config_path: str
    findings: list[Finding] = field(default_factory=list)
    snapshots: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    patches: list[Patch] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def sorted_findings(self) -> list[Finding]:
        return sorted(self.findings, key=Finding.sort_key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "locus-md.report.v1",
            "run_id": self.run_id,
            "mode": self.mode,
            "state": self.state.value,
            "config_digest": self.config_digest,
            "config_path": self.config_path,
            "snapshots": dict(sorted(self.snapshots.items())),
            "findings": [finding.to_dict() for finding in self.sorted_findings()],
            "patches": [patch.to_dict() for patch in self.patches],
            "metadata": self.metadata,
        }


def has_failure(findings: Sequence[Finding]) -> bool:
    return any(_SEVERITY_ORDER[finding.severity] >= _SEVERITY_ORDER[Severity.ERROR] and finding.state != RunState.UNVERIFIED for finding in findings)
