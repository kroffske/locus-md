---
title: locus-md Documentation Rules
type: guide
status: active
owner: team:locus-md
tags: [documentation, authoring]
---

# locus-md Documentation

This file is the local contract for documentation changes. Keep each page
self-contained, link it from the public index, and verify it with `locus-md`.

Reading order:

1. `index.md` — documentation map.
2. `design/00-executive-summary.md` — product boundary.
3. `design/01-product-requirements.md` — verifiable requirements.
4. `design/02-system-design.md` — components and dependencies.
5. `implementation-status.md` — current implemented surface.

`docs/index.md` remains the single public entry point. Add every new page to
the index in the same change. locus-md validates frontmatter and links.
