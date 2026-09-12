"""Configuration management for Mimir-Win."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]


# --- XDG paths ---


def config_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "mimir-win"


def data_dir() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "mimir-win"


def cache_dir() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "mimir-win"


# --- Data classes ---


@dataclass
class RDPConfig:
    user: str = "MyWindowsUser"
    password: str = ""
    password_file: str = ""
    domain: str = ""
    ip: str = "127.0.0.1"
    port: int = 3389
    scale: int = 100
    extra_flags: str = ""


@dataclass
class VMConfig:
    backend: str = "podman"  # podman | docker | manual
    image: str = "ghcr.io/dockur/windows:latest"
    container_name: str = "Mimir-Win"
    cpus: int = 4
    memory: str = "4G"
    disk_size: str = "64G"
    win_version: str = "11pro"
    data_dir: str = ""
    home_share: str = ""
    auto_start: bool = False
    idle_timeout: int = 300  # seconds, 0 = disabled
    idle_action: str = "pause"  # pause | stop


@dataclass
class DisplayConfig:
    prefer_native_wayland: bool = True
    multimon: str = "none"  # none | multi | span
    scale: float = 1.0  # DPI 缩放比例


@dataclass
class Config:
    rdp: RDPConfig = field(default_factory=RDPConfig)
    vm: VMConfig = field(default_factory=VMConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    debug: bool = False

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Load config from TOML file, falling back to defaults.

        优先级：
        1. 显式传入的 path
        2. 环境变量 MIMIR_WIN_CONFIG（NixOS 使用）
        3. 默认路径 ~/.config/mimir-win/mimir-win.toml
        """
        if path is None:
            env_path = os.environ.get("MIMIR_WIN_CONFIG")
            if env_path:
                path = Path(env_path)
            else:
                path = config_dir() / "mimir-win.toml"

        if not path.exists():
            return cls()

        with open(path, "rb") as f:
            data = tomllib.load(f)

        cfg = cls()
        if "rdp" in data:
            for k, v in data["rdp"].items():
                if hasattr(cfg.rdp, k):
                    setattr(cfg.rdp, k, v)
        if "vm" in data:
            for k, v in data["vm"].items():
                if hasattr(cfg.vm, k):
                    setattr(cfg.vm, k, v)
        if "display" in data:
            for k, v in data["display"].items():
                if hasattr(cfg.display, k):
                    setattr(cfg.display, k, v)
        if "debug" in data:
            cfg.debug = bool(data["debug"])

        # Defaults for data_dir
        if not cfg.vm.data_dir:
            cfg.vm.data_dir = str(data_dir() / "vm")

        return cfg

    def save(self, path: Path | None = None) -> None:
        """Save config to TOML file with restricted permissions."""
        path = path or config_dir() / "mimir-win.toml"
        path.parent.mkdir(parents=True, exist_ok=True)

        lines = ["# Mimir-Win configuration file", ""]

        # RDP section
        lines.append("[rdp]")
        for k, v in self.rdp.__dict__.items():
            if k == "password" and v:
                lines.append(f'{k} = "{v}"')
            elif k == "password_file" or v != "":
                lines.append(f"{k} = {_toml_value(v)}")
        lines.append("")

        # VM section
        lines.append("[vm]")
        for k, v in self.vm.__dict__.items():
            if v != "" and v is not False:
                lines.append(f"{k} = {_toml_value(v)}")
        lines.append("")

        # Display section
        lines.append("[display]")
        for k, v in self.display.__dict__.items():
            lines.append(f"{k} = {_toml_value(v)}")
        lines.append("")

        path.write_text("\n".join(lines) + "\n")
        # 限制文件权限，只有 owner 可读写
        import stat as _stat

        path.chmod(_stat.S_IRUSR | _stat.S_IWUSR)

    def resolve_password(self) -> str:
        """Resolve password from direct value or file."""
        if self.rdp.password_file:
            p = Path(self.rdp.password_file).expanduser()
            if p.exists():
                return p.read_text().strip()
        return self.rdp.password


def _toml_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return f'"{v}"'
    return f'"{v}"'
