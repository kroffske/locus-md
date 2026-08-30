from __future__ import annotations

from pathlib import Path

import pytest

import locus_md.api as api
from locus_md import lint_workspace as public_lint_workspace
from locus_md.config import load_config
from locus_md.models import Report, RunState


def test_lint_workspace_uses_supplied_config_without_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = Path(__file__).resolve().parents[1] / "examples" / "basic" / ".locus" / "config.ini"
    workspace = load_config(explicit=config_path)
    monkeypatch.setattr(api, "load_workspace", lambda **_: pytest.fail("embedded lint must not load config"))
    monkeypatch.setattr(api, "load_config", lambda **_: pytest.fail("embedded lint must not parse config"))

    report = api.lint_workspace(workspace)

    assert public_lint_workspace is api.lint_workspace
    assert isinstance(report, Report)
    assert report.state == RunState.PASSED


def test_lint_workspace_forwards_surface_and_strict_controls(example_workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = load_config(explicit=example_workspace / ".locus" / "config.ini")
    registry = object()
    captured: dict[str, object] = {}

    class RecordingEngine:
        def __init__(self, supplied: object, *, registry: object | None) -> None:
            captured["workspace"] = supplied
            captured["registry"] = registry

        def lint(self, *, surfaces: set[str] | None, force_strict: bool) -> Report:
            captured["surfaces"] = surfaces
            captured["force_strict"] = force_strict
            return Report("run", "lint", RunState.PASSED, workspace.config_digest, str(workspace.config_path))

    monkeypatch.setattr(api, "Engine", RecordingEngine)

    report = api.lint_workspace(workspace, surfaces={"other"}, strict=True, registry=registry)

    assert isinstance(report, Report)
    assert report.mode == "lint"
    assert captured == {
        "workspace": workspace,
        "registry": registry,
        "surfaces": {"other"},
        "force_strict": True,
    }


def test_lint_and_lint_workspace_have_matching_reports(example_workspace: Path) -> None:
    workspace = load_config(explicit=example_workspace / ".locus" / "config.ini")
    legacy = api.lint(config=example_workspace / ".locus" / "config.ini")
    embedded = api.lint_workspace(workspace)

    assert legacy.state == embedded.state
    assert [finding.to_dict() for finding in legacy.sorted_findings()] == [finding.to_dict() for finding in embedded.sorted_findings()]
    assert legacy.metadata == embedded.metadata
