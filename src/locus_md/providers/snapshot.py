from __future__ import annotations

from typing import Mapping, Sequence

from ..models import Finding, ProviderQuery, ProviderSnapshot, Severity
from ..utils import is_inside
from .base import ProviderContext
from .common import build_snapshot, load_snapshot_file, select_query_union


class SnapshotProvider:
    api_version = "1"
    plugin_id = "snapshot"
    plugin_version = "0.1.0"

    def validate_config(self, options: Mapping[str, str]) -> list[Finding]:
        if not options.get("path"):
            return [Finding(code="PROV-010", message="snapshot provider requires option path", severity=Severity.ERROR)]
        return []

    def open(self, context: ProviderContext, options: Mapping[str, str]) -> "SnapshotSession":
        return SnapshotSession(context, options)


class SnapshotSession:
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
        source = load_snapshot_file(path, provider=self.context.provider_name)
        records = select_query_union(source.records, queries)
        return build_snapshot(provider=self.context.provider_name, adapter="snapshot", adapter_version="0.1.0", revision=source.revision,
                              consistency=source.consistency, captured_at=source.captured_at, records=records)

    def close(self) -> None:
        return None
