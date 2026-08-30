from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

import yaml
from jsonschema import Draft202012Validator
from markdown_it import MarkdownIt

from .models import DocumentRecord, Finding, FrontmatterRecord, LinkRecord, ManagedBlock, Severity, SurfaceConfig, WorkspaceConfig
from .utils import digest_bytes, display_surface_path

_MARKER_RE = re.compile(r"^\s*<!--\s*locus:([a-z][a-z0-9-]{0,31})\s+([a-z0-9][a-z0-9._-]{0,31})\s+(begin|end)\s*-->\s*$")
_LOCUS_COMMENT_RE = re.compile(r"<!--\s*locus:", re.IGNORECASE)
_FENCE_OPEN_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")


def normalize_heading(value: str) -> str:
    return " ".join(value.split())


def extract_headings(text: str) -> tuple[str, ...]:
    """Return visible heading text using markdown-it's token stream."""
    headings: list[str] = []
    tokens = MarkdownIt("commonmark").parse(text)
    for index, token in enumerate(tokens):
        if token.type != "heading_open" or index + 1 >= len(tokens):
            continue
        inline = tokens[index + 1]
        if inline.type != "inline" or not inline.children:
            continue
        visible = "".join(child.content if child.type != "softbreak" else " " for child in inline.children)
        normalized = normalize_heading(visible)
        if normalized:
            headings.append(normalized)
    return tuple(headings)


class _NoTimestampSafeLoader(yaml.SafeLoader):
    pass


_NoTimestampSafeLoader.yaml_implicit_resolvers = {
    key: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:timestamp"] for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _line_without_newline(line: str) -> str:
    if line.endswith("\r\n"):
        return line[:-2]
    if line.endswith("\n") or line.endswith("\r"):
        return line[:-1]
    return line


def _detect_newline(text: str) -> str:
    crlf = text.count("\r\n")
    bare_lf = text.count("\n") - crlf
    return "\r\n" if crlf > bare_lf else "\n"


def _external_schema_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str) and not ref.startswith("#"):
            refs.append(ref)
        for item in value.values():
            refs.extend(_external_schema_refs(item))
    elif isinstance(value, list):
        for item in value:
            refs.extend(_external_schema_refs(item))
    return refs


