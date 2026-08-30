from __future__ import annotations

import difflib
import uuid
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .errors import ConfigError, ProviderUnavailable
from .graph import validate_graph
from .lock import load_lock, lock_path, serialize_lock
from .markdown import scan_document
from .models import ContractBinding, DocumentRecord, Finding, LockEntry, LockState, ManagedBlock, Patch, ProviderQuery, ProviderSnapshot
from .models import Remediation, Report, RunState, Severity, WorkspaceConfig, has_failure
from .plugins import PluginRegistry
from .providers.base import ProviderContext
from .providers.common import load_snapshot_file
from .rewrite import apply_patches
from .rules.execution import execute_rules
from .utils import digest_bytes, digest_text, display_surface_path, utc_now
from .workspace import inventory_workspace


@dataclass(slots=True)
class ScanResult:
    documents: dict[tuple[str, str], DocumentRecord]
    blocks: dict[tuple[str, str, str, str], tuple[DocumentRecord, ManagedBlock]]
    findings: list[Finding]
    lock: LockState


@dataclass(slots=True)
class PlannedContract:
    binding: ContractBinding
    document: DocumentRecord
    block: ManagedBlock
    handler: Any
    provider: str
    queries: list[ProviderQuery]


class Engine:
    def __init__(self, config: WorkspaceConfig, *, registry: PluginRegistry | None = None) -> None:
        self.config = config
        self.registry = registry or PluginRegistry()
        self.registry.validate_references(config)

    def _display_path(self, document: DocumentRecord) -> str:
        return display_surface_path(self.config.surfaces[document.surface].root, document.relative_path)

    def _strict_findings(self, findings: Iterable[Finding], force_strict: bool = False) -> list[Finding]:
        strict = self.config.global_config.strict or force_strict
        if not strict:
            return list(findings)
        result: list[Finding] = []
        for finding in findings:
            if finding.severity == Severity.WARNING:
                result.append(
                    Finding(
                        code=finding.code,
                        message=finding.message,
                        severity=Severity.ERROR,
                        path=finding.path,
                        line=finding.line,
                        column=finding.column,
                        surface=finding.surface,
                        contract_id=finding.contract_id,
                        state=finding.state,
                        details=finding.details,
                        remediation=finding.remediation,
                    )
                )
            else:
                result.append(finding)
        return result

    def scan(self, *, surfaces: set[str] | None = None, force_strict: bool = False) -> ScanResult:
        unknown = (surfaces or set()) - set(self.config.surfaces)
        if unknown:
            raise ConfigError("CFG-010", f"unknown surface filter(s): {', '.join(sorted(unknown))}")
        inventory, findings = inventory_workspace(self.config, surfaces)
        documents: dict[tuple[str, str], DocumentRecord] = {}
        for surface, relative, absolute in inventory:
            document, document_findings = scan_document(self.config, surface, relative, absolute)
            findings.extend(document_findings)
            if document is not None:
                documents[document.key] = document
        selected_surfaces = surfaces or set(self.config.global_config.surfaces)
        findings.extend(validate_graph(self.config, documents, selected_surfaces=selected_surfaces))
        for declaration in self.config.documents.values():
            if declaration.surface not in selected_surfaces:
                continue
            key = (declaration.surface, declaration.path)
            display_path = display_surface_path(self.config.surfaces[declaration.surface].root, declaration.path)
            document = documents.get(key)
            if document is None:
                findings.append(Finding(code="DOC-DECL-001", message=f"declared document {declaration.name!r} does not exist", severity=Severity.ERROR,
                                        path=display_path, surface=declaration.surface, contract_id=declaration.name,
                                        details={"document": declaration.name, "surface": declaration.surface, "path": declaration.path}))
                continue
            for section in declaration.sections.values():
                if section.required and section.heading not in document.headings:
                    findings.append(Finding(code="DOC-SECTION-001", message=f"required section {section.heading!r} is missing",
                                            severity=Severity.ERROR, path=display_path, surface=declaration.surface, contract_id=declaration.name,
                                            details={"document": declaration.name, "section": section.name, "heading": section.heading}))
        blocks: dict[tuple[str, str, str, str], tuple[DocumentRecord, ManagedBlock]] = {}
        configured_keys = {binding.key: binding for binding in self.config.contracts.values() if binding.surface in selected_surfaces}
        for document in documents.values():
            for block in document.blocks:
                key = (document.surface, document.relative_path, block.kind, block.block_id)
                blocks[key] = (document, block)
                if key not in configured_keys:
                    findings.append(
                        Finding(code="DOC-BLOCK-010", message=f"managed block {block.kind}/{block.block_id} has no contract binding", severity=Severity.ERROR,
                                path=self._display_path(document), line=block.start_line, surface=document.surface)
                    )
        for binding in self.config.contracts.values():
            if binding.surface not in selected_surfaces:
                continue
            surface = self.config.surfaces[binding.surface]
            if binding.provider_explicit and surface.default_provider and binding.provider != surface.default_provider:
                findings.append(
                    Finding(code="DOC-BLOCK-030", message=f"contract explicitly uses provider {binding.provider!r} while surface default is {surface.default_provider!r}",
                            severity=Severity.WARNING, path=display_surface_path(surface.root, binding.path), surface=binding.surface, contract_id=binding.name)
                )
            if binding.required and binding.key not in blocks:
                surface = self.config.surfaces[binding.surface]
                findings.append(
                    Finding(code="DOC-BLOCK-011", message=f"required contract {binding.name!r} has no matching marker {binding.block_kind}/{binding.block_id}",
                            severity=Severity.ERROR, path=display_surface_path(surface.root, binding.path), surface=binding.surface, contract_id=binding.name)
                )
        lock, lock_findings = load_lock(self.config)
        findings.extend(lock_findings)
        active_contracts = {name for name, binding in self.config.contracts.items() if binding.surface in selected_surfaces}
        for name, entry in lock.entries.items():
            if name not in self.config.contracts and not surfaces:
                findings.append(Finding(code="DOC-LOCK-005", message=f"lock contains entry for unknown contract {name!r}", severity=Severity.WARNING,
                                        path=self.config.global_config.lock_file, contract_id=name))
        for name, binding in self.config.contracts.items():
            if name not in active_contracts or binding.key not in blocks:
                continue
            document, block = blocks[binding.key]
            entry = lock.entries.get(name)
            if entry is None:
                if binding.mode in {"projection", "snapshot"}:
                    findings.append(
                        Finding(code="DOC-LOCK-003", message="managed projection has no lock evidence; run sync --write", severity=Severity.INFO,
                                path=self._display_path(document), line=block.start_line, surface=document.surface, contract_id=name,
                                remediation=Remediation("command", "locus-md sync --write"))
                    )
                continue
            metadata_matches = (
                entry.surface == binding.surface
                and entry.path == binding.path
                and entry.block_kind == binding.block_kind
                and entry.block_id == binding.block_id
                and entry.contract_schema == binding.schema
                and entry.renderer == binding.renderer
                and entry.provider == binding.provider
            )
            if not metadata_matches:
                findings.append(Finding(code="DOC-LOCK-004", message="lock metadata differs from the current contract binding", severity=Severity.WARNING,
                                        path=self._display_path(document), line=block.start_line, surface=document.surface, contract_id=name))
            current_digest = digest_text(document.body(block))
            if current_digest != entry.body_digest:
                findings.append(
                    Finding(code="DOC-BLOCK-020", message="managed block body differs from the last synchronized lock digest", severity=binding.severity,
                            path=self._display_path(document), line=block.start_line, surface=document.surface, contract_id=name,
                            details={"current_body_digest": current_digest, "locked_body_digest": entry.body_digest},
                            remediation=Remediation("command", "locus-md sync --check"))
                )
        return ScanResult(documents=documents, blocks=blocks, findings=self._strict_findings(findings, force_strict), lock=lock)

    def lint(self, *, surfaces: set[str] | None = None, force_strict: bool = False) -> Report:
        scan = self.scan(surfaces=surfaces, force_strict=force_strict)
        state = RunState.FAILED if has_failure(scan.findings) else RunState.PASSED
        return self._report("lint", state, scan.findings, metadata={"document_count": len(scan.documents), "block_count": len(scan.blocks)})

    def _plan(self, scan: ScanResult, *, providers: set[str] | None = None, surfaces: set[str] | None = None) -> list[PlannedContract]:
        unknown_providers = (providers or set()) - set(self.config.providers)
        if unknown_providers:
            raise ConfigError("CFG-020", f"unknown provider filter(s): {', '.join(sorted(unknown_providers))}")
        planned: list[PlannedContract] = []
        for binding in self.config.contracts.values():
            if surfaces and binding.surface not in surfaces:
                continue
            if binding.key not in scan.blocks or binding.provider is None:
                continue
            if providers and binding.provider not in providers:
                continue
            document, block = scan.blocks[binding.key]
            handler = self.registry.contract(binding.schema)
            planned.append(PlannedContract(binding=binding, document=document, block=block, handler=handler, provider=binding.provider,
                                           queries=handler.plan(binding, document, block)))
        return planned

    def _provider_unavailable_finding(self, provider_name: str, message: str) -> Finding:
        provider = self.config.providers[provider_name]
        policy = self.config.global_config.unverified
        if not provider.required or policy == "ignore":
            severity = Severity.INFO
        elif policy == "warn":
            severity = Severity.WARNING
        else:
            severity = Severity.ERROR
        return Finding(code="PROV-001", message=message, severity=severity, state=RunState.UNVERIFIED, details={"provider": provider_name})

    def _capture_snapshots(self, planned: list[PlannedContract], *, offline: bool, network: bool) -> tuple[dict[str, ProviderSnapshot], list[Finding], bool]:
        queries_by_provider: dict[str, dict[str, ProviderQuery]] = {}
        capabilities_by_provider: dict[str, set[str]] = {}
        for item in planned:
            queries_by_provider.setdefault(item.provider, {})
            for query in item.queries:
                queries_by_provider[item.provider][query.digest] = query
            capabilities_by_provider.setdefault(item.provider, set()).update(item.handler.required_capabilities)
        snapshots: dict[str, ProviderSnapshot] = {}
        findings: list[Finding] = []
        required_unverified = False
        for provider_name in sorted(queries_by_provider):
            provider_config = self.config.providers[provider_name]
            network_allowed = not provider_config.network
            if provider_config.network:
                network_allowed = False if offline else self.config.global_config.network == "allow" or (self.config.global_config.network == "explicit" and network)
            try:
                if provider_config.network and not network_allowed:
                    if provider_config.snapshot_file:
                        snapshot = load_snapshot_file((self.config.workspace_root / provider_config.snapshot_file).resolve(strict=False), provider=provider_name)
                    else:
                        reason = "offline mode forbids network access" if offline else "network access was not explicitly allowed"
                        raise ProviderUnavailable(provider_name, reason)
                else:
                    plugin = self.registry.provider(provider_config.adapter)
                    validation = plugin.validate_config(provider_config.options)
                    if has_failure(validation):
                        findings.extend(validation)
                        raise ProviderUnavailable(provider_name, "provider configuration is invalid")
                    context = ProviderContext(workspace_root=self.config.workspace_root, provider_name=provider_name, offline=offline, network_allowed=network_allowed)
                    session = plugin.open(context, provider_config.options)
                    try:
                        missing = capabilities_by_provider[provider_name] - set(session.capabilities)
                        if missing:
                            raise ProviderUnavailable(provider_name, f"adapter lacks required capabilities: {', '.join(sorted(missing))}")
                        snapshot = session.capture(tuple(queries_by_provider[provider_name].values()))
                    finally:
                        session.close()
                snapshots[provider_name] = snapshot
            except (ProviderUnavailable, ConfigError) as exc:
                finding = self._provider_unavailable_finding(provider_name, str(exc))
                findings.append(finding)
                if provider_config.required and self.config.global_config.unverified == "fail":
                    required_unverified = True
            except Exception as exc:
                finding = self._provider_unavailable_finding(provider_name, f"provider raised {type(exc).__name__}: {exc}")
                findings.append(finding)
                if provider_config.required and self.config.global_config.unverified == "fail":
                    required_unverified = True
        return snapshots, findings, required_unverified

    def _projection_patch(self, item: PlannedContract, expected: str) -> Patch:
        current = item.document.body(item.block)
        display_path = self._display_path(item.document)
        diff = "".join(
            difflib.unified_diff(
                current.splitlines(keepends=True),
                expected.splitlines(keepends=True),
                fromfile=f"a/{display_path}",
                tofile=f"b/{display_path}",
            )
        )
        return Patch(
            path=display_path,
            absolute_path=item.document.absolute_path,
            start=item.block.body_start,
            end=item.block.body_end,
            old_text=current,
            replacement=expected,
            original_digest=item.document.source_digest,
            contract_id=item.binding.name,
            description="replace managed block body with canonical projection",
            diff=diff,
        )

    def _evaluate(
        self, planned: list[PlannedContract], snapshots: Mapping[str, ProviderSnapshot], *, mode: str, emit_outdated: bool
    ) -> tuple[list[Finding], list[Patch], dict[str, tuple[PlannedContract, ProviderSnapshot, str]]]:
        findings: list[Finding] = []
        patches: list[Patch] = []
        materialized: dict[str, tuple[PlannedContract, ProviderSnapshot, str]] = {}
        for item in planned:
            snapshot = snapshots.get(item.provider)
            if snapshot is None:
                continue
            findings.extend(item.handler.validate(item.binding, item.document, item.block, snapshot))
            if item.binding.mode == "authored":
                continue
            if item.binding.mode == "snapshot" and mode == "verify":
                continue
            try:
                expected = item.handler.render(item.binding, snapshot, item.document.newline)
            except Exception as exc:
                findings.append(Finding(code="CONTRACT-002", message=f"renderer failed: {exc}", severity=item.binding.severity,
                                        path=self._display_path(item.document), line=item.block.start_line, surface=item.document.surface,
                                        contract_id=item.binding.name))
                continue
            materialized[item.binding.name] = (item, snapshot, expected)
            current = item.document.body(item.block)
            if current != expected:
                if emit_outdated:
                    findings.append(
                        Finding(code="DOC-BLOCK-021", message=f"projection differs from provider snapshot {item.provider}@{snapshot.revision}",
                                severity=item.binding.severity, path=self._display_path(item.document), line=item.block.start_line,
                                surface=item.document.surface, contract_id=item.binding.name, remediation=Remediation("command", "locus-md sync --check"))
                    )
                if mode.startswith("sync"):
                    patches.append(self._projection_patch(item, expected))
        return findings, patches, materialized

    def _desired_lock_patch(self, scan: ScanResult, materialized: Mapping[str, tuple[PlannedContract, ProviderSnapshot, str]]) -> Patch | None:
        entries = dict(scan.lock.entries)
        now = utc_now()
        for contract_name, (item, snapshot, expected) in materialized.items():
            existing = entries.get(contract_name)
            candidate = LockEntry(
                surface=item.binding.surface,
                path=item.binding.path,
                block_kind=item.binding.block_kind,
                block_id=item.binding.block_id,
                contract_schema=item.binding.schema,
                renderer=item.binding.renderer,
                provider=item.provider,
                provider_revision=snapshot.revision,
                snapshot_digest=snapshot.content_digest,
                body_digest=digest_text(expected),
                synced_at=now,
            )
            if existing is not None:
                same_except_time = candidate.to_dict() | {"synced_at": existing.synced_at} == existing.to_dict()
                if same_except_time:
                    candidate = LockEntry(**(candidate.to_dict() | {"synced_at": existing.synced_at}))
            entries[contract_name] = candidate
        desired = serialize_lock(entries)
        current = scan.lock.source_text
        if desired == current:
            return None
        path = lock_path(self.config)
        original_raw = path.read_bytes() if path.exists() else b""
        diff = "".join(
            difflib.unified_diff(current.splitlines(keepends=True), desired.splitlines(keepends=True),
                                 fromfile=f"a/{self.config.global_config.lock_file}", tofile=f"b/{self.config.global_config.lock_file}")
        )
        return Patch(path=self.config.global_config.lock_file, absolute_path=path, start=0, end=len(current), old_text=current, replacement=desired,
                     original_digest=digest_bytes(original_raw), description="update projection lock evidence", diff=diff)

    def verify(self, *, surfaces: set[str] | None = None, providers: set[str] | None = None, offline: bool = False, network: bool = False, force_strict: bool = False) -> Report:
        scan = self.scan(surfaces=surfaces, force_strict=force_strict)
        planned = self._plan(scan, providers=providers, surfaces=surfaces)
        snapshots, provider_findings, required_unverified = self._capture_snapshots(planned, offline=offline, network=network)
        contract_findings, _, _ = self._evaluate(planned, snapshots, mode="verify", emit_outdated=True)
        rules = execute_rules(self.config, self.registry, scan.documents, surfaces=surfaces)
        findings = self._strict_findings([*scan.findings, *provider_findings, *contract_findings, *rules.findings], force_strict)
        if has_failure(findings):
            state = RunState.FAILED
        elif required_unverified or rules.required_unverified:
            state = RunState.UNVERIFIED
        else:
            state = RunState.PASSED
        return self._report(
            "verify",
            state,
            findings,
            snapshots=snapshots,
            metadata={
                "document_count": len(scan.documents),
                "contract_count": len(planned),
                "rule_invocation_count": rules.invocation_count,
                "rules": [item.to_dict() for item in rules.provenance],
                "offline": offline,
            },
        )

    def sync(
        self, *, write: bool = False, surfaces: set[str] | None = None, providers: set[str] | None = None, offline: bool = False,
        network: bool = False, force_strict: bool = False
    ) -> Report:
        scan = self.scan(surfaces=surfaces, force_strict=force_strict)
        planned = self._plan(scan, providers=providers, surfaces=surfaces)
        snapshots, provider_findings, required_unverified = self._capture_snapshots(planned, offline=offline, network=network)
        contract_findings, patches, materialized = self._evaluate(planned, snapshots, mode="sync-write" if write else "sync-check", emit_outdated=not write)
        rules = execute_rules(self.config, self.registry, scan.documents, surfaces=surfaces)
        lock_patch = self._desired_lock_patch(scan, materialized)
        if lock_patch:
            patches.append(lock_patch)
        findings = [*scan.findings, *provider_findings, *contract_findings, *rules.findings]
        if write:
            fixable = {"DOC-BLOCK-020", "DOC-BLOCK-021", "DOC-LOCK-003", "DOC-LOCK-004"}
            findings = [finding for finding in findings if finding.code not in fixable]
            if patches and not required_unverified and not rules.required_unverified and not rules.failed:
                written = apply_patches(patches, workspace_root=self.config.workspace_root, lock_path=lock_path(self.config))
                files = [str(path.relative_to(self.config.workspace_root)) for path in written]
                findings.append(Finding(code="SYNC-010", message=f"applied {len(patches)} patch(es) across {len(written)} file(s)",
                                        severity=Severity.INFO, details={"files": files}))
        findings = self._strict_findings(findings, force_strict)
        if has_failure(findings):
            state = RunState.FAILED
        elif required_unverified or rules.required_unverified:
            state = RunState.UNVERIFIED
        elif patches and not write:
            state = RunState.FAILED
        else:
            state = RunState.PASSED
        metadata = {
            "contract_count": len(planned),
            "rule_invocation_count": rules.invocation_count,
            "rules": [item.to_dict() for item in rules.provenance],
            "offline": offline,
            "write": write,
        }
        return self._report("sync-write" if write else "sync-check", state, findings, snapshots=snapshots, patches=patches, metadata=metadata)

    def contracts_list(self, *, surfaces: set[str] | None = None) -> list[dict[str, Any]]:
        scan = self.scan(surfaces=surfaces)
        result: list[dict[str, Any]] = []
        for name, binding in sorted(self.config.contracts.items()):
            if surfaces and binding.surface not in surfaces:
                continue
            found = binding.key in scan.blocks
            lock_entry = scan.lock.entries.get(name)
            result.append(
                {
                    "name": name,
                    "surface": binding.surface,
                    "path": binding.path,
                    "block_kind": binding.block_kind,
                    "block_id": binding.block_id,
                    "schema": binding.schema,
                    "mode": binding.mode,
                    "provider": binding.provider,
                    "renderer": binding.renderer,
                    "found": found,
                    "locked": lock_entry is not None,
                }
            )
        return result

    def _report(
        self, mode: str, state: RunState, findings: list[Finding], *, snapshots: Mapping[str, ProviderSnapshot] | None = None,
        patches: list[Patch] | None = None, metadata: dict[str, Any] | None = None
    ) -> Report:
        return Report(
            run_id=str(uuid.uuid4()),
            mode=mode,
            state=state,
            config_digest=self.config.config_digest,
            config_path=str(self.config.config_path),
            findings=sorted(findings, key=Finding.sort_key),
            snapshots={name: snapshot.metadata() for name, snapshot in (snapshots or {}).items()},
            patches=patches or [],
            metadata=metadata or {},
        )
