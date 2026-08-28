---
title: "Locus MD — system design"
status: proposed
date: "2026-08-27"
---

# 1. Архитектурный стиль

Locus MD строится как **library-first modular monolith** с plugin boundaries.

```text
CLI / Python API
       ↓
Workspace + Config
       ↓
Document Scanner + Repository Graph
       ↓
Contract Planner
       ↓
Provider Sessions / Snapshots
       ↓
Validation + Rendering
       ↓
Findings + Patches + Lock
```

Это не microservice и не набор scripts. Provider plugin может обращаться к API, но orchestration остаётся в одном process.

# 2. System context

См. `diagrams/context.mmd`.

Actors:

- maintainer;
- CI;
- LLM host;
- Locus host;
- provider systems;
- Git repository.

Trust boundaries:

- repository content считается untrusted input;
- shared INI считается versioned intent, но валидируется;
- plugins являются executable trusted code;
- remote responses считаются untrusted data и нормализуются;
- secrets поступают только через environment или host credential layer.

# 3. Компоненты

## 3.1. `config`

Ответственность:

- config discovery;
- чтение namespaced sections;
- type conversion;
- schema validation;
- inheritance;
- path resolution;
- config digest.

Запрещено читать unrelated sections, получать credentials, обращаться к providers или молча выбирать default при неоднозначности.

## 3.2. `workspace`

Определяет workspace root, Git root, configured surfaces, file inventory, ignore rules и symlink policy.

## 3.3. `markdown`

Парсит документ один раз и возвращает:

- frontmatter span и data;
- headings;
- links;
- fenced-code ranges;
- HTML comments;
- managed block spans;
- line/column map.

AST используется для понимания структуры, но rewrite выполняется splice-операциями по исходным offsets.

## 3.4. `graph`

Строит repository graph:

```text
DocumentNode
LinkEdge
IndexRoot
OwnedResourceEdge
ContractEdge
```

Graph checks не зависят от managed block providers.

## 3.5. `contracts`

Содержит registry contract handlers.

Handler:

- парсит body;
- объявляет provider query;
- валидирует records;
- строит canonical body;
- описывает supported fields.

Core не должен содержать tracker-specific semantics.

## 3.6. `providers`

Registry и session lifecycle:

- discover adapter;
- validate provider options;
- open session;
- batch query;
- capture snapshot;
- normalize records;
- expose revision and consistency.

## 3.7. `planner`

Преобразует documents + config в:

```text
StaticRulePlan
ContractPlan
ProviderQueryPlan
PatchPlan
```

До I/O обнаруживаются unbound blocks, bindings без blocks, duplicate IDs, unknown schemas/plugins и incompatible capabilities.

## 3.8. `engine`

Координирует run phases:

- lint;
- verify;
- sync-check;
- sync-write;
- inspect/config.

## 3.9. `rewrite`

Получает ordered non-overlapping patches и:

1. проверяет исходный file digest;
2. применяет replacements с конца файла к началу;
3. сохраняет encoding и newline convention;
4. пишет temporary file;
5. атомарно заменяет target;
6. обновляет lock после успешной записи files.

## 3.10. `reporting`

Форматы:

- human;
- JSON;
- позже SARIF.

Findings сортируются по `surface → path → line → column → code → message`.

# 4. Run pipeline

## Phase A — Bootstrap

1. Определить workspace.
2. Найти config.
3. Загрузить только `locus.docs*`.
4. Нормализовать config.
5. Загрузить plugin registry.
6. Зафиксировать run metadata.

## Phase B — Inventory

1. Развернуть surface globs.
2. Нормализовать paths.
3. Применить excludes.
4. Вычислить content hashes.
5. Прочитать tracked lock.

## Phase C — Parse

1. Parse frontmatter.
2. Parse Markdown tokens.
3. Scan managed markers с учётом fenced blocks.
4. Построить document records.
5. Собрать local link edges.

## Phase D — Static lint

1. Envelope schemas.
2. Naming.
3. Local links.
4. Reachability.
5. Marker grammar.
6. Binding coverage.
7. Lock/body digest comparison.

`lint` заканчивается здесь и не требует provider access.

## Phase E — Plan semantic verification

1. Разрешить contract inheritance.
2. Проверить capabilities.
3. Сгруппировать provider queries.
4. Зафиксировать provider requirements.
5. Определить offline/cache policy.

