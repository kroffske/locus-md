---
schema: locus.doc.v1
id: docs.cli
title: locus-md CLI Reference
type: guide
status: active
owner: team:locus-md
tags: [cli, diagnostics]
---

# CLI reference

All commands accept `--config`, `--start`, `--format human|json`, `--strict`,
and `--debug` where shown by `locus-md --help`. The default config is
`.locus/locus-md.toml`.

## Configuration and orientation

```bash
locus-md init [--check|--print]
locus-md config validate
locus-md config show
locus-md guide <document-id>
locus-md doctor
```

`init` creates the canonical TOML file only when absent. `config validate`
checks types, paths, active surfaces, and plug-in references. `config show`
prints sanitized normalized configuration. `guide` prints one declared
document's authoring envelope; its JSON schema is `locus-md.guide.v1`.
`doctor` reports environment and plug-in availability and is informational.

## Deterministic checks

```bash
locus-md lint [--surface NAME]
locus-md verify [--surface NAME] [--provider NAME] [--offline|--network]
locus-md impact --base GIT_REF
```

`lint` is local and static and does not execute configured rules. `verify` adds
provider assertions and configured read-only rules. The same configured rules
also execute during both `sync --check` and `sync --write`. `--offline` forbids
remote provider calls; `--network` is the explicit opt-in when the policy
permits them. `impact` reports Git changes and current inbound dependents
without writing.

## Managed synchronization

```bash
locus-md sync --check [--surface NAME] [--provider NAME] [--offline|--network]
locus-md sync --write [--surface NAME] [--provider NAME] [--offline|--network]
locus-md contracts list [--surface NAME]
```

`sync --check` prints required patches and never writes. `sync --write` applies
safe managed-body patches and updates lock evidence. `contracts list` shows
bindings, block locations, providers, schemas, and lock state.

## Output and exit states

Human reports show each finding and a summary. JSON reports include a versioned
schema, state, findings, patches, and metadata. Common exit codes are:

- `0` — passed;
- `1` — deterministic findings or failed checks;
- `2` — configuration or Git input error;
- `3` — unverified evidence when policy keeps it visible;
- `4` — write conflict;
- `5` — unexpected internal error.

Finding families include `CFG-*` for configuration, `DOC-ENV-*` for front
matter, `DOC-LINK-*` for links and graph, `DOC-BLOCK-*` and `DOC-LOCK-*` for
managed state, `PROV-*` for providers, `CONTRACT-*` for handlers, and `RULE-*`
for installed document rules.

The embedded Python API accepts an already constructed `WorkspaceConfig` via
`lint_workspace`. It does not discover configuration on behalf of the caller.
