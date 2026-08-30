# locus-md

locus-md is a standalone semantic documentation linter for Markdown repositories. It keeps authored prose free-form while validating document envelopes, repository links, managed blocks, and deterministic projections against declared providers.

## Implemented through 0.3.0

- dedicated `.locus/locus.md.toml` TOML configuration;
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
- read-only `verify` rule plugins over immutable whole-document projections.

## Quick start

```bash
uv tool install .
cd examples/basic
locus-md config validate
locus-md lint
locus-md verify --offline
locus-md sync --check --offline
```

The default discovery path is `.locus/locus.md.toml`. The file uses only the
`[locus.md]` namespace. The separate Locus runtime `.locus/config.toml` is not
read by locus-md. Set `LOCUS_MD_CONFIG` to override discovery.

`locus-md` is the standalone command. It does not route through the `locus` CLI.

## Managed block

```md
<!-- locus:milestone tasks begin -->
| Task | Title | Status |
|---|---|---|
| T-101 | Create repository skeleton | done |
<!-- locus:milestone tasks end -->
```

Provider, selector, schema, mode, and renderer remain in the tracked TOML
contract rather than in the marker.

## Status

This is a runnable alpha/MVP implementation. The repository dogfoods its own
contract through `.locus/locus.md.toml`; run `locus-md lint`, `locus-md verify
--offline`, and `locus-md sync --check --offline` from the repository root.
Remote GitHub and Linear adapters, SARIF, changed-files mode, and bidirectional
synchronization remain intentionally out of scope.

## Read-only rule plugins

An installed package can expose a rule through the `locus_md.rules` entry-point
group. A configured rule runs once per selected document during `verify`,
`sync --check`, and `sync --write`. Static `lint` never runs rules. Rules return
findings only and cannot contribute patches.

```toml
[locus.md.rule.policy-coverage]
adapter = "policy-coverage"
phase = "verify"
surface = "docs"
severity = "error"
options = { registry = "docs/policies.json" }
```

See `docs/design/06-provider-plugin-api.md` for the public Python protocol and
the aggregate failure policy.
