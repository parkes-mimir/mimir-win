"""应用管理 CLI - 对标 WinApps 的 app 功能。

用法：
  mimir-win app run <id>           # 无缝启动 Windows 应用
  mimir-win app run <id> file.docx # 用指定应用打开文件
  mimir-win app list               # 列出可用应用
  mimir-win app refresh            # 从 Windows 刷新应用列表
  mimir-win run <exe>              # 手动运行任意 Windows 可执行文件
"""

from __future__ import annotations

import re

import argparse
import json
import sys
from pathlib import Path

from mimir_win.core.config import Config, data_dir
from mimir_win.core import vm, rdp
from mimir_win.core.daemon import ensure_awake


def handle_app(args: argparse.Namespace) -> None:
    if not hasattr(args, "app_action") or args.app_action is None:
        print("用法: mimir-win app {run|list|refresh} ...")
        sys.exit(1)

    cfg = Config.load()

    if args.app_action == "run":
        _cmd_run(cfg, args)
    elif args.app_action == "list":
        _cmd_list(cfg)
    elif args.app_action == "refresh":
        _cmd_refresh(cfg)


def handle_run(args: argparse.Namespace) -> None:
    """mimir-win run <exe> - 手动运行任意 Windows 可执行文件。"""
    cfg = Config.load()
    _ensure_ready(cfg)

    exe = args.executable
    print(f"运行 {exe}...")
    proc = rdp.launch(cfg, app_exe=exe, app_name=Path(exe).stem, file_path=args.file)
    if proc:
        proc.wait()


def _cmd_run(cfg: Config, args: argparse.Namespace) -> None:
    app_id = args.app_id
    file_path = getattr(args, "file", None)

    # 特殊：全屏桌面
    if app_id in ("__windows__", "desktop", "windows"):
        _ensure_ready(cfg)
        print("启动 Windows 桌面...")
        proc = rdp.launch(cfg)
        if proc:
            proc.wait()
        return

    # 查找应用
    app = _find_app(cfg, app_id)
    if app:
        exe = app["path"]
        name = app.get("name", app_id)
    else:
        # 当作原始路径处理
        exe = app_id
        name = Path(app_id).stem

    _ensure_ready(cfg)
    print(f"启动 {name}...")
    proc = rdp.launch(cfg, app_exe=exe, app_name=name, file_path=file_path)
    if proc:
        proc.wait()


def _cmd_list(cfg: Config) -> None:
    """列出已安装的 Windows 应用。"""
    apps = _load_apps(cfg)
    if not apps:
        print("暂无应用缓存。运行 'mimir-win app refresh' 从 Windows 刷新。")
        return

    print(f"{'ID':<24} {'名称':<30} {'来源':<12}")
    print("─" * 66)
    for app in apps:
        app_id = _make_id(app.get("name", "unknown"))
        print(f"{app_id:<24} {app.get('name', '?'):<30} {app.get('source', '?'):<12}")

    print(f"\n共 {len(apps)} 个应用")


def _cmd_refresh(cfg: Config) -> None:
    """从 Windows 刷新应用列表并生成桌面快捷方式。"""
    _ensure_ready(cfg)

    # 确保 agent 可用
    from mimir_win.core.provisioner import ensure_agent
    if not ensure_agent(cfg):
        print("Guest Agent 不可用。")
        print("可能原因：")
        print("  1. VM 刚启动，Windows 还在安装（首次启动需要 10-30 分钟）")
        print("  2. Guest Agent 未正确安装")
        print("  3. 防火墙阻止了连接")
        print()
        print("提示：可通过 VNC 查看安装进度")
        print(f"      http://127.0.0.1:{cfg.rdp.port + 1}")
        print()
        print("或手动安装：通过 VNC 运行 C:\\OEM\\install.bat")
        sys.exit(1)

    print("正在查询 Guest Agent...")
    from mimir_win.guest.client import GuestClient
    client = GuestClient(port=cfg.rdp.port + 2)

    if not client.health():
        print("Guest Agent 不可用。")
        print("可能原因：")
        print("  1. VM 刚启动，Windows 还在安装（首次启动需要 10-30 分钟）")
        print("  2. Guest Agent 未正确安装")
        print("  3. 防火墙阻止了连接")
        print()
        print("提示：可通过 VNC 查看安装进度")
        print(f"      http://127.0.0.1:{cfg.rdp.port + 1}")
        sys.exit(1)

    guest_apps = client.get_apps()
    apps = [
        {"name": a.name, "path": a.path, "source": a.source, "icon": a.icon_b64}
        for a in guest_apps
    ]

    # 缓存
    cache = _apps_cache_path(cfg)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(apps, indent=2, ensure_ascii=False))
    print(f"已缓存 {len(apps)} 个应用")

    # 生成桌面快捷方式
    _create_desktop_entries(cfg, apps)
    print("桌面快捷方式已更新")


