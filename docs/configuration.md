---
schema: locus.doc.v1
id: docs.configuration
title: locus-md Configuration
type: guide
status: active
owner: team:locus-md
tags: [configuration, toml]
---

# Configuration

The configuration answers where documentation lives and which contract applies
to it. It is TOML at `.locus/locus-md.toml`. Every owned table starts with the
hyphenated `[locus-md]` namespace.

## Discovery and environment override

The command resolves configuration in this order:

1. an explicit `--config` path;
2. `LOCUS_MD_CONFIG`;
3. `.locus/locus-md.toml` found while walking upward to the Git root.

`LOCUS_CONFIG` is not read. It belongs to another configuration contract.
`.locus/locus.md.toml`, `.locus/config.ini`, `locus.ini`, and `.locus.ini` are
recognized only to produce a stable migration error. No migration path writes
or rewrites a file.

## Global table

```toml
[locus-md]
schema = 1
surfaces = ["root", "docs"]
strict = false
lock_file = ".locus/docs.lock.json"
cache_dir = ".locus/cache/locus-md"
network = "deny"
unverified = "fail"
```

`schema` is the configuration version. `surfaces` is the explicit activation
list; a declared surface that is not listed is inactive. `strict` promotes
warnings to errors. `lock_file` stores managed-block evidence, while
`cache_dir` stores provider cache data. `unverified` controls unavailable
provider evidence (`fail`, `warn`, or `ignore`).

`network` has one narrow meaning: it controls provider I/O permission. `deny`
blocks it, `explicit` requires a command-level opt-in, and `allow` permits an
eligible provider. It does not give an LLM network access and does not crawl
external Markdown links.

## Surfaces are folders

```toml
[locus-md.surface.docs]
root = "docs"
include = ["**/*.md"]
exclude = ["drafts/**"]
index = ["index.md"]
frontmatter = "required"
require_reachable = true
allow_external_links = true
follow_symlinks = false
```

Use a surface when a folder has one selection and graph policy. `root` is
relative to the workspace. `include` selects Markdown paths relative to that
root; `exclude` removes matches. `index` names entry documents. Reachability
checks whether selected documents can be reached from those indexes.

`frontmatter` is a surface default (`required`, `optional`, or `forbidden`),
but every explicit document requires YAML front matter except the exact root
`AGENTS.md` envelope. `allow_external_links` permits external URLs without
trying to fetch them. `follow_symlinks` controls inventory traversal.

The root surface uses `root = "."`. It is useful for top-level `README.md` and
`AGENTS.md` without making every repository file part of the contract.

## Environment substitution

Use `${ENV:NAME}` in TOML strings when a deployment-specific value should stay
outside the file:

```toml
[locus-md.surface.docs]
root = "${ENV:DOCS_ROOT}"
include = ["**/*.md", "${ENV:EXTRA_DOC_GLOB}"]
```

Substitution is recursive. Cross-section references are not supported.

## Providers, contracts, and rules

These advanced tables are independent of the folder/document hierarchy:

- `provider` obtains normalized source facts, usually from a file or snapshot.
- `contract` binds a managed block to a provider and a contract handler.
- `rule` selects an installed Python rule for `verify`.

Their purpose and lifecycle are explained in [Rules and plug-ins](rules-and-plugins.md).
