from __future__ import annotations

from typing import Mapping, Sequence

from ..models import Finding, ProviderQuery, ProviderSnapshot, Severity
from ..utils import digest_bytes, is_inside
from .base import ProviderContext
from .common import build_snapshot, load_json, parse_entity_records, select_query_union


class FileJsonProvider:
    api_version = "1"
    plugin_id = "file-json"
    plugin_version = "0.1.0"

    def validate_config(self, options: Mapping[str, str]) -> list[Finding]:
        if not options.get("path"):
            return [Finding(code="PROV-010", message="file-json provider requires option path", severity=Severity.ERROR)]
        return []

    def open(self, context: ProviderContext, options: Mapping[str, str]) -> "FileJsonSession":
        return FileJsonSession(context, options)


class FileJsonSession:
    capabilities = frozenset({"resolve", "list", "revision", "batch", "offline", "atomic-snapshot"})

    def __init__(self, context: ProviderContext, options: Mapping[str, str]) -> None:
        self.context = context
        self.options = dict(options)

    def capture(self, queries: Sequence[ProviderQuery]) -> ProviderSnapshot:
        raw_path = self.options.get("path", "")
        path = (self.context.workspace_root / raw_path).resolve(strict=False)
        if not is_inside(path, self.context.workspace_root):
            from ..errors import ProviderUnavailable

            raise ProviderUnavailable(self.context.provider_name, f"path escapes workspace: {raw_path}")
        payload = load_json(path, provider=self.context.provider_name)
        records = select_query_union(parse_entity_records(payload, provider=self.context.provider_name), queries)
        raw = path.read_bytes()
        revision = str(payload.get("revision")) if isinstance(payload, dict) and payload.get("revision") is not None else digest_bytes(raw)
        return build_snapshot(provider=self.context.provider_name, adapter="file-json", adapter_version="0.1.0", revision=revision, consistency="local", records=records)

    def close(self) -> None:
        return None
