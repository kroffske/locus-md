---
schema: locus.doc.v1
id: docs.design.configuration
title: "Locus MD — INI configuration specification"
type: guide
status: active
owner: team:locus-md
tags: [configuration, contract]
updated: "2026-08-28T00:27:14Z"
source_commit: "6ecd7cfe5fd1"
update_event: "user_request"
description: "Validated and connected to Locus MD navigation and self-validation contracts."
---

# 1. Purpose

Locus MD runs as a standalone CLI or an embedded library. A repository may use
one shared project INI file. The documentation contract never depends on values
from unrelated sections.

# 2. Discovery

Precedence:

1. `--config PATH`;
2. `LOCUS_MD_CONFIG`;
3. `LOCUS_CONFIG`;
4. upward search for `.locus/config.ini`, `locus.ini`, or `.locus.ini`;
5. stop at the Git root or filesystem root.

More than one candidate at the same level is a configuration error. The
selected configuration file defines the workspace root. An enclosing Git
repository does not override it.

# 3. Namespace isolation

Allowed sections:

```text
[locus.docs]
[locus.docs.surface:<name>]
[locus.docs.contract:<name>]
[locus.docs.provider:<name>]
[locus.docs.rule:<name>]
```

The loader parses the complete INI syntax but copies only allowed sections into
the normalized model. It does not interpolate unrelated sections, expose their
values in diagnostics, or rewrite them during initialization.

```ini
[application]
project = example

[tasks]
provider = remote

[locus.docs]
schema = 1
surfaces = docs
```

Standalone `locus.md` sees only `locus.docs*`.

# 4. Syntax rules

- Encoding: UTF-8.
- Booleans: `true` and `false`.
- Integers: base 10.
- Lists: comma-separated.
- Objects: strict JSON.
- Paths: POSIX-style and relative to the workspace root.
- Duplicate sections or keys: error.
- Empty values do not replace missing required values.
- Parser: `ConfigParser(strict=True, interpolation=None)`.

# 5. Environment substitution

Allowed:

```ini
token = ${ENV:PROVIDER_TOKEN}
```

Forbidden:

```ini
value = ${tasks:provider}
```

The core has no cross-section dependency.

# 6. Global section

```ini
[locus.docs]
schema = 1
surfaces = docs, handbook
strict = true
lock_file = .locus/docs.lock.json
cache_dir = .locus/cache/locus-md
report_dir = .locus/reports/locus-md
default_output = human
network = explicit
unverified = fail
```

| Key | Type | Default | Meaning |
|---|---:|---|---|
| `schema` | int | required | INI contract version |
| `surfaces` | list | required | Active surface IDs |
| `strict` | bool | `false` | Promote configured warnings |
| `lock_file` | path | `.locus/docs.lock.json` | Tracked projection evidence |
| `cache_dir` | path | `.locus/cache/locus-md` | Ignored acceleration state |
| `report_dir` | path | empty | Optional run reports |
| `default_output` | enum | `human` | `human` or `json` |
| `network` | enum | `explicit` | `deny`, `explicit`, or `allow` |
| `unverified` | enum | `fail` | `fail`, `warn`, or `ignore` |

`cache_dir` and `report_dir` are validated and exposed in the normalized
configuration. Version `0.1.1` does not yet write cache or report files.

# 7. Surface section

```ini
[locus.docs.surface:docs]
root = docs
include = **/*.md
exclude = vendor/**, generated/**
index = index.md
frontmatter = required
frontmatter_schema = schemas/document.schema.json
require_reachable = true
allow_external_links = true
follow_symlinks = false
default_provider = tasks
```

| Key | Required | Meaning |
|---|---:|---|
| `root` | yes | Surface root |
| `include` | yes | Include globs |
| `exclude` | no | Exclude globs |
| `index` | no | One or more graph roots |
| `frontmatter` | no | `required`, `optional`, or `forbidden` |
| `frontmatter_schema` | no | JSON Schema path |
| `require_reachable` | no | Require index reachability |
| `allow_external_links` | no | Allow remote URLs |
| `follow_symlinks` | no | Follow symlinked documents; default false |
| `default_provider` | no | Provider used by inherited bindings |

Surface names match `[a-z][a-z0-9-]{0,31}`.

# 8. Provider section

```ini
[locus.docs.provider:tasks]
adapter = file-json
path = data/tasks.json
required = true
network = false
snapshot_file = .locus/snapshots/tasks.json
```

Reserved keys:

| Key | Meaning |
|---|---|
| `adapter` | Python entry-point name |
| `required` | Whether failure affects the aggregate result |
| `network` | Whether the provider needs network permission |
| `snapshot_file` | Optional offline snapshot |
| `cache_ttl` | Reserved cache policy; parsed but not executed in `0.1.1` |

All other keys are passed to the plugin as string options. Provider names are
local identities, not service names.

# 9. Contract section

```ini
[locus.docs.contract:active-milestone]
surface = docs
path = milestones.md
block_kind = milestone
block_id = tasks
schema = task-table.v1
mode = projection
provider = tasks
selector = {"milestone":"m01"}
renderer = task-table.v1
severity = error
required = true
```

Binding identity:

```text
surface + normalized path + block_kind + block_id
```

| Key | Required | Meaning |
|---|---:|---|
| `surface` | yes | Surface ID |
| `path` | yes | Path relative to the surface |
| `block_kind` | yes | Marker kind |
| `block_id` | yes | Short local identifier |
| `schema` | yes | Contract schema |
| `mode` | yes | `authored`, `projection`, or `snapshot` |
| `provider` | conditional | Provider ID or inherited surface default |
| `selector` | conditional | Strict JSON object |
| `renderer` | projection | Renderer ID |
| `severity` | no | Default finding severity |
| `required` | no | Treat a missing marker as an error |

# 10. Rule section

```ini
[locus.docs.rule:policy-coverage]
adapter = policy-coverage
surface = docs
severity = error
options = {"registry":"docs/policies.json"}
```

The namespace is reserved, but rule execution is not implemented in API
`0.1.1`. Declaring a rule currently fails configuration validation with
`CFG-037`; the tool never silently ignores it.

# 11. Precedence

Configuration path:

```text
CLI > LOCUS_MD_CONFIG > LOCUS_CONFIG > discovery
```

Contract fields:

```text
explicit contract > surface default > global default > safe built-in default
```

Provider and mode are never guessed without an unambiguous default. CLI flags
may select surfaces or providers, deny network, choose output, and raise
strictness. They never change provider, mode, selector, or renderer semantics.

# 12. Configuration editing

`locus.md init` creates `.locus/config.ini` when missing or adds only absent
`locus.docs*` sections. It does not reformat the complete INI. `--check` and
`--print` provide non-writing modes.

# 13. Validation codes

```text
CFG-001 config file not found
CFG-002 duplicate section or key
CFG-003 unsupported schema
CFG-010 unknown surface
CFG-020 unknown provider
CFG-030 invalid selector JSON
CFG-040 cross-section interpolation forbidden
CFG-050 path escapes workspace
CFG-060 ambiguous config discovery
```

# 14. Compatibility

A future TOML frontend may build the same normalized model. It must preserve
the namespace and isolation rules defined here.
