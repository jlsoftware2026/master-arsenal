"""Resolve MALE's persistent workspace location without relying on install paths."""
from __future__ import annotations

import os
from pathlib import Path


def default_workspace(environ: dict[str, str] | None = None, *, platform: str | None = None) -> Path:
    """Return a per-user writable workspace on Windows and a local default elsewhere."""
    env = os.environ if environ is None else environ
    current_platform = os.name if platform is None else platform
    if current_platform == "nt":
        local_app_data = env.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "MASTER-ARSENAL" / "workspace"
        return Path.home() / "AppData" / "Local" / "MASTER-ARSENAL" / "workspace"
    return Path("MASTER-ARSENAL-LOCAL")
