# Release verification

Verified in the build environment on 2026-08-30.

- Python source compilation: passed.
- Test suite: 27 tests passed.
- Source line-width gate: all Python lines are at most 200 characters.
- Wheel build: passed with `uv build --wheel --out-dir dist`.
- Wheel installation smoke test: passed.
- Installed CLI smoke test: `--version`, `config validate`, `lint`, `verify --offline`, and `sync --check --offline` passed against `examples/basic`.
- The installed wheel exposes `locus-md` and does not expose the old dotted command.
- Packaged JSON Schema lookup through `importlib.resources`: passed.

Wheel SHA-256:

`94d018b05643fc70155d2b9bb9166017328f7d4f56ec9eb93afadcdbabb925f9  locus_md-0.1.1-py3-none-any.whl`
