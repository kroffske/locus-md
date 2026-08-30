---
schema: locus.doc.v1
id: docs.design.configuration
title: "locus-md — TOML configuration specification"
type: guide
status: active
owner: team:locus-md
tags: [configuration, contract]
updated: "2026-08-30T00:00:00Z"
---

# 1. Purpose

locus-md owns one dedicated TOML file. The default path is
`.locus/locus.md.toml`. The file contains only the `locus.md` namespace.
The separate Locus runtime file `.locus/config.toml` is not read by locus-md.

# 2. Discovery

Precedence:

1. explicit `--config PATH` or API `explicit` path;
2. `LOCUS_MD_CONFIG`;
3. upward search for `.locus/locus.md.toml` until the Git or filesystem root.

A path with a non-`.toml` suffix returns `CFG-061` migration guidance. Legacy
names `.locus/config.ini`, `locus.ini`, and `.locus.ini` are never parsed.
If one is found during discovery, locus-md returns `CFG-061` without writing.

The selected file defines the workspace root. An enclosing Git repository does
not override it.

# 3. Namespace

The file uses these TOML tables:

```toml
[locus.md]
[locus.md.surface.<name>]
[locus.md.provider.<name>]
[locus.md.contract.<name>]
[locus.md.rule.<name>]
```

Top-level keys other than `locus`, and child tables under `locus` other
than `md`, are rejected. This keeps locus-md configuration separate from the
Locus runtime configuration.

# 4. Syntax and types

- Encoding is UTF-8.
- TOML is parsed by the Python standard-library `tomllib`.
- Booleans use TOML booleans, not quoted strings.
- Integer fields use TOML integers. Booleans are not integers.
- List fields are arrays containing only strings.
- Paths, names, enums, and adapter identifiers are strings.
- Selectors and rule `options` are TOML tables containing JSON-compatible
  strings, booleans, integers, finite floats, arrays, and nested tables.
- Provider adapter options are strings. Reserved provider keys retain their
  typed fields.
- TOML dates, times, datetimes, and non-finite floats are rejected with
  `ConfigError`.
- Duplicate keys and invalid TOML are rejected.
- `${ENV:NAME}` substitution is recursive for every string value. The
  replacement remains a string and is never coerced into another TOML type.
- Paths are POSIX-style and relative to the workspace root.

# 5. Global table

```toml
[locus.md]
schema = 1
surfaces = ["docs", "handbook"]
strict = true
lock_file = ".locus/docs.lock.json"
cache_dir = ".locus/cache/locus-md"
report_dir = ".locus/reports/locus-md"
default_output = "human"
network = "explicit"
unverified = "fail"
```

| Key | Type | Default | Meaning |
|---|---|---|---|
| `schema` | integer | required | Configuration schema version; currently `1` |
| `surfaces` | string array | required | Active surface IDs |
| `strict` | boolean | `false` | Promote configured warnings |
| `lock_file` | path string | `.locus/docs.lock.json` | Tracked projection evidence |
| `cache_dir` | path string | `.locus/cache/locus-md` | Ignored acceleration state |
| `report_dir` | path string | absent | Optional run reports |
| `default_output` | enum | `human` | `human` or `json` |
| `network` | enum | `explicit` | `deny`, `explicit`, or `allow` |
| `unverified` | enum | `fail` | `fail`, `warn`, or `ignore` |

# 6. Surface table

```toml
[locus.md.surface.docs]
root = "docs"
include = ["**/*.md"]
exclude = ["vendor/**", "generated/**"]
index = ["index.md"]
frontmatter = "required"
frontmatter_schema = "schemas/document.schema.json"
require_reachable = true
allow_external_links = true
follow_symlinks = false
default_provider = "tasks"
```

`root` and `include` are required. Other keys are optional. Surface names
match `[a-z][a-z0-9-]{0,31}`.

# 7. Provider table

```toml
[locus.md.provider.tasks]
adapter = "file-json"
path = "data/tasks.json"
required = true
network = false
snapshot_file = ".locus/snapshots/tasks.json"
```

Reserved keys are `adapter`, `required`, `network`, `snapshot_file`,
and `cache_ttl`. Any other provider keys are passed to the adapter as string
options. Provider names are local identities.

# 8. Contract table

```toml
[locus.md.contract.active-milestone]
surface = "docs"
path = "milestones.md"
block_kind = "milestone"
block_id = "tasks"
schema = "task-table.v1"
mode = "projection"
provider = "tasks"
selector = { milestone = "m01" }
renderer = "task-table.v1"
severity = "error"
required = true
```

Binding identity is `surface + normalized path + block_kind + block_id`.
`provider` may be `inherit` to use the surface default. Projection mode
requires `renderer`.

# 9. Rule table

```toml
[locus.md.rule.policy-coverage]
adapter = "policy-coverage"
phase = "verify"
surface = "docs"
severity = "error"
options = { registry = "docs/policies.json" }
```

Rules use the `locus_md.rules` entry-point group. A rule runs once per selected
document during `verify`, `sync --check`, and `sync --write`. Static
`lint` never runs rules. Rules return findings only and cannot return patches.

# 10. Initialization

`locus-md init` creates the canonical TOML scaffold only when the target is
missing. Running it again on a valid file succeeds unchanged. It never appends
to an existing file. `--check` reports whether the file exists and validates
an existing file without writing. `--print` prints the scaffold without
writing.

An invalid canonical file, a missing `[locus.md]` namespace, an old INI file,
or an explicit non-TOML path returns migration guidance and leaves all files
unchanged.

# 11. Validation codes

```text
CFG-001 config file not found
CFG-003 unsupported schema
CFG-004 invalid boolean, enum, or string type
CFG-005 invalid integer type
CFG-007 invalid TOML
CFG-008 missing [locus.md] namespace
CFG-009 missing required key
CFG-010 unknown or inactive surface
CFG-020 unknown provider
CFG-025 invalid contract name
CFG-036 invalid rule/options type or JSON-compatible value
CFG-040 cross-section or unsupported interpolation
CFG-050 path escapes workspace
CFG-061 legacy/non-TOML configuration migration required
CFG-062 unsupported top-level or [locus] child namespace
```

The normalized output remains `locus-md.config.normalized.v1`; changing the
source format does not change the embedded runtime model.
