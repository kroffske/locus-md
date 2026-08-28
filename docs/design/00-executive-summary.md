---
schema: locus.doc.v1
id: docs.design.executive-summary
title: "Locus MD — executive summary"
type: overview
status: active
owner: team:locus-md
tags: [product, overview]
updated: "2026-08-28T00:27:14Z"
source_commit: "6ecd7cfe5fd1"
update_event: "user_request"
description: "Validated and connected to Locus MD navigation and self-validation contracts."
---

# 1. Product decision

Locus MD is a standalone package that installs and runs without another host
application.

> Locus MD validates not only Markdown form, but also whether declared document
> projections match their data sources. Authored text outside managed regions
> remains unchanged.

The tool occupies the layer between ordinary Markdown validation and domain
systems:

```text
Markdown style / prose / links
                ↓
       Locus MD contracts
                ↓
files / JSON / Git / remote trackers / custom providers
```

# 2. Why a standalone package

The target users are broader than one host application:

- teams that need a reproducible documentation gate;
- other CLIs and build systems;
- repositories whose source of truth lives in JSON, YAML, Git, or remote services;
- pre-commit and CI environments;
- LLM agents that need a safe boundary between authored and machine-owned content.

The core therefore knows nothing about a host repository layout, a specific
task store, a particular tracker, or a host configuration runtime.

# 3. Main architecture decisions

## 3.1. Config-driven surfaces

The core does not require `docs/`, `docs/index.md`, or a fixed frontmatter enum.
A repository declares one or more surfaces:

```text
surface = root + include/exclude + index + envelope rules + graph rules
```

This supports `docs/`, `handbook/`, `adr/`, `runbooks/`, monorepo README sets,
or individual contract files.

## 3.2. One shared INI file

The default path is `.locus/config.ini`; `--config` accepts another path.
Locus MD reads only these namespaces:

```text
[locus.docs]
[locus.docs.surface:*]
[locus.docs.contract:*]
[locus.docs.provider:*]
[locus.docs.rule:*]
```

Unrelated sections are neither interpreted nor interpolated.

## 3.3. Short Markdown, detailed configuration

Markers contain only local identity:

```md
<!-- locus:milestone tasks begin -->
...
<!-- locus:milestone tasks end -->
```

Configuration carries the semantics:

```text
path + block_kind + block_id
→ schema + mode + provider + selector + renderer
```

## 3.4. Sidecar lock

`.locus/docs.lock.json` records the managed-body digest, provider-snapshot
digest, source revision, renderer, contract schema, and last successful
materialization. It detects manual drift without expanding the marker syntax.

## 3.5. Snapshot consistency

The engine builds the full query plan before provider I/O. Each provider then
captures one immutable snapshot for the run. All contracts for that provider
see the same revision.

## 3.6. One-way integration

```text
locus-md core
      ↑
optional provider plugins
      ↑
host adapter
```

The core never imports a host application. A host may call the public Python
API, register providers, or run `locus.md` as a subprocess.

# 4. First release boundary

Included:

- namespaced INI loading;
- configurable documentation surfaces;
- YAML frontmatter with JSON Schema;
- Markdown scanning and repository graphs;
- short managed-block markers and config bindings;
- `file-json` and snapshot providers;
- immutable snapshots;
- `lint`, `verify`, `sync --check`, and `sync --write`;
- lock evidence and JSON diagnostics;
- provider and contract plugin APIs.

Excluded:

- remote writes and bidirectional sync;
- LLM-mediated pass/fail decisions;
- a custom version-control system;
- a language server;
- a general prose or style linter.

# 5. Acceptance criteria

1. A clean checkout reproduces `lint`, `verify`, and `sync --check`.
2. The same configuration and snapshot produce the same findings and rendered block.
3. `sync --write` changes no bytes outside managed spans.
4. Repeated sync is a no-op.
5. Lock evidence or a fresh render detects manual projection edits.
6. An unavailable required provider produces `unverified`, never a false pass.
7. Unknown schemas, providers, and renderers produce clear configuration errors.
8. Contracts backed by different providers can coexist in one document.
9. The standalone CLI has no host-runtime dependency.
