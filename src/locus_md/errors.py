from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class LocusMdError(Exception):
    """Base expected error."""


@dataclass(slots=True)
class ConfigError(LocusMdError):
    code: str
    message: str
    path: Path | None = None

    def __str__(self) -> str:
        location = f" ({self.path})" if self.path else ""
        return f"{self.code}: {self.message}{location}"


@dataclass(slots=True)
class ProviderUnavailable(LocusMdError):
    provider: str
    message: str

    def __str__(self) -> str:
        return f"Provider {self.provider!r} unavailable: {self.message}"


@dataclass(slots=True)
class WriteConflict(LocusMdError):
    path: Path
    message: str

    def __str__(self) -> str:
        return f"Write conflict for {self.path}: {self.message}"
