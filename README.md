# Locus MD

Locus MD is a standalone semantic documentation linter for Markdown repositories. It keeps authored prose free-form while validating document envelopes, repository links, managed blocks, and deterministic projections against declared providers.

## Implemented in 0.1.0

- isolated `[locus.docs*]` INI configuration;
- configurable documentation surfaces;
- YAML frontmatter validated by JSON Schema;
- local Markdown links and reachability checks;
- fenced-code-aware managed block scanner;
- contract bindings and stable findings;
- built-in `file-json` and snapshot providers;
- deterministic `task-table.v1` projections;
- `lint`, `verify`, `sync --check`, `sync --write`, `contracts list`, `config validate/show`, `doctor`, and `init`;
- sidecar `.locus/docs.lock.json` drift evidence;
- byte-preserving span rewrites, atomic replacement, and write-conflict checks;
- Python entry-point extension boundaries for providers and contract handlers.

## Quick start

```bash
uv tool install .
cd examples/basic
locus.md config validate
locus.md lint
locus.md verify --offline
locus.md sync --check --offline
```

The default discovery path is `.locus/config.ini`. A shared INI may contain unrelated Locus sections; Locus MD reads only its own namespace.

`locus.md` is the primary standalone command. `locus-md` remains available as
a compatibility alias. Neither command routes through the `locus` CLI.

## Managed block

```md
<!-- locus:milestone tasks begin -->
| Task | Title | Status |
|---|---|---|
| T-101 | Create repository skeleton | done |
<!-- locus:milestone tasks end -->
```

Provider, selector, schema, mode, and renderer remain in the tracked INI contract rather than in the marker.

## Status

This is a runnable alpha/MVP implementation. The repository dogfoods its own
contract through `.locus/config.ini`; run `locus.md lint`, `locus.md verify
--offline`, and `locus.md sync --check --offline` from the repository root.
Remote GitHub and Linear adapters, SARIF, changed-files mode, and bidirectional
synchronization remain intentionally out of scope.
