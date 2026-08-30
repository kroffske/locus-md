# Changelog

## 0.2.1

- Export `WorkspaceConfig`, `GlobalConfig`, and `SurfaceConfig` from the
  package root for embedded callers.
- Replace the tracked wheel snapshot with the 0.2.1 package build.

## 0.2.0

- Expose `lint_workspace` from the package root while preserving the existing
  config-loading `lint` wrapper.
- Replace the tracked wheel snapshot with the 0.2.0 package build.

## 0.1.1

- Rename the standalone CLI from the dotted spelling to `locus-md` everywhere.
- Remove the legacy dotted command alias.
- Rewrite public documentation and local project guidance in English.
- Remove machine-specific paths, usernames, and sibling-repository references from documentation.

- Bind each workspace to the selected config location instead of an enclosing Git root.
- Add the repository's own tracked document contract, documentation index, and navigation.
- Install the standalone CLI globally through `uv tool`.

## 0.1.0

- Initial standalone MVP with static documentation linting, managed blocks, file-backed provider verification, deterministic synchronization, lock evidence, CLI, plugin entry points, tests, and example workspace.
