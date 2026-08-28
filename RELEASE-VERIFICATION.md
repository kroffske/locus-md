# Release verification

Verified in the build environment on 2026-08-28.

- Python source compilation: passed.
- Test suite: 24 tests passed.
- Source line-width gate: all Python lines are at most 200 characters.
- Wheel build: passed with setuptools and no build isolation.
- Wheel installation smoke test: passed.
- Installed CLI smoke test: `--version`, `config validate`, `lint`, `verify --offline`, and `sync --check --offline` passed against `examples/basic`.
- Packaged JSON Schema lookup through `importlib.resources`: passed.

Wheel SHA-256:

`7252b174f9e9a25b82c8b90434591dcafb8d195ee34f256f99ed2d1f6cb87ad6  locus_md-0.1.0-py3-none-any.whl`
