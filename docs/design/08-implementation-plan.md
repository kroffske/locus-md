---
schema: locus.doc.v1
id: docs.design.implementation-plan
title: "Locus MD — implementation plan"
type: note
status: needs-review
owner: team:locus-md
tags: [plan, roadmap]
updated: "2026-08-28T00:27:14Z"
source_commit: "6ecd7cfe5fd1"
update_event: "user_request"
description: "Проверено и подключено к навигации и dogfood-контракту Locus MD."
---

# 1. Delivery strategy

Разработка идёт вертикальными slices. Каждый milestone заканчивается runnable CLI и acceptance test, а не только внутренними abstractions.

# 2. Milestone M0 — repository and contract baseline

## Goal

Создать самостоятельный repository и зафиксировать public boundaries.

## Work items

| ID | Task | Depends on |
|---|---|---|
| MD-001 | Repository skeleton, license, contribution policy | — |
| MD-002 | Product naming и package mapping | MD-001 |
| MD-003 | ADR по shared INI namespace | MD-002 |
| MD-004 | Public config/finding/snapshot schemas | MD-003 |
| MD-005 | CI, type checking, tests, package build | MD-001 |
| MD-006 | Example workspace | MD-004 |
| MD-007 | Pre-1.0 compatibility policy | MD-004 |

## Acceptance

- `uv tool install .` и `locus.md --help` работают.
- Schemas публикуются в wheel.
- Example config проходит `config validate`.
- CI собирает sdist и wheel.
- Core не содержит dependency на Locus.

# 3. Milestone M1 — static documentation engine

## Goal

Полезный standalone lint без providers.

## Work items

| ID | Task |
|---|---|
| MD-101 | Config discovery и namespace isolation |
| MD-102 | Normalized config model и validation |
| MD-103 | Surface inventory и path safety |
| MD-104 | Markdown/frontmatter parser |
| MD-105 | Link extraction и repository graph |
| MD-106 | Reachability rules |
| MD-107 | Marker scanner с fenced-code awareness |
| MD-108 | Finding model и JSON output |
| MD-109 | `lint`, `config validate`, `contracts list` |
| MD-110 | Read-only lock/body drift check |

## Acceptance

- Общий INI с unrelated sections обрабатывается без чтения их значений.
- Две surfaces имеют разные roots и schemas.
- Broken link и orphan doc дают stable findings.
- Marker в code fence не распознаётся.
- Nested/unclosed/duplicate blocks обнаруживаются.
- Lint не выполняет network calls.
- Findings deterministic byte-for-byte.

# 4. Milestone M2 — managed projections and file provider

## Goal

Полный local end-to-end use case.

## Work items

| ID | Task |
|---|---|
| MD-201 | Contract registry и binding resolution |
| MD-202 | Provider query/snapshot models |
| MD-203 | Built-in `file-json` provider |
| MD-204 | Contract handler protocol |
| MD-205 | Bundled `task-table.v1` example handler |
| MD-206 | Deterministic renderer |
| MD-207 | Patch planner |
| MD-208 | `sync --check` |
| MD-209 | Transactional `sync --write` |
| MD-210 | Lock write/update |
| MD-211 | Offline snapshot mode |

## Acceptance

- Milestone table строится из `data/tasks.json`.
- Ручное изменение status даёт out-of-date finding.
- `sync --write` меняет только block body.
- Текст и whitespace вне spans byte-identical.
- Второй sync не создаёт diff.
- Lock содержит snapshot/body digests.
- Изменение файла между scan и write даёт conflict.

# 5. Milestone M3 — plugin platform

## Goal

Коллеги добавляют integrations без fork.

## Work items

| ID | Task |
|---|---|
| MD-301 | Entry-point discovery |
| MD-302 | Provider contract test kit |
| MD-303 | Contract/renderer plugin APIs |
| MD-304 | Plugin version negotiation |
| MD-305 | Capability planning |
| MD-306 | Failure isolation и diagnostic wrapping |
| MD-307 | Plugin authoring guide |
| MD-308 | Reference plugin fixture |

## Acceptance

- Third-party package регистрирует provider без изменения core.
- Unknown API version отклоняется до execution.
- Provider exceptions становятся provider findings.
- Test kit проверяет normalization, determinism и partial failures.

# 6. Milestone M4 — Locus integration

## Goal

Подключить core к `locus docs`, сохранив standalone operation.

## Work items

| ID | Task |
|---|---|
| MD-401 | `HostServices` API |
| MD-402 | Host-injected provider |
| MD-403 | Locus task snapshot mapper |
| MD-404 | Shared INI compatibility fixture |
| MD-405 | Command/exit parity tests |
| MD-406 | Optional snapshot export contract |
| MD-407 | Integration documentation |

## Acceptance

- `locus docs verify` и `locus.md verify` формируют одинаковую finding schema.
- Locus host provider использует task policy Locus, но core не читает `[locus.tasks]`.
- Standalone mode использует exported snapshot.
- Отсутствующий Locus host не ломает import core.

# 7. Milestone M5 — GitHub/Linear and ecosystem hardening

## Goal

Подтвердить universality двумя remote adapters.

## Work items

| ID | Task |
|---|---|
| MD-501 | Read-only GitHub provider |
| MD-502 | Read-only Linear provider |
| MD-503 | Network permission policy |
| MD-504 | Cache and offline behavior |
| MD-505 | SARIF output |
| MD-506 | Pre-commit hook |
| MD-507 | Changed-files mode |
| MD-508 | Migration and troubleshooting guide |

## Acceptance

```text
repository default provider = linear
block A = explicit local/file snapshot
block B = inherited linear
both blocks validate in one document
provider override is explicit and deterministic
manual edit in either projection is detected
free Markdown is untouched
```

# 8. Critical path

```text
Config namespace
→ surface inventory
→ parser/spans
→ contract binding
→ snapshot model
→ deterministic renderer
→ safe rewrite
→ plugin API
→ Locus/GitHub/Linear adapters
```

Provider SDK work не начинается до фиксации snapshot и capability contracts.

# 9. Issue template

Каждый issue содержит:

- observable outcome;
- входные schemas;
- failure semantics;
- acceptance test;
- backward-compatibility note;
- отсутствие hidden dependency на Locus.

# 10. Definition of done

- implementation;
- unit tests;
- integration/golden test;
- docs;
- stable finding code для нового failure mode;
- no unexplained changes;
- example/fixture для user-facing surface.
