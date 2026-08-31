---
schema: locus.doc.v1
id: docs.plugin-api
title: locus-md Plug-in API
type: guide
status: active
owner: team:locus-md
tags: [plugins, api, providers, contracts, rules]
---

# Plug-in API

locus-md has three extension points. A provider reads source facts. A
contract handler validates or renders one managed block. A rule checks the
whole-document view. All three are installed Python entry points and use
`api_version = "1"`.

## Register an extension

Declare an entry point in the package metadata:

```toml
[project.entry-points.locus_md.providers]
my-provider = "my_package.provider:MyProvider"

[project.entry-points.locus_md.contracts]
my-table.v1 = "my_package.contract:MyTable"

[project.entry-points.locus_md.rules]
my-rule = "my_package.rule:MyRule"
```

locus-md discovers the three groups as `locus_md.providers`,
`locus_md.contracts`, and `locus_md.rules`. An entry point may name a class,
which locus-md instantiates, or an already-created object. The registry
rejects an extension whose `api_version` is not `"1"`. Duplicate names keep
the built-in or first registered implementation unless the host explicitly
uses the Python registration API with `replace=True`.

## Provider protocol

A provider declares `plugin_id`, `plugin_version`, and these methods:

```python
class ProviderPlugin:
    api_version: str

    def validate_config(self, options: Mapping[str, str]) -> list[Finding]: ...
    def open(self, context: ProviderContext, options: Mapping[str, str]) -> ProviderSession: ...

class ProviderSession:
    capabilities: frozenset[str]

    def capture(self, queries: Sequence[ProviderQuery]) -> ProviderSnapshot: ...
    def close(self) -> None: ...
```

`ProviderContext` supplies the workspace path, provider name, offline flag,
and the resolved network permission. Provider options are strings from its
TOML table; residual option names are intentionally provider-defined. A
provider must validate its own options, return a typed snapshot, and close
its session. The core applies the configured network policy before provider
I/O. `network` does not grant access to rules, LLMs, or external-link scans.

The provider lifecycle is `validate_config` → `open` → `capture` → `close`.
`capture` receives batched immutable `ProviderQuery` values and returns a
`ProviderSnapshot` containing normalized `EntityRecord` values, a revision,
consistency, capture time, and content digest. The engine uses
handler-declared capabilities before capture. The built-in
providers are `file-json` and `snapshot`; an embedding application may also
call `PluginRegistry.register_provider` with an explicit adapter name.

Warning-only findings from `validate_config` are not emitted and do not stop
capture. When validation contains a failure, those validation findings are
appended, capture stops, and `PROV-001` with `UNVERIFIED` state is added.
Provider exceptions likewise prevent a snapshot and produce `PROV-001` with
`UNVERIFIED` state. A direct Python caller sees handler `plan`/`validate`
exceptions propagate. The CLI maps known `LocusMdError` values in its top-level
handler; unexpected exceptions become `INTERNAL-001` and exit 5, with a
traceback only when `--debug` is set.

## Contract protocol

A contract handler declares `schema_id`, `renderer_ids`, and
`required_capabilities`, then implements:

```python
class ContractHandler:
    api_version: str

    def plan(self, binding: ContractBinding, document: DocumentRecord,
             block: ManagedBlock) -> list[ProviderQuery]: ...
    def validate(self, binding: ContractBinding, document: DocumentRecord,
                 block: ManagedBlock, snapshot: ProviderSnapshot) -> list[Finding]: ...
    def render(self, binding: ContractBinding, snapshot: ProviderSnapshot,
               newline: str) -> str: ...
```

The `[locus-md.contract.NAME]` table selects the schema, provider, selector,
mode, and renderer. The handler owns the meaning of its snapshot and the
rendered managed-block body. The core owns marker spans, path safety, finding
ordering, patch planning, and the sync write gate.

Only projection and snapshot modes use `render`; authored mode validates the
body written by a person. Rendering must be deterministic and must not open a
provider or write a file. A handler's `required_capabilities` is checked
before the provider session captures its planned queries.

The engine translates a handler `render` exception into a `CONTRACT-002`
finding with the binding's severity; it does not set an explicit
`RunState.FAILED` on that finding. Handler `plan` and `validate` exceptions
currently propagate to a direct Python caller; the CLI maps them through its
command-level error handler rather than converting them to a local contract
finding.

## Rule protocol

A rule declares `plugin_id`, `plugin_version`, and these methods:

```python
class RulePlugin:
    api_version: str

    def validate_config(self, options: Mapping[str, object]) -> None: ...
    def check(self, context: RuleContext, document: RuleDocument,
              options: Mapping[str, object]) -> Sequence[Finding]: ...
```

`RuleContext` identifies the configured rule, its `surface`, and severity. Its
phase is always `"verify"`: it describes rule semantics, while the Engine
owns whether the command is `verify`, `sync --check`, or `sync --write`.
`RuleDocument` contains immutable front matter and links plus document text
and workspace-relative paths. The core snapshots plug-in identity and
version once per command and adds that provenance to normalized findings.

Rules may return only `Finding` values with a valid code, message, severity,
optional location, JSON-serializable details, and valid remediation. A
plug-in finding's `state` must be `FAILED` or `UNVERIFIED`; the core rejects
other states. Exceptions and invalid findings become failed `RULE-*` findings.
A rule that returns an unverified finding follows the configured `unverified`
policy. The core normalizes severity, fills the document location and rule
name when omitted, and attaches rule, adapter, identity, and version
provenance.

## Trust and write boundary

Installed plug-ins are trusted in-process Python code. They receive a
workspace path and can perform Python I/O or network calls themselves. The
core does not provide an operating-system sandbox. “Read-only rule” means
only that the core rule protocol has no patch handle and the core does not
apply rule-returned file changes; it is not a security isolation guarantee.

The core itself keeps `lint`, `verify`, `guide`, and `impact` read-only.
`sync --check` plans without writing. `sync --write` applies only validated
managed-block and lock patches. A failed rule, invalid output, unverified
required evidence, span conflict, or path conflict prevents those writes.
Plug-in authors must therefore keep side effects explicit and document any
external access their package performs.

## Compatibility checklist

Before publishing an extension, verify `api_version = "1"`, stable identity
and version strings, entry-point group/name, configuration validation, typed
return values, and deterministic ordering. Test unavailable providers,
invalid options, malformed findings, exceptions, offline mode, and sync
write gating. The extension seam is versioned at the entry-point boundary;
the core may reject a future API version rather than silently adapting it.
