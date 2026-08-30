from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

from .errors import ConfigError

_ENV_PATTERN = re.compile(r"\$\{ENV:([A-Za-z_][A-Za-z0-9_]*)\}")
_ANY_SUBSTITUTION_PATTERN = re.compile(r"\$\{[^}]+\}")
_SECRET_KEY_PATTERN = re.compile(r"(?:token|secret|password|credential|api[_-]?key|private[_-]?key)", re.IGNORECASE)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def digest_text(value: str) -> str:
    return digest_bytes(value.encode("utf-8"))


def digest_json(value: Any) -> str:
    return digest_bytes(canonical_json_bytes(value))


def substitute_environment(value: str, env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in source:
            raise ConfigError("CFG-041", f"environment variable {name!r} is not set")
        return source[name]

    replaced = _ENV_PATTERN.sub(replace, value)
    if _ANY_SUBSTITUTION_PATTERN.search(replaced):
        raise ConfigError("CFG-040", "cross-section or unsupported interpolation is forbidden")
    return replaced


def safe_relative_posix(value: str, *, key: str) -> str:
    raw = value.strip().replace("\\", "/")
    path = PurePosixPath(raw)
    if not raw or path.is_absolute():
        raise ConfigError("CFG-050", f"{key} must be a non-empty relative path, got {value!r}")
    parts: list[str] = []
    for part in path.parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                raise ConfigError("CFG-050", f"{key} escapes the workspace: {value!r}")
            parts.pop()
        else:
            parts.append(part)
    if not parts:
        raise ConfigError("CFG-050", f"{key} must resolve to a non-empty relative path, got {value!r}")
    return PurePosixPath(*parts).as_posix()


def resolve_inside(root: Path, relative: str, *, key: str) -> Path:
    normalized = safe_relative_posix(relative, key=key)
    candidate = (root / Path(normalized)).resolve(strict=False)
    root_resolved = root.resolve(strict=False)
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ConfigError("CFG-050", f"{key} escapes the workspace: {relative!r}") from exc
    return candidate


def is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def redact_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        if _SECRET_KEY_PATTERN.search(key):
            result[key] = "<redacted>"
        elif isinstance(item, Mapping):
            result[key] = redact_mapping(item)
        elif isinstance(item, list):
            result[key] = [redact_mapping(v) if isinstance(v, Mapping) else v for v in item]
        else:
            result[key] = item
    return result


def unique_stable(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)
