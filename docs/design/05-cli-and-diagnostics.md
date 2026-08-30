---
schema: locus.doc.v1
id: docs.design.cli-and-diagnostics
title: "locus-md — CLI and diagnostics"
type: guide
status: active
owner: team:locus-md
tags: [cli, diagnostics]
updated: "2026-08-28T00:27:14Z"
source_commit: "6ecd7cfe5fd1"
update_event: "user_request"
description: "Validated and connected to locus-md navigation and self-validation contracts."
---

# 1. Command model

## `locus-md init`

Creates the dedicated `.locus/locus.md.toml` configuration scaffold when it is
missing. It never appends to an existing file.

```bash
locus-md init
locus-md init --config .locus/locus.md.toml --check
locus-md init --print
```

## `locus-md config validate`

Validates discovery, namespace isolation, types, paths, and plugin references.

```bash
locus-md config validate
locus-md config show
```

`config show` returns the normalized locus-md model from the dedicated TOML file.

## `locus-md lint`

Runs static checks only:

- contract-binding coverage;
- frontmatter schemas;
- links and reachability;
- marker grammar;
- lock/body drift.

It never opens a network provider.

```bash
locus-md lint
locus-md lint --surface docs
locus-md lint --format json
```

## `locus-md verify`

Adds provider-backed assertions.

```bash
locus-md verify
locus-md verify --offline
locus-md verify --provider tasks
```

`--provider` filters contracts. It never changes the provider declared in
configuration.

## `locus-md sync --check`

Builds canonical projections without writing.

```bash
locus-md sync --check --offline
```

Human output includes a summary and unified diff. JSON output includes patches.

## `locus-md sync --write`

Applies deterministic patches and updates lock evidence.

```bash
locus-md sync --write --offline
```

No sync command writes unless `--write` is present.

# 1.1 Embedded Python API

Applications that already own workspace configuration can call the typed
`lint_workspace` entrypoint without repeating TOML discovery:

```python
from pathlib import Path

from locus_md import GlobalConfig, SurfaceConfig, WorkspaceConfig, lint_workspace

workspace = WorkspaceConfig(
    config_path=Path(".locus/locus.md.toml"),
    workspace_root=Path("."),
    global_config=GlobalConfig(schema=1, surfaces=("docs",)),
    surfaces={"docs": SurfaceConfig(name="docs", root="docs", include=("**/*.md",))},
    providers={},
    contracts={},
    rules={},
    config_digest="caller-owned-digest",
)
report = lint_workspace(workspace, surfaces={"docs"}, strict=True)
```

The package root exports the three workspace construction types used by this
example. They are aliases of the dataclasses in `locus_md.models`.
`lint_workspace` accepts an existing `WorkspaceConfig`, optional surface and
strict controls, and an optional `PluginRegistry`. It returns the normal
`Report`. It does not discover or parse configuration. The existing `lint`
function keeps its config-loading behavior and delegates execution to this
entrypoint.

## `locus-md contracts list`

Lists configured bindings, discovered blocks, providers, schema and renderer,
and lock state.

## `locus-md doctor`

Reports Python, platform, selected configuration, workspace, writability,
provider plugins, contract plugins, and plugin-load errors. It is an environment
diagnostic, not a validation gate.

# 2. Output formats

Human example:

```text
ERROR DOC-BLOCK-021 docs/milestones.md:14
  Projection differs from the current provider snapshot.
  Run: locus-md sync --check
```

JSON reports follow the packaged `report.v1.schema.json`:

```json
{
  "schema": "locus-md.report.v1",
  "run_id": "...",
  "mode": "verify",
  "state": "failed",
  "config_digest": "sha256:...",
  "config_path": "/workspace/.locus/locus.md.toml",
  "snapshots": {},
  "findings": [],
  "patches": [],
  "metadata": {
    "document_count": 4,
    "contract_count": 0,
    "rule_invocation_count": 4,
    "rules": [
      {
        "rule": "policy-coverage",
        "adapter": "policy-coverage",
        "plugin_id": "policy-coverage",
        "plugin_version": "1.0",
        "invocation_count": 4
      }
    ],
    "offline": true
  }
}
```

The packaged report and finding schemas describe the actual `Report.to_dict()`
shape. Version `0.3.0` corrects both schemas under their existing v1 identifiers
because earlier files did not validate any report emitted by the CLI. Tests
validate lint, verify, and both sync modes, including zero and multiple rules.

SARIF may be added after the finding schema stabilizes. Finding-code to rule-ID
mapping must remain stable.

# 3. Severity and state

Severities:

```text
info
warning
error
fatal
```

Severity and verification state are separate. A required unavailable provider
may produce `state=unverified` and error severity in CI.

# 4. Finding-code taxonomy

Core findings use `^[A-Z][A-Z0-9-]*$`. External rule packages use a dotted,
lowercase namespace matching
`^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9-]*)+$`. Runtime validation and the packaged
finding schema use this same grammar. For example,
`vendor.rule.status-invalid` remains an external finding and is not rewritten to
`RULE-002`.

```text
CFG-*       configuration
DOC-ENV-*   document envelope
DOC-LINK-*  links and graph
DOC-BLOCK-* managed blocks
DOC-LOCK-*  lock state
PROV-*      provider
CONTRACT-*  contract handler
RULE-*      read-only document rule
SYNC-*      patch and write
PLUGIN-*    plugin loading
INTERNAL-*  unexpected failure
```

Stable examples:

```text
DOC-BLOCK-001 unclosed marker
DOC-BLOCK-002 nested block
DOC-BLOCK-003 duplicate block
DOC-BLOCK-010 unbound block
DOC-BLOCK-011 missing required block
DOC-BLOCK-020 manual drift
DOC-BLOCK-021 out-of-date projection
PROV-001 unavailable provider
PROV-010 invalid built-in provider options
CONTRACT-001 missing required entity field
CONTRACT-002 renderer failure
PLUGIN-001 unsupported plugin API version
PLUGIN-002 duplicate plugin registration
PLUGIN-003 invalid plugin metadata or return contract
RULE-001 rule execution exception
RULE-002 invalid rule return value
SYNC-001 source file changed
SYNC-010 safe patches applied
```

# 5. Exit codes

| Code | Meaning |
|---:|---|
| `0` | Requested validation passed |
| `1` | Findings reached the failure threshold or sync requires a patch |
| `2` | Usage or configuration error |
| `3` | Required assertions remain unverified |
| `4` | Write conflict or unsafe rewrite refusal |
| `5` | Internal error |

# 6. Aggregate result

```text
internal-error
> configuration-error
> failed
> unverified
> passed
```

# 7. CI recipes

Offline validation:

```bash
locus-md config validate
locus-md lint
locus-md verify --offline
locus-md sync --check --offline
```

Network-enabled validation:

```bash
locus-md verify --network
locus-md sync --check --network
```

Network access must be explicitly permitted when `network=explicit`.

# 8. Pre-commit

```yaml
- repo: https://example.invalid/locus-md
  rev: v0.2.1
  hooks:
    - id: locus-md-lint
```

Pre-commit runs static lint. Provider verification normally remains in CI.

# 9. LLM remediation

A finding may include deterministic remediation:

```json
{
  "remediation": {
    "kind": "command",
    "value": "locus-md sync --check"
  }
}
```

An LLM may explain a finding or propose a change. Free-form model output never
counts as validation evidence.
