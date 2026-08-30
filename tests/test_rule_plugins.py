from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from importlib.resources import files
from pathlib import Path
from typing import Mapping

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from conftest import write_minimal_workspace
from locus_md.cli import main
from locus_md.config import load_config
from locus_md.engine import Engine
from locus_md.errors import ConfigError
from locus_md.models import Finding, Remediation, RunState, Severity
from locus_md.plugins import PluginRegistry
from locus_md.rules import RuleContext, RuleDocument


class RecordingRule:
    api_version = "1"
    plugin_id = "recording"
    plugin_version = "1.0"

    def __init__(self, findings: tuple[Finding, ...] = ()) -> None:
        self.findings = findings
        self.calls: list[tuple[RuleContext, RuleDocument, Mapping[str, object]]] = []
        self.validated: list[Mapping[str, object]] = []

    def validate_config(self, options: Mapping[str, object]) -> None:
        self.validated.append(options)

    def check(
        self,
        context: RuleContext,
        document: RuleDocument,
        options: Mapping[str, object],
    ) -> tuple[Finding, ...]:
        self.calls.append((context, document, options))
        return self.findings


class RaisingRule(RecordingRule):
    def check(self, context: RuleContext, document: RuleDocument, options: Mapping[str, object]):
        raise RuntimeError("boom")


def _append_rule(
    config_path: Path,
    *,
    name: str = "test-rule",
    adapter: str = "recording",
    phase: str = "verify",
    surface: str = "docs",
    options: str = '{ nested = { items = ["one"] } }',
) -> None:
    with config_path.open("a", encoding="utf-8") as handle:
        handle.write(
            f"""
[locus-md.rule.{name}]
adapter = "{adapter}"
phase = "{phase}"
surface = "{surface}"
severity = "warning"
options = {options}
"""
        )


def _engine(config_path: Path, plugin: RecordingRule) -> Engine:
    registry = PluginRegistry(discover=False)
    registry.register_rule("recording", plugin)
    return Engine(load_config(explicit=config_path), registry=registry)


def _packaged_schema(name: str) -> dict:
    schema = files("locus_md").joinpath(f"schemas/{name}.v1.schema.json")
    return json.loads(schema.read_text(encoding="utf-8"))


def _validate_report(payload: dict) -> None:
    finding_schema = _packaged_schema("finding")
    registry = Registry().with_resource(
        finding_schema["$id"], Resource.from_contents(finding_schema)
    )
    Draft202012Validator(_packaged_schema("report"), registry=registry).validate(payload)


def test_rule_phase_is_required_and_verify_only(tmp_path: Path) -> None:
    missing = write_minimal_workspace(tmp_path / "missing")
    _append_rule(missing, phase="")
    with pytest.raises(ConfigError, match="CFG-009"):
        load_config(explicit=missing)

    lint = write_minimal_workspace(tmp_path / "lint")
    _append_rule(lint, phase="lint")
    with pytest.raises(ConfigError, match="phase must be one of"):
        load_config(explicit=lint)


@pytest.mark.parametrize(
    "error",
    [ValueError("unsupported backend"), ConfigError("CFG-PRIVATE-001", "private validation failure")],
)
def test_config_validation_calls_plugin_and_translates_errors(tmp_path: Path, error: Exception) -> None:
    config_path = write_minimal_workspace(tmp_path)
    _append_rule(config_path)

    class InvalidRule(RecordingRule):
        def validate_config(self, options: Mapping[str, object]) -> None:
            raise error

    registry = PluginRegistry(discover=False)
    registry.register_rule("recording", InvalidRule())

    with pytest.raises(ConfigError) as raised:
        registry.validate_references(load_config(explicit=config_path))

    assert raised.value.code == "CFG-038"
    assert raised.value.code != getattr(error, "code", None)
    assert "CFG-PRIVATE" not in raised.value.message
    assert ("unsupported backend" in raised.value.message) or ("private validation failure" in raised.value.message)


def test_rule_inputs_are_immutable_projections(tmp_path: Path) -> None:
    config_path = write_minimal_workspace(tmp_path)
    _append_rule(config_path)
    document_path = tmp_path / "docs" / "index.md"
    document_path.write_text(
        "---\nline_id: demo\nnested:\n  items: [one]\n---\n# Index\n[Task](https://example.invalid/.tasks/T-1/task.md)\n",
        encoding="utf-8",
    )
    plugin = RecordingRule()

    report = _engine(config_path, plugin).verify(offline=True)

    assert report.state == RunState.PASSED
    context, document, options = plugin.calls[0]
    assert context.phase == "verify"
    assert document.display_path == "docs/index.md"
    assert document.links[0].target == "https://example.invalid/.tasks/T-1/task.md"
    assert document.frontmatter is not None
    assert document.frontmatter["nested"]["items"] == ("one",)  # type: ignore[index]
    with pytest.raises(TypeError):
        document.frontmatter["line_id"] = "changed"  # type: ignore[index]
    with pytest.raises(TypeError):
        options["nested"]["items"] = ()  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        document.text = "changed"


