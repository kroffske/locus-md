from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .models import DocumentRecord, Finding, Severity, WorkspaceConfig
from .utils import is_inside

_EXTERNAL_SCHEMES = {"http", "https", "mailto", "ftp", "ftps", "ssh", "tel", "data"}


def validate_graph(config: WorkspaceConfig, documents: dict[tuple[str, str], DocumentRecord], *, selected_surfaces: set[str] | None = None) -> list[Finding]:
    findings: list[Finding] = []
    absolute_index: dict[Path, tuple[str, str]] = {document.absolute_path.resolve(strict=False): key for key, document in documents.items()}
    adjacency: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    canonical_ids: dict[str, tuple[str, str]] = {}
    for key, document in documents.items():
        display_path = f"{config.surfaces[document.surface].root}/{document.relative_path}"
        data = document.frontmatter.data or {}
        doc_id = data.get("id") if isinstance(data, dict) else None
        if isinstance(doc_id, str) and doc_id:
            if doc_id in canonical_ids:
                other = canonical_ids[doc_id]
                findings.append(Finding(code="DOC-ENV-020", message=f"duplicate canonical document id {doc_id!r}; first declared by {other[0]}:{other[1]}",
                                        severity=Severity.ERROR, path=display_path, surface=document.surface))
            else:
                canonical_ids[doc_id] = key
        surface = config.surfaces[document.surface]
        for link in document.links:
            parsed = urlsplit(link.target)
            scheme = parsed.scheme.lower()
            if scheme in _EXTERNAL_SCHEMES or link.target.startswith("//"):
                if not surface.allow_external_links:
                    findings.append(Finding(code="DOC-LINK-010", message=f"external link is forbidden on this surface: {link.target}", severity=Severity.ERROR,
                                            path=display_path, line=link.line, column=link.column, surface=document.surface))
                continue
            if scheme == "locus":
                continue
            if scheme and len(scheme) > 1:
                findings.append(Finding(code="DOC-LINK-011", message=f"unsupported link scheme {scheme!r}: {link.target}", severity=Severity.WARNING,
                                        path=display_path, line=link.line, column=link.column, surface=document.surface))
                continue
            path_part = unquote(parsed.path)
            if not path_part:
                continue
            if path_part.startswith("/"):
                target = config.workspace_root / path_part.lstrip("/")
            else:
                target = document.absolute_path.parent / path_part
            target = target.resolve(strict=False)
            if not is_inside(target, config.workspace_root):
                findings.append(Finding(code="DOC-LINK-002", message=f"link target escapes the workspace: {link.target}", severity=Severity.ERROR,
                                        path=display_path, line=link.line, column=link.column, surface=document.surface))
                continue
            if not target.exists():
                findings.append(Finding(code="DOC-LINK-001", message=f"local link target does not exist: {link.target}", severity=Severity.ERROR,
                                        path=display_path, line=link.line, column=link.column, surface=document.surface))
                continue
            graph_target = target
            if target.is_dir():
                for index_name in ("index.md", "README.md"):
                    candidate = target / index_name
                    if candidate.exists():
                        graph_target = candidate.resolve(strict=False)
                        break
            target_key = absolute_index.get(graph_target)
            if target_key:
                adjacency[key].add(target_key)

    roots: list[tuple[str, str]] = []
    active_surfaces = selected_surfaces or set(config.global_config.surfaces)
    for surface_name in config.global_config.surfaces:
        if surface_name not in active_surfaces:
            continue
        surface = config.surfaces[surface_name]
        if not surface.require_reachable:
            continue
        if not surface.indexes:
            findings.append(Finding(code="DOC-LINK-021", message="require_reachable=true but no index is configured", severity=Severity.ERROR,
                                    path=surface.root, surface=surface_name))
            continue
        for index_path in surface.indexes:
            key = (surface_name, index_path)
            if key not in documents:
                findings.append(Finding(code="DOC-LINK-022", message=f"configured index does not exist in the surface inventory: {index_path}",
                                        severity=Severity.ERROR, path=f"{surface.root}/{index_path}", surface=surface_name))
            else:
                roots.append(key)
    reachable: set[tuple[str, str]] = set()
    queue: deque[tuple[str, str]] = deque(roots)
    while queue:
        current = queue.popleft()
        if current in reachable:
            continue
        reachable.add(current)
        queue.extend(sorted(adjacency.get(current, ())))
    for key, document in documents.items():
        surface = config.surfaces[document.surface]
        if document.surface in active_surfaces and surface.require_reachable and key not in reachable:
            findings.append(Finding(code="DOC-LINK-020", message="document is not reachable from a configured index", severity=Severity.WARNING,
                                    path=f"{surface.root}/{document.relative_path}", surface=document.surface))
    return findings
