from __future__ import annotations

from importlib import metadata
from typing import Any

from .contracts.task_table import TaskTableHandler
from .errors import ConfigError
from .providers.file_json import FileJsonProvider
from .providers.snapshot import SnapshotProvider


class PluginRegistry:
    def __init__(self, *, discover: bool = True) -> None:
        self.providers: dict[str, Any] = {"file-json": FileJsonProvider(), "snapshot": SnapshotProvider()}
        task_table = TaskTableHandler()
        self.contracts: dict[str, Any] = {task_table.schema_id: task_table}
        self.load_errors: list[str] = []
        if discover:
            self._discover_group("locus_md.providers", self.providers)
            self._discover_group("locus_md.contracts", self.contracts)

    def _discover_group(self, group: str, destination: dict[str, Any]) -> None:
        try:
            entries = metadata.entry_points().select(group=group)
        except Exception as exc:
            self.load_errors.append(f"cannot enumerate {group}: {exc}")
            return
        for entry in entries:
            if entry.name in destination:
                continue
            try:
                loaded = entry.load()
                plugin = loaded() if isinstance(loaded, type) else loaded
                if getattr(plugin, "api_version", None) != "1":
                    self.load_errors.append(f"{group}:{entry.name} has unsupported API version {getattr(plugin, 'api_version', None)!r}")
                    continue
                destination[entry.name] = plugin
            except Exception as exc:
                self.load_errors.append(f"cannot load {group}:{entry.name}: {exc}")


    def register_provider(self, adapter: str, plugin: Any, *, replace: bool = False) -> None:
        if getattr(plugin, "api_version", None) != "1":
            raise ConfigError("PLUGIN-001", f"provider {adapter!r} has unsupported API version {getattr(plugin, 'api_version', None)!r}")
        if adapter in self.providers and not replace:
            raise ConfigError("PLUGIN-002", f"provider adapter {adapter!r} is already registered")
        self.providers[adapter] = plugin

    def register_contract(self, schema: str, handler: Any, *, replace: bool = False) -> None:
        if getattr(handler, "api_version", None) != "1":
            raise ConfigError("PLUGIN-001", f"contract {schema!r} has unsupported API version {getattr(handler, 'api_version', None)!r}")
        if schema in self.contracts and not replace:
            raise ConfigError("PLUGIN-002", f"contract schema {schema!r} is already registered")
        self.contracts[schema] = handler

    def provider(self, adapter: str) -> Any:
        try:
            return self.providers[adapter]
        except KeyError as exc:
            raise ConfigError("CFG-020", f"unknown provider adapter {adapter!r}") from exc

    def contract(self, schema: str) -> Any:
        try:
            return self.contracts[schema]
        except KeyError as exc:
            raise ConfigError("CFG-031", f"unknown contract schema {schema!r}") from exc

    def validate_references(self, config: Any) -> None:
        for provider in config.providers.values():
            self.provider(provider.adapter)
        for binding in config.contracts.values():
            handler = self.contract(binding.schema)
            if binding.mode == "projection" and binding.renderer not in handler.renderer_ids:
                raise ConfigError("CFG-032", f"contract {binding.name!r} uses unsupported renderer {binding.renderer!r} for schema {binding.schema!r}")
        if config.rules:
            names = ", ".join(sorted(config.rules))
            raise ConfigError("CFG-037", f"rule plugins are declared but rule execution is not implemented in API v0.1: {names}")
