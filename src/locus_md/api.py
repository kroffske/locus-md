from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .config import load_config
from .engine import Engine
from .models import Report, WorkspaceConfig
from .plugins import PluginRegistry


def load_workspace(*, config: str | Path | None = None, start: str | Path | None = None, env: Mapping[str, str] | None = None) -> WorkspaceConfig:
    return load_config(explicit=config, start=start, env=env)


def lint(
    *, config: str | Path | None = None, start: str | Path | None = None, surfaces: set[str] | None = None, strict: bool = False,
    registry: PluginRegistry | None = None
) -> Report:
    workspace = load_workspace(config=config, start=start)
    return Engine(workspace, registry=registry).lint(surfaces=surfaces, force_strict=strict)


def verify(
    *, config: str | Path | None = None, start: str | Path | None = None, surfaces: set[str] | None = None,
    providers: set[str] | None = None, offline: bool = False, network: bool = False, strict: bool = False,
    registry: PluginRegistry | None = None
) -> Report:
    workspace = load_workspace(config=config, start=start)
    return Engine(workspace, registry=registry).verify(surfaces=surfaces, providers=providers, offline=offline, network=network, force_strict=strict)


def sync(
    *, config: str | Path | None = None, start: str | Path | None = None, write: bool = False, surfaces: set[str] | None = None,
    providers: set[str] | None = None, offline: bool = False, network: bool = False, strict: bool = False,
    registry: PluginRegistry | None = None
) -> Report:
    workspace = load_workspace(config=config, start=start)
    return Engine(workspace, registry=registry).sync(write=write, surfaces=surfaces, providers=providers, offline=offline, network=network, force_strict=strict)