## Phase F — Capture snapshots

Для каждого provider создаётся не более одной session snapshot на run.

Provider может вернуть:

- `verified`;
- `unverified`;
- `failed`;
- `partial`.

Partial snapshot не считается успешным автоматически.

## Phase G — Evaluate

1. Handler получает current block model.
2. Handler получает immutable snapshot view.
3. Возвращает findings.
4. В sync mode строит canonical body.
5. Core вычисляет patch и lock entry.

## Phase H — Commit result

- lint/verify/sync-check: только report;
- sync-write: transactional file rewrite, затем lock rewrite;
- расхождение исходных hashes отменяет write и требует нового run.

# 5. Core data model

```text
WorkspaceConfig
SurfaceConfig
RuleConfig
ProviderConfig
ContractBinding

DocumentRecord
FrontmatterRecord
LinkRecord
ManagedBlock

ProviderQuery
EntityRecord
ProviderSnapshot

Finding
Patch
LockEntry
RunResult
```

## `ManagedBlock`

```text
surface
path
kind
id
marker_start_span
body_span
marker_end_span
body_digest
```

## `ContractBinding`

```text
contract_id
surface
path
block_kind
block_id
schema
mode
provider
selector
renderer
severity
```

## `Finding`

```text
schema
code
severity
message
state
surface
path
range
contract_id?
provider?
help?
data
```

# 6. State model

## Verification state

```text
passed
failed
unverified
skipped
configuration-error
internal-error
```

`unverified` означает, что semantic assertion не доказан. Это не pass и не mismatch.

## Projection authority

```text
authored
projection
snapshot
```

- `authored`: человек владеет body; engine валидирует.
- `projection`: provider владеет data; sync владеет body.
- `snapshot`: historical evidence; live drift не является ошибкой, но provenance обязателен.

Bidirectional authority отсутствует в v1.

# 7. Consistency and cache

## Snapshot digest

Digest считается по canonical JSON:

```text
schema
provider
adapter
adapter_version
revision
consistency
records
```

`captured_at` не входит в content digest.

## Cache

Cache — optional acceleration, а не authority.

Key:

```text
provider_config_digest
query_plan_digest
adapter_version
```

Offline mode использует cache только при явной policy.

## Lock

Lock хранится отдельно от cache и предназначен для tracked provenance.

# 8. Failure semantics

| Ситуация | Результат |
|---|---|
| Невалидный INI или schema | `configuration-error` |
| Unknown plugin | `configuration-error` |
| Marker без binding | `DOC-BLOCK-UNBOUND` |
| Binding без marker | error или warning по policy |
| Provider недоступен | `unverified` |
| Incomplete snapshot | `unverified` |
| Block отличается от canonical render | `failed` |
| Block изменён относительно lock | static drift error |
| File изменился между scan и write | write conflict |
| Internal exception | `internal-error` |

# 9. Concurrency

- Files могут парситься параллельно.
- Providers могут открываться параллельно друг с другом.
- Один provider session определяет свой concurrency.
- Findings и records сортируются после parallel work.
- Write phase всегда serial и transactional на workspace level.

# 10. Public Python API

```python
from locus_md import Engine, HostServices, load_workspace

workspace = load_workspace(config_path=".locus/config.ini")
engine = Engine(workspace, host_services=HostServices())
result = engine.verify()
```

CLI является тонким адаптером над API.

# 11. Repository layout

```text
locus-md/
├── pyproject.toml
├── src/locus_md/
│   ├── api.py
│   ├── cli/
│   ├── config/
│   ├── workspace/
│   ├── markdown/
│   ├── graph/
│   ├── contracts/
│   ├── providers/
│   ├── engine/
│   ├── rewrite/
│   ├── lock/
│   └── reporting/
├── schemas/
├── docs/
├── examples/
└── tests/
```

# 12. Dependency policy

Предлагаемый runtime stack:

- Python 3.11+;
- `markdown-it-py` для Markdown tokens и source maps;
- `ruamel.yaml` для frontmatter parsing/round-trip fixes;
- `jsonschema` для schemas;
- stdlib `configparser`, `pathlib`, `hashlib`, `importlib.metadata`.

Точный set подтверждается prototype. Core не тянет SDK GitHub/Linear; они принадлежат optional plugins.
