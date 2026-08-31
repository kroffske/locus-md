---
schema: locus.doc.v1
id: docs.agents
title: locus-md Documentation Rules
type: guide
status: active
owner: team:locus-md
tags: [documentation, authoring]
---

# locus-md documentation

This directory is the evergreen reader surface. Keep pages self-contained,
use standard front matter, link every page from `index.md`, and verify examples
against the standalone CLI.

## Reading order

1. [Getting started](getting-started.md) — install and run one core check.
2. [Configuration](configuration.md) — define surfaces and discovery.
3. [Document model](document-model.md) — declare documents, sections, and metadata.
4. [Rules and plug-ins](rules-and-plugins.md) — understand built-ins, providers, and adapters.
5. [Plug-in API](plugin-api.md) — implement providers, contracts, and rules safely.
6. [Change impact](change-impact.md) — review changed or deleted documents.
7. [CLI reference](cli.md) — find exact commands, output, and exit behavior.
8. [System design](system-design/locus-md/locus-md.md) — inspect ownership and boundaries.
9. [Implementation status](implementation-status.md) — read the current dogfood snapshot.

`locus-md` validates front matter, links, reachability, managed blocks, and
declared documents. The generic `locus docs` command validates this
repository's documentation format and freshness metadata; it is separate.
