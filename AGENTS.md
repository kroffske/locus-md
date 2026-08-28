# Locus MD

Этот файл — единый репозиторный контракт для агентов. Вложенный `AGENTS.md`
может уточнять правила только для своей директории.

## Назначение

Locus MD — самостоятельная Python-библиотека и CLI для детерминированных
семантических контрактов над Markdown. Свободный текст остаётся человеческим.
Инструмент проверяет структуру, граф ссылок и управляемые проекции данных.

## Начало работы

Перед существенной работой запусти `locus context preamble`. Создай окружение и
установи проект командой `python3 -m venv .venv && .venv/bin/python -m pip
install -e '.[dev]'`.

Проверки:

```bash
.venv/bin/python -m pytest
PATH="$PWD/.venv/bin:$PATH" make example
.venv/bin/locus.md config validate
.venv/bin/locus.md lint
.venv/bin/locus.md verify --offline
.venv/bin/locus.md sync --check --offline
locus docs lint
```

Глобальная установка: `uv tool install --force .`. Сборка wheel:
`.venv/bin/python -m pip wheel . --no-deps -w dist`.

## Правила изменений

- `src/locus_md/` не импортирует Locus, GitHub, Linear или конкретный task tracker.
- Locus MD читает из общего INI только секции `[locus.docs*]`.
- Изменение managed block не должно менять байты вне его span.
- Новый provider или contract failure получает стабильный finding code и тест.
- `dist/` содержит снимок локальной сборки. Не считай его текущим без новой проверки установки.
- `.locus/AGENTS.md` — локальный registry Locus. В clean clone его создаёт `locus init`.
- Перед локальным коммитом загрузи `locus context skill locus-ship` и stage только принадлежащие изменению пути.
- Не выполняй push, публикацию пакета или внешнюю запись без явного запроса.

<navigation>
<!-- Where things live. Describe every major directory and entry point.
     git=tracked    committed; a fresh clone has it
     git=local      deliberately gitignored working surface
     git=generated  build output; absent until the build runs -->
<!-- locus:nav:v1:begin -->
| path | what | git |
| --- | --- | --- |
| `README.md` | Пользовательская точка входа и быстрый запуск | tracked |
| `AGENTS.md` | Репозиторный контракт и проверяемая навигация | tracked |
| `CLAUDE.md` | Точка входа Claude Code; ссылается на `AGENTS.md` | tracked |
| `ARCHITECTURE.md` | Краткая карта границ и пути выполнения | tracked |
| `docs/` | Документация; порядок чтения начинается с `docs/index.md` | tracked |
| `src/locus_md/` | Python-пакет, CLI, engine, providers и schemas | tracked |
| `tests/` | Pytest-проверки публичных и внутренних контрактов | tracked |
| `examples/` | Самодостаточные рабочие пространства для acceptance-проверок | tracked |
| `schemas/` | JSON Schema для документации самого репозитория | tracked |
| `data/` | Нормализованные источники dogfood-контрактов | tracked |
| `.locus/config.ini` | Tracked manifest контрактов Locus MD | tracked |
| `.locus/docs.lock.json` | Воспроизводимое evidence последней materialization | tracked |
| `.locus/soul.md` | Локальная продуктовая идентичность и долгосрочные границы | local |
| `.tasks/` | Локальные task workspaces и evidence | local |
| `.venv/` | Локальное Python-окружение | local |
| `dist/` | Сохранённый wheel исходного релизного снимка | tracked |
| `.github/` | CI workflow для Python 3.11–3.13 | tracked |
<!-- locus:nav:v1:end -->
</navigation>
