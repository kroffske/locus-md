# locus-md example workspace

This directory is a self-contained core-only fixture. Its configuration is
`.locus/locus-md.toml`, under the `[locus-md]` namespace.

```bash
cd examples/basic
locus-md config validate
locus-md lint
locus-md verify --offline
locus-md sync --check --offline
```

Tracked:

- `.locus/locus-md.toml`;
- `.locus/docs.lock.json`;
- optional offline provider snapshot;
- documents and schemas.

Ignored:

- `.locus/cache/`;
- `.locus/reports/`.

The `docs/` surface contains `index.md` and `milestones.md`. The latter has a
managed task table supplied by the local JSON provider. The example does not
require locus-skills-ml; install that optional package only for its separate
rule adapter scenario.
