---
schema: locus.doc.v1
id: docs.design.provider-plugin-api
title: "Locus MD — provider and plugin API"
type: system-design
status: active
owner: team:locus-md
tags: [providers, plugins, api]
updated: "2026-08-28T00:27:14Z"
source_commit: "6ecd7cfe5fd1"
update_event: "user_request"
description: "Validated and connected to Locus MD navigation and self-validation contracts."
---

# 1. Provider responsibility

A provider adapter only obtains and normalizes data. It never parses Markdown,
chooses a contract, renders a block, mutates a remote source, reads unrelated
INI sections, or decides aggregate pass or fail.

# 2. Plugin groups

Python entry points:

```text
locus_md.providers
locus_md.contracts
```

Renderer and rule entry-point groups are deferred. Renderers are currently
owned by a contract handler, while a declared rule is rejected with `CFG-037`.

```toml
[project.entry-points."locus_md.providers"]
example-issues = "example_plugin:IssuesProvider"
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

# 11. Renderer separation

In `0.1.1`, a contract handler advertises its `renderer_ids` and performs the
render. Rendering never opens a provider, writes files, adds nondeterministic
values, or depends on locale and time without explicit input. A separate
renderer plugin group may be added after this boundary is proven by more than
one contract schema.

# 12. Trust and compatibility

- Plugins run in-process and are trusted executable code.
- JSON reports include plugin identifiers and versions.
- `api_version = "1"` is checked before registration or execution.
- A shared third-party contract test kit remains planned rather than shipped.