def parse_frontmatter(text: str, surface: SurfaceConfig, config: WorkspaceConfig, relative_path: str) -> tuple[FrontmatterRecord, list[Finding]]:
    findings: list[Finding] = []
    lines = text.splitlines(keepends=True)
    has_frontmatter = bool(lines and _line_without_newline(lines[0]).strip() == "---")
    display_path = display_surface_path(surface.root, relative_path)
    declaration = next((item for item in config.documents.values() if item.surface == surface.name and item.path == relative_path), None)
    envelope_exception = declaration is not None and surface.name == "root" and relative_path == "AGENTS.md"
    frontmatter_required = False if envelope_exception else bool(declaration) or surface.frontmatter == "required"
    if not has_frontmatter:
        if frontmatter_required:
            findings.append(Finding(code="DOC-ENV-001", message="frontmatter is required", severity=Severity.ERROR, path=display_path, line=1, surface=surface.name))
        return FrontmatterRecord(data=None), findings
    if surface.frontmatter == "forbidden":
        findings.append(Finding(code="DOC-ENV-003", message="frontmatter is forbidden on this surface", severity=Severity.ERROR, path=display_path, line=1, surface=surface.name))
    closing_index: int | None = None
    for index in range(1, len(lines)):
        if _line_without_newline(lines[index]).strip() in {"---", "..."}:
            closing_index = index
            break
    if closing_index is None:
        findings.append(Finding(code="DOC-ENV-002", message="frontmatter opening delimiter has no closing delimiter", severity=Severity.ERROR,
                                path=display_path, line=1, surface=surface.name))
        return FrontmatterRecord(data=None), findings
    start = len(lines[0])
    end_content = sum(len(line) for line in lines[:closing_index])
    span_end = sum(len(line) for line in lines[: closing_index + 1])
    raw = text[start:end_content]
    try:
        parsed = yaml.load(raw, Loader=_NoTimestampSafeLoader)
    except yaml.YAMLError as exc:
        findings.append(Finding(code="DOC-ENV-004", message=f"invalid YAML frontmatter: {exc}", severity=Severity.ERROR, path=display_path, line=1, surface=surface.name))
        return FrontmatterRecord(data=None, span_start=0, span_end=span_end), findings
    if parsed is None:
        parsed = {}
    if not isinstance(parsed, dict):
        findings.append(Finding(code="DOC-ENV-005", message="frontmatter must be a YAML mapping", severity=Severity.ERROR, path=display_path, line=1, surface=surface.name))
        return FrontmatterRecord(data=None, span_start=0, span_end=span_end), findings
    data: Mapping[str, Any] = parsed
    if surface.frontmatter_schema:
        schema_path = (config.workspace_root / surface.frontmatter_schema).resolve(strict=False)
        try:
            import json

            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            external_refs = _external_schema_refs(schema)
            if external_refs:
                message = f"frontmatter schema contains external $ref values, which are disabled: {', '.join(sorted(set(external_refs)))}"
                findings.append(Finding(code="CFG-014", message=message, severity=Severity.ERROR, path=display_path, surface=surface.name))
                return FrontmatterRecord(data=data, span_start=0, span_end=span_end), findings
            validator = Draft202012Validator(schema)
            for error in sorted(validator.iter_errors(data), key=lambda item: (list(item.absolute_path), item.message)):
                location = ".".join(str(part) for part in error.absolute_path)
                suffix = f" at {location}" if location else ""
                findings.append(Finding(code="DOC-ENV-010", message=f"frontmatter schema violation{suffix}: {error.message}", severity=Severity.ERROR,
                                        path=display_path, line=1, surface=surface.name))
        except FileNotFoundError:
            findings.append(Finding(code="CFG-012", message=f"frontmatter schema file not found: {surface.frontmatter_schema}",
                                    severity=Severity.ERROR, path=display_path, surface=surface.name))
        except (OSError, ValueError) as exc:
            findings.append(Finding(code="CFG-013", message=f"cannot load frontmatter schema {surface.frontmatter_schema}: {exc}",
                                    severity=Severity.ERROR, path=display_path, surface=surface.name))
    return FrontmatterRecord(data=data, span_start=0, span_end=span_end), findings


def scan_managed_blocks(text: str, *, display_path: str, surface_name: str) -> tuple[tuple[ManagedBlock, ...], list[Finding]]:
    lines = text.splitlines(keepends=True)
    findings: list[Finding] = []
    blocks: list[ManagedBlock] = []
    seen: set[tuple[str, str]] = set()
    active: tuple[str, str, int, int, int] | None = None
    offset = 0
    fence_char: str | None = None
    fence_length = 0
    for line_number, line in enumerate(lines, start=1):
        content = _line_without_newline(line)
        stripped = content.lstrip(" ")
        leading_spaces = len(content) - len(stripped)
        if fence_char is not None:
            close_re = re.compile(rf"^ {{0,3}}{re.escape(fence_char)}{{{fence_length},}}\s*$")
            if close_re.match(content):
                fence_char = None
                fence_length = 0
            offset += len(line)
            continue
        fence_match = _FENCE_OPEN_RE.match(content)
        if fence_match and leading_spaces <= 3:
            fence = fence_match.group(2)
            fence_char = fence[0]
            fence_length = len(fence)
            offset += len(line)
            continue
        marker_match = _MARKER_RE.match(content)
        if marker_match:
            kind, block_id, boundary = marker_match.groups()
            key = (kind, block_id)
            if boundary == "begin":
                if active is not None:
                    findings.append(Finding(code="DOC-BLOCK-002", message=f"nested block {kind}/{block_id} inside {active[0]}/{active[1]} is forbidden",
                                            severity=Severity.ERROR, path=display_path, line=line_number, surface=surface_name))
                elif key in seen:
                    findings.append(Finding(code="DOC-BLOCK-003", message=f"duplicate block {kind}/{block_id}", severity=Severity.ERROR,
                                            path=display_path, line=line_number, surface=surface_name))
                else:
                    active = (kind, block_id, offset, offset + len(line), line_number)
                    seen.add(key)
            elif active is None:
                findings.append(Finding(code="DOC-BLOCK-004", message=f"end marker {kind}/{block_id} has no matching begin marker",
                                        severity=Severity.ERROR, path=display_path, line=line_number, surface=surface_name))
            elif (active[0], active[1]) != key:
                findings.append(Finding(code="DOC-BLOCK-005", message=f"end marker {kind}/{block_id} does not match active block {active[0]}/{active[1]}",
                                        severity=Severity.ERROR, path=display_path, line=line_number, surface=surface_name))
                active = None
            else:
                blocks.append(
                    ManagedBlock(
                        kind=kind,
                        block_id=block_id,
                        start_marker_start=active[2],
                        start_marker_end=active[3],
                        body_start=active[3],
                        body_end=offset,
                        end_marker_start=offset,
                        end_marker_end=offset + len(line),
                        start_line=active[4],
                        end_line=line_number,
                    )
                )
                active = None
        elif _LOCUS_COMMENT_RE.search(content):
            findings.append(Finding(code="DOC-BLOCK-006", message="malformed locus managed-block marker", severity=Severity.ERROR,
                                    path=display_path, line=line_number, surface=surface_name))
        offset += len(line)
    if active is not None:
        findings.append(Finding(code="DOC-BLOCK-001", message=f"unclosed block {active[0]}/{active[1]}", severity=Severity.ERROR,
                                path=display_path, line=active[4], surface=surface_name))
    return tuple(blocks), findings


