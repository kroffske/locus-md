---
title: "Locus MD — document contract model"
status: proposed
date: "2026-08-27"
---

# 1. Scope model

Locus MD разделяет четыре уровня проверки.

## 1.1. Envelope

Frontmatter, path, naming, lifecycle, ownership и provenance.

## 1.2. Graph

Links, indexes, reachability, duplicate authority, owned resources и cross-surface references.

## 1.3. Managed block

Marker grammar, schema, body structure, drift и canonical render.

## 1.4. Provider assertion

Связывает block или document assertion с normalized source snapshot.

Не каждый rule становится block: reachability — graph contract, task table — managed projection.

# 2. Marker protocol v1

```text
START := <!-- locus:<kind> <id> begin -->
END   := <!-- locus:<kind> <id> end -->
```

`kind`:

```regex
[a-z][a-z0-9-]{0,31}
```

`id`:

```regex
[a-z0-9][a-z0-9._-]{0,31}
```

ID уникален внутри документа для данного `kind`.

```md
<!-- locus:milestone tasks begin -->
...
<!-- locus:milestone tasks end -->
```

Parser rules:

- markers в fenced code blocks игнорируются;
- nested blocks запрещены;
- start без end и end без start — error;
- kind/id пары должны совпадать;
- duplicate pair — error;
- marker lines принадлежат engine;
- body может быть пустым.

# 3. Почему metadata не находится в marker

Provider, selector и authority меняются чаще, чем identity. Их размещение в комментарии создаёт шум, повышает риск поломки LLM, дублирует config и усложняет migration.

Marker отвечает «где и какой блок», config — «как его проверять».

# 4. Binding

```text
(surface, path, kind, id)
→ contract_id
→ schema, mode, provider, selector, renderer
```

При перемещении файла config обновляется явно. Tool может предложить migration, но не применяет его молча.

# 5. Versions

Разделяются:

- marker protocol;
- contract schema;
- renderer;
- provider snapshot schema;
- lock schema;
- optional frontmatter schema.

Одна версия не управляет всеми protocols.

# 6. Authority modes

## Authored

Body принадлежит человеку. Handler проверяет references/facts и не генерирует replacement по умолчанию.

## Projection

Body — materialized view provider data.

- `verify` сравнивает с canonical render;
- `sync --check` показывает patch;
- `sync --write` заменяет body;
- ручная правка считается drift.

## Snapshot

Body фиксирует historical state. Live provider drift не делает snapshot ошибочным, но provenance обязателен.

Bidirectional authority отсутствует в v1.

# 7. Lock model

Tracked path:

```text
.locus/docs.lock.json
```

```json
{
  "schema": "locus-md.lock.v1",
  "contracts": {
    "active-milestone": {
      "surface": "docs",
      "path": "milestones.md",
      "block_kind": "milestone",
      "block_id": "tasks",
      "contract_schema": "task-table.v1",
      "renderer": "task-table.v1",
      "provider": "tasks",
      "provider_revision": "tasks-20260827-01",
      "snapshot_digest": "sha256:...",
      "body_digest": "sha256:...",
      "synced_at": "2026-08-27T08:00:00Z"
    }
  }
}
```

Semantics:

- Config — desired intent.
- Provider — source facts.
- Document — human-readable artifact.
- Lock — evidence последней successful materialization.

Lock не используется для восстановления provider records.

## Drift

```text
current body digest != lock body digest
→ DOC-BLOCK-MANUAL-DRIFT
```

```text
render(current snapshot) != current body
→ DOC-BLOCK-OUT-OF-DATE
```

# 8. Repository graph

Node identity:

```text
surface + normalized relative path
```

Edges:

- Markdown link;
- reference-style link;
- configured index;
- resource ownership;
- contract-to-provider;
- optional typed entity reference.

Graph checks:

- target exists;
- no workspace escape;
- index roots exist;
- required docs reachable;
- no duplicate canonical IDs;
- optional cross-surface policy.

# 9. Frontmatter

Core не навязывает Locus-specific поля. Surface выбирает JSON Schema.

Example:

```yaml
---
schema: locus.doc.v1
id: docs.milestones
title: Milestones
type: plan
status: active
owner: docs-platform
created_at: "2026-08-27"
created_by: "human:ravius"
---
```

`created_by` — provenance, `owner` — current accountability.

# 10. Entity records

```json
{
  "kind": "task",
  "id": "T-101",
  "revision": "42",
  "fields": {
    "title": "Add parser",
    "status": "done",
    "milestone": "m01"
  },
  "url": null
}
```

Core не интерпретирует fields. Handler знает required fields.

# 11. Deterministic rendering

Renderer:

- объявляет stable ID/version;
- сортирует records;
- фиксирует columns;
- нормализует escaping;
- использует target newline convention;
- не добавляет nondeterministic timestamps;
- не читает provider/config самостоятельно.

# 12. Patch safety

Patch изменяет только `body_span`.

Перед write проверяются source digest, non-overlap, marker identity, path containment и symlink policy. После write повторный scan обязан найти тот же marker pair.
