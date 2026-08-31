from __future__ import annotations

import math
import os
import re
import tomllib
from datetime import date, datetime, time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from .errors import ConfigError
from .models import (
    ContractBinding,
    DocumentConfig,
    DocumentSectionConfig,
    GlobalConfig,
    ProviderConfig,
    RuleConfig,
    Severity,
    SurfaceConfig,
    WorkspaceConfig,
)
from .utils import digest_json, safe_relative_posix, substitute_environment, unique_stable

_SURFACE_NAME = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
_KIND_NAME = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
_BLOCK_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,31}$")
_DISCOVERY_NAME = ".locus/locus-md.toml"
_LEGACY_DISCOVERY_NAMES = (".locus/locus.md.toml", ".locus/config.ini", "locus.ini", ".locus.ini")
_ENV_NAME = "LOCUS_MD_CONFIG"


def _normalize_heading(value: str) -> str:
    return " ".join(value.split())


def _surface_path(value: str, *, key: str) -> str:
    if value.strip().replace("\\", "/") == ".":
        return "."
    return safe_relative_posix(value, key=key)


def _matches_path(path: str, patterns: tuple[str, ...]) -> bool:
    from pathlib import PurePosixPath

    candidate = PurePosixPath(path)
    return any(candidate.match(pattern) or (pattern.startswith("**/") and candidate.match(pattern[3:])) for pattern in patterns)


def find_git_root(start: Path) -> Path | None:
    current = start.resolve(strict=False)
    while True:
        if (current / ".git").exists():
            return current
        if current.parent == current:
            return None
        current = current.parent


def _absolute_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (Path.cwd() / path).resolve(strict=False)


def _migration_error(path: Path) -> ConfigError:
    return ConfigError("CFG-061", f"configuration must be TOML at {_DISCOVERY_NAME}; migrate {path} and use [locus-md] tables", path)


def _validate_toml_path(path: Path) -> None:
    if path.name in {"locus.md.toml", "config.ini", "locus.ini", ".locus.ini"} or path.suffix.lower() != ".toml":
        raise _migration_error(path)


def discover_config(*, explicit: str | Path | None = None, start: str | Path | None = None, env: Mapping[str, str] | None = None) -> Path:
    source_env = os.environ if env is None else env
    if explicit is not None:
        path = _absolute_path(explicit)
        _validate_toml_path(path)
        if not path.is_file():
            raise ConfigError("CFG-001", "config file not found", path)
        return path
    value = source_env.get(_ENV_NAME)
    if value:
        path = _absolute_path(value)
        _validate_toml_path(path)
        if not path.is_file():
            raise ConfigError("CFG-001", f"config file from {_ENV_NAME} not found", path)
        return path
    current = _absolute_path(start or Path.cwd())
    if current.is_file():
        current = current.parent
    git_root = find_git_root(current)
    while True:
        canonical = (current / _DISCOVERY_NAME).resolve(strict=False)
        if canonical.is_file():
            return canonical
        legacy = [(current / name).resolve(strict=False) for name in _LEGACY_DISCOVERY_NAMES if (current / name).is_file()]
        if legacy:
            raise _migration_error(legacy[0])
        if current.parent == current or (git_root is not None and current == git_root):
            break
        current = current.parent
    raise ConfigError("CFG-001", "config file not found")


def workspace_root_for_config(config_path: Path) -> Path:
    base = config_path.parent.parent if config_path.parent.name == ".locus" else config_path.parent
    return base.resolve(strict=False)


@dataclass(frozen=True, slots=True)
class InitResult:
    path: Path
    content: str
    action: Literal["print", "missing", "present", "created"]


def _scaffold() -> str:
    return """[locus-md]
schema = 1
surfaces = ["docs"]
strict = false
lock_file = ".locus/docs.lock.json"
cache_dir = ".locus/cache/locus-md"
network = "explicit"
unverified = "fail"

[locus-md.surface.docs]
root = "docs"
include = ["**/*.md"]
index = ["index.md"]
frontmatter = "optional"
require_reachable = true
follow_symlinks = false
"""