def extract_links(text: str, *, display_path: str, surface_name: str) -> tuple[tuple[LinkRecord, ...], list[Finding]]:
    findings: list[Finding] = []
    links: list[LinkRecord] = []
    try:
        tokens = MarkdownIt("commonmark").parse(text)
    except Exception as exc:
        return (), [Finding(code="DOC-ENV-090", message=f"Markdown parser failed: {exc}", severity=Severity.ERROR, path=display_path, surface=surface_name)]
    for token in tokens:
        if token.type != "inline" or not token.children:
            continue
        line = (token.map[0] + 1) if token.map else 1
        for child in token.children:
            if child.type == "link_open":
                target = child.attrGet("href")
                if target:
                    links.append(LinkRecord(target=target, line=line))
            elif child.type == "image":
                target = child.attrGet("src")
                if target:
                    links.append(LinkRecord(target=target, line=line, image=True))
    return tuple(links), findings


def scan_document(config: WorkspaceConfig, surface: SurfaceConfig, relative_path: str, absolute_path: Path) -> tuple[DocumentRecord | None, list[Finding]]:
    display_path = display_surface_path(surface.root, relative_path)
    try:
        raw = absolute_path.read_bytes()
    except OSError as exc:
        return None, [Finding(code="DOC-ENV-091", message=f"cannot read document: {exc}", severity=Severity.ERROR, path=display_path, surface=surface.name)]
    bom = raw.startswith(b"\xef\xbb\xbf")
    payload = raw[3:] if bom else raw
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, [Finding(code="DOC-ENV-092", message=f"document is not valid UTF-8: {exc}", severity=Severity.ERROR, path=display_path, surface=surface.name)]
    frontmatter, frontmatter_findings = parse_frontmatter(text, surface, config, relative_path)
    blocks, block_findings = scan_managed_blocks(text, display_path=display_path, surface_name=surface.name)
    links, link_findings = extract_links(text, display_path=display_path, surface_name=surface.name)
    try:
        headings = extract_headings(text)
    except Exception as exc:
        return None, [Finding(code="DOC-ENV-090", message=f"Markdown parser failed: {exc}", severity=Severity.ERROR, path=display_path, surface=surface.name)]
    record = DocumentRecord(surface=surface.name, relative_path=relative_path, absolute_path=absolute_path, text=text,
                            source_digest=digest_bytes(raw), newline=_detect_newline(text), bom=bom, frontmatter=frontmatter,
                            links=links, blocks=blocks, headings=headings)
    return record, [*frontmatter_findings, *block_findings, *link_findings]
