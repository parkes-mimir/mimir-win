"""Idle monitor with auto-suspend/resume."""

from __future__ import annotations

import logging
import signal
import subprocess
import threading

from mimir_win.core import vm
from mimir_win.core.config import Config

log = logging.getLogger(__name__)

# 优雅退出标志
_stop_event = threading.Event()


def _signal_handler(signum, frame):
    """处理退出信号。"""
    log.info("收到信号 %s，正在停止...", signum)
    _stop_event.set()


def monitor_idle(cfg: Config) -> None:
    """Monitor for idle timeout and pause the VM.

    支持优雅退出：收到 SIGINT/SIGTERM 时停止循环。
    """
    if cfg.vm.idle_timeout <= 0:
        log.info("Idle monitoring disabled")
        return

    # 注册信号处理（仅在主线程中）
    try:
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
    except ValueError:
        log.warning("无法注册信号处理（非主线程）")

    log.info("Idle monitor started (timeout=%ds, action=%s)",
             cfg.vm.idle_timeout, cfg.vm.idle_action)

    while not _stop_event.is_set():
        # 等待 30 秒，但支持提前退出
        if _stop_event.wait(30):
            break

        state = vm.get_state(cfg)
        if state != vm.VMState.RUNNING:
            continue

        # Check for active RDP sessions
        if _has_active_sessions(cfg):
            continue

        # No active sessions - check if timeout elapsed
        log.info("No active RDP sessions, pausing in %ds...", cfg.vm.idle_timeout)
        if _stop_event.wait(cfg.vm.idle_timeout):
            break

        # Re-check after timeout
        if _has_active_sessions(cfg):
            continue

        # 重新检查 VM 状态，避免对已停止的 VM 执行暂停
        state = vm.get_state(cfg)
        if state != vm.VMState.RUNNING:
            continue

        _do_suspend(cfg)

    log.info("Idle monitor stopped")


def _has_active_sessions(cfg: Config) -> bool:
    """Check if there are active RDP sessions."""
    if not vm.is_port_open(cfg, timeout=1):
        return False
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", "xfreerdp|sdl-freerdp"],
            text=True, stderr=subprocess.DEVNULL,
        )
        return bool(out.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _do_suspend(cfg: Config) -> None:
    """Suspend the VM based on configured idle action."""
    if cfg.vm.idle_action == "stop":
        log.info("Idle timeout reached, stopping VM")
        vm.stop(cfg)
    else:
        log.info("Idle timeout reached, pausing VM")
        vm.pause(cfg)


def ensure_awake(cfg: Config) -> bool:
    """Ensure the VM is awake (unpause if paused, start if stopped)."""
    state = vm.get_state(cfg)

    if state == vm.VMState.PAUSED:
        log.info("VM is paused, resuming...")
        vm.unpause(cfg)
        return vm.wait_for_ready(cfg)

    if state == vm.VMState.STOPPED:
        log.info("VM is stopped, starting...")
        vm.start(cfg)
        return vm.wait_for_ready(cfg, timeout=180)

    return state == vm.VMState.RUNNING
