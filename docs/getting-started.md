---
schema: locus.doc.v1
id: docs.getting-started
title: Getting started with locus-md
type: guide
status: active
owner: team:locus-md
tags: [quickstart, installation]
---

# Getting started

Use locus-md when a repository needs predictable documentation structure but
does not need a remote integration yet. The core package works without the
optional locus-skills-ml package.

## 1. Install the command

From a locus-md checkout, install with uv:

```bash
uv tool install .
```

For development, an editable environment also works:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

The installed command is `locus-md`.

## 2. Create the configuration

Run `locus-md init --print` to inspect a starter file, or `locus-md init` to
create `.locus/locus-md.toml` when no canonical or legacy configuration is
present. The command is create-only and idempotent.

The file starts with the literal table `[locus-md]`. The old dotted TOML name
and legacy INI names (`.locus/config.ini`, `locus.ini`, and `.locus.ini`) are
rejected with migration guidance; they are not parsed as compatibility formats.

## 3. Describe one surface and one document

```toml
[locus-md]
schema = 1
surfaces = ["docs"]

[locus-md.surface.docs]
root = "docs"
include = ["**/*.md"]
index = ["index.md"]
frontmatter = "required"

[locus-md.document.index]
surface = "docs"
path = "index.md"
description = "The documentation entry point."

[locus-md.document.index.sections.start]
heading = "Start here"
required = true
```

The document declaration says which selected file must exist, what it is for,
and which heading must be present. It is not a prose template.

## 4. Run the checks

```bash
locus-md config validate
locus-md lint
```

Configuration errors return exit code `2`. A lint report with errors returns
`1`; a passing report returns `0`. Human output is the default. Add
`--format json` for a machine-readable report.

## 5. Add a root agent contract safely

If the repository has a root `AGENTS.md`, declare it on a surface whose root is
`.` and include it explicitly. The exact root declaration is the only document
that may omit YAML front matter. Put its purpose in the required config-side
`description`. A nested `docs/AGENTS.md` remains an ordinary Markdown document
and needs YAML front matter.

Continue with [Configuration](configuration.md), then
[Document model](document-model.md).
