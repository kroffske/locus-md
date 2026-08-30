---
title: locus-md Architecture
type: system-design
status: active
owner: team:locus-md
tags: [architecture, runtime]
---

# locus-md architecture

locus-md is a library-first modular monolith. The CLI and Python API load one
typed TOML configuration, scan Markdown, and run deterministic checks.

```text
CLI / Python API
  -> TOML discovery and typed config
  -> surface inventory
  -> Markdown, front matter, block, and link scan
  -> document and reachability findings
  -> provider snapshots and contract checks
  -> read-only rule plug-ins
  -> report or safe sync patches
```

`src/locus_md/config.py` owns configuration. `DocumentConfig` and
`DocumentSectionConfig` represent explicit document requirements.
`markdown.py` owns front matter, headings, links, and managed-block spans.
`graph.py` owns link and reachability relationships. `impact.py` uses Git for
the changed-path set and the current graph for inbound dependents.

Providers obtain and normalize source facts. Contract handlers validate or
render managed blocks. Rule plug-ins inspect immutable document views and
return findings. Authoring guidance never becomes validation logic.

`.locus/docs.lock.json` records managed projection evidence. Impact does not add
a second graph or expand lock ownership. Sync patches are limited to managed
block bodies and lock evidence, with source-digest and path-safety checks.

See [the documentation index](docs/index.md) for the reader path.
