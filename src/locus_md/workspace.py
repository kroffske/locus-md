from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Iterable

from .models import Finding, Severity, SurfaceConfig, WorkspaceConfig
from .utils import display_surface_path, is_inside


def _matches_any(path: str, patterns: Iterable[str]) -> bool:
    pure = PurePosixPath(path)
    return any(pure.match(pattern) or (pattern.startswith("**/") and pure.match(pattern[3:])) for pattern in patterns)


def inventory_surface(config: WorkspaceConfig, surface: SurfaceConfig) -> tuple[list[tuple[str, Path]], list[Finding]]:
    findings: list[Finding] = []
    root = (config.workspace_root / surface.root).resolve(strict=False)
    if not root.exists():
        return [], [Finding(code="DOC-ENV-100", message=f"surface root does not exist: {surface.root}", severity=Severity.ERROR, path=surface.root, surface=surface.name)]
    if not root.is_dir():
        return [], [Finding(code="DOC-ENV-101", message=f"surface root is not a directory: {surface.root}", severity=Severity.ERROR, path=surface.root, surface=surface.name)]
    candidates: dict[str, Path] = {}
    for pattern in surface.include:
        try:
            matches = root.glob(pattern)
        except ValueError as exc:
            findings.append(Finding(code="CFG-011", message=f"invalid include glob {pattern!r}: {exc}", severity=Severity.ERROR, surface=surface.name))
            continue
        for candidate in matches:
            if not candidate.is_file():
                continue
            try:
                relative = candidate.relative_to(root).as_posix()
            except ValueError:
                continue
            if _matches_any(relative, surface.exclude):
                continue
            if candidate.is_symlink() and not surface.follow_symlinks:
                findings.append(Finding(code="DOC-ENV-102", message="symlinked document skipped because follow_symlinks=false",
                                        severity=Severity.WARNING, path=display_surface_path(surface.root, relative), surface=surface.name))
                continue
            resolved = candidate.resolve(strict=False)
            if not is_inside(resolved, config.workspace_root):
                findings.append(Finding(code="DOC-ENV-103", message="document resolves outside the workspace", severity=Severity.ERROR,
                                        path=display_surface_path(surface.root, relative), surface=surface.name))
                continue
            candidates[relative] = candidate
    return sorted(candidates.items()), findings


def inventory_workspace(config: WorkspaceConfig, surfaces: set[str] | None = None) -> tuple[list[tuple[SurfaceConfig, str, Path]], list[Finding]]:
    inventory: list[tuple[SurfaceConfig, str, Path]] = []
    findings: list[Finding] = []
    selected = surfaces or set(config.global_config.surfaces)
    for name in config.global_config.surfaces:
        if name not in selected:
            continue
        surface = config.surfaces[name]
        files, surface_findings = inventory_surface(config, surface)
        findings.extend(surface_findings)
        inventory.extend((surface, relative, path) for relative, path in files)
    return inventory, findings
