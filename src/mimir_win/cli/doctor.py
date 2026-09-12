"""环境诊断 - 检查所有依赖并给出修复建议。

用法: mimir-win doctor
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from mimir_win.core.config import Config, config_dir


def run_doctor() -> None:
    print("Mimir-Win 环境诊断\n")
    print("═" * 55)

    checks = [
        ("KVM 虚拟化", _check_kvm),
        ("容器后端", _check_backend),
        ("FreeRDP 3+", _check_freerdp),
        ("配置文件", _check_config),
        ("显示环境", _check_display),
        ("compose 工具", _check_compose),
    ]

    results = []
    for name, fn in checks:
        ok, status, fix = fn()
        results.append((ok, name, status, fix))

    # 输出
    for ok, name, status, fix in results:
        icon = "✓" if ok else "✗"
        print(f"  {icon} {name:<16} {status}")
        if not ok and fix:
            print(f"    → {fix}")

    print("═" * 55)

    all_ok = all(r[0] for r in results)
    if all_ok:
        print("\n所有检查通过。可以开始使用 Mimir-Win。")
        print("\n快速开始:")
        print("  mimir-win setup      配置向导")
        print("  mimir-win vm start   启动 VM")
    else:
        failed = sum(1 for r in results if not r[0])
        print(f"\n{failed} 项检查未通过，请按上述提示修复。")
        sys.exit(1)


def _check_kvm() -> tuple[bool, str, str]:
    kvm = Path("/dev/kvm")
    if kvm.exists():
        return True, "/dev/kvm 可用", ""
    return False, "/dev/kvm 不可用", "在 BIOS 中启用虚拟化（VT-x/AMD-V）"


def _check_backend() -> tuple[bool, str, str]:
    for backend in ("podman", "docker"):
        cmd = shutil.which(backend)
        if cmd:
            try:
                out = subprocess.check_output(
                    [cmd, "--version"], text=True, stderr=subprocess.DEVNULL
                )
                ver = out.strip().split("\n")[0]
                return True, ver, ""
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
    return (
        False,
        "未找到 podman 或 docker",
        (
            "NixOS: virtualisation.podman.enable = true\n"
            "       或: virtualisation.docker.enable = true"
        ),
    )


def _check_freerdp() -> tuple[bool, str, str]:
    from mimir_win.core.rdp import find_freerdp

    info = find_freerdp()
    if info:
        return True, f"{info.path} (v{info.version_major}+)", ""
    return (
        False,
        "未找到 FreeRDP 3+",
        (
            "NixOS: environment.systemPackages = [ pkgs.freerdp ];\n"
            "       Ubuntu: sudo apt install freerdp3-x11\n"
            "       Fedora: sudo dnf install freerdp\n"
            "       Arch:   sudo pacman -S freerdp"
        ),
    )


def _check_config() -> tuple[bool, str, str]:
    # 检查环境变量（NixOS）
    import os

    env_path = os.environ.get("MIMIR_WIN_CONFIG")
    if env_path:
        p = Path(env_path)
        if p.exists():
            try:
                cfg = Config.load()
                return True, f"{p} (user={cfg.rdp.user})", ""
            except (OSError, ValueError) as e:
                return False, f"配置无效: {e}", "检查配置文件语法"

    # 检查默认路径
    cfg_path = config_dir() / "mimir-win.toml"
    if cfg_path.exists():
        try:
            cfg = Config.load()
            return True, f"{cfg_path} (user={cfg.rdp.user})", ""
        except (OSError, ValueError) as e:
            return False, f"配置无效: {e}", "运行 mimir-win setup 重新配置"

    return (
        False,
        "未找到配置文件",
        (
            "运行 mimir-win setup 创建配置\n"
            '       或在 NixOS 中设置 services."mimir-win".enable = true'
        ),
    )


def _check_display() -> tuple[bool, str, str]:
    from mimir_win.core.display import detect

    d = detect()
    wayland_note = ""
    if d.session_type == "wayland":
        wayland_note = " (通过 XWayland，FreeRDP 3.32+ 将支持原生 Wayland)"
    return True, f"{d.session_type}{wayland_note}, {d.desktop}, {d.monitors} 显示器", ""


def _check_compose() -> tuple[bool, str, str]:
    for cmd in ("podman-compose", "docker-compose", "docker"):
        if shutil.which(cmd):
            if cmd == "docker":
                # docker compose 是子命令
                try:
                    subprocess.check_output(
                        ["docker", "compose", "version"],
                        text=True,
                        stderr=subprocess.DEVNULL,
                    )
                    return True, "docker compose 可用", ""
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue
            else:
                return True, f"{cmd} 可用", ""
    return (
        False,
        "未找到 compose 工具",
        ("NixOS: 确保 virtualisation.podman.enable = true\n       或安装 docker-compose"),
    )