def test_lint_skips_rules_and_verify_sync_invoke_once_per_selected_document(tmp_path: Path) -> None:
    config_path = write_minimal_workspace(tmp_path)
    _append_rule(config_path)
    (tmp_path / ".locus" / "docs.lock.json").write_text(
        '{\n  "contracts": {},\n  "schema": "locus-md.lock.v1"\n}\n',
        encoding="utf-8",
    )
    (tmp_path / "docs" / "second.md").write_text("# Second\n", encoding="utf-8")
    plugin = RecordingRule()
    engine = _engine(config_path, plugin)

    engine.lint()
    assert plugin.calls == []

    engine.verify(offline=True)
    assert [call[1].relative_path for call in plugin.calls] == ["index.md", "second.md"]

    plugin.calls.clear()
    check = engine.sync(offline=True)
    assert [call[1].relative_path for call in plugin.calls] == ["index.md", "second.md"]
    assert check.patches == []
    assert check.metadata["rules"][0]["invocation_count"] == 2

    plugin.calls.clear()
    write = engine.sync(write=True, offline=True)
    assert [call[1].relative_path for call in plugin.calls] == ["index.md", "second.md"]
    assert write.metadata["rules"][0]["plugin_version"] == "1.0"


def test_rule_surface_and_cli_surface_filter_limit_documents(tmp_path: Path) -> None:
    config_path = write_minimal_workspace(tmp_path)
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        .replace('surfaces = ["docs"]', 'surfaces = ["docs", "other"]')
        + """
[locus-md.surface.other]
root = "other"
include = ["**/*.md"]
""",
        encoding="utf-8",
    )
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "other.md").write_text("# Other\n", encoding="utf-8")
    _append_rule(config_path, surface="docs")
    plugin = RecordingRule()
    engine = _engine(config_path, plugin)

    filtered = engine.verify(surfaces={"other"}, offline=True)
    assert plugin.calls == []
    assert filtered.metadata["rules"] == [
        {
            "rule": "test-rule",
            "adapter": "recording",
            "plugin_id": "recording",
            "plugin_version": "1.0",
            "invocation_count": 0,
        }
    ]

    report = engine.verify(offline=True)
    assert [call[1].display_path for call in plugin.calls] == ["docs/index.md"]
    assert report.metadata["rules"][0]["invocation_count"] == 1


def test_zero_finding_rule_has_serialized_provenance(tmp_path: Path) -> None:
    config_path = write_minimal_workspace(tmp_path)
    _append_rule(config_path)

    report = _engine(config_path, RecordingRule()).verify(offline=True)
    payload = report.to_dict()

    assert report.findings == []
    assert payload["metadata"]["rules"] == [
        {
            "rule": "test-rule",
            "adapter": "recording",
            "plugin_id": "recording",
            "plugin_version": "1.0",
            "invocation_count": 1,
        }
    ]
    json.dumps(payload)
    _validate_report(payload)


def test_report_schema_validates_lint_verify_and_sync_with_zero_rules(tmp_path: Path) -> None:
    config = load_config(explicit=write_minimal_workspace(tmp_path))
    engine = Engine(config, registry=PluginRegistry(discover=False))

    reports = (engine.lint(), engine.verify(offline=True), engine.sync(offline=True), engine.sync(write=True, offline=True))
    for report in reports:
        if report.mode != "lint":
            assert report.metadata["rules"] == []
        _validate_report(report.to_dict())


def test_report_schema_validates_verify_and_sync_with_multiple_rules(tmp_path: Path) -> None:
    config_path = write_minimal_workspace(tmp_path)
    _append_rule(config_path, name="alpha")
    _append_rule(config_path, name="beta")
    plugin = RecordingRule()
    engine = _engine(config_path, plugin)

    reports = (engine.verify(offline=True), engine.sync(offline=True), engine.sync(write=True, offline=True))
    for report in reports:
        assert [item["rule"] for item in report.metadata["rules"]] == ["alpha", "beta"]
        assert report.metadata["rule_invocation_count"] == 2
        _validate_report(report.to_dict())


