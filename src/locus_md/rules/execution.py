from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from typing import Mapping

from ..models import DocumentRecord, Finding, Remediation, RuleConfig, RunState, Severity, WorkspaceConfig
from ..plugins import PluginRegistry
from .api import RuleContext, RuleDocument, RuleLink, RulePlugin, readonly_mapping

_SEVERITY_RANK = {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2, Severity.FATAL: 3}
_FINDING_CODE = re.compile(
    r"(?:[A-Z][A-Z0-9-]*|[a-z][a-z0-9]*(?:\.[a-z][a-z0-9-]*)+)$"
)


class InvalidRuleFinding(ValueError):
    """A plugin returned a Finding that cannot satisfy the public report contract."""


@dataclass(frozen=True, slots=True)
class _RuleAdapterSnapshot:
    plugin: RulePlugin
    plugin_id: str
    plugin_version: str


@dataclass(frozen=True, slots=True)
class RuleProvenance:
    rule: str
    adapter: str
    plugin_id: str
    plugin_version: str
    invocation_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "rule": self.rule,
            "adapter": self.adapter,
            "plugin_id": self.plugin_id,
            "plugin_version": self.plugin_version,
            "invocation_count": self.invocation_count,
        }


@dataclass(frozen=True, slots=True)
class RuleExecution:
    findings: tuple[Finding, ...]
    required_unverified: bool
    failed: bool
    invocation_count: int
    provenance: tuple[RuleProvenance, ...]


def _project_document(config: WorkspaceConfig, document: DocumentRecord) -> RuleDocument:
    frontmatter = document.frontmatter.data
    root = config.surfaces[document.surface].root
    return RuleDocument(
        surface=document.surface,
        relative_path=document.relative_path,
        display_path=f"{root}/{document.relative_path}",
        text=document.text,
        frontmatter=readonly_mapping(frontmatter) if frontmatter is not None else None,
        links=tuple(
            RuleLink(target=link.target, line=link.line, column=link.column, image=link.image)
            for link in document.links
        ),
    )


def _provenance_details(rule: RuleConfig, adapter: _RuleAdapterSnapshot) -> dict[str, str]:
    return {
        "rule": rule.name,
        "adapter": rule.adapter,
        "plugin_id": adapter.plugin_id,
        "plugin_version": adapter.plugin_version,
    }


def _failure(
    rule: RuleConfig,
    adapter: _RuleAdapterSnapshot,
    document: RuleDocument,
    code: str,
    message: str,
) -> Finding:
    return Finding(
        code=code,
        message=message,
        severity=Severity.ERROR,
        path=document.display_path,
        surface=document.surface,
        contract_id=rule.name,
        state=RunState.FAILED,
        details=_provenance_details(rule, adapter),
    )


def _optional_string(value: object, field: str) -> None:
    if value is not None and not isinstance(value, str):
        raise InvalidRuleFinding(f"{field} must be a string or None")


def _positive_integer(value: object, field: str) -> None:
    if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 1):
        raise InvalidRuleFinding(f"{field} must be a positive integer or None")


