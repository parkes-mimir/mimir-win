"""Tests for mimir_win core modules."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from mimir_win.core.config import Config, RDPConfig, VMConfig, DisplayConfig, _toml_value


class TestConfig:
    """Test Config class."""

    def test_default_config(self):
        """Test default config creation."""
        cfg = Config()
        assert cfg.rdp.user == "MyWindowsUser"
        assert cfg.rdp.password == ""
        assert cfg.rdp.port == 3389
        assert cfg.vm.backend == "podman"
        assert cfg.vm.cpus == 4
        assert cfg.vm.memory == "4G"
        assert cfg.debug is False

    def test_config_load_nonexistent(self):
        """Test loading from non-existent file."""
        cfg = Config.load(Path("/tmp/nonexistent.toml"))
        assert cfg.rdp.user == "MyWindowsUser"

    def test_config_save_and_load(self, tmp_path):
        """Test saving and loading config."""
        cfg_path = tmp_path / "test.toml"
        cfg = Config()
        cfg.rdp.user = "testuser"
        cfg.rdp.password = "testpass"
        cfg.vm.cpus = 8
        cfg.save(cfg_path)

        loaded = Config.load(cfg_path)
        assert loaded.rdp.user == "testuser"
        assert loaded.rdp.password == "testpass"
        assert loaded.vm.cpus == 8

    def test_config_save_file_permissions(self, tmp_path):
        """Test that saved config has restricted permissions."""
        cfg_path = tmp_path / "test.toml"
        cfg = Config()
        cfg.save(cfg_path)

        stat = cfg_path.stat()
        mode = oct(stat.st_mode)[-3:]
        assert mode == "600"

    def test_resolve_password_from_value(self):
        """Test password resolution from direct value."""
        cfg = Config()
        cfg.rdp.password = "test123"
        assert cfg.resolve_password() == "test123"

    def test_resolve_password_from_file(self, tmp_path):
        """Test password resolution from file."""
        pwd_file = tmp_path / "password.txt"
        pwd_file.write_text("filepass\n")

        cfg = Config()
        cfg.rdp.password_file = str(pwd_file)
        assert cfg.resolve_password() == "filepass"


class TestTomlValue:
    """Test _toml_value helper."""

    def test_bool_true(self):
        assert _toml_value(True) == "true"

    def test_bool_false(self):
        assert _toml_value(False) == "false"

    def test_int(self):
        assert _toml_value(42) == "42"

    def test_string(self):
        assert _toml_value("hello") == '"hello"'


class TestRDPConfig:
    """Test RDPConfig defaults."""

    def test_defaults(self):
        rdp = RDPConfig()
        assert rdp.user == "MyWindowsUser"
        assert rdp.port == 3389
        assert rdp.scale == 100


class TestVMConfig:
    """Test VMConfig defaults."""

    def test_defaults(self):
        vm = VMConfig()
        assert vm.backend == "podman"
        assert vm.cpus == 4
        assert vm.memory == "4G"
        assert vm.disk_size == "64G"
        assert vm.auto_start is False


class TestDisplayConfig:
    """Test DisplayConfig defaults."""

    def test_defaults(self):
        disp = DisplayConfig()
        assert disp.prefer_native_wayland is True
        assert disp.multimon == "none"
        assert disp.scale == 1.0
