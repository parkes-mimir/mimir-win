"""CLI 入口 - 对标 WinApps 的完整命令集。

用法：
  mimir-win setup              交互式安装向导
  mimir-win doctor             检查系统依赖
  mimir-win vm start           启动 Windows VM
  mimir-win vm stop            停止 VM
  mimir-win vm status          查看 VM 状态
  mimir-win vm pause           暂停 VM
  mimir-win vm resume          恢复 VM
  mimir-win app run <id>       无缝启动 Windows 应用
  mimir-win app list           列出可用应用
  mimir-win app refresh        从 Windows 刷新应用列表
  mimir-win run <exe>          手动运行任意 Windows 可执行文件
  mimir-win config show        查看配置
  mimir-win config set key val 设置配置项
  mimir-win windows            启动完整 Windows 桌面
"""

from __future__ import annotations

import argparse
import logging
import sys

from mimir_win import __version__


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="mimir_win",
        description="Mimir-Win - 在 Linux 桌面上无缝运行 Windows 应用",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  mimir-win setup                    # 首次安装向导
  mimir-win vm start                 # 启动 Windows VM
  mimir-win app run word             # 启动 Word
  mimir-win app run word file.docx   # 用 Word 打开文件
  mimir-win run "C:\\\\app\\\\my.exe"    # 运行任意 exe
  mimir-win windows                  # 完整 Windows 桌面
""",
    )
    parser.add_argument("--version", action="version", version=f"mimir-win {__version__}")
    parser.add_argument("--debug", action="store_true", help="启用调试日志")

    sub = parser.add_subparsers(dest="command")

    # setup
    p_setup = sub.add_parser("setup", help="交互式安装向导")
    p_setup.add_argument("--non-interactive", action="store_true",
                         help="非交互模式（使用默认值）")

    # doctor
    sub.add_parser("doctor", help="检查系统依赖和配置")

    # windows - 快捷方式，等同于 app run desktop
    sub.add_parser("windows", help="启动完整 Windows 桌面")

    # vm
    p_vm = sub.add_parser("vm", help="虚拟机管理")
    vm_sub = p_vm.add_subparsers(dest="vm_action")
    vm_sub.add_parser("start", help="启动 Windows VM")
    vm_sub.add_parser("stop", help="停止 VM")
    vm_sub.add_parser("status", help="查看 VM 状态")
    vm_sub.add_parser("pause", help="暂停 VM（释放 CPU）")
    vm_sub.add_parser("resume", help="恢复暂停的 VM")

    # app
    p_app = sub.add_parser("app", help="应用管理")
    app_sub = p_app.add_subparsers(dest="app_action")
    p_run = app_sub.add_parser("run", help="无缝启动 Windows 应用")
    p_run.add_argument("app_id", help="应用 ID 或可执行文件路径")
    p_run.add_argument("file", nargs="?", help="要打开的文件")
    app_sub.add_parser("list", help="列出可用应用")
    app_sub.add_parser("refresh", help="从 Windows 刷新应用列表")

    # run - 手动运行任意 exe
    p_run = sub.add_parser("run", help="手动运行任意 Windows 可执行文件")
    p_run.add_argument("executable", help="Windows 可执行文件路径")
    p_run.add_argument("file", nargs="?", help="要打开的文件")

    # config
    p_config = sub.add_parser("config", help="查看或修改配置")
    config_sub = p_config.add_subparsers(dest="config_action")
    p_set = config_sub.add_parser("set", help="设置配置项")
    p_set.add_argument("key", help="配置键（如 rdp.user）")
    p_set.add_argument("value", help="配置值")
    config_sub.add_parser("show", help="查看当前配置")
    config_sub.add_parser("path", help="显示配置文件路径")

    args = parser.parse_args(argv)

    # 日志
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s" if not args.debug else "%(name)s: %(message)s",
    )

    # 分发
    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "setup":
        from mimir_win.cli.setup import run_setup
        run_setup(non_interactive=args.non_interactive)

    elif args.command == "doctor":
        from mimir_win.cli.doctor import run_doctor
        run_doctor()

    elif args.command == "windows":
        # 快捷方式：启动完整桌面，关闭后自动刷新应用列表
        from mimir_win.cli.app import _cmd_refresh, _ensure_ready
        from mimir_win.core.config import Config
        cfg = Config.load()
        _ensure_ready(cfg)
        from mimir_win.core import rdp
        print("启动 Windows 桌面...")
        proc = rdp.launch(cfg)
        if proc:
            proc.wait()
            # 桌面关闭后自动刷新应用列表
            print("Windows 桌面已关闭，正在刷新应用列表...")
            try:
                _cmd_refresh(cfg)
            except (OSError, ValueError, RuntimeError) as e:
                print(f"刷新应用列表失败: {e}")

    elif args.command == "vm":
        from mimir_win.cli.vm import handle_vm
        handle_vm(args)

    elif args.command == "app":
        from mimir_win.cli.app import handle_app
        handle_app(args)

    elif args.command == "run":
        from mimir_win.cli.app import handle_run
        handle_run(args)

    elif args.command == "config":
        from mimir_win.cli.config_cmd import handle_config
        handle_config(args)