def _validated_details(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise InvalidRuleFinding("details must be a mapping")
    try:
        details = dict(value)
    except Exception as exc:
        raise InvalidRuleFinding(f"details cannot be materialized: {type(exc).__name__}: {exc}") from exc
    if any(not isinstance(key, str) for key in details):
        raise InvalidRuleFinding("details keys must be strings")
    try:
        json.dumps(details, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise InvalidRuleFinding(f"details must be JSON-serializable: {exc}") from exc
    return details


def _validate_remediation(value: object) -> None:
    if value is None:
        return
    if not isinstance(value, Remediation):
        raise InvalidRuleFinding("remediation must be a Remediation or None")
    if value.kind not in {"command", "config", "manual"}:
        raise InvalidRuleFinding("remediation.kind must be command, config, or manual")
    if not isinstance(value.value, str) or not value.value:
        raise InvalidRuleFinding("remediation.value must be a non-empty string")


def _validated_finding(finding: Finding) -> Finding:
    if not isinstance(finding.code, str) or not _FINDING_CODE.fullmatch(finding.code):
        raise InvalidRuleFinding(
            "code must match ^[A-Z][A-Z0-9-]*$ or "
            "^[a-z][a-z0-9]*(?:\\.[a-z][a-z0-9-]*)+$"
        )
    if not isinstance(finding.message, str) or not finding.message:
        raise InvalidRuleFinding("message must be a non-empty string")
    if not isinstance(finding.severity, Severity):
        raise InvalidRuleFinding("severity must be a Severity")
    if not isinstance(finding.state, RunState) or finding.state not in {RunState.FAILED, RunState.UNVERIFIED}:
        raise InvalidRuleFinding("state must be failed or unverified")
    for field in ("path", "surface", "contract_id"):
        _optional_string(getattr(finding, field), field)
    _positive_integer(finding.line, "line")
    _positive_integer(finding.column, "column")
    _validate_remediation(finding.remediation)
    return replace(finding, details=_validated_details(finding.details))


def _normalize(
    config: WorkspaceConfig,
    rule: RuleConfig,
    adapter: _RuleAdapterSnapshot,
    document: RuleDocument,
    finding: Finding,
) -> Finding:
    finding = _validated_finding(finding)
    if finding.state == RunState.UNVERIFIED:
        severity = {
            "fail": Severity.ERROR,
            "warn": Severity.WARNING,
            "ignore": Severity.INFO,
        }[config.global_config.unverified]
    else:
        severity = max((finding.severity, rule.severity, Severity.ERROR), key=_SEVERITY_RANK.__getitem__)
    return replace(
        finding,
        severity=severity,
        path=finding.path or document.display_path,
        surface=finding.surface or document.surface,
        contract_id=finding.contract_id or rule.name,
        details={**dict(finding.details), **_provenance_details(rule, adapter)},
    )


def _check_document(
    config: WorkspaceConfig,
    adapter: _RuleAdapterSnapshot,
    rule: RuleConfig,
    context: RuleContext,
    document: RuleDocument,
    options: Mapping[str, object],
) -> tuple[Finding, ...]:
    try:
        returned = adapter.plugin.check(context, document, options)
    except Exception as exc:
        return (
            _failure(
                rule,
                adapter,
                document,
                "RULE-001",
                f"rule {rule.name!r} raised {type(exc).__name__}: {exc}",
            ),
        )
    try:
        findings = tuple(returned)
    except Exception as exc:
        message = f"rule {rule.name!r} returned invalid findings: {type(exc).__name__}: {exc}"
        return (_failure(rule, adapter, document, "RULE-002", message),)
    if any(not isinstance(item, Finding) for item in findings):
        message = f"rule {rule.name!r} returned a non-Finding value"
        return (_failure(rule, adapter, document, "RULE-002", message),)
    try:
        return tuple(
            _normalize(config, rule, adapter, document, finding)
            for finding in findings
        )
    except InvalidRuleFinding as exc:
        message = f"rule {rule.name!r} returned an invalid Finding: {exc}"
        return (_failure(rule, adapter, document, "RULE-002", message),)


def execute_rules(
    config: WorkspaceConfig,
    registry: PluginRegistry,
    documents: Mapping[tuple[str, str], DocumentRecord],
    *,
    surfaces: set[str] | None,
) -> RuleExecution:
    selected_surfaces = surfaces or set(config.global_config.surfaces)
    findings: list[Finding] = []
    provenance: list[RuleProvenance] = []
    invocation_count = 0
    resolved_adapters: dict[str, _RuleAdapterSnapshot] = {}
    for adapter_name in sorted({rule.adapter for rule in config.rules.values()}):
        plugin, plugin_id, plugin_version = registry.resolve_rule(adapter_name)
        resolved_adapters[adapter_name] = _RuleAdapterSnapshot(plugin, plugin_id, plugin_version)
    for _, rule in sorted(config.rules.items()):
        rule_invocations = 0
        adapter = resolved_adapters[rule.adapter]
        if rule.surface is not None and rule.surface not in selected_surfaces:
            provenance.append(
                RuleProvenance(rule.name, rule.adapter, adapter.plugin_id, adapter.plugin_version, 0)
            )
            continue
        context = RuleContext(
            workspace_root=config.workspace_root,
            rule_name=rule.name,
            phase="verify",
            surface=rule.surface,
            severity=rule.severity,
        )
        options = readonly_mapping(rule.options)
        selected_documents = (
            document
            for key, document in sorted(documents.items())
            if key[0] in selected_surfaces and (rule.surface is None or key[0] == rule.surface)
        )
        for record in selected_documents:
            document = _project_document(config, record)
            invocation_count += 1
            rule_invocations += 1
            findings.extend(
                _check_document(
                    config,
                    adapter,
                    rule,
                    context,
                    document,
                    options,
                )
            )
        provenance.append(
            RuleProvenance(
                rule.name,
                rule.adapter,
                adapter.plugin_id,
                adapter.plugin_version,
                rule_invocations,
            )
        )
    failed = any(finding.state == RunState.FAILED for finding in findings)
    required_unverified = config.global_config.unverified == "fail" and any(
        finding.state == RunState.UNVERIFIED for finding in findings
    )
    return RuleExecution(tuple(findings), required_unverified, failed, invocation_count, tuple(provenance))
