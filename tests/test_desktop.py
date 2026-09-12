"""Tests for desktop entry generation."""

from __future__ import annotations

import pytest
from pathlib import Path

from mimir_win.desktop.icons import icon_hash


class TestIconHash:
    """Test icon hash function."""

    def test_consistent_hash(self):
        """Test that same input produces same hash."""
        data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVQI12NgAAIABQABNjN9GQAAAAlwSFlzAAAWJQAAFiUBSVIk8AAAAA0lEQVQI12P4z8BQDwAEgAF/QualzQAAAABJRU5ErkJggg=="
        h1 = icon_hash(data)
        h2 = icon_hash(data)
        assert h1 == h2

    def test_different_hash(self):
        """Test that different inputs produce different hashes."""
        h1 = icon_hash("data1")
        h2 = icon_hash("data2")
        assert h1 != h2

    def test_hash_length(self):
        """Test hash length is 16."""
        h = icon_hash("test")
        assert len(h) == 16
