---
schema: locus.doc.v1
id: docs.design.document-contract-model
title: "Locus MD — document contract model"
type: system-design
status: active
owner: team:locus-md
tags: [contracts, design]
updated: "2026-08-28T00:27:14Z"
source_commit: "6ecd7cfe5fd1"
update_event: "user_request"
description: "Validated and connected to Locus MD navigation and self-validation contracts."
---

# 1. Scope model

Locus MD validates four levels.

## 1.1. Envelope

Frontmatter, path, naming, lifecycle, ownership, and provenance.

## 1.2. Graph

Links, indexes, reachability, duplicate authority, owned resources, and
cross-surface references.

## 1.3. Managed block

Marker grammar, schema, body structure, drift, and canonical rendering.

## 1.4. Provider assertion

Connects a block or document assertion to a normalized source snapshot.

Not every rule becomes a block. Reachability is a graph contract; a task table
is a managed projection.

# 2. Marker protocol version 1

```text
START := <!-- locus:<kind> <id> begin -->
END   := <!-- locus:<kind> <id> end -->
```

`kind` matches `[a-z][a-z0-9-]{0,31}`. `id` matches
`[a-z0-9][a-z0-9._-]{0,31}` and is unique per kind within a document.

```md
<!-- locus:milestone tasks begin -->
...
<!-- locus:milestone tasks end -->
```

Parser rules:

- ignore marker-like text inside fenced code blocks;
- reject nested managed blocks;
- reject unmatched start or end markers;
- require matching kind and ID pairs;
- reject duplicate pairs;
- treat marker lines as engine-owned;
- allow an empty body.

# 3. Why metadata stays outside the marker

Provider, selector, authority, and rendering rules change more often than block
identity. Putting them in comments creates noise, duplicates configuration, and
makes safe migration harder. The marker answers "where and what";
configuration answers "how to validate it."

# 4. Binding

```text
(surface, path, kind, id)
→ contract_id
→ schema, mode, provider, selector, renderer
```

Moving a file requires an explicit configuration update. A tool may propose a
migration but must never apply an ambiguous move silently.

# 5. Versions

Marker protocol, contract schema, renderer, provider snapshot, lock schema, and
optional frontmatter schema evolve independently. One version never controls
all protocols.

# 6. Authority modes

## Authored

An author owns the body. The handler validates references and facts but does not
render a replacement by default.

## Projection

The body is a materialized view of provider data.

- `verify` compares it with canonical rendering.
- `sync --check` reports a patch.
- `sync --write` replaces only the body.
- A manual edit is drift.

## Snapshot

The body records historical state. Live provider drift does not invalidate the
snapshot, but provenance is required.

Bidirectional authority is outside version 1.

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
      "provider_revision": "revision-42",
      "snapshot_digest": "sha256:...",
      "body_digest": "sha256:...",
      "synced_at": "2026-08-27T08:00:00Z"
    }
  }
}
```

- Configuration records desired intent.
- The provider supplies source facts.
- The document is the human-readable artifact.
- The lock records the last successful materialization.

The lock never reconstructs provider records.

```text
current body digest != lock body digest
→ DOC-BLOCK-MANUAL-DRIFT

render(current snapshot) != current body
→ DOC-BLOCK-OUT-OF-DATE
```

# 8. Repository graph

Node identity is `surface + normalized relative path`. Edges represent Markdown
links, reference-style links, configured indexes, resource ownership,
contract-to-provider bindings, and optional typed entity references.

Graph checks require existing targets, contained paths, valid index roots,
reachable required documents, unique canonical IDs, and configured
cross-surface behavior.

# 9. Frontmatter

The core imposes no host-specific fields. Each surface selects a JSON Schema.

```yaml
---
schema: locus.doc.v1
id: docs.milestones
title: Milestones
type: plan
status: active
owner: docs-platform
created_at: "2026-08-27"
created_by: "human:maintainer"
---
```

`created_by` records provenance. `owner` records current accountability.

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

The core does not interpret `fields`; the contract handler owns required field
semantics.

# 11. Deterministic rendering

A renderer declares a stable ID and version, sorts records, fixes column order,
normalizes escaping, preserves the target newline convention, excludes
nondeterministic timestamps, and never reads a provider or configuration by
itself.

# 12. Patch safety

A patch changes only `body_span`. Before writing, the engine checks the source
digest, patch overlap, marker identity, path containment, and symlink policy.
After writing, a second scan must find the same marker pair.
