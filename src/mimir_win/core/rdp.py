"""FreeRDP client wrapper (X11/Wayland auto-detection, RemoteApp mode)."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from mimir_win.core.config import Config
from mimir_win.core.display import detect_session_type, snap_scale

log = logging.getLogger(__name__)

# Safe FreeRDP flags that users can pass through
_BARE_FLAGS: frozenset[str] = frozenset({
    "+fonts", "-fonts", "+aero", "-aero", "+wallpaper", "-wallpaper",
    "+grab-keyboard", "-grab-keyboard", "+gfx", "-gfx",
    "+auto-reconnect", "-auto-reconnect",
    "+home-drive", "-home-drive",
    "+clipboard", "-clipboard",
    "+multimon", "-multimon",
    "+span", "-span",
    "+decorations", "-decorations",
})
_SIMPLE_VALUE_FLAGS: dict[str, re.Pattern[str]] = {
    "/scale": re.compile(r"[1-9][0-9]{0,3}$"),
    "/sound": re.compile(r"[a-zA-Z0-9_:-]{1,64}$"),
    "/microphone": re.compile(r"[a-zA-Z0-9_:-]{1,64}$"),
    "/sec": re.compile(r"[a-zA-Z]{1,16}$"),
    "/kbd": re.compile(r"[a-zA-Z0-9_:-]{1,32}$"),
    "/network": re.compile(r"[a-zA-Z]{1,16}$"),
}


@dataclass
class FreeRDPInfo:
    path: str
    kind: str  # "xfreerdp" | "sdl-freerdp" | "flatpak"
    version_major: int


def find_freerdp() -> FreeRDPInfo | None:
    """Locate the best available FreeRDP 3+ client."""
    # Prefer Flatpak xfreerdp (more reliable on NixOS)
    if shutil.which("flatpak"):
        try:
            out = subprocess.check_output(
                ["flatpak", "run", "--command=xfreerdp", "com.freerdp.FreeRDP", "--version"],
                text=True, stderr=subprocess.DEVNULL,
            )
            major = _parse_major_version(out)
            if major >= 3:
                return FreeRDPInfo(
                    path="flatpak",
                    kind="flatpak",
                    version_major=major,
                )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    # Fallback to native xfreerdp
    for cmd in ("xfreerdp3", "xfreerdp"):
        info = _probe(cmd, "xfreerdp")
        if info:
            return info

    return None


def find_sdl_freerdp() -> FreeRDPInfo | None:
    """Locate sdl-freerdp3 (for future native Wayland RAIL)."""
    for cmd in ("sdl-freerdp3", "sdl3-freerdp", "sdl-freerdp"):
        info = _probe(cmd, "sdl-freerdp")
        if info:
            return info
    return None


def _probe(cmd: str, kind: str) -> FreeRDPInfo | None:
    """Probe a FreeRDP binary for version 3+."""
    path = shutil.which(cmd)
    if not path:
        return None
    try:
        out = subprocess.check_output(
            [path, "--version"], text=True, stderr=subprocess.STDOUT
        )
        major = _parse_major_version(out)
        if major >= 3:
            return FreeRDPInfo(path=path, kind=kind, version_major=major)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None


def _parse_major_version(output: str) -> int:
    """Extract major version from FreeRDP --version output."""
    match = re.search(r"version\s+(\d+)\.", output, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 0


# --- Command building ---

def build_rdp_command(
    cfg: Config,
    app_exe: str | None = None,
    app_name: str | None = None,
    file_path: str | None = None,
) -> list[str]:
    """Build the FreeRDP command line.

    If app_exe is set, uses RemoteApp mode for seamless window.
    Otherwise, opens a full desktop session.
    """
    freerdp = find_freerdp()
    if not freerdp:
        raise RuntimeError("FreeRDP 3+ not found. Install freerdp3 or xfreerdp.")

    cmd: list[str] = []
    password = cfg.resolve_password()

    # Build base command
    if freerdp.kind == "flatpak":
        cmd = ["flatpak", "run", "--command=xfreerdp", "com.freerdp.FreeRDP"]
    else:
        cmd = [freerdp.path]

    # Connection args（密码通过环境变量传递，不在命令行暴露）
    cmd += [
        f"/v:{cfg.rdp.ip}:{cfg.rdp.port}",
        f"/u:{cfg.rdp.user}",
    ]
    if cfg.rdp.domain:
        cmd.append(f"/d:{cfg.rdp.domain}")

    # Common flags
    cmd += [
        "/cert:tofu",
        "+clipboard",
        "/sound:sys:pulse",
        "/microphone:sys:pulse",
        "+home-drive",
        "/compression",
        "/sec:tls",
    ]

    # Scale
    scale = snap_scale(getattr(cfg.display, 'scale', 1.0))
    cmd.append(f"/scale:{scale}")

    if app_exe:
        # RemoteApp mode - seamless individual window
        name = app_name or Path(app_exe).stem
        app_arg = f'/app:program:{app_exe},name:{name}'
        if file_path:
            unc = _linux_to_unc(file_path)
            app_arg += f',cmd:{unc}'
        cmd.append(app_arg)

        # Extra user flags
        if cfg.rdp.extra_flags:
            cmd.extend(_parse_extra_flags(cfg.rdp.extra_flags))
    else:
        # Full desktop session
        cmd += [
            "+auto-reconnect",
            "+dynamic-resolution",
            "/t:Windows Desktop [Mimir-Win]",
        ]
        if cfg.rdp.extra_flags:
            cmd.extend(_parse_extra_flags(cfg.rdp.extra_flags))

    return cmd


def _linux_to_unc(path: str) -> str:
    """Convert Linux path to Windows UNC path via tsclient."""
    home = str(Path.home())
    unc = path.replace(home, "\\\\tsclient\\home")
    unc = unc.replace("/", "\\")
    return unc


def _parse_extra_flags(flags_str: str) -> list[str]:
    """Parse and validate user-provided extra flags."""
    result: list[str] = []
    for flag in flags_str.split():
        flag = flag.strip()
        if not flag:
            continue
        if flag in _BARE_FLAGS:
            result.append(flag)
            continue
        for prefix, pattern in _SIMPLE_VALUE_FLAGS.items():
            if flag.startswith(prefix + ":") or flag.startswith(prefix + "="):
                value = flag.split(":", 1)[-1] if ":" in flag else flag.split("=", 1)[-1]
                if pattern.match(value):
                    result.append(flag)
                    break
            else:
                continue
        else:
            log.warning("Ignoring unsafe FreeRDP flag: %s", flag)
    return result


# --- Session management ---

def launch(
    cfg: Config,
    app_exe: str | None = None,
    app_name: str | None = None,
    file_path: str | None = None,
) -> subprocess.Popen[bytes] | None:
    """Launch a FreeRDP session. Returns the process handle."""
    cmd = build_rdp_command(cfg, app_exe=app_exe, app_name=app_name, file_path=file_path)
    log.info("Launching FreeRDP: %s", _sanitize_cmd(cmd))

    # 通过 stdin 传递密码，避免命令行暴露和注入
    password = cfg.resolve_password()
    if password:
        # 使用 /from-stdin 或环境变量
        import os
        env = os.environ.copy()
        # 创建临时密码文件，权限 600
        import tempfile
        fd, tmp_path = tempfile.mkstemp(suffix=".pwd", dir="/dev/shm")
        try:
            os.write(fd, password.encode())
            os.close(fd)
            os.chmod(tmp_path, 0o600)
            env["FREERDP_PASSWORD_FILE"] = tmp_path
            # 添加 /p: 从文件读取
            cmd_with_pass = cmd + [f"/p:file:{tmp_path}"]
        except Exception:
            os.close(fd)
            cmd_with_pass = cmd + [f"/p:{password}"]
    else:
        cmd_with_pass = cmd
        env = None

    proc = subprocess.Popen(cmd_with_pass, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)

    # 清理临时文件
    if password and 'tmp_path' in dir():
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return proc


def _sanitize_cmd(cmd: list[str]) -> list[str]:
    """Hide password from log output."""
    result = []
    for arg in cmd:
        if arg.startswith("/p:"):
            result.append("/p:****")
        else:
            result.append(arg)
    return result
