---
title: Правила документации Locus MD
type: guide
status: active
owner: team:locus-md
tags: [documentation, authoring]
---

# Документация Locus MD

Используй `$locus-docs` для изменения этой директории. Общий формат задаёт
`locus-docs/references/documentation-standard.md` из установленного набора Locus.

Порядок чтения:

1. `index.md` — карта документации.
2. `design/00-executive-summary.md` — продуктовая граница.
3. `design/01-product-requirements.md` — проверяемые требования.
4. `design/02-system-design.md` — компоненты и зависимости.
5. `implementation-status.md` — текущая реализованная поверхность.

`docs/index.md` остаётся единственной публичной точкой входа. Новая страница
добавляется в индекс тем же изменением. Frontmatter проверяют Locus и Locus MD.
