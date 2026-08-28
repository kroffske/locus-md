from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..errors import ProviderUnavailable
from ..models import EntityRecord, ProviderQuery, ProviderSnapshot
from ..utils import digest_json, utc_now


def parse_entity_records(payload: Any, *, provider: str) -> tuple[EntityRecord, ...]:
    raw_records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(raw_records, list):
        raise ProviderUnavailable(provider, "provider document must be a list or an object with a records list")
    records: list[EntityRecord] = []
    for index, raw in enumerate(raw_records):
        if not isinstance(raw, dict):
            raise ProviderUnavailable(provider, f"record {index} must be an object")
        kind = raw.get("kind")
        entity_id = raw.get("id")
        fields = raw.get("fields", {})
        if not isinstance(kind, str) or not kind:
            raise ProviderUnavailable(provider, f"record {index} has no valid kind")
        if not isinstance(entity_id, str) or not entity_id:
            raise ProviderUnavailable(provider, f"record {index} has no valid id")
        if not isinstance(fields, dict):
            raise ProviderUnavailable(provider, f"record {entity_id!r} fields must be an object")
        revision = raw.get("revision")
        url = raw.get("url")
        records.append(EntityRecord(kind=kind, entity_id=entity_id, revision=str(revision) if revision is not None else None,
                                    fields=fields, url=str(url) if url is not None else None))
    return tuple(sorted(records, key=lambda item: (item.kind, item.entity_id, item.revision or "")))


def matches_query(record: EntityRecord, query: ProviderQuery) -> bool:
    if record.kind != query.kind:
        return False
    for key, expected in query.selector.items():
        actual = record.entity_id if key == "id" else record.kind if key == "kind" else record.fields.get(key)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def select_query_union(records: Iterable[EntityRecord], queries: Iterable[ProviderQuery]) -> tuple[EntityRecord, ...]:
    query_list = list(queries)
    if not query_list:
        return tuple(records)
    selected = [record for record in records if any(matches_query(record, query) for query in query_list)]
    return tuple(sorted(selected, key=lambda item: (item.kind, item.entity_id, item.revision or "")))


def snapshot_digest(records: Iterable[EntityRecord]) -> str:
    return digest_json([record.canonical() for record in sorted(records, key=lambda item: (item.kind, item.entity_id, item.revision or ""))])


def load_json(path: Path, *, provider: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProviderUnavailable(provider, f"file not found: {path}") from exc
    except UnicodeDecodeError as exc:
        raise ProviderUnavailable(provider, f"file is not UTF-8: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ProviderUnavailable(provider, f"invalid JSON in {path}: {exc.msg}") from exc
    except OSError as exc:
        raise ProviderUnavailable(provider, f"cannot read {path}: {exc}") from exc


def build_snapshot(
    *, provider: str, adapter: str, adapter_version: str, revision: str, consistency: str, records: tuple[EntityRecord, ...],
    captured_at: str | None = None
) -> ProviderSnapshot:
    return ProviderSnapshot(provider=provider, adapter=adapter, adapter_version=adapter_version, revision=revision, consistency=consistency,
                            captured_at=captured_at or utc_now(), records=records, content_digest=snapshot_digest(records))


def load_snapshot_file(path: Path, *, provider: str) -> ProviderSnapshot:
    payload = load_json(path, provider=provider)
    if not isinstance(payload, Mapping) or payload.get("schema") != "locus-md.snapshot.v1":
        raise ProviderUnavailable(provider, f"snapshot file {path} does not use schema locus-md.snapshot.v1")
    records = parse_entity_records(payload, provider=provider)
    return build_snapshot(
        provider=provider,
        adapter=str(payload.get("adapter", "snapshot")),
        adapter_version=str(payload.get("adapter_version", "unknown")),
        revision=str(payload.get("revision", payload.get("content_digest", "snapshot"))),
        consistency=str(payload.get("consistency", "snapshot")),
        captured_at=str(payload.get("captured_at", utc_now())),
        records=records,
    )