def _legacy_paths_for_config(config_path: Path) -> tuple[Path, ...]:
    workspace = workspace_root_for_config(config_path)
    return tuple(workspace / name for name in _LEGACY_DISCOVERY_NAMES)


def initialize_config(*, explicit: str | Path | None = None, check: bool = False, print_only: bool = False) -> InitResult:
    target = _absolute_path(explicit or _DISCOVERY_NAME)
    _validate_toml_path(target)
    if target.exists():
        load_config(explicit=target)
        if print_only:
            return InitResult(target, _scaffold(), "print")
        return InitResult(target, _scaffold(), "present")
    for legacy in _legacy_paths_for_config(target):
        if legacy.is_file():
            raise _migration_error(legacy)
    if print_only:
        return InitResult(target, _scaffold(), "print")
    if check:
        return InitResult(target, _scaffold(), "missing")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_scaffold(), encoding="utf-8")
    return InitResult(target, _scaffold(), "created")


def _substitute_tree(value: Any, env: Mapping[str, str] | None) -> Any:
    if isinstance(value, str):
        return substitute_environment(value, env)
    if isinstance(value, list):
        return [_substitute_tree(item, env) for item in value]
    if isinstance(value, dict):
        return {key: _substitute_tree(item, env) for key, item in value.items()}
    return value


def _read_toml(config_path: Path, env: Mapping[str, str] | None) -> dict[str, Any]:
    try:
        parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise ConfigError("CFG-006", "config must be UTF-8", config_path) from exc
    except tomllib.TOMLDecodeError as exc:
        message = str(exc)
        code = "CFG-002" if "Cannot overwrite" in message or "Cannot declare" in message else "CFG-007"
        raise ConfigError(code, message, config_path) from exc
    parsed = _substitute_tree(parsed, env)
    if "locus" in parsed:
        raise _migration_error(config_path)
    if set(parsed) - {"locus-md"}:
        keys = ", ".join(sorted(set(parsed) - {"locus-md"}))
        raise ConfigError("CFG-062", f"unsupported top-level key(s): {keys}; use only [locus-md] tables", config_path)
    md = parsed.get("locus-md")
    if not isinstance(md, dict):
        raise ConfigError("CFG-008", "missing [locus-md] section", config_path)
    allowed = {"schema", "surfaces", "strict", "lock_file", "cache_dir", "report_dir", "default_output", "network", "unverified", "surface", "provider", "contract", "rule", "document"}
    unknown = set(md) - allowed
    if unknown:
        raise ConfigError("CFG-062", f"unsupported [locus-md] child table/key(s): {', '.join(sorted(unknown))}", config_path)
    return md


