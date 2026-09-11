"""VM lifecycle management - 开箱即用。

整个启动流程：
  mimir_win vm start
    → 1. 检测配置是否存在，不存在则自动生成
    → 2. 检测 compose.yaml 是否存在，不存在则自动生成
    → 3. 检测 OEM 资产是否就绪，未就绪则自动准备
    → 4. 启动容器（docker/podman compose up -d）
    → 5. 等待 RDP 端口就绪
    → 6. 首次启动：等待 Windows 安装完成 + Guest Agent 就绪
"""

from __future__ import annotations

import json
import logging
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from mimir_win.core.config import Config, config_dir, data_dir

log = logging.getLogger(__name__)


class VMState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    UNKNOWN = "unknown"


# ============================================================
# Compose 模板 - 完整配置，开箱即用
# ============================================================

COMPOSE_TEMPLATE = '''\
name: "mimir-win"
services:
  windows:
    image: {image}
    container_name: {container_name}
    environment:
      VERSION: "{win_version}"
      RAM_SIZE: "{memory}"
      CPU_CORES: "{cpus}"
      DISK_SIZE: "{disk_size}"
      USERNAME: "{rdp_user}"
      PASSWORD: "${{PASSWORD}}"
      {proxy_env}
    devices:
      - /dev/kvm
      - /dev/net/tun
    cap_add:
      - NET_ADMIN
      - SYS_ADMIN
    security_opt:
      - seccomp:unconfined
    ports:
      - "127.0.0.1:{rdp_port}:3389/tcp"
      - "127.0.0.1:{rdp_port}:3389/udp"
      - "127.0.0.1:{vnc_port}:8006"
      - "127.0.0.1:{agent_port}:8765/tcp"
    volumes:
      - {data_dir}:/storage
      - {home_share}:/shared
      - {oem_dir}:/oem
'''


def generate_compose(cfg: Config) -> str:
    """生成 compose.yaml 内容。密码通过环境变量传递，不写入文件。"""
    import os

    # 检测代理设置
    proxy_lines = []
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"):
        val = os.environ.get(key, "")
        if val:
            # 将 127.0.0.1 替换为宿主机 IP
            if "127.0.0.1" in val:
                import subprocess
                try:
                    out = subprocess.check_output(["ip", "route", "get", "1"], text=True, stderr=subprocess.DEVNULL)
                    parts = out.split()
                    for i, part in enumerate(parts):
                        if part == "via" and i + 1 < len(parts):
                            val = val.replace("127.0.0.1", parts[i + 1])
                            break
                except Exception:
                    val = val.replace("127.0.0.1", "host.containers.internal")
            proxy_lines.append(f'{key}: "{val}"')
    proxy_env = "\n      ".join(proxy_lines) if proxy_lines else ""

    return COMPOSE_TEMPLATE.format(
        image=cfg.vm.image,
        container_name=cfg.vm.container_name,
        win_version=cfg.vm.win_version,
        memory=cfg.vm.memory,
        cpus=cfg.vm.cpus,
        disk_size=cfg.vm.disk_size,
        rdp_user=cfg.rdp.user,
        rdp_port=cfg.rdp.port,
        vnc_port=cfg.rdp.port + 1,
        agent_port=cfg.rdp.port + 2,
        data_dir=cfg.vm.data_dir,
        home_share=cfg.vm.home_share or str(Path.home()),
        oem_dir=str(_ensure_oem_assets()),
        proxy_env=proxy_env,
    )


def write_compose(cfg: Config) -> Path:
    """写入 compose.yaml 到数据目录。"""
    compose_path = Path(cfg.vm.data_dir) / "compose.yaml"
    compose_path.parent.mkdir(parents=True, exist_ok=True)
    compose_path.write_text(generate_compose(cfg))
    log.info("写入 compose: %s", compose_path)
    return compose_path


# ============================================================
# 容器后端抽象
# ============================================================

def _compose_cmd(cfg: Config) -> list[str]:
    if cfg.vm.backend == "podman":
        return ["podman-compose"]
    return ["docker", "compose"]


