# Release verification

Verified in the build environment on 2026-08-30.

- Python source compilation: passed.
- Test suite: 32 tests passed.
- Source line-width gate: all Python lines are at most 200 characters.
- Wheel build: passed with `uv build --wheel --out-dir dist`.
- Wheel installation smoke test: passed.
- Installed CLI smoke test: `--version`, `config validate`, `lint`, `verify --offline`, and `sync --check --offline` passed against `examples/basic`.
- Installed wheel embedded API smoke test: imported `WorkspaceConfig`, `GlobalConfig`, `SurfaceConfig`, and `lint_workspace` from the package root, constructed the example `WorkspaceConfig` without configuration loading, and received a `Report` from `lint_workspace`.
- The installed wheel exposes `locus-md` and does not expose the old dotted command.
- Packaged JSON Schema lookup through `importlib.resources`: passed.

Wheel SHA-256:

`8a206126f7dc25bb65e0987f4b4ee8d2a2d4b832c6b903b6da3317d6f840b812  locus_md-0.2.1-py3-none-any.whl`