def _section(value: Any, key: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError("CFG-011", f"{key} must be a TOML table")
    return value


def _required(section: Mapping[str, Any], key: str, section_name: str) -> Any:
    if key not in section or section[key] is None:
        raise ConfigError("CFG-009", f"missing required key {key!r} in [{section_name}]")
    return section[key]


def _string(value: Any, *, key: str, required: bool = False, default: str | None = None) -> str | None:
    if value is None:
        if required:
            raise ConfigError("CFG-009", f"missing required key {key!r}")
        return default
    if not isinstance(value, str):
        raise ConfigError("CFG-004", f"{key} must be a string, got {type(value).__name__}")
    if required and not value.strip():
        raise ConfigError("CFG-009", f"missing required key {key!r}")
    return value.strip()


def _integer(value: Any, *, key: str, default: int | None = None) -> int | None:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError("CFG-005", f"{key} must be an integer, got {type(value).__name__}")
    return value


def _boolean(value: Any, *, key: str, default: bool = False) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ConfigError("CFG-004", f"{key} must be a boolean, got {type(value).__name__}")
    return value


def _string_list(value: Any, *, key: str, required: bool = False) -> tuple[str, ...]:
    if value is None:
        if required:
            raise ConfigError("CFG-009", f"missing required key {key!r}")
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ConfigError("CFG-004", f"{key} must be an array of strings")
    values = unique_stable(item.strip() for item in value if item.strip())
    if required and not values:
        raise ConfigError("CFG-009", f"{key} must not be empty")
    return values


def _choice(value: Any, choices: set[str], *, key: str, default: str | None = None) -> str:
    selected = _string(value, key=key, default=default)
    if selected is None or selected.lower() not in choices:
        raise ConfigError("CFG-004", f"{key} must be one of {sorted(choices)}, got {value!r}")
    return selected.lower()


def _severity(value: Any, *, key: str, default: Severity = Severity.ERROR) -> Severity:
    selected = _string(value, key=key, default=default.value)
    try:
        return Severity(selected.lower())
    except ValueError as exc:
        raise ConfigError("CFG-004", f"{key} must be one of {[item.value for item in Severity]}, got {value!r}") from exc


def _json_value(value: Any, *, key: str) -> Any:
    if isinstance(value, (datetime, date, time)):
        raise ConfigError("CFG-036", f"{key} must use JSON-compatible values; dates and times are unsupported")
    if isinstance(value, float) and not math.isfinite(value):
        raise ConfigError("CFG-036", f"{key} must use finite JSON-compatible numbers")
    if isinstance(value, dict):
        return {str(name): _json_value(item, key=key) for name, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item, key=key) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise ConfigError("CFG-036", f"{key} must use JSON-compatible values")


def _object(value: Any, *, key: str, code: str = "CFG-036", default: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    if value is None:
        return {} if default is None else default
    if not isinstance(value, dict):
        raise ConfigError(code, f"{key} must be a TOML table")
    try:
        return _json_value(value, key=key)
    except ConfigError as exc:
        raise ConfigError(code, exc.message) from exc


def _config_digest_payload(
    global_config: GlobalConfig, surfaces: Mapping[str, SurfaceConfig], providers: Mapping[str, ProviderConfig],
    contracts: Mapping[str, ContractBinding], rules: Mapping[str, RuleConfig]
) -> dict[str, object]:
    return {
        "global": {"schema": global_config.schema, "surfaces": list(global_config.surfaces), "strict": global_config.strict,
                   "lock_file": global_config.lock_file, "cache_dir": global_config.cache_dir, "report_dir": global_config.report_dir,
                   "default_output": global_config.default_output, "network": global_config.network, "unverified": global_config.unverified},
        "surfaces": {name: {"root": item.root, "include": list(item.include), "exclude": list(item.exclude), "indexes": list(item.indexes),
                            "frontmatter": item.frontmatter, "frontmatter_schema": item.frontmatter_schema, "require_reachable": item.require_reachable,
                            "allow_external_links": item.allow_external_links, "follow_symlinks": item.follow_symlinks, "default_provider": item.default_provider}
                     for name, item in sorted(surfaces.items())},
        "providers": {name: {"adapter": item.adapter, "required": item.required, "network": item.network, "snapshot_file": item.snapshot_file,
                             "cache_ttl": item.cache_ttl, "options": dict(sorted(item.options.items()))} for name, item in sorted(providers.items())},
        "contracts": {name: {"surface": item.surface, "path": item.path, "block_kind": item.block_kind, "block_id": item.block_id, "schema": item.schema,
                             "mode": item.mode, "provider": item.provider, "provider_explicit": item.provider_explicit, "selector": dict(item.selector),
                             "renderer": item.renderer, "severity": item.severity.value, "required": item.required} for name, item in sorted(contracts.items())},
        "rules": {name: {"adapter": item.adapter, "phase": item.phase, "surface": item.surface, "severity": item.severity.value, "options": dict(item.options)}
                  for name, item in sorted(rules.items())},
    }


def _unknown_keys(raw: Mapping[str, Any], allowed: set[str], section_name: str, code: str) -> None:
    unknown = set(raw) - allowed
    if unknown:
        raise ConfigError(code, f"unknown key(s) in [{section_name}]: {', '.join(sorted(unknown))}")


def _parse_global(raw: Mapping[str, Any], *, config_path: Path | None = None) -> GlobalConfig:
    schema = _integer(_required(raw, "schema", "locus-md"), key="locus-md.schema")
    if schema != 1:
        raise ConfigError("CFG-003", f"unsupported config schema {schema!r}; expected 1", config_path)
    raw_active_surfaces = _required(raw, "surfaces", "locus-md")
    if isinstance(raw_active_surfaces, list) and all(isinstance(item, str) for item in raw_active_surfaces) and len(raw_active_surfaces) != len(set(raw_active_surfaces)):
        raise ConfigError("CFG-010", "locus-md.surfaces must not contain duplicate names")
    active_surfaces = _string_list(raw_active_surfaces, key="locus-md.surfaces", required=True)
    report_dir = _string(raw.get("report_dir"), key="locus-md.report_dir")
    return GlobalConfig(
        schema=1,
        surfaces=active_surfaces,
        strict=_boolean(raw.get("strict"), key="locus-md.strict"),
        lock_file=safe_relative_posix(_string(raw.get("lock_file"), key="locus-md.lock_file", default=".locus/docs.lock.json"), key="locus-md.lock_file"),
        cache_dir=safe_relative_posix(_string(raw.get("cache_dir"), key="locus-md.cache_dir", default=".locus/cache/locus-md"), key="locus-md.cache_dir"),
        report_dir=safe_relative_posix(report_dir, key="locus-md.report_dir") if report_dir else None,
        default_output=_choice(raw.get("default_output"), {"human", "json"}, key="locus-md.default_output", default="human"),
        network=_choice(raw.get("network"), {"deny", "explicit", "allow"}, key="locus-md.network", default="explicit"),
        unverified=_choice(raw.get("unverified"), {"fail", "warn", "ignore"}, key="locus-md.unverified", default="fail"),
    )


def _parse_surfaces(raw_sections: Mapping[str, Any], active: tuple[str, ...]) -> dict[str, SurfaceConfig]:
    surfaces: dict[str, SurfaceConfig] = {}
    raw_surfaces = _section(raw_sections.get("surface"), "locus-md.surface")
    allowed = {"root", "include", "exclude", "index", "frontmatter", "frontmatter_schema", "require_reachable", "allow_external_links", "follow_symlinks", "default_provider"}
    for name in active:
        if not _SURFACE_NAME.fullmatch(name):
            raise ConfigError("CFG-010", f"invalid surface name {name!r}")
        section_name = f"locus-md.surface.{name}"
        raw = _section(raw_surfaces.get(name), section_name)
        if not raw:
            raise ConfigError("CFG-010", f"missing [{section_name}] section")
        _unknown_keys(raw, allowed, section_name, "CFG-063")
        root = _surface_path(_string(_required(raw, "root", section_name), key=f"{section_name}.root", required=True), key=f"{section_name}.root")
        includes = _string_list(_required(raw, "include", section_name), key=f"{section_name}.include", required=True)
        excludes = _string_list(raw.get("exclude"), key=f"{section_name}.exclude")
        indexes = tuple(safe_relative_posix(value, key=f"{section_name}.index") for value in _string_list(raw.get("index"), key=f"{section_name}.index"))
        frontmatter_schema = _string(raw.get("frontmatter_schema"), key=f"{section_name}.frontmatter_schema")
        if frontmatter_schema:
            frontmatter_schema = safe_relative_posix(frontmatter_schema, key=f"{section_name}.frontmatter_schema")
        surfaces[name] = SurfaceConfig(name=name, root=root, include=includes, exclude=excludes, indexes=indexes,
                                       frontmatter=_choice(raw.get("frontmatter"), {"required", "optional", "forbidden"}, key=f"{section_name}.frontmatter", default="optional"),
                                       frontmatter_schema=frontmatter_schema,
                                       require_reachable=_boolean(raw.get("require_reachable"), key=f"{section_name}.require_reachable"),
                                       allow_external_links=_boolean(raw.get("allow_external_links"), key=f"{section_name}.allow_external_links", default=True),
                                       follow_symlinks=_boolean(raw.get("follow_symlinks"), key=f"{section_name}.follow_symlinks"),
                                       default_provider=_string(raw.get("default_provider"), key=f"{section_name}.default_provider"))
    return surfaces


def _parse_document_sections(raw: Mapping[str, Any], section_name: str, document_name: str) -> dict[str, DocumentSectionConfig]:
    sections_config: dict[str, DocumentSectionConfig] = {}
    headings: set[str] = set()
    section_keys = {"heading", "required", "guidance"}
    raw_sections = _section(raw.get("sections"), f"{section_name}.sections")
    for section_id, section_value in raw_sections.items():
        if not isinstance(section_id, str) or not _SURFACE_NAME.fullmatch(section_id):
            raise ConfigError("CFG-057", f"invalid section name {section_id!r} in [{section_name}.sections]")
        section_table_name = f"{section_name}.sections.{section_id}"
        section_raw = _section(section_value, section_table_name)
        _unknown_keys(section_raw, section_keys, section_table_name, "CFG-058")
        heading_value = _string(_required(section_raw, "heading", section_table_name), key=f"{section_table_name}.heading", required=True)
        heading = _normalize_heading(heading_value or "")
        if not heading:
            raise ConfigError("CFG-059", f"{section_table_name}.heading must not be empty")
        if heading in headings:
            raise ConfigError("CFG-059", f"duplicate normalized heading {heading!r} in document {document_name!r}")
        headings.add(heading)
        sections_config[section_id] = DocumentSectionConfig(
            name=section_id, heading=heading,
            required=_boolean(section_raw.get("required"), key=f"{section_table_name}.required", default=True),
            guidance=_string(section_raw.get("guidance"), key=f"{section_table_name}.guidance"),
        )
    return sections_config


def _parse_documents(raw_sections: Mapping[str, Any], surfaces: Mapping[str, SurfaceConfig]) -> dict[str, DocumentConfig]:
    documents: dict[str, DocumentConfig] = {}
    document_paths: dict[tuple[str, str], str] = {}
    raw_documents = _section(raw_sections.get("document"), "locus-md.document")
    document_keys = {"surface", "path", "description", "guidance", "sections"}
    for name, value in raw_documents.items():
        if not isinstance(name, str) or not _SURFACE_NAME.fullmatch(name):
            raise ConfigError("CFG-055", f"invalid document name {name!r}")
        section_name = f"locus-md.document.{name}"
        raw = _section(value, section_name)
        unknown = set(raw) - document_keys
        if unknown:
            raise ConfigError("CFG-056", f"unknown key(s) in [{section_name}]: {', '.join(sorted(unknown))}")
        surface_name = _string(_required(raw, "surface", section_name), key=f"{section_name}.surface", required=True)
        if surface_name not in surfaces:
            raise ConfigError("CFG-010", f"document {name!r} references unknown or inactive surface {surface_name!r}")
        path = safe_relative_posix(_string(_required(raw, "path", section_name), key=f"{section_name}.path", required=True), key=f"{section_name}.path")
        document_key = (surface_name, path)
        if document_key in document_paths:
            raise ConfigError("CFG-053", f"documents {document_paths[document_key]!r} and {name!r} have the same path {surface_name}:{path}")
        document_paths[document_key] = name
        description = _string(_required(raw, "description", section_name), key=f"{section_name}.description", required=True)
        guidance = _string(raw.get("guidance"), key=f"{section_name}.guidance")
        surface = surfaces[surface_name]
        if not _matches_path(path, surface.include) or _matches_path(path, surface.exclude):
            raise ConfigError("CFG-054", f"document {name!r} path {path!r} is not selected by surface {surface_name!r}")
        sections_config = _parse_document_sections(raw, section_name, name)
        documents[name] = DocumentConfig(name=name, surface=surface_name, path=path, description=description, guidance=guidance, sections=sections_config)
    return documents


def _parse_providers(raw_sections: Mapping[str, Any]) -> dict[str, ProviderConfig]:
    providers: dict[str, ProviderConfig] = {}
    raw_providers = _section(raw_sections.get("provider"), "locus-md.provider")
    provider_reserved = {"adapter", "required", "network", "snapshot_file", "cache_ttl"}
    for name, value in raw_providers.items():
        if not isinstance(name, str) or not _SURFACE_NAME.fullmatch(name):
            raise ConfigError("CFG-020", f"invalid provider name {name!r}")
        section_name = f"locus-md.provider.{name}"
        raw = _section(value, section_name)
        options = {key: item for key, item in raw.items() if key not in provider_reserved}
        if any(not isinstance(key, str) or not isinstance(item, str) for key, item in options.items()):
            raise ConfigError("CFG-004", f"{section_name} provider options must be strings")
        snapshot_file = _string(raw.get("snapshot_file"), key=f"{section_name}.snapshot_file")
        if snapshot_file:
            snapshot_file = safe_relative_posix(snapshot_file, key=f"{section_name}.snapshot_file")
        providers[name] = ProviderConfig(name=name, adapter=_string(_required(raw, "adapter", section_name), key=f"{section_name}.adapter", required=True),
                                         required=_boolean(raw.get("required"), key=f"{section_name}.required", default=True),
                                         network=_boolean(raw.get("network"), key=f"{section_name}.network"), snapshot_file=snapshot_file,
                                         cache_ttl=_integer(raw.get("cache_ttl"), key=f"{section_name}.cache_ttl"), options=options)
    return providers


def _parse_contracts(raw_sections: Mapping[str, Any], surfaces: Mapping[str, SurfaceConfig], providers: Mapping[str, ProviderConfig]) -> dict[str, ContractBinding]:
    contracts: dict[str, ContractBinding] = {}
    binding_keys: dict[tuple[str, str, str, str], str] = {}
    raw_contracts = _section(raw_sections.get("contract"), "locus-md.contract")
    allowed = {"surface", "path", "block_kind", "block_id", "schema", "mode", "provider", "selector", "renderer", "severity", "required"}
    for name, value in raw_contracts.items():
        if not isinstance(name, str) or not _SURFACE_NAME.fullmatch(name):
            raise ConfigError("CFG-025", f"invalid contract name {name!r}")
        section_name = f"locus-md.contract.{name}"
        raw = _section(value, section_name)
        _unknown_keys(raw, allowed, section_name, "CFG-064")
        surface_name = _string(_required(raw, "surface", section_name), key=f"{section_name}.surface", required=True)
        if surface_name not in surfaces:
            raise ConfigError("CFG-010", f"contract {name!r} references unknown or inactive surface {surface_name!r}")
        path = safe_relative_posix(_string(_required(raw, "path", section_name), key=f"{section_name}.path", required=True), key=f"{section_name}.path")
        kind = _string(_required(raw, "block_kind", section_name), key=f"{section_name}.block_kind", required=True)
        block_id = _string(_required(raw, "block_id", section_name), key=f"{section_name}.block_id", required=True)
        if not _KIND_NAME.fullmatch(kind):
            raise ConfigError("CFG-026", f"invalid block kind {kind!r} in contract {name!r}")
        if not _BLOCK_ID.fullmatch(block_id):
            raise ConfigError("CFG-027", f"invalid block id {block_id!r} in contract {name!r}")
        mode = _choice(_required(raw, "mode", section_name), {"authored", "projection", "snapshot"}, key=f"{section_name}.mode")
        raw_provider = _string(raw.get("provider"), key=f"{section_name}.provider")
        provider_explicit = raw_provider not in {None, "inherit"}
        provider = surfaces[surface_name].default_provider if raw_provider == "inherit" else raw_provider
        if mode in {"authored", "projection"} and provider is None:
            raise ConfigError("CFG-020", f"contract {name!r} has no provider and surface {surface_name!r} has no default_provider")
        if provider is not None and provider not in providers:
            raise ConfigError("CFG-020", f"contract {name!r} references unknown provider {provider!r}")
        renderer = _string(raw.get("renderer"), key=f"{section_name}.renderer")
        if mode == "projection" and renderer is None:
            raise ConfigError("CFG-028", f"projection contract {name!r} requires renderer")
        binding = ContractBinding(name=name, surface=surface_name, path=path, block_kind=kind, block_id=block_id,
                                  schema=_string(_required(raw, "schema", section_name), key=f"{section_name}.schema", required=True), mode=mode,
                                  provider=provider, provider_explicit=provider_explicit, selector=_object(raw.get("selector"), code="CFG-030", key=f"{section_name}.selector"),
                                  renderer=renderer, severity=_severity(raw.get("severity"), key=f"{section_name}.severity"),
                                  required=_boolean(raw.get("required"), key=f"{section_name}.required", default=True))
        if binding.key in binding_keys:
            raise ConfigError("CFG-029", f"contracts {binding_keys[binding.key]!r} and {name!r} have the same binding key {binding.key}")
        binding_keys[binding.key] = name
        contracts[name] = binding
    return contracts


def _parse_rules(raw_sections: Mapping[str, Any], surfaces: Mapping[str, SurfaceConfig]) -> dict[str, RuleConfig]:
    rules: dict[str, RuleConfig] = {}
    rule_keys = {"adapter", "phase", "surface", "severity", "options"}
    raw_rules = _section(raw_sections.get("rule"), "locus-md.rule")
    for name, value in raw_rules.items():
        if not isinstance(name, str) or not _SURFACE_NAME.fullmatch(name):
            raise ConfigError("CFG-035", f"invalid rule name {name!r}")
        section_name = f"locus-md.rule.{name}"
        raw = _section(value, section_name)
        unknown_keys = set(raw) - rule_keys
        if unknown_keys:
            raise ConfigError("CFG-036", f"unknown key(s) in [{section_name}]: {', '.join(sorted(unknown_keys))}")
        surface_name = _string(raw.get("surface"), key=f"{section_name}.surface")
        if surface_name is not None and surface_name not in surfaces:
            raise ConfigError("CFG-010", f"rule {name!r} references unknown surface {surface_name!r}")
        phase = _choice(_string(_required(raw, "phase", section_name), key=f"{section_name}.phase", required=True), {"verify"}, key=f"{section_name}.phase")
        rules[name] = RuleConfig(name=name, adapter=_string(_required(raw, "adapter", section_name), key=f"{section_name}.adapter", required=True),
                                 phase=phase, surface=surface_name, severity=_severity(raw.get("severity"), key=f"{section_name}.severity"),
                                 options=_object(raw.get("options"), key=f"{section_name}.options"))
    return rules


def _document_digest_payload(documents: Mapping[str, DocumentConfig]) -> dict[str, Any]:
    return {
        name: {
            "surface": item.surface, "path": item.path, "description": item.description, "guidance": item.guidance,
            "sections": {key: {"heading": section.heading, "required": section.required, "guidance": section.guidance} for key, section in item.sections.items()},
        }
        for name, item in sorted(documents.items())
    }


def load_config(*, explicit: str | Path | None = None, start: str | Path | None = None, env: Mapping[str, str] | None = None) -> WorkspaceConfig:
    config_path = discover_config(explicit=explicit, start=start, env=env)
    workspace_root = workspace_root_for_config(config_path)
    sections = _read_toml(config_path, env)
    global_config = _parse_global(sections, config_path=config_path)
    surfaces = _parse_surfaces(sections, global_config.surfaces)
    documents = _parse_documents(sections, surfaces)
    providers = _parse_providers(sections)
    contracts = _parse_contracts(sections, surfaces, providers)
    rules = _parse_rules(sections, surfaces)
    for surface in surfaces.values():
        if surface.default_provider and surface.default_provider not in providers:
            raise ConfigError("CFG-020", f"surface {surface.name!r} references unknown default_provider {surface.default_provider!r}")
    digest_payload = _config_digest_payload(global_config, surfaces, providers, contracts, rules)
    digest_payload["documents"] = _document_digest_payload(documents)
    return WorkspaceConfig(config_path=config_path, workspace_root=workspace_root, global_config=global_config, surfaces=surfaces,
                           providers=providers, contracts=contracts, rules=rules, config_digest=digest_json(digest_payload), documents=documents)
