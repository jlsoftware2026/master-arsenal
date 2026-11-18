"""Resolve per-user persistent paths for packaged Windows use."""
from __future__ import annotations

import os
from pathlib import Path


def default_snapshot_output(environ: dict[str, str] | None = None, *, platform: str | None = None) -> Path:
    """Keep default snapshots outside the replaceable application installation."""
    env = os.environ if environ is None else environ
    current_platform = os.name if platform is None else platform
    if current_platform == "nt":
        local_app_data = env.get("LOCALAPPDATA")
        root = (
            Path(local_app_data) if local_app_data
            else Path.home() / "AppData" / "Local"
        )
        return root / "MASTER-ARSENAL" / "workspace" / "data" / "snapshots" / "snapshot.json"
    return Path("snapshot.json")
