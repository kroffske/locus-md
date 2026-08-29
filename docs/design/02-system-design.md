---
schema: locus.doc.v1
id: docs.design.system-design
title: "locus-md — system design"
type: system-design
status: active
owner: team:locus-md
tags: [architecture, design]
updated: "2026-08-28T00:27:14Z"
source_commit: "6ecd7cfe5fd1"
update_event: "user_request"
description: "Validated and connected to locus-md navigation and self-validation contracts."
---

# 1. Architecture style

locus-md is a **library-first modular monolith** with plugin boundaries.

```text
CLI / Python API
       ↓
Workspace + Config
       ↓
Document Scanner + Repository Graph
       ↓
Contract Planner
       ↓
Provider Sessions / Snapshots
       ↓
Validation + Rendering
       ↓
Findings + Patches + Lock
```

It is neither a microservice nor a collection of scripts. Provider plugins may
perform external I/O, but orchestration remains in one process.

# 2. System context

Actors:

- maintainers;
- CI systems;
- programmatic hosts, including LLM applications;
- provider systems;
- Git repositories.

Trust boundaries:

- repository content is untrusted input;
- shared INI files are versioned intent and must be validated;
- plugins are executable trusted code;
- remote responses are untrusted data and must be normalized;
- secrets enter only through environment variables or a host credential layer.

# 3. Components

## 3.1. `config`

Responsibilities:

- discover configuration;
- read namespaced sections;
- convert and validate values;
- resolve inheritance and paths;
- compute the configuration digest.

It must not read unrelated sections, obtain credentials, call providers, or
choose a silent default when discovery is ambiguous.

## 3.2. `workspace`

Derives the workspace root from the selected configuration file. It then builds
surface inventories, applies include and exclude rules, and enforces symlink
policy. An enclosing Git repository must not capture a nested standalone
workspace.

## 3.3. `markdown`

Parses each document once and returns:

- frontmatter span and data;
- headings and links;
- fenced-code ranges and HTML comments;
- managed-block spans;
- line and column maps.

Tokens describe structure. Rewrites use source offsets so authored formatting
is preserved.

## 3.4. `graph`

Builds a repository graph from document nodes, local-link edges, index roots,
owned-resource edges, and contract edges. Graph checks do not depend on
managed-block providers.

## 3.5. `contracts`

Owns the contract-handler registry. A handler parses a body, declares provider
queries, validates normalized records, renders a canonical body, and describes
required fields. The core contains no tracker-specific semantics.

## 3.6. `providers`

Owns adapter discovery and session lifecycle:

- validate provider options;
- open one session;
- batch queries;
- capture and normalize one snapshot;
- expose revision and consistency.

## 3.7. `planner`

Transforms documents and configuration into static-rule, contract,
provider-query, and patch plans. Before provider I/O it rejects unbound blocks,
missing markers, duplicate identifiers, unknown plugins, and incompatible
capabilities.

## 3.8. `engine`

Coordinates `lint`, `verify`, `sync --check`, `sync --write`, and inspection
commands.

## 3.9. `rewrite`

Accepts ordered, non-overlapping patches and:

1. validates the source digest;
2. applies replacements from the end of the file;
3. preserves encoding and newline convention;
4. writes a temporary file;
5. validates every prepared source before replacement;
6. atomically replaces each target, with the lock ordered last.

The current release does not promise rollback after a filesystem failure during
the replacement phase. It prevents stale and partial preparation from being
committed, but a process or filesystem failure between replacements still
requires inspection before retrying.

## 3.10. `reporting`

Produces human and JSON output. SARIF is a later format. Findings sort by
surface, path, line, column, code, and message.

# 4. Run pipeline

## Phase A — Bootstrap

1. Discover configuration.
2. Derive the workspace from that configuration.
3. Load only `locus.docs*` sections.
4. Normalize configuration.
5. Load the plugin registry.
6. Record run metadata.

## Phase B — Inventory

1. Expand surface globs.
2. Normalize paths and apply exclusions.
3. Compute content digests.
4. Read tracked lock evidence.

## Phase C — Parse

1. Parse frontmatter and Markdown tokens.
2. Scan markers while respecting fenced code blocks.
3. Build document records and local-link edges.

