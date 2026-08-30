---
schema: locus.doc.v1
id: docs.change-impact
title: locus-md Change Impact
type: guide
status: active
owner: team:locus-md
tags: [git, impact, links]
---

# Change impact

Use impact review when a commit changes or deletes a managed document and you
want to know what else may need attention.

```bash
locus-md impact --base main
locus-md impact --base main --format json
```

The command is read-only. It never updates authored Markdown, the lock, or
configuration.

## What the report means

Git supplies the changed, renamed, and deleted path set between the selected
base ref and the current index/worktree. Untracked non-ignored files appear as
additions. The report projects that set onto the locus-md workspace and marks
each emitted row `managed = true` or `managed = false`. Changes outside the
workspace are omitted. The current locus-md configuration decides that flag,
including for a deleted path that is no longer on disk.

The current link graph supplies inbound dependents. If `docs/guide.md` changes
and `docs/index.md` links to it, the report names `docs/index.md`. If the guide
is deleted, that same link is useful evidence for the follow-up broken-link
check. Renames inside the workspace include both old and new paths. A rename
across the workspace boundary is projected as a deletion or addition of the
inside endpoint, with no outside `old_path`.

The report sets `configuration_changed = true` when `.locus/locus-md.toml`
itself changed. It does not reconstruct a historical configuration or pretend
to know dependents that existed only under a removed surface. Paths are shown
relative to the locus-md workspace, including nested workspaces. This single
coordinate system applies to every emitted `path` and `old_path`.

JSON output uses `locus-md.impact.v1`. An invalid Git ref is a typed Git error.
An empty report means Git found no changes in the selected change set. It is not
proof that an old configuration had the same model.

## Suggested review loop

1. Run `impact` against the branch base.
2. Inspect changed and deleted managed documents and their dependents.
3. Run `locus-md lint` for links, front matter, sections, and reachability.
4. Run `locus-md verify --offline` when provider-backed rules or contracts are involved.
5. Use `sync --check` to inspect managed projections; use `sync --write` only when an explicit write is intended.
