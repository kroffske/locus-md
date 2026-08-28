from __future__ import annotations

import configparser
import json
import os
import re
from pathlib import Path
from typing import Mapping

from .errors import ConfigError
from .models import ContractBinding, GlobalConfig, ProviderConfig, RuleConfig, Severity, SurfaceConfig, WorkspaceConfig
from .utils import digest_json, parse_bool, parse_int, safe_relative_posix, split_csv, substitute_environment, unique_stable

_SURFACE_NAME = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
_KIND_NAME = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
_BLOCK_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,31}$")
_ALLOWED_PREFIXES = ("locus.docs.surface:", "locus.docs.contract:", "locus.docs.provider:", "locus.docs.rule:")
_DISCOVERY_NAMES = (".locus/config.ini", "locus.ini", ".locus.ini")


def find_git_root(start: Path) -> Path | None:
    current = start.resolve(strict=False)
    while True:
        if (current / ".git").exists():
            return current
        if current.parent == current:
            return None
        current = current.parent


def discover_config(*, explicit: str | Path | None = None, start: str | Path | None = None, env: Mapping[str, str] | None = None) -> Path:
    source_env = os.environ if env is None else env
    if explicit is not None:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve(strict=False)
        if not path.is_file():
            raise ConfigError("CFG-001", "config file not found", path)
        return path
    for key in ("LOCUS_MD_CONFIG", "LOCUS_CONFIG"):
        value = source_env.get(key)
        if value:
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = (Path.cwd() / path).resolve(strict=False)
            if not path.is_file():
                raise ConfigError("CFG-001", f"config file from {key} not found", path)
            return path
    current = Path(start or Path.cwd()).expanduser().resolve(strict=False)
    if current.is_file():
        current = current.parent
    git_root = find_git_root(current)
    while True:
        matches = [(current / name).resolve(strict=False) for name in _DISCOVERY_NAMES if (current / name).is_file()]
        if len(matches) > 1:
            raise ConfigError("CFG-060", f"ambiguous config discovery at {current}: {', '.join(str(path) for path in matches)}")
        if matches:
            return matches[0]
        if current.parent == current or (git_root is not None and current == git_root):
            break
        current = current.parent
    raise ConfigError("CFG-001", "config file not found")


def workspace_root_for_config(config_path: Path) -> Path:
    base = config_path.parent.parent if config_path.parent.name == ".locus" else config_path.parent
    return base.resolve(strict=False)


def _section_kind(section: str) -> tuple[str, str] | None:
    if section == "locus.docs":
        return ("global", "")
    for prefix in _ALLOWED_PREFIXES:
        if section.startswith(prefix):
            return (prefix[len("locus.docs.") : -1], section[len(prefix) :])
    return None


def _read_parser(config_path: Path, env: Mapping[str, str] | None) -> dict[str, dict[str, str]]:
    try:
        text = config_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ConfigError("CFG-006", "config must be UTF-8", config_path) from exc
    parser = configparser.ConfigParser(strict=True, interpolation=None, empty_lines_in_values=False)
    parser.optionxform = str.lower
    try:
        parser.read_string(text, source=str(config_path))
    except configparser.DuplicateSectionError as exc:
        raise ConfigError("CFG-002", f"duplicate section {exc.section!r}", config_path) from exc
    except configparser.DuplicateOptionError as exc:
        raise ConfigError("CFG-002", f"duplicate key {exc.option!r} in section {exc.section!r}", config_path) from exc
    except configparser.Error as exc:
        raise ConfigError("CFG-007", str(exc), config_path) from exc
    allowed: dict[str, dict[str, str]] = {}
    for section in parser.sections():
        if _section_kind(section) is None:
            continue
        allowed[section] = {key: substitute_environment(value.strip(), env) for key, value in parser.items(section, raw=True)}
    if "locus.docs" not in allowed:
        raise ConfigError("CFG-008", "missing [locus.docs] section", config_path)
    return allowed


