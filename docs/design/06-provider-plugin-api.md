---
title: "Locus MD — provider and plugin API"
status: proposed
date: "2026-08-27"
---

# 1. Цель abstraction

Provider adapter отвечает только за получение и нормализацию данных. Он не:

- парсит Markdown;
- выбирает contract;
- рендерит block;
- изменяет remote source;
- читает unrelated INI sections;
- определяет aggregate pass/fail.

# 2. Plugin groups

Python entry points:

```text
locus_md.providers
locus_md.contracts
locus_md.renderers
locus_md.rules
```

Пример:

```toml
[project.entry-points."locus_md.providers"]
github-issues = "locus_md_github:GitHubIssuesProvider"
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

Один provider plugin может обслуживать несколько configured provider names.

# 4. Interfaces

```python
class ProviderPlugin(Protocol):
    plugin_id: str
    plugin_version: str

    def validate_config(self, options: Mapping[str, str]) -> list[Finding]: ...
    def open(self, context: ProviderContext, options: Mapping[str, str]) -> ProviderSession: ...

class ProviderSession(Protocol):
    capabilities: frozenset[str]

    def capture(self, queries: Sequence[ProviderQuery]) -> ProviderSnapshot: ...
    def close(self) -> None: ...
```

`capture` предпочтительно batch. Если remote API не даёт atomic snapshot, adapter сообщает `consistency=best-effort`.

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

Core canonicalizes key order, set-like lists и field sets.

# 6. Snapshot model

Схема: `schemas/provider-snapshot.v1.schema.json`.

```json
{
  "schema": "locus-md.snapshot.v1",
  "provider": "tasks",
  "adapter": "file-json",
  "adapter_version": "0.1.0",
  "revision": "sha256:...",
  "consistency": "local",
  "captured_at": "2026-08-27T08:00:00Z",
  "records": [],
  "content_digest": "sha256:..."
}
```

`content_digest` пересчитывается core. Plugin-provided digest не считается trusted.

# 7. Capabilities

Initial:

```text
resolve
list
revision
batch
offline
atomic-snapshot
urls
```

Handler объявляет required capabilities. Planning завершается до provider call, если capability отсутствует.

# 8. Built-in providers

MVP:

- `file-json`;
- `snapshot`;
- optional `git` для commits/tracked paths.

Post-MVP convenience:

- `file-yaml`;
- `file-csv`.

Core distribution не включает SDK remote trackers.

# 9. Optional packages

```text
locus-md-locus
locus-md-github
locus-md-linear
```

Remote writes не входят в provider protocol v1.

# 10. Host-injected providers

Host регистрирует runtime object:

```python
host_services.providers.register("workflow", provider_session_factory)
```

Config:

```ini
[locus.docs.provider:workflow]
adapter = host
name = workflow
snapshot_file = .locus/snapshots/workflow.json
```

Standalone mode использует snapshot либо возвращает clear `PROV-001`, не пытаясь импортировать Locus.

# 11. Contract handlers

```python
class ContractHandler(Protocol):
    schema_id: str

    def parse(self, block: ManagedBlock) -> ContractDocument: ...
    def plan(self, binding: ContractBinding, document: ContractDocument) -> list[ProviderQuery]: ...
    def validate(self, binding: ContractBinding, document: ContractDocument, snapshot: ProviderSnapshot) -> list[Finding]: ...
    def render(self, binding: ContractBinding, snapshot: ProviderSnapshot) -> str: ...
```

`render` доступен только projection/snapshot handlers.

# 12. Renderer separation

Renderer не читает provider, не пишет файл, не добавляет nondeterministic values и не зависит от locale/time без explicit input.

# 13. Plugin trust and compatibility

- Plugins исполняются in-process и считаются trusted code.
- JSON report содержит plugin IDs/versions.
- Major API version проверяется до execution.
- Contract test kit публикуется вместе с core.
- Official plugins проходят determinism и failure-injection tests.
