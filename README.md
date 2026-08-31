---
title: locus-md
type: overview
status: active
owner: team:locus-md
tags: [markdown, documentation, contracts]
---

# locus-md

locus-md checks the structure and relationships of Markdown documentation. It
keeps prose authored by people, while making the parts that must stay true
explicit and deterministic.

The mental model is:

```text
folders (surfaces) -> named documents -> front matter and sections
  -> links and managed blocks -> deterministic checks
```

The configuration lives in `.locus/locus-md.toml` under `[locus-md]`. The
standalone command is `locus-md`; it does not read the Locus runtime config.

## First check

Install the package, then run the check from a repository containing the
canonical configuration:

```bash
uv tool install .
locus-md config validate
locus-md lint
```

`config validate` checks TOML shape and installed plug-in references. `lint`
scans selected files, front matter, links, reachability, managed blocks, and
declared documents. It does not contact providers.

For provider-backed checks, make permission explicit:

```bash
locus-md verify --offline
locus-md sync --check --offline
```

`verify` adds provider assertions and read-only rules. Configured read-only
rules also execute during both `sync --check` and `sync --write`; static
`lint` does not execute them. `sync --check` shows deterministic
managed-block patches without writing. Only `sync --write` may update a
managed document block or lock evidence.

## The configuration file

```toml
[locus-md]
schema = 1
surfaces = ["root", "docs"]
network = "deny"

[locus-md.surface.root]
root = "."
include = ["README.md", "AGENTS.md"]
index = ["README.md"]
frontmatter = "optional"

[locus-md.surface.docs]
root = "docs"
include = ["**/*.md"]
index = ["index.md"]
frontmatter = "required"
require_reachable = true

[locus-md.document.readme]
surface = "root"
path = "README.md"
description = "Human entry point for the project."
guidance = "Explain installation and the first successful check."

[locus-md.document.readme.sections.first-check]
heading = "First check"
required = true
guidance = "Show one copy-pasteable command sequence."

[locus-md.document.agents]
surface = "root"
path = "AGENTS.md"
description = "Repository contract and navigation for coding agents."
```

The root `AGENTS.md` declaration is intentional. It is first-class managed
documentation, but keeps its host-compatible shape without YAML front matter.
That exact root path is the only envelope exception. A nested `AGENTS.md` is
an ordinary document and still needs YAML when declared.

Read [Getting started](docs/getting-started.md), then
[Configuration](docs/configuration.md) and [Document model](docs/document-model.md).

## Extensions and boundaries

Built-in checks cover file selection, front matter, local links, index
reachability, declared documents, required headings, managed blocks, and
provider-backed contracts. TOML declares inputs; it is not an executable rule
language.

Installed Python packages can add providers, contract handlers, or read-only
rules through `locus_md.providers`, `locus_md.contracts`, or `locus_md.rules`.
An `adapter` names an installed entry point. It is not inline code or a network
endpoint. Plug-ins are trusted in-process Python and are not OS-sandboxed;
their rule protocol has no core patch API. See [Rules and plug-ins](docs/rules-and-plugins.md)
and the [Plug-in API](docs/plugin-api.md).

`network` controls provider I/O only. Guidance is authoring data for a human or
LLM; it cannot change findings or pass/fail state. There is no automatic prose
generation and no arbitrary executable DSL in TOML.
