from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .errors import GitError
from .graph import current_reverse_links
from .models import DocumentRecord, WorkspaceConfig
from .utils import is_inside


@dataclass(frozen=True, slots=True)
class ImpactChange:
    status: str
    path: str
    old_path: str | None
    managed: bool
    surface: str | None
    document: str | None
    dependents: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"status": self.status, "path": self.path, "managed": self.managed, "dependents": list(self.dependents)}
        if self.old_path is not None:
            result["old_path"] = self.old_path
        if self.surface is not None:
            result["surface"] = self.surface
        if self.document is not None:
            result["document"] = self.document
        return result


@dataclass(frozen=True, slots=True)
class ImpactReport:
    base: str
    configuration_changed: bool
    changes: tuple[ImpactChange, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "locus-md.impact.v1", "base": self.base, "configuration_changed": self.configuration_changed,
                "changes": [change.to_dict() for change in self.changes]}


def _git(workspace: Path, *args: str) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=workspace, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise GitError("IMPACT-GIT-001", f"git command failed: {detail.strip()}") from exc
    return result.stdout


def _repo_root(workspace: Path) -> Path:
    return Path(_git(workspace, "rev-parse", "--show-toplevel").strip()).resolve()


def _changes(workspace: Path, base: str) -> list[tuple[str, str, str | None]]:
    raw = _git(workspace, "diff", "--name-status", "-z", "--find-renames", base, "--")
    fields = raw.split("\x00")
    result: list[tuple[str, str, str | None]] = []
    index = 0
    while index < len(fields):
        status = fields[index]
        index += 1
        if not status:
            continue
        code = status[0]
        if code in {"R", "C"}:
            if index + 1 >= len(fields):
                raise GitError("IMPACT-GIT-002", "git returned an incomplete rename record")
            old_path, new_path = fields[index], fields[index + 1]
            index += 2
            result.append(("renamed" if code == "R" else "copied", new_path, old_path))
        else:
            if index >= len(fields):
                raise GitError("IMPACT-GIT-002", "git returned an incomplete change record")
            result.append(({"A": "added", "D": "deleted", "M": "changed", "T": "changed"}.get(code, "changed"), fields[index], None))
            index += 1
    untracked = _git(workspace, "ls-files", "--others", "--exclude-standard", "-z").split("\x00")
    known = {path for _, path, old in result for path in (path, old) if path}
    result.extend(("added", path, None) for path in untracked if path and path not in known)
    return result


def _workspace_path(repo_root: Path, workspace: Path, repo_path: str) -> str:
    absolute = (repo_root / repo_path).resolve(strict=False)
    if is_inside(absolute, workspace):
        return absolute.relative_to(workspace.resolve()).as_posix()
    return repo_path.replace("\\", "/")


def _classify(config: WorkspaceConfig, absolute: Path, repo_path: str) -> tuple[bool, str | None, str | None]:
    normalized = absolute.resolve(strict=False)
    for name, document in config.documents.items():
        candidate = (config.workspace_root / config.surfaces[document.surface].root / document.path).resolve(strict=False)
        if candidate == normalized:
            return True, document.surface, name
    for name, surface in config.surfaces.items():
        root = (config.workspace_root / surface.root).resolve(strict=False)
        if is_inside(normalized, root):
            relative = normalized.relative_to(root).as_posix()
            included = any(Path(relative).match(pattern) or (pattern.startswith("**/") and Path(relative).match(pattern[3:])) for pattern in surface.include)
            excluded = any(Path(relative).match(pattern) for pattern in surface.exclude)
            if included and not excluded:
                return True, name, None
    return False, None, None


def build_impact(config: WorkspaceConfig, base: str, documents: Iterable[DocumentRecord]) -> ImpactReport:
    repo_root = _repo_root(config.workspace_root)
    reverse = current_reverse_links(config, {document.key: document for document in documents})
    config_abs = config.config_path.resolve(strict=False)
    changes = _changes(config.workspace_root, base)
    rows: list[ImpactChange] = []
    for status, path, old_path in changes:
        absolute = repo_root / path
        managed, surface, document = _classify(config, absolute, path)
        old_absolute = repo_root / old_path if old_path else None
        if old_absolute is not None:
            old_managed, old_surface, old_document = _classify(config, old_absolute, old_path or "")
            managed = managed or old_managed
            surface = surface or old_surface
            document = document or old_document
        dependents = set(reverse.get(absolute.resolve(strict=False), ()))
        if old_absolute is not None:
            dependents.update(reverse.get(old_absolute.resolve(strict=False), ()))
        rows.append(ImpactChange(status=status, path=_workspace_path(repo_root, config.workspace_root, path),
                                 old_path=_workspace_path(repo_root, config.workspace_root, old_path) if old_path else None,
                                 managed=managed, surface=surface, document=document, dependents=tuple(sorted(dependents))))
    config_paths = {config_abs, config.workspace_root / ".locus" / "locus-md.toml"}
    configuration_changed = any(
        (repo_root / candidate).resolve(strict=False) in config_paths
        for _, path, old in changes
        for candidate in ((path, old) if old else (path,))
    )
    return ImpactReport(base=base, configuration_changed=configuration_changed, changes=tuple(rows))