## Phase D — Static lint

1. Validate envelope schemas and naming.
2. Validate local links and reachability.
3. Validate marker grammar and binding coverage.
4. Compare managed bodies with lock evidence.

`lint` stops here and never opens a provider.

## Phase E — Plan semantic verification

1. Resolve contract inheritance.
2. Validate required capabilities.
3. Group provider queries.
4. Resolve network permission and explicit offline snapshot policy.

## Phase F — Capture snapshots

Each provider creates at most one session snapshot per run. A result may be
verified, unverified, failed, or partial. Partial evidence is never promoted to
success automatically.

## Phase G — Evaluate

1. Pass the current block model and immutable snapshot view to the handler.
2. Collect findings.
3. Build a canonical body in sync mode.
4. Compute the patch and new lock entry.

## Phase H — Commit the result

- `lint`, `verify`, and `sync --check` only report.
- `sync --write` prepares and validates every patch, then atomically replaces
  each target with the lock ordered last.
- A source-digest mismatch cancels the write and requires a new run.

# 5. Core data model

```text
WorkspaceConfig
SurfaceConfig
RuleConfig
ProviderConfig
ContractBinding

DocumentRecord
FrontmatterRecord
LinkRecord
ManagedBlock

ProviderQuery
EntityRecord
ProviderSnapshot

Finding
Patch
LockEntry
Report
```

`ManagedBlock` identifies its surface, path, kind, local ID, marker spans, body
span, and body digest. `ContractBinding` connects that identity to schema,
mode, provider, selector, renderer, and severity.

# 6. State model

Verification states:

```text
passed
failed
unverified
configuration-error
internal-error
```

`unverified` means a semantic assertion was not proved. It is neither a pass nor
a mismatch.

Authority modes:

```text
authored
projection
snapshot
```

- `authored`: an author owns the body; the engine validates it.
- `projection`: a provider owns the data; sync owns the body.
- `snapshot`: the body records historical evidence; live drift is not an error, but provenance is required.

Bidirectional authority is outside version 1.

# 7. Consistency, offline evidence, and lock

The snapshot digest covers canonical JSON containing schema, provider, adapter,
adapter version, revision, consistency, and records. `captured_at` is excluded
from the content digest.

The configuration model reserves `cache_dir` and provider `cache_ttl`, but the
current engine does not execute a cache layer. Offline remote-provider evidence
comes only from an explicit `snapshot_file`. Cache behavior remains deferred.

The lock stores reproducible materialization evidence. It is authority evidence,
not a future cache.

# 8. Failure semantics

| Situation | Result |
|---|---|
| Invalid INI or schema | `configuration-error` |
| Unknown plugin | `configuration-error` |
| Marker without a binding | `DOC-BLOCK-010` |
| Required binding without a marker | `DOC-BLOCK-011` |
| Provider unavailable | `unverified` |
| Block differs from canonical render | `DOC-BLOCK-021` and `failed` |
| Block differs from lock evidence | `DOC-BLOCK-020` and `failed` |
| File changes between scan and write | write conflict |
| Unexpected internal exception | `internal-error` |

# 9. Concurrency

The current engine executes document parsing, provider capture, and writes
serially. Providers may manage concurrency inside their own session, but their
returned snapshot must already be stable and normalized. A future parallel
engine must preserve deterministic ordering and keep writes serial.

# 10. Public Python API

```python
from locus_md import verify

result = verify(config=".locus/config.ini", offline=True)
```

The CLI is a thin adapter over the public API.

# 11. Repository layout

```text
locus-md/
├── pyproject.toml
├── src/locus_md/
│   ├── api.py
│   ├── cli.py
│   ├── config.py
│   ├── workspace.py
│   ├── markdown.py
│   ├── graph.py
│   ├── engine.py
│   ├── rewrite.py
│   ├── lock.py
│   ├── contracts/
│   ├── providers/
│   └── schemas/
├── docs/
├── examples/
└── tests/
```

# 12. Dependency policy

Runtime dependencies are Python 3.11+, `markdown-it-py`, `PyYAML`, and
`jsonschema`, plus standard-library configuration, path, hashing, and plugin
discovery modules. The core does not include remote-service SDKs; integrations
belong in optional plugins.