def test_rule_findings_are_deterministic_and_receive_document_identity(tmp_path: Path) -> None:
    config_path = write_minimal_workspace(tmp_path)
    _append_rule(config_path)
    plugin = RecordingRule(
        (
            Finding(code="Z-RULE", message="later", severity=Severity.INFO, state=RunState.FAILED),
            Finding(code="A-RULE", message="earlier", severity=Severity.INFO, state=RunState.FAILED),
        )
    )

    report = _engine(config_path, plugin).verify(offline=True)

    assert report.state == RunState.FAILED
    assert [finding.code for finding in report.findings] == ["A-RULE", "Z-RULE"]
    assert all(finding.path == "docs/index.md" for finding in report.findings)
    assert all(finding.surface == "docs" for finding in report.findings)
    assert all(finding.contract_id == "test-rule" for finding in report.findings)
    assert all(finding.severity == Severity.ERROR for finding in report.findings)


def test_external_namespaced_finding_code_is_preserved_and_schema_valid(tmp_path: Path) -> None:
    config_path = write_minimal_workspace(tmp_path)
    _append_rule(config_path)
    plugin = RecordingRule(
        (
            Finding(
                code="vendor.rule.status-invalid",
                message="status is invalid",
                state=RunState.FAILED,
                remediation=Remediation("manual", "Set a documented status."),
            ),
        )
    )

    report = _engine(config_path, plugin).verify(offline=True)

    assert [finding.code for finding in report.findings] == ["vendor.rule.status-invalid"]
    _validate_report(report.to_dict())


@pytest.mark.parametrize(
    "code",
    ["vendor", "vendor.Rule.invalid", "vendor..invalid", "vendor.rule.",
     "vendor.rule.bad_value", "Vendor.rule.invalid", "-RULE"],
)
def test_malformed_finding_code_becomes_rule_002_and_schema_valid(tmp_path: Path, code: str) -> None:
    config_path = write_minimal_workspace(tmp_path)
    _append_rule(config_path)
    plugin = RecordingRule((Finding(code=code, message="bad code", state=RunState.FAILED),))

    report = _engine(config_path, plugin).verify(offline=True)

    assert [finding.code for finding in report.findings] == ["RULE-002"]
    _validate_report(report.to_dict())


def test_rule_provenance_cannot_be_replaced_by_plugin_details(tmp_path: Path) -> None:
    config_path = write_minimal_workspace(tmp_path)
    _append_rule(config_path)
    plugin = RecordingRule(
        (
            Finding(
                code="RULE-DOC-001",
                message="invalid document",
                state=RunState.FAILED,
                details={
                    "rule": "spoofed-rule",
                    "adapter": "spoofed-adapter",
                    "plugin_id": "spoofed-plugin",
                    "plugin_version": "999",
                    "consumer_detail": "preserved",
                },
            ),
        )
    )

    report = _engine(config_path, plugin).verify(offline=True)

    assert report.findings[0].details == {
        "rule": "test-rule",
        "adapter": "recording",
        "plugin_id": "recording",
        "plugin_version": "1.0",
        "consumer_detail": "preserved",
    }


@pytest.mark.parametrize(
    ("policy", "expected_state", "expected_severity", "write_allowed"),
    [
        ("fail", RunState.UNVERIFIED, Severity.ERROR, False),
        ("warn", RunState.PASSED, Severity.WARNING, True),
        ("ignore", RunState.PASSED, Severity.INFO, True),
    ],
)
def test_unverified_policy_controls_sync_write(
    example_workspace: Path,
    policy: str,
    expected_state: RunState,
    expected_severity: Severity,
    write_allowed: bool,
) -> None:
    config_path = example_workspace / ".locus" / "locus-md.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
            .replace('unverified = "fail"', f'unverified = "{policy}"')
        .replace("strict = true", "strict = false"),
        encoding="utf-8",
    )
    _append_rule(config_path)
    tasks_path = example_workspace / "data" / "tasks.json"
    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8").replace('"status": "doing"', '"status": "done"'),
        encoding="utf-8",
    )
    document_path = example_workspace / "docs" / "milestones.md"
    before = document_path.read_bytes()
    plugin = RecordingRule(
        (Finding(code="RULE-EVIDENCE-001", message="missing evidence", state=RunState.UNVERIFIED),)
    )

    report = _engine(config_path, plugin).sync(write=True, offline=True)

    assert report.state == expected_state
    rule_findings = [finding for finding in report.findings if finding.code == "RULE-EVIDENCE-001"]
    assert rule_findings
    assert {finding.severity for finding in rule_findings} == {expected_severity}
    assert (document_path.read_bytes() != before) is write_allowed


