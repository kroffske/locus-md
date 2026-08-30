# locus-md

This file is the single repository contract for agents. A nested `AGENTS.md`
may add rules only for its own directory.

## Purpose

locus-md is a standalone Python library and CLI for deterministic semantic
contracts over Markdown. Authored prose remains free-form. The tool validates
document structure, link graphs, and managed data projections.

## Getting started

Create an environment and install the project with `python3 -m venv .venv &&
.venv/bin/python -m pip install -e '.[dev]'`.

Verification commands:

```bash
.venv/bin/python -m pytest
PATH="$PWD/.venv/bin:$PATH" make example
.venv/bin/locus-md config validate
.venv/bin/locus-md lint
.venv/bin/locus-md verify --offline
.venv/bin/locus-md sync --check --offline
.venv/bin/locus-md impact --base main
```

Install the global tool with `uv tool install --force .`. Build a wheel with
`.venv/bin/python -m pip wheel . --no-deps -w dist`.

Optional host metadata is separate from the product. If this checkout uses
Locus project memory, run `locus init` to regenerate its private
`.locus/AGENTS.md` registry. locus-md never reads that registry.

## Change rules

- `src/locus_md/` must not import a host application, remote tracker, or concrete task store.
- locus-md reads only `.locus/locus-md.toml` and its `[locus-md]` namespace.
- A managed-block update must preserve every byte outside its span.
- Every new provider or contract failure requires a stable finding code and a test.
- `dist/` contains a saved build snapshot. Treat it as current only after a new installation check.
- Before a local commit, run the repository checks and stage exact owned paths.
- Do not push, publish a package, or perform an external write without explicit authorization.
- Write repository documentation and persisted project prose in English.
- Never put user-specific absolute paths, usernames, or sibling-repository references in public documentation.

<navigation>
<!-- Where things live. Describe every major directory and entry point.
     git=tracked    committed; a fresh clone has it
     git=local      deliberately gitignored working surface
     git=generated  build output; absent until the build runs -->
<!-- locus:nav:v1:begin -->
| path | what | git |
| --- | --- | --- |
| `README.md` | User entry point and quick start | tracked |
| `AGENTS.md` | Repository contract and validated navigation | tracked |
| `CLAUDE.md` | Claude Code entry point that references `AGENTS.md` | tracked |
| `ARCHITECTURE.md` | Compact boundary map and execution path | tracked |
| `docs/` | Documentation; reading starts at `docs/index.md` | tracked |
| `src/locus_md/` | Python package, CLI, engine, providers, and schemas | tracked |
| `tests/` | Pytest coverage for public and internal contracts | tracked |
| `examples/` | Self-contained workspaces for acceptance checks | tracked |
| `schemas/` | JSON Schema for this repository's documentation | tracked |
| `data/` | Normalized sources used by self-validation contracts | tracked |
| `.locus/locus-md.toml` | Tracked locus-md contract manifest | tracked |
| `.locus/docs.lock.json` | Reproducible evidence of the last materialization | tracked |
| `.locus/soul.md` | Local product identity and durable direction | local |
| `.tasks/` | Local task workspaces and evidence | local |
| `.venv/` | Local Python environment | local |
| `dist/` | Current saved wheel snapshot | tracked |
| `.github/` | CI workflow for Python 3.11–3.13 | tracked |
<!-- locus:nav:v1:end -->
</navigation>
