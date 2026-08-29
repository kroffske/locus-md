---
schema: locus.doc.v1
id: docs.design.product-requirements
title: "locus-md — product requirements"
type: prd
status: active
owner: team:locus-md
tags: [product, requirements]
updated: "2026-08-28T00:27:14Z"
source_commit: "6ecd7cfe5fd1"
update_event: "user_request"
description: "Validated and connected to locus-md navigation and self-validation contracts."
---

# 1. Problem

Markdown repositories combine four classes of content:

1. **Authored prose** — rationale, explanations, and notes.
2. **Document envelope** — title, type, status, owner, and provenance.
3. **Repository graph** — links, indexes, reachability, and ownership.
4. **Materialized projections** — task tables, milestone status, inventories, and generated indexes.

Ordinary Markdown linters validate form. They cannot prove that a task table
matches its source, that an index reaches every required page, or that an active
policy has an executable validator.

> A document can look structured and current while remaining a manual
> declaration with no reproducible contract.

# 2. Users

## Maintainer

Needs a deterministic CI gate with findings that name the path and remediation.

## Documentation platform owner

Defines surfaces, schemas, graph rules, and managed projections.

## Tool integrator

Adds a provider or contract kind without forking the core.

## LLM agent

Must distinguish freely editable regions from machine-owned regions.

## CI

Requires stable exit codes, machine-readable output, and clean-checkout
reproducibility.

# 3. Product goals

- Validate document structure and frontmatter.
- Validate the repository graph.
- Declare typed managed blocks.
- Compare blocks with provider snapshots.
- Update projections safely.
- Run as a standalone tool.
- Support custom surfaces, contracts, providers, and renderers.
- Produce the same result for humans, CI, and programmatic hosts.

# 4. Non-goals

- Replace `markdownlint`, Vale, spell checking, or a site generator.
- Create or close remote tasks from documentation commands.
- Infer the source of truth heuristically.
- Rewrite authored prose.
- Provide bidirectional synchronization in the first stable line.
- Store secrets.
- Become a VCS or object store.
- Execute arbitrary shell commands from configuration.
- Treat an LLM as part of the trusted validation path.

# 5. Functional requirements

| ID | Requirement |
|---|---|
| FR-001 | Discover configuration through an explicit path, environment, or project search |
| FR-002 | Read only `locus.docs*` sections |
| FR-003 | Support multiple independent documentation surfaces |
| FR-004 | Parse UTF-8 Markdown, YAML frontmatter, links, fenced blocks, and HTML comments |
| FR-005 | Validate frontmatter with JSON Schema |
| FR-006 | Build a repository graph of links, roots, indexes, and reachability |
| FR-007 | Validate paired managed markers, nesting, duplicates, and missing endpoints |
| FR-008 | Bind contracts by `surface + path + kind + id` |
| FR-009 | Build the full provider query plan before I/O |
| FR-010 | Capture immutable normalized provider snapshots |
| FR-011 | Run domain validation through contract handlers |
| FR-012 | Render projections deterministically |
| FR-013 | Run `sync --check` without writes |
| FR-014 | Restrict `sync --write` to block bodies and lock evidence |
| FR-015 | Return `unverified` offline when required evidence is absent |
| FR-016 | Discover plugins through Python entry points |
| FR-017 | Provide human and JSON output; add SARIF after the first release |
| FR-018 | Keep stable rule and finding identifiers |
| FR-019 | Expose a public host-integration API |
| FR-020 | Detect lock/body drift without provider access |

# 6. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-001 | Deterministic ordering and output |
| NFR-002 | Idempotent synchronization |
| NFR-003 | Byte preservation outside managed spans |
| NFR-004 | Reproducible static checks in a clean checkout |
| NFR-005 | Distinct failure states |
| NFR-006 | Plugin extensibility without engine changes |
| NFR-007 | Path, symlink, secret, and plugin security |
| NFR-008 | Linux, macOS, and Windows support |
| NFR-009 | Parse once, batch queries, and cache by digest |
| NFR-010 | Run IDs plus configuration, snapshot, and plugin-version evidence |

# 7. Success measures

- Share of repositories where `sync --check` works in a clean checkout.
- Number of false-positive findings.
- Number of manual managed-block edits stopped before merge.
- Share of providers that pass the shared contract test suite.
- Number of authored-prose changes caused by sync: always zero.
- JSON Schema stability across patch and minor releases.
- Repeat-run speed on an unchanged workspace.

# 8. Product invariants

- Configuration declares intent.
- The provider supplies external truth.
- A managed projection is not a second source of truth.
- The lock records evidence but never replaces the provider.
- A CLI flag filters work but never changes contract meaning.
- An LLM never decides pass or fail.
- The documentation engine never performs remote mutation.
