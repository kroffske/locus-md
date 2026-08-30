---
schema: locus.doc.v1
id: docs.document-model
title: locus-md Document Model
type: guide
status: active
owner: team:locus-md
tags: [documents, frontmatter, sections]
---

# Document model

Once a surface selects a folder, document declarations make important files
and their minimum structure explicit.

## Declare a document

```toml
[locus-md.document.configuration]
surface = "docs"
path = "configuration.md"
description = "Explains every user-facing configuration choice."
guidance = "Lead with a scenario, then show the smallest valid TOML."
```

The table name is a stable document id. `surface` must be active. `path` is
safe and relative to the surface root, and must match that surface's include
patterns without matching its excludes. `description` is required config-side
metadata. A declared file missing from disk is a deterministic finding.

Document ids and `(surface, path)` pairs are unique. This prevents two names
from silently describing the same file.

## Require sections

Sections are Markdown headings, not arbitrary text ranges:

```toml
[locus-md.document.configuration.sections.discovery]
heading = "Discovery and environment override"
required = true
guidance = "Explain explicit path, LOCUS_MD_CONFIG, and upward discovery."
```

Headings use visible inline text. ATX and setext headings are supported;
whitespace is collapsed and comparison is case-sensitive. Section ids and
normalized headings must be unique within a document. Missing required
headings produce a stable `DOC-SECTION-001` finding.

The current contract does not judge section order, prose quality, minimum
length, or semantic meaning. Those would be style or language-model policy,
not deterministic structure checks.

## Front matter and AGENTS.md

An ordinary explicit document must begin with YAML front matter. A surface can
also require or forbid it for selected files. A JSON Schema may constrain the
front matter when the surface sets `frontmatter_schema`.

The exact root document declaration `surface = "root"` and `path = "AGENTS.md"`
is the sole exception. Its required config-side `description` is the metadata
envelope, so the host instruction file remains valid without a YAML preamble.
This exception is not inherited by `docs/AGENTS.md` or any other nested path.

## Guidance is for authoring

Document and section `guidance` fields are plain text for a human or LLM that
is writing the page. Retrieve them without running validation:

```bash
locus-md guide configuration
locus-md guide --format json configuration
```

JSON output uses `locus-md.guide.v1`. Guidance is inert. Removing or changing
it may change the normalized configuration and its digest, but it cannot change
findings, patches, exit codes, pass/fail state, or authored Markdown bytes.

## Links and graph checks

Markdown links are resolved relative to their source document. locus-md reports
broken local targets and can require selected documents to be reachable from a
surface index. External links are treated according to `allow_external_links`;
network policy does not turn them into a crawler.

Managed blocks are fenced by `locus` markers. Their provider, schema, selector,
mode, and renderer are configured separately. Sync changes only the managed
body and lock evidence, preserving the rest of the document.