def _required(section: Mapping[str, str], key: str, section_name: str) -> str:
    value = section.get(key)
    if value is None or value.strip() == "":
        raise ConfigError("CFG-009", f"missing required key {key!r} in [{section_name}]")
    return value.strip()


def _choice(value: str, choices: set[str], *, key: str) -> str:
    normalized = value.strip().lower()
    if normalized not in choices:
        raise ConfigError("CFG-004", f"{key} must be one of {sorted(choices)}, got {value!r}")
    return normalized


def _severity(value: str | None, *, default: Severity = Severity.ERROR) -> Severity:
    if value is None:
        return default
    try:
        return Severity(value.strip().lower())
    except ValueError as exc:
        raise ConfigError("CFG-004", f"severity must be one of {[item.value for item in Severity]}, got {value!r}") from exc


def _parse_json_object(value: str | None, *, code: str, key: str, default: Mapping[str, object] | None = None) -> Mapping[str, object]:
    if value is None:
        return {} if default is None else default
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ConfigError(code, f"{key} must be strict JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ConfigError(code, f"{key} must be a JSON object")
    return parsed


def _config_digest_payload(
    global_config: GlobalConfig, surfaces: Mapping[str, SurfaceConfig], providers: Mapping[str, ProviderConfig],
    contracts: Mapping[str, ContractBinding], rules: Mapping[str, RuleConfig]
) -> dict[str, object]:
    return {
        "global": {
            "schema": global_config.schema,
            "surfaces": list(global_config.surfaces),
            "strict": global_config.strict,
            "lock_file": global_config.lock_file,
            "cache_dir": global_config.cache_dir,
            "report_dir": global_config.report_dir,
            "default_output": global_config.default_output,
            "network": global_config.network,
            "unverified": global_config.unverified,
        },
        "surfaces": {
            name: {
                "root": item.root,
                "include": list(item.include),
                "exclude": list(item.exclude),
                "indexes": list(item.indexes),
                "frontmatter": item.frontmatter,
                "frontmatter_schema": item.frontmatter_schema,
                "require_reachable": item.require_reachable,
                "allow_external_links": item.allow_external_links,
                "follow_symlinks": item.follow_symlinks,
                "default_provider": item.default_provider,
            }
            for name, item in sorted(surfaces.items())
        },
        "providers": {
            name: {
                "adapter": item.adapter,
                "required": item.required,
                "network": item.network,
                "snapshot_file": item.snapshot_file,
                "cache_ttl": item.cache_ttl,
                "options": dict(sorted(item.options.items())),
            }
            for name, item in sorted(providers.items())
        },
        "contracts": {
            name: {
                "surface": item.surface,
                "path": item.path,
                "block_kind": item.block_kind,
                "block_id": item.block_id,
                "schema": item.schema,
                "mode": item.mode,
                "provider": item.provider,
                "provider_explicit": item.provider_explicit,
                "selector": dict(item.selector),
                "renderer": item.renderer,
                "severity": item.severity.value,
                "required": item.required,
            }
            for name, item in sorted(contracts.items())
        },
        "rules": {name: {"adapter": item.adapter, "surface": item.surface, "severity": item.severity.value, "options": dict(item.options)} for name, item in sorted(rules.items())},
    }


def load_config(*, explicit: str | Path | None = None, start: str | Path | None = None, env: Mapping[str, str] | None = None) -> WorkspaceConfig:
    config_path = discover_config(explicit=explicit, start=start, env=env)
    workspace_root = workspace_root_for_config(config_path)
    sections = _read_parser(config_path, env)
    raw_global = sections["locus.docs"]
    schema = parse_int(_required(raw_global, "schema", "locus.docs"), key="locus.docs.schema")
    if schema != 1:
        raise ConfigError("CFG-003", f"unsupported config schema {schema!r}; expected 1", config_path)
    active_surfaces = unique_stable(split_csv(_required(raw_global, "surfaces", "locus.docs")))
    if not active_surfaces:
        raise ConfigError("CFG-009", "locus.docs.surfaces must not be empty")
    lock_file = safe_relative_posix(raw_global.get("lock_file", ".locus/docs.lock.json"), key="locus.docs.lock_file")
    cache_dir = safe_relative_posix(raw_global.get("cache_dir", ".locus/cache/locus-md"), key="locus.docs.cache_dir")
    report_dir = raw_global.get("report_dir")
    if report_dir:
        report_dir = safe_relative_posix(report_dir, key="locus.docs.report_dir")
    global_config = GlobalConfig(
        schema=1,
        surfaces=active_surfaces,
        strict=parse_bool(raw_global.get("strict"), key="locus.docs.strict"),
        lock_file=lock_file,
        cache_dir=cache_dir,
        report_dir=report_dir,
        default_output=_choice(raw_global.get("default_output", "human"), {"human", "json"}, key="locus.docs.default_output"),
        network=_choice(raw_global.get("network", "explicit"), {"deny", "explicit", "allow"}, key="locus.docs.network"),
        unverified=_choice(raw_global.get("unverified", "fail"), {"fail", "warn", "ignore"}, key="locus.docs.unverified"),
    )

    surfaces: dict[str, SurfaceConfig] = {}
    for name in active_surfaces:
        if not _SURFACE_NAME.fullmatch(name):
            raise ConfigError("CFG-010", f"invalid surface name {name!r}")
        section_name = f"locus.docs.surface:{name}"
        raw = sections.get(section_name)
        if raw is None:
            raise ConfigError("CFG-010", f"missing [{section_name}] section")
        root = safe_relative_posix(_required(raw, "root", section_name), key=f"{section_name}.root")
        includes = unique_stable(split_csv(_required(raw, "include", section_name)))
        if not includes:
            raise ConfigError("CFG-009", f"{section_name}.include must not be empty")
        excludes = unique_stable(split_csv(raw.get("exclude")))
        indexes = tuple(safe_relative_posix(value, key=f"{section_name}.index") for value in unique_stable(split_csv(raw.get("index"))))
        frontmatter_schema = raw.get("frontmatter_schema")
        if frontmatter_schema:
            frontmatter_schema = safe_relative_posix(frontmatter_schema, key=f"{section_name}.frontmatter_schema")
        surfaces[name] = SurfaceConfig(
            name=name,
            root=root,
            include=includes,
            exclude=excludes,
            indexes=indexes,
            frontmatter=_choice(raw.get("frontmatter", "optional"), {"required", "optional", "forbidden"}, key=f"{section_name}.frontmatter"),
            frontmatter_schema=frontmatter_schema,
            require_reachable=parse_bool(raw.get("require_reachable"), key=f"{section_name}.require_reachable"),
            allow_external_links=parse_bool(raw.get("allow_external_links"), default=True, key=f"{section_name}.allow_external_links"),
            follow_symlinks=parse_bool(raw.get("follow_symlinks"), key=f"{section_name}.follow_symlinks"),
            default_provider=raw.get("default_provider") or None,
        )

    providers: dict[str, ProviderConfig] = {}
    provider_reserved = {"adapter", "required", "network", "snapshot_file", "cache_ttl"}
    for section_name, raw in sections.items():
        prefix = "locus.docs.provider:"
        if not section_name.startswith(prefix):
            continue
        name = section_name[len(prefix) :]
        if not _SURFACE_NAME.fullmatch(name):
            raise ConfigError("CFG-020", f"invalid provider name {name!r}")
        snapshot_file = raw.get("snapshot_file")
        if snapshot_file:
            snapshot_file = safe_relative_posix(snapshot_file, key=f"{section_name}.snapshot_file")
        providers[name] = ProviderConfig(
            name=name,
            adapter=_required(raw, "adapter", section_name),
            required=parse_bool(raw.get("required"), default=True, key=f"{section_name}.required"),
            network=parse_bool(raw.get("network"), key=f"{section_name}.network"),
            snapshot_file=snapshot_file,
            cache_ttl=parse_int(raw.get("cache_ttl"), key=f"{section_name}.cache_ttl"),
            options={key: value for key, value in raw.items() if key not in provider_reserved},
        )

    contracts: dict[str, ContractBinding] = {}
    binding_keys: dict[tuple[str, str, str, str], str] = {}
    for section_name, raw in sections.items():
        prefix = "locus.docs.contract:"
        if not section_name.startswith(prefix):
            continue
        name = section_name[len(prefix) :]
        if not _SURFACE_NAME.fullmatch(name):
            raise ConfigError("CFG-025", f"invalid contract name {name!r}")
        surface_name = _required(raw, "surface", section_name)
        if surface_name not in surfaces:
            raise ConfigError("CFG-010", f"contract {name!r} references unknown or inactive surface {surface_name!r}")
        path = safe_relative_posix(_required(raw, "path", section_name), key=f"{section_name}.path")
        kind = _required(raw, "block_kind", section_name)
        block_id = _required(raw, "block_id", section_name)
        if not _KIND_NAME.fullmatch(kind):
            raise ConfigError("CFG-026", f"invalid block kind {kind!r} in contract {name!r}")
        if not _BLOCK_ID.fullmatch(block_id):
            raise ConfigError("CFG-027", f"invalid block id {block_id!r} in contract {name!r}")
        mode = _choice(_required(raw, "mode", section_name), {"authored", "projection", "snapshot"}, key=f"{section_name}.mode")
        raw_provider = raw.get("provider") or None
        provider_explicit = raw_provider not in {None, "inherit"}
        provider = raw_provider
        if provider == "inherit":
            provider = surfaces[surface_name].default_provider
        if mode in {"authored", "projection"} and provider is None:
            raise ConfigError("CFG-020", f"contract {name!r} has no provider and surface {surface_name!r} has no default_provider")
        if provider is not None and provider not in providers:
            raise ConfigError("CFG-020", f"contract {name!r} references unknown provider {provider!r}")
        renderer = raw.get("renderer") or None
        if mode == "projection" and renderer is None:
            raise ConfigError("CFG-028", f"projection contract {name!r} requires renderer")
        binding = ContractBinding(
            name=name,
            surface=surface_name,
            path=path,
            block_kind=kind,
            block_id=block_id,
            schema=_required(raw, "schema", section_name),
            mode=mode,
            provider=provider,
            provider_explicit=provider_explicit,
            selector=_parse_json_object(raw.get("selector"), code="CFG-030", key=f"{section_name}.selector"),
            renderer=renderer,
            severity=_severity(raw.get("severity")),
            required=parse_bool(raw.get("required"), default=True, key=f"{section_name}.required"),
        )
        if binding.key in binding_keys:
            raise ConfigError("CFG-029", f"contracts {binding_keys[binding.key]!r} and {name!r} have the same binding key {binding.key}")
        binding_keys[binding.key] = name
        contracts[name] = binding

    rules: dict[str, RuleConfig] = {}
    for section_name, raw in sections.items():
        prefix = "locus.docs.rule:"
        if not section_name.startswith(prefix):
            continue
        name = section_name[len(prefix) :]
        if not _SURFACE_NAME.fullmatch(name):
            raise ConfigError("CFG-035", f"invalid rule name {name!r}")
        surface_name = raw.get("surface") or None
        if surface_name is not None and surface_name not in surfaces:
            raise ConfigError("CFG-010", f"rule {name!r} references unknown surface {surface_name!r}")
        rules[name] = RuleConfig(name=name, adapter=_required(raw, "adapter", section_name), surface=surface_name,
                                 severity=_severity(raw.get("severity")),
                                 options=_parse_json_object(raw.get("options"), code="CFG-036", key=f"{section_name}.options"))

    for surface in surfaces.values():
        if surface.default_provider and surface.default_provider not in providers:
            raise ConfigError("CFG-020", f"surface {surface.name!r} references unknown default_provider {surface.default_provider!r}")

    digest_payload = _config_digest_payload(global_config, surfaces, providers, contracts, rules)
    return WorkspaceConfig(config_path=config_path, workspace_root=workspace_root, global_config=global_config, surfaces=surfaces,
                           providers=providers, contracts=contracts, rules=rules, config_digest=digest_json(digest_payload))
