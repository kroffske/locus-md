---
schema: locus.doc.v1
id: docs.system-design.locus-md
title: locus-md System Design
type: system-design
status: active
owner: team:locus-md
tags: [architecture, contracts, runtime]
---

# locus-md system design

locus-md turns a repository's documentation intent into deterministic evidence.
The design follows the user's reading order rather than the Python file tree.

## Request flow

```text
discover .locus/locus-md.toml
  -> parse [locus-md] into typed values
    -> inventory each active surface
      -> scan Markdown, front matter, headings, links, and blocks
        -> validate documents and reachability
          -> plan provider queries and plug-in rule calls
            -> emit a report or bounded sync patches
```

Configuration discovery has one override, `LOCUS_MD_CONFIG`, and never reads
the generic `LOCUS_CONFIG`. A hyphen is valid in a TOML table name, so the
public namespace is exactly `[locus-md]`.

## Responsibility boundaries

Surfaces own selection and graph policy. Document declarations own identity,
description, required headings, and authoring guidance. Markdown scanning owns
source spans and parser records. The graph owns local-link and reachability
relationships. Impact owns the Git change set plus current inbound dependents.

Providers obtain normalized source facts. Contract handlers validate or render
managed blocks. Rules are installed Python code selected by an `adapter` name.
Configured rules execute during `verify` and both synchronization flows, but
not during static `lint`. The core validates plug-in output and orders
findings; the rule protocol has no core patch API. Plug-ins are trusted
in-process Python code, not OS-sandboxed processes, so this protocol boundary
does not prevent a plug-in from performing its own file or network I/O. See
[the plug-in API](../../plugin-api.md) for the complete contract.

## Write boundary

`lint`, `verify`, `guide`, and `impact` are read-only. `sync --check` plans
patches but does not apply them. `sync --write` can change only a managed block
body and lock evidence after digest, span, and path checks.

The lock is evidence for managed projections, not a historical document graph.
Impact therefore reports limits honestly: every emitted workspace change row is
marked by whether the current configuration manages it, and the current graph
supplies dependents. Changes outside a nested workspace are filtered out. It
does not reconstruct a removed configuration from Git history.

## Extension seam

TOML can select built-ins and installed entry points, but cannot embed arbitrary
executable code. Providers use `locus_md.providers`; contracts use
`locus_md.contracts`; read-only document rules use `locus_md.rules`. The
`network` setting gates provider I/O only and does not grant network access to
an LLM or external-link crawler.
