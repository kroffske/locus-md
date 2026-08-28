---
schema: locus.doc.v1
id: docs.design.implementation-plan
title: "Locus MD — implementation plan"
type: note
status: needs-review
owner: team:locus-md
tags: [plan, roadmap]
updated: "2026-08-28T00:27:14Z"
source_commit: "6ecd7cfe5fd1"
update_event: "user_request"
description: "Validated and connected to Locus MD navigation and self-validation contracts."
---

# 1. Delivery strategy

Development proceeds in vertical slices. Each milestone ends with a runnable
standalone CLI and an acceptance test, not only internal abstractions.

# 2. Milestone M0 — repository and contract baseline

## Goal

Create a standalone repository and fix the public boundaries.

## Work items

| ID | Task | Depends on |
|---|---|---|
| MD-001 | Repository skeleton, license, and contribution policy | — |
| MD-002 | Product naming and package mapping | MD-001 |
| MD-003 | Shared INI namespace decision | MD-002 |
| MD-004 | Public configuration, finding, and snapshot schemas | MD-003 |
| MD-005 | CI, tests, and package build | MD-001 |
| MD-006 | Self-contained example workspace | MD-004 |
| MD-007 | Pre-1.0 compatibility policy | MD-004 |

## Acceptance

- `uv tool install .` and `locus.md --help` work.
- Schemas are present in the wheel.
- The example passes `config validate`.
- CI builds and tests the package.
- The core has no application-specific runtime dependency.

# 3. Milestone M1 — static documentation engine

## Goal

Provide useful standalone lint without providers.

## Work items

| ID | Task |
|---|---|
| MD-101 | Configuration discovery and namespace isolation |
| MD-102 | Normalized configuration model and validation |
| MD-103 | Surface inventory and path safety |
| MD-104 | Markdown and frontmatter parser |
| MD-105 | Link extraction and repository graph |
| MD-106 | Reachability rules |
| MD-107 | Fenced-code-aware marker scanner |
| MD-108 | Finding model and JSON output |
| MD-109 | `lint`, `config validate`, and `contracts list` |
| MD-110 | Read-only lock/body drift detection |

## Acceptance

- A shared INI with unrelated sections does not expose their values.
- Different surfaces may use different roots and schemas.
- Broken links and orphaned documents produce stable findings.
- Marker-like text inside code fences is ignored.
- Nested, unclosed, and duplicate blocks are detected.
- Lint performs no network calls.
- Findings are byte-for-byte deterministic.

# 4. Milestone M2 — managed projections and file provider

## Goal

Complete one local end-to-end use case.

## Work items

| ID | Task |
|---|---|
| MD-201 | Contract registry and binding resolution |
| MD-202 | Provider query and snapshot models |
| MD-203 | Built-in `file-json` provider |
| MD-204 | Contract-handler protocol |
| MD-205 | Bundled `task-table.v1` handler |
| MD-206 | Deterministic renderer |
| MD-207 | Patch planner |
| MD-208 | `sync --check` |
| MD-209 | Transactional `sync --write` |
| MD-210 | Lock update |
| MD-211 | Offline snapshot mode |

## Acceptance

- A milestone table is built from a tracked JSON source.
- Manual status changes produce an out-of-date finding.
- `sync --write` changes only the block body and lock.
- Text and whitespace outside managed spans remain byte-identical.
- A second sync produces no diff.
- Lock evidence contains snapshot and body digests.
- A source change between scan and write produces a conflict.

# 5. Milestone M3 — plugin platform

## Goal

Allow third parties to add integrations without forking the core.

## Work items

| ID | Task |
|---|---|
| MD-301 | Entry-point discovery |
| MD-302 | Provider contract test kit |
| MD-303 | Contract and renderer plugin APIs |
| MD-304 | Plugin version negotiation |
| MD-305 | Capability planning |
| MD-306 | Failure isolation and diagnostic wrapping |
| MD-307 | Plugin authoring guide |
| MD-308 | Reference plugin fixture |

## Acceptance

- A third-party package registers a provider without changing the core.
- Unsupported API versions fail before execution.
- Provider exceptions become provider findings.
- The test kit covers normalization, determinism, and partial failures.

# 6. Milestone M4 — standalone distribution

## Goal

Make installation, upgrade, and self-validation reliable without another CLI.

## Work items

| ID | Task |
|---|---|
| MD-401 | Global `uv tool` installation |
| MD-402 | Canonical `locus.md` executable |
| MD-403 | Compatibility alias |
| MD-404 | Wheel entry-point verification |
| MD-405 | Packaged-schema verification |
| MD-406 | Self-validation contract |
| MD-407 | Standalone installation and troubleshooting guide |

## Acceptance

- `uv tool install .` exposes `locus.md` globally.
- The globally installed tool validates this repository and the nested example.
- Explicit and discovered configuration resolve the same workspace.
- The wheel contains both executable entry points and all schemas.

# 7. Milestone M5 — ecosystem hardening

## Goal

Prove provider neutrality through optional read-only integrations.

## Work items

| ID | Task |
|---|---|
| MD-501 | First read-only remote provider |
| MD-502 | Second independent remote provider |
| MD-503 | Network permission policy |
| MD-504 | Cache and offline behavior |
| MD-505 | SARIF output |
| MD-506 | Pre-commit hook |
| MD-507 | Changed-files mode |
| MD-508 | Migration and troubleshooting guide |

## Acceptance

```text
repository default provider = remote
block A = explicit local file snapshot
block B = inherited remote provider
both blocks validate in one document
provider override is explicit and deterministic
manual edits in either projection are detected
authored Markdown remains untouched
```

# 8. Critical path

```text
configuration namespace
→ surface inventory
→ parser and spans
→ contract binding
→ snapshot model
→ deterministic renderer
→ safe rewrite
→ plugin API
→ optional external providers
```

Provider SDK expansion starts only after snapshot and capability contracts are
stable.

# 9. Issue contract

Every issue states:

- observable outcome;
- input schemas;
- failure semantics;
- acceptance test;
- backward-compatibility impact;
- confirmation that the core remains standalone.

# 10. Definition of done

- implementation;
- unit tests;
- integration or golden test;
- documentation;
- stable finding code for each new failure mode;
- no unexplained changes;
- a fixture for every user-facing surface.
