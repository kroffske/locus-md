# Implementation status

## Implemented

- M0 repository/package baseline.
- M1 static engine: config isolation, surfaces, frontmatter schema, links, reachability, marker grammar, findings, lock drift.
- M2 local projection slice: contract registry, snapshot model, `file-json`, `snapshot`, `task-table.v1`, safe check/write synchronization, lock update, offline behavior.
- Initial M3 boundary: entry-point discovery and host registration for provider and contract plugins.

## Deliberately deferred

- GitHub and Linear packages.
- Remote writes and bidirectional authority.
- SARIF and language-server integration.
- Changed-files dependency closure.
- Rule and renderer plugin groups as independently versioned SDKs.
- Cross-process sandboxing of plugins.

The deferred items are not silently emulated. Unknown adapters and schemas are configuration errors; unavailable required providers produce an explicit `unverified` state.
