"""Display environment detection (Wayland/X11, DPI, multi-monitor)."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class DisplayInfo:
    session_type: str  # "x11" | "wayland" | "unknown"
    desktop: str  # "gnome" | "kde" | "sway" | "hyprland" | "unknown"
    scale: float  # DPI scale factor (1.0 = 100%)
    monitors: int  # number of monitors


def detect_session_type() -> str:
    """Detect the current display server type."""
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session in ("x11", "wayland"):
        return session
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "unknown"


def detect_desktop() -> str:
    """Detect the desktop environment."""
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "gnome" in desktop:
        return "gnome"
    if "kde" in desktop:
        return "kde"
    if "sway" in desktop:
        return "sway"
    if "hyprland" in desktop:
        return "hyprland"
    if "cinnamon" in desktop:
        return "cinnamon"
    if "xfce" in desktop:
        return "xfce"
    return "unknown"


def detect_scale() -> float:
    """Detect the current DPI scale factor."""
    de = detect_desktop()

    if de == "gnome":
        return _gnome_scale()
    elif de == "kde":
        return _kde_scale()
    elif de in ("sway", "hyprland"):
        return _wayland_compositor_scale(de)
    elif de == "cinnamon":
        return _cinnamon_scale()

    return _env_scale()


def detect_monitor_count() -> int:
    """Detect the number of connected monitors."""
    xrandr = shutil.which("xrandr")
    if xrandr:
        try:
            out = subprocess.check_output(
                [xrandr, "--query"], text=True, stderr=subprocess.DEVNULL, timeout=5
            )
            return sum(1 for line in out.splitlines() if " connected" in line)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass

    wlr_randr = shutil.which("wlr-randr")
    if wlr_randr:
        try:
            out = subprocess.check_output(
                [wlr_randr], text=True, stderr=subprocess.DEVNULL, timeout=5
            )
            return sum(1 for line in out.splitlines() if line and not line.startswith(" "))
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return 1


def detect() -> DisplayInfo:
    """Detect full display environment."""
    return DisplayInfo(
        session_type=detect_session_type(),
        desktop=detect_desktop(),
        scale=detect_scale(),
        monitors=detect_monitor_count(),
    )


def snap_scale(scale: float) -> int:
    """Snap to nearest FreeRDP-supported scale value."""
    valid = [100, 140, 180]
    return min(valid, key=lambda v: abs(v - int(scale * 100)))


# --- Private helpers ---

def _gnome_scale() -> float:
    try:
        out = subprocess.check_output(
            ["gsettings", "get", "org.gnome.desktop.interface", "scaling-factor"],
            text=True, stderr=subprocess.DEVNULL,
        )
        scale = int(out.strip().split()[-1])
        if scale > 0:
            return float(scale)
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        pass
    return 1.0


def _kde_scale() -> float:
    for cmd in ("kreadconfig6", "kreadconfig5"):
        try:
            out = subprocess.check_output(
                [cmd, "--group", "KScreen", "--key", "ScaleFactor"],
                text=True, stderr=subprocess.DEVNULL,
            )
            scale = float(out.strip())
            if scale > 0:
                return scale
        except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
            pass
    return 1.0


def _wayland_compositor_scale(compositor: str) -> float:
    if compositor == "sway":
        try:
            out = subprocess.check_output(
                ["swaymsg", "-t", "get_outputs", "-r"],
                text=True, stderr=subprocess.DEVNULL,
            )
            import json
            outputs = json.loads(out)
            for o in outputs:
                if o.get("focused"):
                    return o.get("scale", 1.0)
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError, KeyError):
            pass
    elif compositor == "hyprland":
        try:
            out = subprocess.check_output(
                ["hyprctl", "monitors", "-j"],
                text=True, stderr=subprocess.DEVNULL,
            )
            import json
            monitors = json.loads(out)
            for m in monitors:
                if m.get("focused"):
                    return m.get("scale", 1.0)
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError, KeyError):
            pass
    return _env_scale()


def _cinnamon_scale() -> float:
    try:
        out = subprocess.check_output(
            ["gsettings", "get", "org.cinnamon.desktop.interface", "scaling-factor"],
            text=True, stderr=subprocess.DEVNULL,
        )
        scale = int(out.strip().split()[-1])
        if scale > 0:
            return float(scale)
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        pass
    return 1.0


def _env_scale() -> float:
    """Check environment variables for scale hints."""
    gdk = os.environ.get("GDK_SCALE")
    if gdk:
        try:
            return float(gdk)
        except ValueError:
            pass
    qt = os.environ.get("QT_SCALE_FACTOR")
    if qt:
        try:
            return float(qt)
        except ValueError:
            pass
    return 1.0