def _cmd_run_manual(cfg: Config, exe: str, file_path: str | None = None) -> None:
    """手动运行任意 Windows 可执行文件。"""
    _ensure_ready(cfg)
    name = Path(exe).stem
    print(f"运行 {exe}...")
    proc = rdp.launch(cfg, app_exe=exe, app_name=name, file_path=file_path)
    if proc:
        proc.wait()


def _ensure_ready(cfg: Config) -> None:
    """确保 VM 运行且 FreeRDP 可用。"""
    from mimir_win.core.rdp import find_freerdp
    freerdp = find_freerdp()
    if not freerdp:
        print("错误: 未找到 FreeRDP 3+", file=sys.stderr)
        print()
        print("安装方法：")
        print("  NixOS:    确保 freerdp 在 environment.systemPackages 中")
        print("  Ubuntu:   sudo apt install freerdp3-x11")
        print("  Fedora:   sudo dnf install freerdp")
        print("  Arch:     sudo pacman -S freerdp")
        sys.exit(1)

    if not ensure_awake(cfg):
        print("错误: VM 未就绪", file=sys.stderr)
        print()
        print("尝试运行: mimir-win vm start")
        sys.exit(1)


def _load_apps(cfg: Config) -> list[dict]:
    """加载缓存的应用列表。"""
    cache = _apps_cache_path(cfg)
    if not cache.exists():
        return []
    try:
        return json.loads(cache.read_text())
    except json.JSONDecodeError:
        return []


def _find_app(cfg: Config, app_id: str) -> dict | None:
    """按 ID 查找应用。"""
    for app in _load_apps(cfg):
        if _make_id(app.get("name", "")) == app_id:
            return app
    return None


def _make_id(name: str) -> str:
    """应用名 → 文件系统安全 ID。"""
    return name.lower().replace(" ", "-").replace(".", "-").replace("(", "").replace(")", "")


def _apps_cache_path(cfg: Config) -> Path:
    return data_dir() / "apps.json"


def _create_desktop_entries(cfg: Config, apps: list[dict]) -> None:
    """为所有应用生成 .desktop 文件。"""
    from mimir_win.desktop.entry import create_app_entry, create_windows_entry, create_menu_directory

    mimir_win_bin = "mimir-win"

    # 创建菜单分类目录
    create_menu_directory()

    # Windows 桌面快捷方式
    create_windows_entry(mimir_win_bin)

    # 过滤系统组件（不是用户应用）
    _SKIP_PATTERNS = [
        # UWP 系统框架
        "microsoft.windows", "microsoft.aad", "microsoft.accounts",
        "microsoft.async", "microsoft.bio", "microsoft.cred",
        "microsoft.ecapp", "microsoft.lock", "microsoft.win32",
        "microsoft.xbox", "microsoft.zune",
        "microsoft.sechealth", "microsoft.todos", "microsoft.raw",
        "microsoft.vp9", "microsoft.web", "microsoft.power",
        "microsoft.screen", "microsoft.yourphone",
        "microsoft.phone", "microsoft.widgets", "microsoft.cbs",
        "microsoft.client", "microsoft.oobe", "microsoft.photon",
        "microsoft.undocked", "microsoft.crossdevice",
        "microsoft.quickassist", "microsoft.xboxspeech",
        "microsoft.xboxgaming", "microsoft.xboxtcui",
        "microsoft.windowspackagemanager",
        "microsoft.outlookinstaller",
        "microsoftterminal",
        # 系统工具（非用户应用）
        "diagnostics utility", "licensemanager",
        "touch keyboard", "windows contacts",
        "gethelp", "skype", "winget", "store",
        "WindowsPackageManagerServer",
        "microsoft.gethelp", "microsoft.skype",
        "microsoft.desktopappinstaller",
    ]

    # UUID 正则
    _UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)

    # 每个应用
    for app in apps:
        name = app.get("name", "")
        if not name:
            continue
        app_id = _make_id(name)

        # 跳过 UUID 应用
        if _UUID_RE.match(app_id):
            continue

        # 跳过系统应用
        name_lower = name.lower()
        if any(pat in name_lower for pat in _SKIP_PATTERNS):
            continue

        icon_path = None

        # 保存图标
        icon_b64 = app.get("icon", "")
        if icon_b64:
            from mimir_win.desktop.icons import save_icon
            try:
                icon_path = str(save_icon(app_id, icon_b64))
            except Exception:
                pass

        create_app_entry(
            app_id=app_id,
            name=name,
            exe=app.get("path", ""),
            icon_path=icon_path,
            mimir_win_bin=mimir_win_bin,
        )
import re