def test_strict_promotes_rule_warning_without_changing_unverified_state(example_workspace: Path) -> None:
    config_path = example_workspace / ".locus" / "locus-md.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace('unverified = "fail"', 'unverified = "warn"'),
        encoding="utf-8",
    )
    _append_rule(config_path)
    plugin = RecordingRule(
        (Finding(code="RULE-EVIDENCE-001", message="missing evidence", state=RunState.UNVERIFIED),)
    )

    report = _engine(config_path, plugin).verify(offline=True)

    assert report.state == RunState.PASSED
    rule_findings = [finding for finding in report.findings if finding.code == "RULE-EVIDENCE-001"]
    assert {finding.severity for finding in rule_findings} == {Severity.ERROR}


@pytest.mark.parametrize("policy", ["fail", "warn", "ignore"])
def test_failed_rule_always_blocks_sync_write(example_workspace: Path, policy: str) -> None:
    config_path = example_workspace / ".locus" / "locus-md.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace("unverified = fail", f"unverified = {policy}"),
        encoding="utf-8",
    )
    _append_rule(config_path)
    tasks_path = example_workspace / "data" / "tasks.json"
    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8").replace('"status": "doing"', '"status": "done"'),
        encoding="utf-8",
    )
    document_path = example_workspace / "docs" / "milestones.md"
    before = document_path.read_bytes()
    plugin = RecordingRule((Finding(code="RULE-DOC-001", message="invalid document", state=RunState.FAILED),))

    report = _engine(config_path, plugin).sync(write=True, offline=True)

    assert report.state == RunState.FAILED
    assert document_path.read_bytes() == before


def test_plugin_exception_is_a_stable_failure(tmp_path: Path) -> None:
    config_path = write_minimal_workspace(tmp_path)
    _append_rule(config_path)

    report = _engine(config_path, RaisingRule()).verify(offline=True)

    assert report.state == RunState.FAILED
    assert [finding.code for finding in report.findings] == ["RULE-001"]
    assert report.findings[0].state == RunState.FAILED


def test_rule_cannot_return_implicit_state(tmp_path: Path) -> None:
    config_path = write_minimal_workspace(tmp_path)
    _append_rule(config_path)
    plugin = RecordingRule((Finding(code="RULE-BAD", message="missing state"),))

    report = _engine(config_path, plugin).verify(offline=True)

    assert report.state == RunState.FAILED
    assert [finding.code for finding in report.findings] == ["RULE-002"]


@pytest.mark.parametrize(
    "malformed",
    [
        Finding(code="RULE-BAD", message="bad", state=RunState.FAILED, details=object()),  # type: ignore[arg-type]
        Finding(code="RULE-BAD", message="bad", state=RunState.FAILED, details={"bad": object()}),
        Finding(code="RULE-BAD", message="bad", state=RunState.FAILED, severity="error"),  # type: ignore[arg-type]
        Finding(code="RULE-BAD", message="bad", state="failed"),  # type: ignore[arg-type]
        Finding(code="RULE-BAD", message="bad", state=RunState.FAILED, line="1"),  # type: ignore[arg-type]
        Finding(code="RULE-BAD", message="bad", state=RunState.FAILED, remediation=object()),  # type: ignore[arg-type]
        Finding(code="RULE-BAD", message="bad", state=RunState.FAILED, remediation=Remediation("other", "fix")),
    ],
)
def test_malformed_finding_fields_become_serializable_rule_002(tmp_path: Path, malformed: Finding) -> None:
    config_path = write_minimal_workspace(tmp_path)
    _append_rule(config_path)

    report = _engine(config_path, RecordingRule((malformed,))).verify(offline=True)

    assert report.state == RunState.FAILED
    assert [finding.code for finding in report.findings] == ["RULE-002"]
    assert report.findings[0].state == RunState.FAILED
    json.dumps(report.to_dict())


def test_cli_serializes_malformed_finding_as_rule_002(tmp_path: Path, monkeypatch, capsys) -> None:
    config_path = write_minimal_workspace(tmp_path)
    _append_rule(config_path)
    plugin = RecordingRule(
        (Finding(code="RULE-BAD", message="bad", state=RunState.FAILED, details=object()),)  # type: ignore[arg-type]
    )
    registry = PluginRegistry(discover=False)
    registry.register_rule("recording", plugin)
    monkeypatch.setattr("locus_md.cli.PluginRegistry", lambda: registry)

    exit_code = main(["--config", str(config_path), "--format", "json", "verify", "--offline"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert captured.err == ""
    assert payload["state"] == "failed"
    assert [finding["code"] for finding in payload["findings"]] == ["RULE-002"]
