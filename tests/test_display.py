"""Tests for display detection."""

from __future__ import annotations

import pytest

from mimir_win.core.display import (
    detect_session_type,
    detect_desktop,
    snap_scale,
    DisplayInfo,
)


class TestSnapScale:
    """Test snap_scale function."""

    def test_100(self):
        assert snap_scale(1.0) == 100

    def test_140(self):
        assert snap_scale(1.4) == 140

    def test_180(self):
        assert snap_scale(1.8) == 180

    def test_closest_100(self):
        assert snap_scale(1.1) == 100

    def test_closest_140(self):
        assert snap_scale(1.3) == 140

    def test_closest_180(self):
        assert snap_scale(1.7) == 180


class TestDetectSessionType:
    """Test session type detection."""

    def test_xdg_session_type(self, monkeypatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        assert detect_session_type() == "wayland"

    def test_wayland_display(self, monkeypatch):
        monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        assert detect_session_type() == "wayland"

    def test_display(self, monkeypatch):
        monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        monkeypatch.setenv("DISPLAY", ":0")
        assert detect_session_type() == "x11"

    def test_unknown(self, monkeypatch):
        monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        monkeypatch.delenv("DISPLAY", raising=False)
        assert detect_session_type() == "unknown"


class TestDetectDesktop:
    """Test desktop environment detection."""

    def test_gnome(self, monkeypatch):
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
        assert detect_desktop() == "gnome"

    def test_kde(self, monkeypatch):
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
        assert detect_desktop() == "kde"

    def test_sway(self, monkeypatch):
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", "sway")
        assert detect_desktop() == "sway"

    def test_unknown(self, monkeypatch):
        monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
        assert detect_desktop() == "unknown"
