"""VM management CLI commands - 开箱即用。

一条命令完成所有事情：
  mimir-win vm start
    → 检测配置 → 生成 compose → 准备 OEM → 启动容器 → 等待就绪
"""

from __future__ import annotations

import argparse
import sys
import time

from mimir_win.core.config import Config, config_dir
from mimir_win.core import vm


def handle_vm(args: argparse.Namespace) -> None:
    cfg = Config.load()

    if not hasattr(args, "vm_action") or args.vm_action is None:
        print("用法: mimir-win vm {start|stop|status|pause|resume}")
        sys.exit(1)

    action = args.vm_action

    if action == "start":
        _cmd_start(cfg)
    elif action == "stop":
        _cmd_stop(cfg)
    elif action == "status":
        _cmd_status(cfg)
    elif action == "pause":
        _cmd_pause(cfg)
    elif action == "resume":
        _cmd_resume(cfg)


def _cmd_start(cfg: Config) -> None:
    state = vm.get_state(cfg)

    if state == vm.VMState.RUNNING and vm.is_port_open(cfg):
        print("VM 已在运行，RDP 端口就绪")
        _print_summary(cfg)
        return

    if state == vm.VMState.PAUSED:
        print("正在恢复暂停的 VM...")
        vm.unpause(cfg)
    else:
        print("正在启动 VM...")
        print(f"  后端:     {cfg.vm.backend}")
        print(f"  CPU:      {cfg.vm.cpus} 核")
        print(f"  内存:     {cfg.vm.memory}")
        print(f"  磁盘:     {cfg.vm.disk_size}")
        print(f"  RDP 端口: {cfg.rdp.port}")
        print()
        vm.start(cfg)

    print("等待 RDP 端口就绪...", end="", flush=True)
    if vm.wait_for_ready(cfg, timeout=180):
        print(" 就绪!")
        _print_summary(cfg)
    else:
        print(" 超时!")
        print("提示: 首次启动需要安装 Windows，可能需要 10-30 分钟", file=sys.stderr)
        print("      可以通过 VNC 查看安装进度: http://127.0.0.1:{}".format(cfg.rdp.port + 1))
        sys.exit(1)


def _cmd_stop(cfg: Config) -> None:
    state = vm.get_state(cfg)
    if state == vm.VMState.STOPPED:
        print("VM 已停止")
        return
    print("正在停止 VM...")
    vm.stop(cfg)
    print("VM 已停止")


def _cmd_status(cfg: Config) -> None:
    state = vm.get_state(cfg)
    port_open = vm.is_port_open(cfg) if state == vm.VMState.RUNNING else False

    print(f"后端:     {cfg.vm.backend}")
    print(f"容器:     {cfg.vm.container_name}")
    print(f"状态:     {state.value}")
    print(f"RDP 端口: {cfg.rdp.ip}:{cfg.rdp.port} ({'就绪' if port_open else '未就绪'})")

    if state == vm.VMState.RUNNING and port_open:
        print(f"VNC:      http://127.0.0.1:{cfg.rdp.port + 1}")
        print(f"Agent:    http://127.0.0.1:{cfg.rdp.port + 2}")


def _cmd_pause(cfg: Config) -> None:
    state = vm.get_state(cfg)
    if state == vm.VMState.PAUSED:
        print("VM 已暂停")
        return
    if state != vm.VMState.RUNNING:
        print(f"无法暂停状态为 {state.value} 的 VM")
        sys.exit(1)
    print("正在暂停 VM...")
    vm.pause(cfg)
    print("VM 已暂停（CPU 已释放，内存保留）")


def _cmd_resume(cfg: Config) -> None:
    state = vm.get_state(cfg)
    if state != vm.VMState.PAUSED:
        print(f"VM 未暂停（当前状态: {state.value}）")
        return
    print("正在恢复 VM...")
    vm.unpause(cfg)
    if vm.wait_for_ready(cfg):
        print("VM 已恢复")
        _print_summary(cfg)
    else:
        print("WARNING: VM 已恢复但 RDP 端口未就绪", file=sys.stderr)


def _print_summary(cfg: Config) -> None:
    print()
    print("─" * 40)
    print(f"  RDP:    {cfg.rdp.ip}:{cfg.rdp.port}")
    print(f"  VNC:    http://127.0.0.1:{cfg.rdp.port + 1}")
    print(f"  Agent:  http://127.0.0.1:{cfg.rdp.port + 2}")
    print(f"  用户:   {cfg.rdp.user}")
    print("─" * 40)
    print()
    print("下一步:")
    print("  mimir-win app refresh   刷新应用列表")
    print("  mimir-win app list      查看可用应用")
    print("  mimir-win app run <id>  启动 Windows 应用")
