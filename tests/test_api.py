from __future__ import annotations

from pathlib import Path

import pytest

import locus_md
import locus_md.api as api
from locus_md import GlobalConfig, SurfaceConfig, WorkspaceConfig, lint_workspace as public_lint_workspace
from locus_md.config import load_config
from locus_md.models import GlobalConfig as ModelGlobalConfig
from locus_md.models import Report, RunState, SurfaceConfig as ModelSurfaceConfig
from locus_md.models import WorkspaceConfig as ModelWorkspaceConfig


def test_public_workspace_types_construct_and_lint_without_loading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text("# Index\n", encoding="utf-8")
    workspace = WorkspaceConfig(
        config_path=tmp_path / ".locus" / "locus-md.toml",
        workspace_root=tmp_path,
        global_config=GlobalConfig(schema=1, surfaces=("docs",)),
        surfaces={
            "docs": SurfaceConfig(
                name="docs",
                root="docs",
                include=("**/*.md",),
                indexes=("index.md",),
                require_reachable=True,
            )
        },
        providers={},
        contracts={},
        rules={},
        config_digest="constructed-for-test",
    )
    monkeypatch.setattr(api, "load_workspace", lambda **_: pytest.fail("embedded lint must not load config"))
    monkeypatch.setattr(api, "load_config", lambda **_: pytest.fail("embedded lint must not parse config"))

    report = public_lint_workspace(workspace)

    assert WorkspaceConfig is ModelWorkspaceConfig
    assert GlobalConfig is ModelGlobalConfig
    assert SurfaceConfig is ModelSurfaceConfig
    assert {"WorkspaceConfig", "GlobalConfig", "SurfaceConfig"}.issubset(locus_md.__all__)
    assert isinstance(report, Report)
    assert report.state == RunState.PASSED


def test_lint_workspace_uses_supplied_config_without_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = Path(__file__).resolve().parents[1] / "examples" / "basic" / ".locus" / "locus-md.toml"
    workspace = load_config(explicit=config_path)
    monkeypatch.setattr(api, "load_workspace", lambda **_: pytest.fail("embedded lint must not load config"))
    monkeypatch.setattr(api, "load_config", lambda **_: pytest.fail("embedded lint must not parse config"))

    report = api.lint_workspace(workspace)

    assert public_lint_workspace is api.lint_workspace
    assert isinstance(report, Report)
    assert report.state == RunState.PASSED


def test_lint_workspace_forwards_surface_and_strict_controls(example_workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = load_config(explicit=example_workspace / ".locus" / "locus-md.toml")
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
    workspace = load_config(explicit=example_workspace / ".locus" / "locus-md.toml")
    legacy = api.lint(config=example_workspace / ".locus" / "locus-md.toml")
    embedded = api.lint_workspace(workspace)

    assert legacy.state == embedded.state
    assert [finding.to_dict() for finding in legacy.sorted_findings()] == [finding.to_dict() for finding in embedded.sorted_findings()]
    assert legacy.metadata == embedded.metadata
