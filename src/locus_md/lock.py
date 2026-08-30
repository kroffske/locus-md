from __future__ import annotations

import json
from pathlib import Path

from .models import Finding, LockEntry, LockState, Severity, WorkspaceConfig
from .utils import digest_bytes, resolve_inside


def lock_path(config: WorkspaceConfig) -> Path:
    return resolve_inside(config.workspace_root, config.global_config.lock_file, key="locus.md.lock_file")


def load_lock(config: WorkspaceConfig) -> tuple[LockState, list[Finding]]:
    path = lock_path(config)
    if not path.exists():
        return LockState(entries={}), []
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        payload = json.loads(text)
    except UnicodeDecodeError as exc:
        finding = Finding(code="DOC-LOCK-001", message=f"lock file is not UTF-8: {exc}", severity=Severity.ERROR, path=config.global_config.lock_file)
        return LockState(entries={}, source_digest=digest_bytes(path.read_bytes())), [finding]
    except json.JSONDecodeError as exc:
        state = LockState(entries={}, source_text=path.read_text(encoding="utf-8", errors="replace"), source_digest=digest_bytes(path.read_bytes()))
        finding = Finding(code="DOC-LOCK-001", message=f"invalid lock JSON: {exc.msg}", severity=Severity.ERROR,
                          path=config.global_config.lock_file, line=exc.lineno, column=exc.colno)
        return state, [finding]
    except OSError as exc:
        return LockState(entries={}), [Finding(code="DOC-LOCK-001", message=f"cannot read lock file: {exc}", severity=Severity.ERROR, path=config.global_config.lock_file)]
    if not isinstance(payload, dict) or payload.get("schema") != "locus-md.lock.v1" or not isinstance(payload.get("contracts", {}), dict):
        finding = Finding(code="DOC-LOCK-002", message="lock file must use schema locus-md.lock.v1 and contain a contracts object",
                          severity=Severity.ERROR, path=config.global_config.lock_file)
        return LockState(entries={}, source_text=text, source_digest=digest_bytes(raw)), [finding]
    entries: dict[str, LockEntry] = {}
    findings: list[Finding] = []
    for name, item in payload.get("contracts", {}).items():
        if not isinstance(name, str) or not isinstance(item, dict):
            findings.append(Finding(code="DOC-LOCK-002", message="invalid contract entry in lock file", severity=Severity.ERROR, path=config.global_config.lock_file))
            continue
        required = ("surface", "path", "block_kind", "block_id", "contract_schema", "provider", "provider_revision", "snapshot_digest", "body_digest", "synced_at")
        missing = [key for key in required if not isinstance(item.get(key), str)]
        if missing:
            findings.append(Finding(code="DOC-LOCK-002", message=f"lock entry {name!r} is missing string fields: {', '.join(missing)}",
                                    severity=Severity.ERROR, path=config.global_config.lock_file))
            continue
        entries[name] = LockEntry(
            surface=item["surface"],
            path=item["path"],
            block_kind=item["block_kind"],
            block_id=item["block_id"],
            contract_schema=item["contract_schema"],
            renderer=item.get("renderer") if isinstance(item.get("renderer"), str) else None,
            provider=item["provider"],
            provider_revision=item["provider_revision"],
            snapshot_digest=item["snapshot_digest"],
            body_digest=item["body_digest"],
            synced_at=item["synced_at"],
        )
    return LockState(entries=entries, source_text=text, source_digest=digest_bytes(raw)), findings


def serialize_lock(entries: dict[str, LockEntry]) -> str:
    payload = {"schema": "locus-md.lock.v1", "contracts": {name: entry.to_dict() for name, entry in sorted(entries.items())}}
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
