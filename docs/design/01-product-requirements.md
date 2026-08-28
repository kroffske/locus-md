---
title: "Locus MD — product requirements"
status: proposed
date: "2026-08-27"
---

# 1. Проблема

Markdown-репозитории смешивают четыре класса содержания:

1. **Authored prose** — rationale, объяснения, заметки.
2. **Document envelope** — title, type, status, owner, provenance.
3. **Repository graph** — links, indexes, reachability, ownership.
4. **Materialized projections** — task tables, milestone status, inventories, generated indexes.

Обычные Markdown-линтеры проверяют форму, но не могут доказать, что таблица задач соответствует реальному tracker, индекс покрывает все страницы или policy действительно исполняется.

Основной failure mode:

> Документ выглядит структурированным и актуальным, но является вручную поддерживаемой декларацией без воспроизводимого контракта.

# 2. Пользователи

## Maintainer

Хочет включить deterministic gate в CI и видеть конкретные findings с путём и remediation.

## Documentation platform owner

Определяет surfaces, schemas, graph rules и managed projections.

## Tool integrator

Подключает provider или contract kind без fork ядра.

## LLM agent

Должен понимать, какие участки можно свободно редактировать, а какие принадлежат машине.

## CI

Требует стабильных exit codes, JSON/SARIF и воспроизводимости в clean checkout.

# 3. Product goals

- Проверять структуру документов и frontmatter.
- Проверять repository graph.
- Объявлять typed managed blocks.
- Сверять блоки с provider snapshots.
- Безопасно обновлять projections.
- Работать standalone.
- Интегрироваться с Locus без зависимости core от Locus.
- Поддерживать custom surfaces, contracts, providers и renderers.
- Давать одинаковый результат человеку, CI и LLM-host.

# 4. Non-goals

- Не заменять `markdownlint`, Vale, spellcheck или site generator.
- Не создавать и не закрывать remote tasks в docs-командах.
- Не определять source of truth эвристически.
- Не переписывать authored prose.
- Не делать bidirectional sync в первой стабильной линии.
- Не хранить secrets.
- Не становиться VCS или object store.
- Не выполнять произвольные shell-команды из config.
- Не считать LLM частью trusted validation path.

# 5. Functional requirements

| ID | Requirement |
|---|---|
| FR-001 | Config discovery через explicit path, environment или project discovery |
| FR-002 | Чтение только `locus.docs*` sections |
| FR-003 | Несколько independent documentation surfaces |
| FR-004 | UTF-8 Markdown, YAML frontmatter, links, fenced blocks и HTML comments |
| FR-005 | JSON Schema для frontmatter |
| FR-006 | Repository graph: links, roots, indexes и reachability |
| FR-007 | Парные managed markers, ошибки nesting/duplicates/unclosed |
| FR-008 | Binding по `surface + path + kind + id` |
| FR-009 | Полный provider query plan до I/O |
| FR-010 | Immutable normalized provider snapshots |
| FR-011 | Domain validation через contract handler |
| FR-012 | Deterministic render для projections |
| FR-013 | `sync --check` без writes |
| FR-014 | `sync --write` меняет только block body и lock |
| FR-015 | Offline mode с `unverified`, если snapshot отсутствует |
| FR-016 | Plugins через Python entry points |
| FR-017 | Human и JSON output; SARIF после MVP |
| FR-018 | Stable rule IDs |
| FR-019 | Host integration API для Locus |
| FR-020 | Static lock/body drift detection без provider access |

# 6. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-001 | Deterministic ordering и output |
| NFR-002 | Idempotent sync |
| NFR-003 | Byte preservation вне managed spans |
| NFR-004 | Reproducible static checks в clean checkout |
| NFR-005 | Раздельные failure states |
| NFR-006 | Plugin extensibility без изменения engine |
| NFR-007 | Path, symlink, secret и plugin security |
| NFR-008 | Linux, macOS и Windows |
| NFR-009 | Parse once, batch queries, hash cache |
| NFR-010 | Run ID, config digest, snapshot digests и plugin versions |

# 7. Success metrics

- доля репозиториев, где `sync --check` работает в clean checkout;
- число false positive findings;
- число ручных изменений managed blocks, остановленных до merge;
- доля providers, проходящих общий contract test suite;
- число изменений authored prose при sync — всегда ноль;
- стабильность JSON schema между patch/minor releases;
- ускорение повторного запуска на неизменившемся workspace.

# 8. Product invariants

- Config задаёт intent.
- Provider задаёт external truth.
- Managed projection не становится вторым source of truth.
- Lock хранит evidence, но не заменяет provider.
- CLI flag фильтрует работу, но не переосмысливает contract.
- LLM не участвует в pass/fail.
- Remote mutation не выполняется docs engine.
