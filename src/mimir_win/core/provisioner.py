"""首次启动自动化 - 自动安装 Guest Agent。"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from pathlib import Path

from mimir_win.core.config import Config, data_dir

log = logging.getLogger(__name__)


def get_oem_dir() -> Path:
    """获取 OEM 目录（bind-mount 到容器）。"""
    return data_dir() / "oem"


def prepare_oem_assets() -> Path:
    """准备 OEM 目录。"""
    oem = get_oem_dir()
    oem.mkdir(parents=True, exist_ok=True)

    guest_src = Path.cwd() / "guest"
    if not guest_src.exists():
        guest_src = data_dir() / "guest"

    if guest_src.exists():
        for f in guest_src.iterdir():
            dst = oem / f.name
            if f.is_file():
                shutil.copy2(f, dst)
            elif f.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(f, dst)

    return oem


def is_first_boot(cfg: Config) -> bool:
    """检查是否首次启动。"""
    marker = Path(cfg.vm.data_dir) / ".provisioned"
    return not marker.exists()


def mark_provisioned(cfg: Config) -> None:
    """标记已配置完成。"""
    marker = Path(cfg.vm.data_dir) / ".provisioned"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(f"provisioned at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")


def auto_install_agent(cfg: Config) -> bool:
    """自动启动 Guest Agent（通过 RDP 执行 PowerShell 脚本）。

    流程：
    1. 等待 VM 就绪
    2. 通过 FreeRDP RemoteApp 执行 agent.ps1
    3. 等待 Agent 端口可用
    """
    from mimir_win.core.rdp import find_freerdp
    from mimir_win.core import vm

    if not vm.is_port_open(cfg):
        log.info("VM 未就绪，跳过 agent 安装")
        return False

    # 检查 agent 是否已在运行
    if _check_agent_port(cfg):
        log.info("Agent 已在运行")
        return True

    # 通过 RDP 启动 agent
    freerdp = find_freerdp()
    if not freerdp:
        log.warning("FreeRDP 不可用，无法自动安装 agent")
        return False

    log.info("自动启动 Guest Agent...")

    # 构建命令 - 通过 RemoteApp 执行 PowerShell 启动 agent
    if freerdp.kind == "flatpak":
        cmd = ["flatpak", "run", "--command=xfreerdp", "com.freerdp.FreeRDP"]
    else:
        cmd = [freerdp.path]

    password = cfg.resolve_password()
    cmd += [
        f"/v:{cfg.rdp.ip}:{cfg.rdp.port}",
        f"/u:{cfg.rdp.user}",
        "/cert:tofu",
        "/sec:tls",
        # 通过 PowerShell 执行 install.bat
        '/app:program:powershell.exe,args:-ExecutionPolicy Bypass -File C:\\OEM\\agent.ps1,name:agent',
    ]

    log.info("执行: flatpak run ... /app:program:powershell.exe ...")

    try:
        # 启动 agent（密码通过环境变量传递）
        import os
        env = os.environ.copy()
        if password:
            env["FREERDP_PASSWORD"] = password
            cmd.append(f"/p:{password}")

        # 启动进程
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )

        # 等待 agent 启动
        log.info("等待 Agent 启动...")
        for _ in range(30):
            if _check_agent_port(cfg):
                log.info("Agent 启动成功")
                mark_provisioned(cfg)
                return True
            time.sleep(2)

        log.warning("Agent 启动超时")
        # 清理进程
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        return False

    except Exception as e:
        log.warning("Agent 启动失败: %s", e)
        return False


def _check_agent_port(cfg: Config) -> bool:
    """检查 agent 是否正常响应。"""
    from mimir_win.guest.client import GuestClient
    client = GuestClient(port=cfg.rdp.port + 2)
    return client.health()


def ensure_agent(cfg: Config) -> bool:
    """确保 agent 可用。如果不可用，尝试自动安装。"""
    if _check_agent_port(cfg):
        return True

    return auto_install_agent(cfg)
