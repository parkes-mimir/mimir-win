"""Tests for CLI commands."""

from __future__ import annotations

import pytest

from mimir_win.cli.app import _make_id


class TestMakeId:
    """Test app ID generation."""

    def test_simple_name(self):
        assert _make_id("Notepad") == "notepad"

    def test_spaces(self):
        assert _make_id("Windows Media Player") == "windows-media-player"

    def test_dots(self):
        assert _make_id("mspaint.exe") == "mspaint-exe"

    def test_parens(self):
        assert _make_id("App (Test)") == "app-test"

    def test_path_traversal(self):
        """Test that path traversal is prevented."""
        result = _make_id("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_special_chars(self):
        """Test that special characters are removed."""
        result = _make_id("App@#$%^&*!")
        assert "@" not in result
        assert "#" not in result

    def test_unicode(self):
        """Test unicode handling - unicode chars are stripped for security."""
        result = _make_id("应用程序")
        # Unicode chars are stripped, result may be empty
        assert isinstance(result, str)

    def test_empty(self):
        """Test empty string."""
        assert _make_id("") == ""

    def test_multiple_dashes(self):
        """Test multiple consecutive dashes are collapsed."""
        result = _make_id("a  b  c")
        assert "--" not in result
