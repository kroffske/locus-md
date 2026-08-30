---
schema: locus.doc.v1
id: docs.implementation-status
title: Implementation status
type: note
status: active
owner: team:locus-md
tags: [implementation, dogfood]
---

# Implementation status

This page is the repository's managed dogfood document. The provider reads
`data/project-status.json`; the `[locus-md.contract.implementation-status]`
binding in `.locus/locus-md.toml` owns only the marked table body. Authored
prose outside the markers remains unchanged by synchronization.

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

- Remote GitHub and Linear packages.
- Remote writes and bidirectional authority.
- SARIF and language-server integration.
- A historical graph reconstruction beyond the current-config impact report.
- Renderer plug-ins as an independently versioned SDK.
- Cross-process sandboxing of plug-ins.

Read-only document rules use the `locus_md.rules` entry-point group. Unknown
adapters and schemas are configuration errors. Unavailable required providers
or rule evidence produce an explicit `unverified` state according to policy.
