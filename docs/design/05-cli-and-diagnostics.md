---
title: "Locus MD — CLI and diagnostics"
status: proposed
date: "2026-08-27"
---

# 1. Командная модель

## `locus-md init`

Создаёт или добавляет namespaced config scaffold.

```bash
locus-md init
locus-md init --config .locus/config.ini --check
locus-md init --print
```

## `locus-md config validate`

Проверяет discovery, namespace, types, paths и plugin references.

```bash
locus-md config validate
locus-md config show --normalized
```

`show` не выводит secret-like values.

## `locus-md lint`

Только static checks:

- config binding coverage;
- frontmatter;
- links;
- reachability;
- marker grammar;
- lock/body drift.

Не открывает network providers.

```bash
locus-md lint
locus-md lint --surface docs
locus-md lint --format json
```

## `locus-md verify`

Добавляет provider assertions.

```bash
locus-md verify
locus-md verify --offline
locus-md verify --provider tasks
```

`--provider` фильтрует contracts, но не заменяет provider в config.

## `locus-md sync --check`

Строит canonical projections без writes.

```bash
locus-md sync --check
```

Human output показывает summary и unified diff; JSON содержит patches.

## `locus-md sync --write`

Применяет deterministic patches и обновляет lock.

```bash
locus-md sync --write
```

Без `--write` команда не модифицирует workspace.

## `locus-md contracts list`

Показывает configured bindings, найденные blocks, providers, schema/renderer, state и lock status.

## `locus-md doctor`

Проверяет environment, plugin versions, writable paths, Git state, network policy и availability authentication. Doctor не является validation gate.

# 2. Output formats

## Human

```text
ERROR DOC-BLOCK-OUT-OF-DATE docs/milestones.md:14
  Contract active-milestone differs from provider snapshot tasks@rev-42.
  Run: locus-md sync --check
```

## JSON

Схема: `schemas/finding.v1.schema.json`.

```json
{
  "schema": "locus-md.report.v1",
  "run_id": "...",
  "mode": "verify",
  "state": "failed",
  "config_digest": "sha256:...",
  "snapshots": {},
  "findings": [],
  "patches": []
}
```

## SARIF

Добавляется после стабилизации finding schema. Mapping code → rule ID сохраняется.

# 3. Severity

```text
info
warning
error
fatal
```

Severity и verification state — разные измерения.

Provider outage может иметь `state=unverified` и `severity=error` в CI, но warning локально.

# 4. Rule code taxonomy

```text
CFG-*       configuration
DOC-ENV-*   document envelope
DOC-LINK-*  links and graph
DOC-BLOCK-* managed blocks
DOC-LOCK-*  lock state
PROV-*      provider
CONTRACT-*  contract handler
SYNC-*      patch/write
PLUGIN-*    plugin loading
INTERNAL-*  unexpected failure
```

Stable examples:

```text
DOC-BLOCK-001 unclosed marker
DOC-BLOCK-002 nested block
DOC-BLOCK-003 duplicate block
DOC-BLOCK-010 unbound block
DOC-BLOCK-011 missing required block
DOC-BLOCK-020 manual drift
DOC-BLOCK-021 out-of-date projection
PROV-001 unavailable
PROV-002 partial snapshot
PROV-003 unsupported capability
SYNC-001 source file changed
SYNC-002 overlapping patches
```

# 5. Exit codes

| Code | Meaning |
|---:|---|
| `0` | Requested verification passed |
| `1` | Findings at or above failure threshold |
| `2` | Usage/configuration error |
| `3` | Required assertions remained unverified |
| `4` | Write conflict or unsafe rewrite refusal |
| `5` | Internal error |

`sync --check` использует `1`, если patch required.

# 6. Aggregate result

```text
internal-error
> configuration-error
> failed
> unverified
> passed
```

`skipped` не повышает aggregate state, если skip разрешён.

# 7. CI recipes

## Basic offline

```bash
locus-md config validate
locus-md lint
locus-md verify --offline
locus-md sync --check --offline
```

## Network-enabled

```bash
locus-md verify --network
locus-md sync --check --network
```

Network разрешается явно при `network=explicit`.

## Changed files

Post-MVP:

```bash
locus-md lint --changed origin/main
```

Graph dependencies расширяют affected set за пределы изменённых файлов.

# 8. Pre-commit

Recommended hook:

```yaml
- repo: https://github.com/example/locus-md
  rev: v0.1.0
  hooks:
    - id: locus-md-lint
```

Pre-commit запускает static lint. Provider verification обычно остаётся в CI.

# 9. LLM remediation

Finding может включать:

```json
{
  "remediation": {
    "kind": "command",
    "value": "locus-md sync --check"
  }
}
```

LLM может объяснить finding, предложить config change или подготовить patch. Engine не принимает free-form LLM answer как evidence.