def _ensure_oem_assets() -> Path:
    """确保 OEM 资产目录就绪（Guest Agent + install.bat + 注册表）。"""
    oem = data_dir() / "oem"
    oem.mkdir(parents=True, exist_ok=True)

    if (oem / "install.bat").exists():
        return oem

    candidates = [
        Path.cwd() / "guest",
        Path(__file__).parent.parent.parent.parent / "guest",
        Path.home() / ".local" / "share" / "mimir-win" / "guest",
        Path("/usr/local/share/mimir-win/guest"),
        Path("/run/current-system/sw/share/mimir-win/guest"),
    ]

    for src in candidates:
        if src.exists() and (src / "install.bat").exists():
            log.info("复制 OEM 资产: %s → %s", src, oem)
            for f in src.iterdir():
                dst = oem / f.name
                if f.is_file():
                    shutil.copy2(f, dst)
                elif f.is_dir():
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(f, dst)
            return oem

    log.warning("未找到 OEM 资产目录，首次启动可能需要手动配置 Windows")
    return oem


def _container_cmd(cfg: Config) -> list[str]:
    if cfg.vm.backend == "podman":
        return ["podman"]
    return ["docker"]


# ============================================================
# 生命周期
# ============================================================

def start(cfg: Config) -> None:
    """启动 Windows VM。密码通过环境变量传递，不落盘。"""
    compose_path = write_compose(cfg)
    cmd = _compose_cmd(cfg) + ["--file", str(compose_path), "up", "-d"]
    log.info("启动 VM: %s", " ".join(cmd))

    # 通过环境变量传递密码，不写入 compose.yaml
    import os
    env = os.environ.copy()
    env["PASSWORD"] = cfg.resolve_password()

    subprocess.run(cmd, check=True, cwd=str(compose_path.parent), env=env, timeout=600)


def stop(cfg: Config) -> None:
    """停止 Windows VM。"""
    compose_path = Path(cfg.vm.data_dir) / "compose.yaml"
    if not compose_path.exists():
        log.info("compose.yaml 不存在，跳过")
        return
    cmd = _compose_cmd(cfg) + ["--file", str(compose_path), "stop"]
    log.info("停止 VM: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(compose_path.parent))


def pause(cfg: Config) -> None:
    """暂停容器（释放 CPU，保留内存）。"""
    cmd = _container_cmd(cfg) + ["pause", cfg.vm.container_name]
    subprocess.run(cmd, check=True)


def unpause(cfg: Config) -> None:
    """恢复暂停的容器。"""
    cmd = _container_cmd(cfg) + ["unpause", cfg.vm.container_name]
    subprocess.run(cmd, check=True)


def remove(cfg: Config) -> None:
    """删除容器和 compose 项目。"""
    compose_path = Path(cfg.vm.data_dir) / "compose.yaml"
    if compose_path.exists():
        cmd = _compose_cmd(cfg) + ["--file", str(compose_path), "down"]
        subprocess.run(cmd, check=False, cwd=str(compose_path.parent))


# ============================================================
# 状态查询
# ============================================================

def get_state(cfg: Config) -> VMState:
    """查询容器当前状态。"""
    try:
        cmd = _container_cmd(cfg) + [
            "inspect", "--format", "{{.State.Status}}", cfg.vm.container_name
        ]
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
        mapping = {
            "running": VMState.RUNNING,
            "paused": VMState.PAUSED,
            "exited": VMState.STOPPED,
            "created": VMState.STOPPED,
            "restarting": VMState.STARTING,
            "dead": VMState.STOPPED,
        }
        return mapping.get(out, VMState.UNKNOWN)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return VMState.UNKNOWN


def is_port_open(cfg: Config, timeout: float = 2.0) -> bool:
    """检查 RDP 端口是否可达。"""
    try:
        with socket.create_connection((cfg.rdp.ip, cfg.rdp.port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


def wait_for_ready(cfg: Config, timeout: int = 120) -> bool:
    """等待 RDP 端口就绪。"""
    log.info("等待 RDP 端口 %s:%s ...", cfg.rdp.ip, cfg.rdp.port)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_port_open(cfg):
            log.info("RDP 端口已就绪")
            return True
        time.sleep(2)
    log.warning("等待 RDP 端口超时 (%ss)", timeout)
    return False


def ensure_running(cfg: Config) -> bool:
    """确保 VM 运行且 RDP 端口就绪。全自动：检测状态 → 启动/恢复 → 等待。"""
    state = get_state(cfg)

    if state == VMState.RUNNING:
        if is_port_open(cfg):
            return True
        return wait_for_ready(cfg)

    if state == VMState.PAUSED:
        log.info("VM 已暂停，正在恢复...")
        unpause(cfg)
        return wait_for_ready(cfg)

    if state in (VMState.STOPPED, VMState.UNKNOWN):
        log.info("VM 未运行，正在启动...")
        start(cfg)
        return wait_for_ready(cfg, timeout=180)

    if state == VMState.STARTING:
        return wait_for_ready(cfg)

    return False
