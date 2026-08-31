# Release verification

Verified in the build environment on 2026-08-31.

- Python source compilation: passed.
- Test suite: 114 tests passed.
- Ruff and the strict documentation lint passed.
- Wheel build: passed with `uv build --wheel --offline`.
- Package parity: all 37 packaged `locus_md/**` source and schema entries are byte-identical to the reviewed checkout.
- Fresh core-only offline installation resolved `locus_md` from `site-packages` at version `0.4.0`.
- Installed `config validate` passed with 14 declared documents; installed `guide readme` returned `locus-md.guide.v1`; installed `impact` returned `locus-md.impact.v1`.
- Fresh paired offline installation resolved both `locus-md` and `locus-ml-skills` from `site-packages` and discovered the `locus_md.rules / locus-ml-line-document` entry point.
- Paired integration suite: 67 tests passed with zero failures, errors, or skips.
- Repeated installed `config validate`, `lint`, `verify --offline`, and `sync --check --offline` returned stable normalized results without mutating fixtures.
- The canonical configuration is `.locus/locus-md.toml` with `[locus-md]`; the legacy filename and dotted namespace return `CFG-061` without writes.
- Independent quality review passed at 8/10 with all five review questions closed and the Python policy passing.

Wheel SHA-256:

`76f813850bbf5351e74c5c7d2c736b500bc030d3dde146f503e34778e6504f93  locus_md-0.4.0-py3-none-any.whl`
