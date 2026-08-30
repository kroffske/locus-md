---
schema: locus.doc.v1
id: docs.design.provider-plugin-api
title: "locus-md — provider and plugin API"
type: system-design
status: active
owner: team:locus-md
tags: [providers, plugins, api]
updated: "2026-08-28T00:27:14Z"
source_commit: "6ecd7cfe5fd1"
update_event: "user_request"
description: "Validated and connected to locus-md navigation and self-validation contracts."
---

# 1. Provider responsibility

A provider adapter only obtains and normalizes data. It never parses Markdown,
chooses a contract, renders a block, mutates a remote source, reads unrelated
configuration sections, or decides aggregate pass or fail.

# 2. Plugin groups

Python entry points:

```text
locus_md.providers
locus_md.contracts
locus_md.rules
```

Renderer entry points remain deferred. Renderers are currently owned by a
contract handler. Rule entry points expose read-only whole-document checks.

```toml
[project.entry-points."locus_md.providers"]
example-issues = "example_plugin:IssuesProvider"

[project.entry-points."locus_md.rules"]
policy-coverage = "example_plugin:PolicyCoverageRule"
```

# 3. Provider lifecycle

```text
load class
→ validate options
→ open session
→ canonicalize queries
→ capture snapshot
→ close session
```

One plugin may serve multiple configured provider names.

# 4. Interfaces

```python
class ProviderPlugin(Protocol):
    api_version: str
    plugin_id: str
    plugin_version: str

    def validate_config(self, options: Mapping[str, str]) -> list[Finding]: ...
    def open(
        self,
        context: ProviderContext,
        options: Mapping[str, str],
    ) -> ProviderSession: ...


class ProviderSession(Protocol):
    capabilities: frozenset[str]

    def capture(
        self,
        queries: Sequence[ProviderQuery],
    ) -> ProviderSnapshot: ...
    def close(self) -> None: ...
```

`capture` should batch queries. If a remote service cannot provide an atomic
snapshot, the adapter reports `consistency=best-effort`.

# 5. Query model

```json
{
  "kind": "task",
  "selector": {
    "milestone": "m01",
    "status": ["open", "doing", "done"]
  },
  "fields": ["id", "title", "status", "milestone"]
}
```

The core canonicalizes key order, set-like lists, and field sets.

# 6. Snapshot model

The packaged `provider-snapshot.v1.schema.json` defines the format.

```json
{
  "schema": "locus-md.snapshot.v1",
  "provider": "tasks",
  "adapter": "file-json",
  "adapter_version": "0.1.1",
  "revision": "sha256:...",
  "consistency": "local",
  "captured_at": "2026-08-27T08:00:00Z",
  "records": [],
  "content_digest": "sha256:..."
}
```

The core recomputes `content_digest`; a plugin-provided digest is untrusted.

# 7. Capabilities

Initial capabilities:

```text
resolve
list
revision
batch
offline
atomic-snapshot
urls
```

A handler declares required capabilities. Planning fails before provider I/O
when a required capability is absent.

# 8. Built-in providers

The first release includes `file-json` and `snapshot`. File-based YAML and CSV
providers are optional later additions. Remote service SDKs do not belong in
the core distribution.

# 9. Injected providers

An embedding application may register a runtime provider factory through the
public plugin registry. Standalone mode uses configured plugins or snapshots.
If neither exists, it returns `PROV-001` instead of importing an application at
runtime.

# 10. Contract handlers

```python
class ContractHandler(Protocol):
    api_version: str
    schema_id: str
    renderer_ids: frozenset[str]
    required_capabilities: frozenset[str]

    def plan(
        self,
        binding: ContractBinding,
        document: DocumentRecord,
        block: ManagedBlock,
    ) -> list[ProviderQuery]: ...
    def validate(
        self,
        binding: ContractBinding,
        document: DocumentRecord,
        block: ManagedBlock,
        snapshot: ProviderSnapshot,
    ) -> list[Finding]: ...
    def render(
        self,
        binding: ContractBinding,
        snapshot: ProviderSnapshot,
        newline: str,
    ) -> str: ...
```

Only projection and snapshot handlers render replacements.

# 11. Read-only document rules

Rules use the public API from `locus_md.rules`:

```python
class RulePlugin(Protocol):
    api_version: str
    plugin_id: str
    plugin_version: str

    def validate_config(self, options: Mapping[str, object]) -> None: ...
    def check(
        self,
        context: RuleContext,
        document: RuleDocument,
        options: Mapping[str, object],
    ) -> Sequence[Finding]: ...
```

`RuleContext` contains the workspace root, configured rule name, `verify`
phase, optional surface, and configured severity. `RuleDocument` contains the
surface-relative and display paths, source text, recursively read-only
frontmatter, and immutable `RuleLink` values. It does not expose parser spans,
absolute document paths, mutable engine records, or rewrite handles.
Nested mappings are read-only mappings and YAML sequences are tuples.

Each returned finding must declare `state=failed` or `state=unverified`.
Missing state, malformed nested fields, non-finding values, and values that
cannot be serialized become `RULE-002`. Plugin exceptions become `RULE-001`.
The core fills the current document identity when the plugin omits it, orders
all findings deterministically, and applies the configured severity and global
unverified policy.

Finding codes use one of two exact grammars. Core codes match
`^[A-Z][A-Z0-9-]*$`. External adapters use a lowercase dotted namespace that
matches `^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9-]*)+$`. The runtime validator and
packaged finding schema enforce the same pair. External codes such as
`vendor.rule.status-invalid` retain their identity in the report.

`validate_config` raises an adapter-owned ordinary exception for invalid
options. The adapter does not import `locus_md.errors` or assign private
`CFG-*` codes. The core translates every adapter validation exception to
`CFG-038` before scan or execution.

The core owns rule provenance. Every verify or sync JSON report includes one
entry under `metadata.rules` for every configured rule. Each entry contains
`rule`, `adapter`, `plugin_id`, `plugin_version`, and `invocation_count`.
This evidence remains present when a rule returns no findings or a command
filter selects no documents. Plugin-provided finding details cannot replace
these identity fields.

Before the first document call, the core resolves every distinct configured
adapter and reads its `plugin_id` and `plugin_version` once. That immutable
command snapshot supplies every finding and every `metadata.rules` row,
including multiple rule names that share one adapter. Mutating or dynamic
plugin attributes cannot make provenance disagree within one report.

Rules execute in process and may perform read-only local I/O. They run only
during `verify` and both sync modes. A rule has no patch API, and a determined
rule failure prevents `sync --write` from applying provider projection patches.

# 12. Renderer separation

In `0.1.1`, a contract handler advertises its `renderer_ids` and performs the
render. Rendering never opens a provider, writes files, adds nondeterministic
values, or depends on locale and time without explicit input. A separate
renderer plugin group may be added after this boundary is proven by more than
one contract schema.

# 13. Trust and compatibility

- Plugins run in-process and are trusted executable code.
- Provider snapshots and `metadata.rules` include the executed plugin
  identifiers and versions.
- `api_version = "1"` is checked before registration or execution.
- Rule adapters must declare non-empty `plugin_id` and `plugin_version`.
- A shared third-party contract test kit remains planned rather than shipped.
