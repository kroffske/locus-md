---
schema: locus.doc.v1
id: docs.rules-and-plugins
title: locus-md Rules and Plug-ins
type: guide
status: active
owner: team:locus-md
tags: [rules, providers, plugins]
---

# Rules and plug-ins

There are three different ways a repository gets a check. Keeping them
separate makes the configuration predictable.

## 1. Built-in checks

The core owns deterministic mechanics: path selection, missing declared
documents, YAML front matter, required headings, local links, index
reachability, marker grammar, managed-block drift, and report ordering. These
checks do not need a plug-in.

## 2. Declarative TOML

TOML supplies inputs to those checks. Surfaces declare folders and selection.
Documents declare identity, description, sections, and inert guidance.
Contracts declare a managed block's provider, schema, selector, mode, and
renderer. TOML cannot contain arbitrary executable validation code.

## 3. Installed Python plug-ins

Use an installed package when a repository needs executable integration logic:

```toml
[locus-md.rule.policy-coverage]
adapter = "policy-coverage"
phase = "verify"
surface = "docs"
severity = "error"
options = { registry = "docs/policies.json" }
```

`adapter` is the entry-point name resolved from the `locus_md.rules` group.
The plug-in receives an immutable whole-document view and returns findings. It
does not receive rewrite handles and cannot contribute patches. Configured
rules execute during `verify` and during both `sync --check` and
`sync --write`; static `lint` does not execute them.

The same entry-point model supports `locus_md.providers` and
`locus_md.contracts`. A provider obtains source facts. A contract handler
validates or renders a managed block. Neither owns document declarations.

## Managed blocks and providers

A document can contain a block such as:

```md
<!-- locus:milestone tasks begin -->
| Task | Title | Status |
|---|---|---|
<!-- locus:milestone tasks end -->
```

The `contract` table maps that marker to a handler. A `provider` such as
`file-json` or `snapshot` supplies records. `schema` identifies the handler's
contract, `selector` chooses records, `mode` says whether the block is
authored, projected, or snapshot-backed, and `renderer` names the deterministic
projection format.

`network` is only a provider-I/O policy. `deny` is suitable for a local-only
check; `explicit` requires `--network` for eligible providers; `allow` permits
them subject to provider settings. It does not affect built-in link checks,
rule authority, or LLM access.

## Optional locus-skills-ml rule

The core quick start stays dependency-free. If the optional locus-skills-ml
package is installed, it can contribute a rule adapter. Add the package first,
then configure the adapter in the core TOML:

```toml
[locus-md.rule.ml-line-document]
adapter = "locus-ml-line-document"
phase = "verify"
surface = "docs"
severity = "error"
options = { backend = "filesystem", run_store_root = "artifacts/ml" }
```

This table selects code that is already installed. It does not turn TOML into
an ML runtime and does not make an LLM the validation authority. If the package
or adapter is unavailable, configuration validation reports the missing
reference instead of silently skipping it.
