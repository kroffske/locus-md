---
schema: locus.doc.v1
id: docs.design.configuration
title: "Locus MD — INI configuration specification"
type: guide
status: active
owner: team:locus-md
tags: [configuration, contract]
updated: "2026-08-28T00:27:14Z"
source_commit: "6ecd7cfe5fd1"
update_event: "user_request"
description: "Проверено и подключено к навигации и dogfood-контракту Locus MD."
---

# 1. Цель

Locus MD работает внутри Locus, как standalone CLI и в чужом репозитории с одним общим project INI.

Конфигурационный контракт не требует установки Locus и не зависит от значений других секций.

# 2. Discovery

Порядок:

1. `--config PATH`;
2. `LOCUS_MD_CONFIG`;
3. `LOCUS_CONFIG`;
4. поиск вверх:
   - `.locus/config.ini`;
   - `locus.ini`;
   - `.locus.ini`;
5. остановка на Git root или filesystem root.

Несколько файлов на одном уровне — configuration error.

# 3. Namespace isolation

Разрешённые секции:

```text
[locus.docs]
[locus.docs.surface:<name>]
[locus.docs.contract:<name>]
[locus.docs.provider:<name>]
[locus.docs.rule:<name>]
```

Loader:

- синтаксически парсит файл;
- переносит в normalized model только разрешённые секции;
- не выполняет interpolation через другие sections;
- не раскрывает unrelated values в diagnostics;
- не изменяет unrelated sections при `init`.

Пример общего файла:

```ini
[locus]
project = example

[locus.tasks]
provider = linear

[locus.docs]
schema = 1
surfaces = docs
```

Standalone `locus.md` видит только `locus.docs*`.

# 4. Syntax rules

- Encoding: UTF-8.
- Boolean: `true`/`false`.
- Integer: base-10.
- Lists: comma-separated.
- JSON objects: strict JSON.
- Paths: POSIX-style в config, relative to workspace root.
- Duplicate sections и keys — error.
- Empty value не заменяет missing key без explicit schema rule.
- `ConfigParser(strict=True, interpolation=None)`.

# 5. Environment substitution

Разрешён только:

```ini
token = ${ENV:GITHUB_TOKEN}
```

Запрещено:

```ini
value = ${locus.tasks:provider}
```

Core не имеет cross-section dependency.

# 6. Global section

```ini
[locus.docs]
schema = 1
surfaces = docs, handbook
strict = true
lock_file = .locus/docs.lock.json
cache_dir = .locus/cache/locus-md
report_dir = .locus/reports/locus-md
default_output = human
network = explicit
unverified = fail
```

| Key | Type | Default | Semantics |
|---|---:|---|---|
| `schema` | int | required | Версия INI contract |
| `surfaces` | list | required | Активные surface IDs |
| `strict` | bool | `false` | Повышение configured warnings |
| `lock_file` | path | `.locus/docs.lock.json` | Tracked projection evidence |
| `cache_dir` | path | `.locus/cache/locus-md` | Ignored acceleration state |
| `report_dir` | path | empty | Optional run reports |
| `default_output` | enum | `human` | `human` или `json` |
| `network` | enum | `explicit` | `deny`, `explicit`, `allow` |
| `unverified` | enum | `fail` | `fail`, `warn`, `ignore` |

# 7. Surface section

```ini
[locus.docs.surface:docs]
root = docs
include = **/*.md
exclude = vendor/**, generated/**
index = index.md
frontmatter = required
frontmatter_schema = schemas/document.schema.json
require_reachable = true
allow_external_links = true
follow_symlinks = false
default_provider = tasks
```

| Key | Required | Semantics |
|---|---:|---|
| `root` | yes | Корень surface |
| `include` | yes | Include globs |
| `exclude` | no | Exclude globs |
| `index` | no | Один или несколько graph roots |
| `frontmatter` | no | `required`, `optional`, `forbidden` |
| `frontmatter_schema` | no | JSON Schema |
| `require_reachable` | no | Проверять reachability |
| `allow_external_links` | no | Разрешать remote URLs |
| `follow_symlinks` | no | По умолчанию false |
| `default_provider` | no | Provider для `inherit` |

Surface name: `[a-z][a-z0-9-]{0,31}`.

# 8. Provider section

```ini
[locus.docs.provider:tasks]
adapter = file-json
path = data/tasks.json
required = true
network = false
snapshot_file = .locus/snapshots/tasks.json
```

Reserved keys:

| Key | Semantics |
|---|---|
| `adapter` | Entry-point name |
| `required` | Влияет на aggregate result |
| `network` | Требуется ли network permission |
| `snapshot_file` | Optional offline snapshot |
| `cache_ttl` | Optional cache policy |

Остальные keys передаются plugin как string options.

Provider name не равен tracker name. Два GitHub repositories могут быть providers `core-issues` и `docs-issues`.

# 9. Contract section

```ini
[locus.docs.contract:active-milestone]
surface = docs
path = milestones.md
block_kind = milestone
block_id = tasks
schema = task-table.v1
mode = projection
provider = tasks
selector = {"milestone":"m01"}
renderer = task-table.v1
severity = error
required = true
```

Binding key:

```text
surface + normalized path + block_kind + block_id
```

| Key | Required | Semantics |
|---|---:|---|
| `surface` | yes | Surface ID |
| `path` | yes | Relative path внутри surface |
| `block_kind` | yes | Marker kind |
| `block_id` | yes | Short ID |
| `schema` | yes | Contract schema |
| `mode` | yes | `authored`, `projection`, `snapshot` |
| `provider` | conditional | Provider ID или `inherit` |
| `selector` | conditional | Strict JSON object |
| `renderer` | projection | Renderer ID |
| `severity` | no | Default severity |
| `required` | no | Binding без marker является error |

# 10. Rule section

```ini
[locus.docs.rule:policy-coverage]
adapter = policy-coverage
surface = docs
severity = error
options = {"registry":"docs/policies.json"}
```

Rule plugins работают на envelope, graph или workspace scope и не выполняют writes через `lint`/`verify`.

# 11. Precedence

## Config path

```text
CLI > LOCUS_MD_CONFIG > LOCUS_CONFIG > discovery
```

## Contract fields

```text
explicit contract
    >
surface default
    >
global default
    >
built-in safe default
```

Provider и mode не угадываются без однозначного default.

## CLI flags

Flags могут выбирать surfaces/providers, запрещать network, менять output и повышать strictness. Они не меняют `provider`, `mode`, `selector` или `renderer` contract.

# 12. Config editing

`locus.md init`:

- создаёт `.locus/config.ini`, если файла нет;
- добавляет только отсутствующие `locus.docs*` sections;
- не форматирует весь INI;
- поддерживает `--check` и `--print`.

Full-file normalize не входит в MVP.

# 13. Validation codes

```text
CFG-001 config file not found
CFG-002 duplicate section
CFG-003 unsupported schema
CFG-010 unknown surface
CFG-020 unknown provider
CFG-030 invalid selector JSON
CFG-040 cross-section interpolation forbidden
CFG-050 path escapes workspace
CFG-060 ambiguous config discovery
```

# 14. Compatibility

Будущая TOML-поддержка возможна отдельным frontend, который строит тот же normalized model.
