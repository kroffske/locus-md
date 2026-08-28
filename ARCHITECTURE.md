# Architecture

Locus MD is a library-first modular monolith. The execution path is:

```text
CLI / Python API
→ isolated INI configuration
→ workspace inventory
→ Markdown/frontmatter scan
→ repository graph and static findings
→ contract query plan
→ one immutable snapshot per provider
→ contract validation and deterministic rendering
→ safe span patches
→ lock evidence
```

The core does not import Locus, GitHub, Linear, or any task tracker. Hosts inject provider adapters through `PluginRegistry`, while installable integrations use Python entry points. Providers are read-only in API v1.

See `docs/design/` for the detailed product and system design.
