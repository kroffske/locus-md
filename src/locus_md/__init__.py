"""locus-md public package."""

from .api import lint_workspace, load_workspace, lint, sync, verify
from .models import GlobalConfig, SurfaceConfig, WorkspaceConfig

__all__ = [
    "__version__",
    "load_workspace",
    "lint_workspace",
    "lint",
    "verify",
    "sync",
    "WorkspaceConfig",
    "GlobalConfig",
    "SurfaceConfig",
]
__version__ = "0.2.1"
