"""Desktop entry (.desktop file) generation and management."""

from __future__ import annotations

import os
import stat
from pathlib import Path

DESKTOP_DIR = Path.home() / ".local" / "share" / "applications"
BIN_DIR = Path.home() / ".local" / "bin"
ICON_DIR = Path.home() / ".local" / "share" / "icons" / "mimir-win"


def _ensure_dirs() -> None:
    """确保目录存在。"""
    DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    ICON_DIR.mkdir(parents=True, exist_ok=True)


def _create_default_icon() -> Path:
    """创建默认 Windows 图标（SVG）。"""
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    icon_path = ICON_DIR / "windows-app.svg"
    if icon_path.exists():
        return icon_path

    # 简单的 Windows logo SVG
    svg = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">
  <rect x="2" y="2" width="20" height="20" fill="#0078d4" rx="2"/>
  <rect x="26" y="2" width="20" height="20" fill="#0078d4" rx="2"/>
  <rect x="2" y="26" width="20" height="20" fill="#0078d4" rx="2"/>
  <rect x="26" y="26" width="20" height="20" fill="#0078d4" rx="2"/>
</svg>'''
    icon_path.write_text(svg)
    return icon_path


def create_app_entry(
    app_id: str,
    name: str,
    exe: str,
    icon_path: str | None = None,
    categories: str = "Utility",
    mime_types: str = "",
    mimir_win_bin: str = "mimir-win",
) -> Path:
    """Create a .desktop entry for a Windows application."""
    _ensure_dirs()

    # 使用默认图标如果没有提供
    if not icon_path:
        icon_path = str(_create_default_icon())

    # Create launcher script
    launcher = BIN_DIR / f"mimir-win-{app_id}"
    # 使用当前工作目录或配置的项目路径
    import os
    project_dir = os.environ.get("MIMIR_WIN_PROJECT_DIR", os.getcwd())
    launcher.write_text(
        f'#!/usr/bin/env bash\nexec nix develop "{project_dir}" --command python -m mimir_win app run {app_id} "$@"\n'
    )
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)

    # Create .desktop file
    desktop = DESKTOP_DIR / f"mimir-win-{app_id}.desktop"
    lines = [
        "[Desktop Entry]",
        f"Name={name}",
        f"Exec={launcher} %F",
        "Terminal=false",
        "Type=Application",
        f"Categories=Mimir-Win;",
        "NoDisplay=false",
        "StartupWMClass=" + name,
        f"Icon={icon_path}",
        "Comment=Windows 应用 (Mimir-Win)",
    ]
    if mime_types:
        lines.append(f"MimeType={mime_types}")

    desktop.write_text("\n".join(lines) + "\n")
    return desktop


def remove_app_entry(app_id: str) -> None:
    """Remove a .desktop entry and its launcher script."""
    desktop = DESKTOP_DIR / f"mimir-win-{app_id}.desktop"
    launcher = BIN_DIR / f"mimir-win-{app_id}"
    desktop.unlink(missing_ok=True)
    launcher.unlink(missing_ok=True)


def create_windows_entry(mimir_win_bin: str = "mimir-win") -> Path:
    """Create a .desktop entry for a full Windows desktop session."""
    _ensure_dirs()
    icon = _create_default_icon()

    desktop = DESKTOP_DIR / "mimir-win-windows.desktop"
    desktop.write_text(
        f"""\
[Desktop Entry]
Name=Windows 桌面
Exec=nix develop "/home/mimir/win project/mimir-win" --command python -m mimir_win windows %F
Terminal=false
Type=Application
Categories=Mimir-Win;System;
Icon={icon}
StartupWMClass=Windows Desktop
Comment=完整 Windows 桌面 (Mimir-Win)
"""
    )
    return desktop


def create_menu_directory() -> Path:
    """创建 KDE 开始菜单的 Mimir-Win 分类目录。"""
    menu_dir = Path.home() / ".config" / "menus" / "applications-merged"
    menu_dir.mkdir(parents=True, exist_ok=True)

    menu_file = menu_dir / "mimir-win.menu"
    menu_file.write_text("""\
<!DOCTYPE Menu PUBLIC "-//freedesktop//DTD Menu 1.0//EN"
  "http://www.freedesktop.org/standards/menu-spec/menu-1.0.dtd">
<Menu>
  <Name>Applications</Name>
  <Menu>
    <Name>Mimir-Win</Name>
    <Directory>mimir-win.directory</Directory>
    <Include>
      <Category>Mimir-Win</Category>
    </Include>
  </Menu>
</Menu>
""")

    # 创建 .directory 文件（菜单分类定义）
    directory_file = Path.home() / ".local" / "share" / "desktop-directories" / "mimir-win.directory"
    directory_file.parent.mkdir(parents=True, exist_ok=True)
    icon = _create_default_icon()
    directory_file.write_text(f"""\
[Desktop Entry]
Type=Directory
Name=Mimir-Win
Name[zh]=Windows 应用
Icon={icon}
Comment=Windows 应用 (Mimir-Win)
""")

    return menu_file


def list_entries() -> list[Path]:
    """List all Mimir-Win .desktop entries."""
    if not DESKTOP_DIR.exists():
        return []
    return sorted(DESKTOP_DIR.glob("mimir-win-*.desktop"))
