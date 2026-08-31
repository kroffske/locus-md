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
        self.rules: dict[str, Any] = {}
        self.load_errors: list[str] = []
        self.rule_load_errors: dict[str, str] = {}
        if discover:
            self._discover_group("locus_md.providers", self.providers)
            self._discover_group("locus_md.contracts", self.contracts)
            self._discover_group("locus_md.rules", self.rules, named_errors=self.rule_load_errors)

    def _discover_group(
        self,
        group: str,
        destination: dict[str, Any],
        *,
        named_errors: dict[str, str] | None = None,
    ) -> None:
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
                    message = f"{group}:{entry.name} has unsupported API version {getattr(plugin, 'api_version', None)!r}"
                    self.load_errors.append(message)
                    if named_errors is not None:
                        named_errors[entry.name] = message
                    continue
                destination[entry.name] = plugin
            except Exception as exc:
                message = f"cannot load {group}:{entry.name}: {exc}"
                self.load_errors.append(message)
                if named_errors is not None:
                    named_errors[entry.name] = message


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

    def register_rule(self, adapter: str, plugin: Any, *, replace: bool = False) -> None:
        if getattr(plugin, "api_version", None) != "1":
            raise ConfigError("PLUGIN-001", f"rule {adapter!r} has unsupported API version {getattr(plugin, 'api_version', None)!r}")
        self._snapshot_rule_metadata(adapter, plugin)
        if adapter in self.rules and not replace:
            raise ConfigError("PLUGIN-002", f"rule adapter {adapter!r} is already registered")
        self.rules[adapter] = plugin
        self.rule_load_errors.pop(adapter, None)

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

    def rule(self, adapter: str) -> Any:
        plugin, _, _ = self.resolve_rule(adapter)
        return plugin

    def resolve_rule(self, adapter: str) -> tuple[Any, str, str]:
        if adapter in self.rule_load_errors:
            raise ConfigError("PLUGIN-001", self.rule_load_errors[adapter])
        try:
            plugin = self.rules[adapter]
        except KeyError as exc:
            raise ConfigError("CFG-037", f"unknown rule adapter {adapter!r}") from exc
        plugin_id, plugin_version = self._snapshot_rule_metadata(adapter, plugin)
        return plugin, plugin_id, plugin_version

    @staticmethod
    def _snapshot_rule_metadata(adapter: str, plugin: Any) -> tuple[str, str]:
        try:
            plugin_id = plugin.plugin_id
            plugin_version = plugin.plugin_version
        except Exception as exc:
            raise ConfigError("PLUGIN-003", f"rule {adapter!r} metadata cannot be read: {type(exc).__name__}: {exc}") from exc
        if not all(isinstance(value, str) and bool(value.strip()) for value in (plugin_id, plugin_version)):
            raise ConfigError("PLUGIN-003", f"rule {adapter!r} must declare plugin_id and plugin_version")
        return plugin_id, plugin_version

    def validate_references(self, config: Any) -> None:
        for provider in config.providers.values():
            self.provider(provider.adapter)
        for binding in config.contracts.values():
            handler = self.contract(binding.schema)
            if binding.mode == "projection" and binding.renderer not in handler.renderer_ids:
                raise ConfigError("CFG-032", f"contract {binding.name!r} uses unsupported renderer {binding.renderer!r} for schema {binding.schema!r}")
        from .rules.api import readonly_mapping

        for rule in config.rules.values():
            plugin, _, _ = self.resolve_rule(rule.adapter)
            try:
                result = plugin.validate_config(readonly_mapping(rule.options))
            except Exception as exc:
                reason = exc.message if isinstance(exc, ConfigError) else f"{type(exc).__name__}: {exc}"
                raise ConfigError("CFG-038", f"rule {rule.name!r} rejected its options: {reason}") from exc
            if result is not None:
                raise ConfigError("PLUGIN-003", f"rule {rule.name!r} validate_config must return None")
