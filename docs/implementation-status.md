---
schema: locus.doc.v1
id: docs.implementation-status
title: Implementation status
type: note
status: active
owner: team:locus-md
tags: [implementation, dogfood]
updated: "2026-08-28T00:27:13Z"
source_commit: "6ecd7cfe5fd1"
update_event: "user_request"
description: "Validated and connected to locus-md navigation and self-validation contracts."
---

# Implementation status

## Implemented self-validation path

This table is materialized from `data/project-status.json`. The
`.locus/config.ini` manifest binds the source to this block. Synchronization
never rewrites the authored text outside the markers.

<!-- locus:milestone dogfood begin -->
| Task | Title | Status |
|---|---|---|
| MD-001 | Create the standalone Python package and CLI | done |
| MD-002 | Validate Markdown surfaces and links | done |
| MD-003 | Validate and synchronize managed blocks | done |
| MD-004 | Apply a document contract to the locus-md repository | done |
| MD-005 | Install locus-md globally with uv tool | done |
<!-- locus:milestone dogfood end -->

## Deliberately deferred

- GitHub and Linear packages.
- Remote writes and bidirectional authority.
- SARIF and language-server integration.
- Changed-files dependency closure.
- Rule and renderer plugin groups as independently versioned SDKs.
- Cross-process sandboxing of plugins.

The deferred items are not silently emulated. Unknown adapters and schemas are configuration errors; unavailable required providers produce an explicit `unverified` state.
