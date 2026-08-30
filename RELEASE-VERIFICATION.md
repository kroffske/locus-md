# Release verification

Verified in the build environment on 2026-08-30.

- Python source compilation: passed.
- Test suite: 31 tests passed.
- Source line-width gate: all Python lines are at most 200 characters.
- Wheel build: passed with `uv build --wheel --out-dir dist`.
- Wheel installation smoke test: passed.
- Installed CLI smoke test: `--version`, `config validate`, `lint`, `verify --offline`, and `sync --check --offline` passed against `examples/basic`.
- Installed wheel embedded API smoke test: imported `lint_workspace`, loaded the example `WorkspaceConfig`, and received a `Report` from `lint_workspace`.
- The installed wheel exposes `locus-md` and does not expose the old dotted command.
- Packaged JSON Schema lookup through `importlib.resources`: passed.

Wheel SHA-256:

`3ab77a79556f4e244826c1a40f6b606ee16fac7aefd21c440dcfb77537d216b0  locus_md-0.2.0-py3-none-any.whl`
