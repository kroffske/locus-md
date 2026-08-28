---
schema: locus.doc.v1
id: docs.implementation-status
title: Implementation status
type: note
status: active
owner: team:locus-md
tags: [implementation, dogfood]
updated: "2026-08-28T00:27:13Z"
source_commit: "6ecd7cfe5fd1"
update_event: "user_request"
description: "Проверено и подключено к навигации и dogfood-контракту Locus MD."
---

# Implementation status

## Реализованный dogfood-контур

Эта таблица материализуется из `data/project-status.json`. Файл конфигурации
`.locus/config.ini` связывает источник с блоком. Свободный текст ниже не
перезаписывается.

<!-- locus:milestone dogfood begin -->
| Task | Title | Status |
|---|---|---|
| MD-001 | Создать самостоятельный Python-пакет и CLI | done |
| MD-002 | Проверять Markdown-поверхности и ссылки | done |
| MD-003 | Проверять и синхронизировать managed blocks | done |
| MD-004 | Подключить контракт к репозиторию Locus MD | done |
<!-- locus:milestone dogfood end -->

## Deliberately deferred

- GitHub and Linear packages.
- Remote writes and bidirectional authority.
- SARIF and language-server integration.
- Changed-files dependency closure.
- Rule and renderer plugin groups as independently versioned SDKs.
- Cross-process sandboxing of plugins.

The deferred items are not silently emulated. Unknown adapters and schemas are configuration errors; unavailable required providers produce an explicit `unverified` state.
