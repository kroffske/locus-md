---
title: "Locus MD — executive summary"
status: proposed
date: "2026-08-27"
---

# 1. Продуктовое решение

Создать самостоятельный open-source или internal-shared репозиторий **`locus-md`**, который устанавливается и запускается без Locus.

Продуктовая формула:

> Locus MD проверяет не только форму Markdown, но и соответствие документальных проекций объявленным источникам данных, сохраняя весь неуправляемый текст без изменений.

Инструмент занимает слой между обычным Markdown linting и предметными системами:

```text
Markdown style / prose / links
                ↓
       Locus MD contracts
                ↓
files / JSON / Git / Locus / GitHub / Linear / custom providers
```

# 2. Почему отдельный репозиторий оправдан

Первый подтверждённый host — Locus, но целевой consumer set шире:

- коллеги, которым нужен воспроизводимый documentation gate без установки Locus;
- другие CLI и build systems;
- репозитории, где source of truth хранится в JSON/YAML/GitHub/Linear;
- pre-commit и CI;
- LLM-агенты, которым нужна безопасная граница между authored и machine-owned содержимым.

Поэтому ядро не должно знать о структуре `locus-skills`, `.tasks`, конкретном tracker или внутреннем config runtime.

# 3. Главные архитектурные решения

## 3.1. Config-driven surfaces

В коде нет обязательного `docs/`, `docs/index.md` или конкретного frontmatter enum. Репозиторий объявляет одну или несколько поверхностей:

```text
surface = root + include/exclude + index + envelope rules + graph rules
```

Это позволяет проверять `docs/`, `handbook/`, `adr/`, `runbooks/`, набор README по monorepo или отдельные contract-файлы.

## 3.2. Один общий INI-файл

Базовый путь — `.locus/config.ini`, но путь можно передать через `--config`.

Locus MD читает только:

```text
[locus.docs]
[locus.docs.surface:*]
[locus.docs.contract:*]
[locus.docs.provider:*]
[locus.docs.rule:*]
```

Другие секции не интерпретируются и не участвуют в interpolation.

## 3.3. Короткий Markdown, подробный конфиг

Маркеры содержат только понятный минимум:

```md
<!-- locus:milestone tasks begin -->
...
<!-- locus:milestone tasks end -->
```

Вся семантика находится в конфиге:

```text
path + block_kind + block_id
→ schema + mode + provider + selector + renderer
```

## 3.4. Sidecar lock вместо тяжёлых markers

`.locus/docs.lock.json` хранит digest тела блока, digest provider snapshot, source revision, renderer, contract schema и момент последней успешной синхронизации.

Это позволяет обнаружить ручной drift даже без сети и не увеличивает нагрузку на человека или LLM.

## 3.5. Snapshot consistency

Сначала engine строит полный query plan, затем каждый provider захватывает один immutable snapshot на запуск. Все блоки одного provider проверяются против одной ревизии.

## 3.6. Однонаправленная интеграция

```text
locus-md core
      ↑
optional provider plugins
      ↑
Locus host adapter
```

`locus-md` никогда не импортирует Locus. Locus либо вызывает public Python API, регистрирует host providers, либо запускает standalone CLI как subprocess.

# 4. MVP

MVP включает:

- namespaced INI loader;
- несколько configurable surfaces;
- YAML frontmatter + JSON Schema;
- Markdown scanning и repository graph;
- короткие managed block markers;
- config bindings;
- `file-json` provider;
- immutable snapshots;
- `lint`, `verify`, `sync --check`, `sync --write`;
- lock-file;
- JSON diagnostics;
- provider/plugin API;
- Locus adapter как отдельный integration package или host module.

MVP не включает remote writes, bidirectional sync, LLM-mediated pass/fail, собственную систему версионирования, language server или полный prose/style linter.

# 5. Критерий готовности

1. Чистый checkout воспроизводит `lint`, `verify` и `sync --check`.
2. Один и тот же config + snapshot дают одинаковые findings и rendered block.
3. `sync --write` не меняет ни одного байта вне managed spans.
4. Повторный sync является no-op.
5. Ручное изменение projection обнаруживается через lock или повторный render.
6. Недоступный provider даёт `unverified`, а не ложный `passed`.
7. Неизвестный schema/provider/renderer даёт понятную configuration error.
8. В одном документе безопасно сосуществуют блоки разных providers.
9. Standalone CLI не требует Locus.
10. `locus docs` использует то же ядро и тот же `[locus.docs]` config.
