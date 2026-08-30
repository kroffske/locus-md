from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import traceback
from typing import Any, Sequence

from . import __version__
from .config import initialize_config, load_config
from .engine import Engine
from .errors import ConfigError, GitError, LocusMdError, WriteConflict
from .impact import build_impact
from .models import Report, RunState
from .plugins import PluginRegistry


def _set(values: Sequence[str] | None) -> set[str] | None:
    return set(values) if values else None


def _exit_code(report: Report) -> int:
    return {RunState.PASSED: 0, RunState.FAILED: 1, RunState.CONFIGURATION_ERROR: 2, RunState.UNVERIFIED: 3, RunState.INTERNAL_ERROR: 5}[report.state]


def _print_report(report: Report, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        return
    for finding in report.sorted_findings():
        location = ""
        if finding.path:
            location = f" {finding.path}"
            if finding.line:
                location += f":{finding.line}"
                if finding.column:
                    location += f":{finding.column}"
        contract = f" [{finding.contract_id}]" if finding.contract_id else ""
        print(f"{finding.severity.value.upper()} {finding.code}{location}{contract}")
        print(f"  {finding.message}")
        if finding.remediation:
            print(f"  {finding.remediation.kind}: {finding.remediation.value}")
    for patch in report.patches:
        if patch.diff:
            print(patch.diff, end="" if patch.diff.endswith("\n") else "\n")
    print(f"{report.mode}: {report.state.value}; findings={len(report.findings)}; patches={len(report.patches)}")


def _init_config(args: argparse.Namespace) -> int:
    result = initialize_config(explicit=args.config, check=args.check, print_only=args.print_only)
    if result.action == "print":
        print(result.content, end="")
    elif result.action == "missing":
        print(f"{result.path}: locus-md scaffold is missing")
        return 1
    elif result.action == "created":
        print(f"created {result.path}")
    else:
        print(f"{result.path}: locus-md scaffold already present" if args.check else f"unchanged {result.path}")
    return 0


def _config_validate(args: argparse.Namespace, registry: PluginRegistry) -> int:
    config = load_config(explicit=args.config, start=args.start)
    registry.validate_references(config)
    payload = {
        "state": "passed", "config_path": str(config.config_path), "workspace_root": str(config.workspace_root),
        "config_digest": config.config_digest, "surfaces": sorted(config.surfaces), "providers": sorted(config.providers),
        "contracts": sorted(config.contracts), "rules": sorted(config.rules), "documents": sorted(config.documents),
    }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Configuration OK: {config.config_path}")
        print(
            f"workspace={config.workspace_root} surfaces={len(config.surfaces)} providers={len(config.providers)} "
            f"contracts={len(config.contracts)} rules={len(config.rules)} documents={len(config.documents)}"
        )
    return 0


def _config_show(args: argparse.Namespace, registry: PluginRegistry) -> int:
    config = load_config(explicit=args.config, start=args.start)
    registry.validate_references(config)
    print(json.dumps(config.normalized(redact=True), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _guide(args: argparse.Namespace, config: Any) -> int:
    document = config.documents.get(args.document)
    if document is None:
        available = ", ".join(sorted(config.documents)) or "none"
        raise ConfigError("CFG-070", f"unknown document id {args.document!r}; available ids: {available}")
    surface = config.surfaces[document.surface]
    path = document.path if surface.root == "." else f"{surface.root}/{document.path}"
    payload = {
        "schema": "locus-md.guide.v1",
        "document": {
            "id": document.name,
            "surface": document.surface,
            "path": path,
            "description": document.description,
            "guidance": document.guidance,
            "sections": [
                {"id": section.name, "heading": section.heading, "required": section.required, "guidance": section.guidance}
                for section in document.sections.values()
            ],
        },
    }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print(f"Document: {document.name}")
    print(f"Path: {path}")
    print(f"Description: {document.description}")
    if document.guidance:
        print(f"Guidance: {document.guidance}")
    for section in document.sections.values():
        print(f"Section: {section.heading} ({'required' if section.required else 'optional'})")
        if section.guidance:
            print(f"  Guidance: {section.guidance}")
    return 0


def _impact(args: argparse.Namespace, engine: Engine) -> int:
    scan = engine.scan()
    report = build_impact(engine.config, args.base, scan.documents.values())
    if args.format == "json":
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Base: {report.base}")
        print(f"Configuration changed: {'yes' if report.configuration_changed else 'no'}")
        for change in report.changes:
            managed = "managed" if change.managed else "unmanaged"
            rename = f" from {change.old_path}" if change.old_path else ""
            print(f"{change.status}: {change.path}{rename} ({managed})")
            if change.dependents:
                print(f"  dependents: {', '.join(change.dependents)}")
    return 0


def _contracts_list(args: argparse.Namespace, engine: Engine) -> int:
    rows = engine.contracts_list(surfaces=_set(args.surface))
    if args.format == "json":
        print(json.dumps({"schema": "locus-md.contract-list.v1", "contracts": rows}, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        if not rows:
            print("No contracts configured.")
        for row in rows:
            state = "found" if row["found"] else "missing"
            locked = "locked" if row["locked"] else "unlocked"
            print(f"{row['name']}: {row['surface']}:{row['path']} {row['block_kind']}/{row['block_id']} schema={row['schema']} provider={row['provider']} {state} {locked}")
    return 0


def _doctor(args: argparse.Namespace, config: Any, registry: PluginRegistry) -> int:
    lock = config.workspace_root / config.global_config.lock_file
    payload = {
        "state": "informational",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "config_path": str(config.config_path),
        "workspace_root": str(config.workspace_root),
        "workspace_writable": os.access(config.workspace_root, os.W_OK),
        "lock_parent_writable": os.access(lock.parent if lock.parent.exists() else config.workspace_root, os.W_OK),
        "providers": sorted(registry.providers),
        "contracts": sorted(registry.contracts),
        "rules": sorted(registry.rules),
        "plugin_load_errors": registry.load_errors,
    }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0


def _add_common_options(target: argparse.ArgumentParser, *, suppress_defaults: bool) -> None:
    default = argparse.SUPPRESS if suppress_defaults else None
    target.add_argument("--config", default=default, help="explicit TOML configuration path")
    target.add_argument("--start", default=default, help="directory used for config discovery")
    target.add_argument("--format", choices=("human", "json"), default=argparse.SUPPRESS if suppress_defaults else "human", help="output format")
    target.add_argument("--strict", action="store_true", default=argparse.SUPPRESS if suppress_defaults else False, help="promote warnings to errors")
    target.add_argument("--debug", action="store_true", default=argparse.SUPPRESS if suppress_defaults else False, help="show traceback for unexpected failures")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="locus-md", description="Semantic documentation contracts for Markdown repositories")
    parser.add_argument("--version", action="version", version=f"locus-md {__version__}")
    _add_common_options(parser, suppress_defaults=False)
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="create a locus-md TOML configuration scaffold")
    _add_common_options(init, suppress_defaults=True)
    init.add_argument("--check", action="store_true", help="check whether the scaffold is present")
    init.add_argument("--print", dest="print_only", action="store_true", help="print scaffold without writing")

    config = commands.add_parser("config", help="configuration commands")
    _add_common_options(config, suppress_defaults=True)
    config_commands = config.add_subparsers(dest="config_command", required=True)
    validate = config_commands.add_parser("validate", help="validate configuration and plugin references")
    _add_common_options(validate, suppress_defaults=True)
    show = config_commands.add_parser("show", help="show sanitized normalized configuration")
    _add_common_options(show, suppress_defaults=True)
    show.add_argument("--normalized", action="store_true", default=True)

    guide = commands.add_parser("guide", help="show authoring guidance for a declared document")
    _add_common_options(guide, suppress_defaults=True)
    guide.add_argument("document", help="declared document id")

    impact = commands.add_parser("impact", help="report documents affected by Git changes")
    _add_common_options(impact, suppress_defaults=True)
    impact.add_argument("--base", required=True, help="Git ref to compare with the current worktree")

    lint = commands.add_parser("lint", help="run static documentation checks")
    _add_common_options(lint, suppress_defaults=True)
    lint.add_argument("--surface", action="append", help="limit to a configured surface")

    verify = commands.add_parser("verify", help="run static checks and provider assertions")
    _add_common_options(verify, suppress_defaults=True)
    verify.add_argument("--surface", action="append", help="limit to a configured surface")
    verify.add_argument("--provider", action="append", help="limit to contracts using a configured provider")
    verify_network = verify.add_mutually_exclusive_group()
    verify_network.add_argument("--offline", action="store_true", help="forbid remote provider calls")
    verify_network.add_argument("--network", action="store_true", help="allow network providers when policy is explicit")

    sync = commands.add_parser("sync", help="check or write deterministic managed projections")
    _add_common_options(sync, suppress_defaults=True)
    sync.add_argument("--surface", action="append", help="limit to a configured surface")
    sync.add_argument("--provider", action="append", help="limit to contracts using a configured provider")
    sync_mode = sync.add_mutually_exclusive_group()
    sync_mode.add_argument("--check", action="store_true", help="show required patches without writing")
    sync_mode.add_argument("--write", action="store_true", help="apply safe patches and update lock evidence")
    sync_network = sync.add_mutually_exclusive_group()
    sync_network.add_argument("--offline", action="store_true", help="forbid remote provider calls")
    sync_network.add_argument("--network", action="store_true", help="allow network providers when policy is explicit")

    contracts = commands.add_parser("contracts", help="inspect contract bindings")
    _add_common_options(contracts, suppress_defaults=True)
    contract_commands = contracts.add_subparsers(dest="contracts_command", required=True)
    contract_list = contract_commands.add_parser("list", help="list bindings, blocks, providers, and lock status")
    _add_common_options(contract_list, suppress_defaults=True)
    contract_list.add_argument("--surface", action="append", help="limit to a configured surface")

    doctor = commands.add_parser("doctor", help="inspect environment and plugin availability")
    _add_common_options(doctor, suppress_defaults=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            return _init_config(args)
        registry = PluginRegistry()
        if args.command == "config" and args.config_command == "validate":
            return _config_validate(args, registry)
        if args.command == "config" and args.config_command == "show":
            return _config_show(args, registry)
        config = load_config(explicit=args.config, start=args.start)
        if args.command == "guide":
            return _guide(args, config)
        engine = Engine(config, registry=registry)
        if args.command == "impact":
            return _impact(args, engine)
        if args.command == "lint":
            report = engine.lint(surfaces=_set(args.surface), force_strict=args.strict)
            _print_report(report, args.format)
            return _exit_code(report)
        if args.command == "verify":
            report = engine.verify(surfaces=_set(args.surface), providers=_set(args.provider), offline=args.offline, network=args.network, force_strict=args.strict)
            _print_report(report, args.format)
            return _exit_code(report)
        if args.command == "sync":
            report = engine.sync(write=args.write, surfaces=_set(args.surface), providers=_set(args.provider), offline=args.offline, network=args.network, force_strict=args.strict)
            _print_report(report, args.format)
            return _exit_code(report)
        if args.command == "contracts" and args.contracts_command == "list":
            return _contracts_list(args, engine)
        if args.command == "doctor":
            return _doctor(args, config, registry)
        parser.error("unsupported command")
        return 2
    except ConfigError as exc:
        if args.format == "json":
            payload = {"schema": "locus-md.error.v1", "state": "configuration-error", "code": exc.code, "message": exc.message,
                       "path": str(exc.path) if exc.path else None}
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(str(exc), file=sys.stderr)
        return 2
    except WriteConflict as exc:
        if args.format == "json":
            payload = {"schema": "locus-md.error.v1", "state": "write-conflict", "code": "SYNC-001", "message": str(exc), "path": str(exc.path)}
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"SYNC-001: {exc}", file=sys.stderr)
        return 4
    except GitError as exc:
        if args.format == "json":
            print(json.dumps({"schema": "locus-md.error.v1", "state": "git-error", "code": exc.code, "message": exc.message}, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(str(exc), file=sys.stderr)
        return 2
    except LocusMdError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        if args.debug:
            traceback.print_exc()
        else:
            print(f"INTERNAL-001: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 5
