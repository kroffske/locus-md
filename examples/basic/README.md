# Locus MD example workspace

This directory is a self-contained design fixture.

```bash
cd examples/basic
locus.md config validate
locus.md lint
locus.md verify --offline
locus.md sync --check --offline
```

Tracked:

- `.locus/config.ini`;
- `.locus/docs.lock.json`;
- optional offline provider snapshot;
- documents and schemas.

Ignored:

- `.locus/cache/`;
- `.locus/reports/`.
