"""Icon extraction and management."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from mimir_win.core.config import data_dir


def icons_dir() -> Path:
    d = data_dir() / "icons"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_icon(app_id: str, icon_b64: str) -> Path:
    """Save a base64-encoded PNG icon and return its path.

    The icon is saved as ~/.local/share/mimir-win/icons/<app_id>.png
    """
    icon_path = icons_dir() / f"{app_id}.png"
    icon_path.write_bytes(base64.b64decode(icon_b64))
    return icon_path


def get_icon_path(app_id: str) -> Path | None:
    """Get the path to an app's icon if it exists."""
    p = icons_dir() / f"{app_id}.png"
    return p if p.exists() else None


def icon_hash(icon_b64: str) -> str:
    """Compute a hash of the icon data for change detection."""
    return hashlib.sha256(icon_b64.encode()).hexdigest()[:16]
