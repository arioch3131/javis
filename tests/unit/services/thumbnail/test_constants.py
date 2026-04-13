"""Tests for constants.py"""

import sys
import unittest
import importlib
from unittest.mock import patch, Mock
from unittest import mock

# Mock dependencies
sys.modules["PyQt6"] = Mock()
sys.modules["PyQt6.QtGui"] = Mock()

from ai_content_classifier.services.thumbnail import constants  # noqa: E402


class TestConstants(unittest.TestCase):
    def test_byte_units(self):
        """Test byte units constant"""
        assert constants.BYTE_UNITS == ["B", "KB", "MB", "GB", "TB"]

    def test_unit_conversion_factor(self):
        """Test unit conversion factor"""
        assert constants.UNIT_CONVERSION_FACTOR == 1024

    def test_size_thresholds(self):
        """Test size threshold constants"""
        assert constants.SVG_SIZE_THRESHOLD_LOW == 1 * 1024 * 1024  # 1MB
        assert constants.SVG_SIZE_THRESHOLD_HIGH == 5 * 1024 * 1024  # 5MB
        assert constants.LARGE_IMAGE_THRESHOLD == 4 * 1024 * 1024  # 4MB

    def test_preview_quality_levels(self):
        """Test preview quality levels"""
        assert constants.PREVIEW_QUALITY_LEVELS == [0.1, 0.3, 1.0]

    def test_default_thumbnail_size(self):
        """Test default thumbnail size"""
        assert constants.DEFAULT_THUMBNAIL_SIZE == (128, 128)

    @patch("ai_content_classifier.services.thumbnail.constants.QT_AVAILABLE", True)
    def test_qt_colors_when_available(self):
        """Test Qt color constants when Qt is available"""
        # Re-import to apply the patch
        import importlib

        importlib.reload(constants)

        # Test that color constants exist when Qt is available
        assert hasattr(constants, "COLOR_HIGH_BIT_JPEG")
        assert hasattr(constants, "COLOR_LOSSLESS_JPEG")
        assert hasattr(constants, "COLOR_UNCOMMON_COLOR_JPEG")
        assert hasattr(constants, "COLOR_DEFAULT_ERROR")
        assert hasattr(constants, "COLOR_SVG_ERROR")
        assert hasattr(constants, "COLOR_TEXT")
        assert hasattr(constants, "PLACEHOLDER_FONT_SIZE")

        # Test font size value
        assert constants.PLACEHOLDER_FONT_SIZE == 8

    def test_qt_available_false_on_import_error(self):
        """Test that QT_AVAILABLE is False when PyQt6.QtGui cannot be imported."""
        # Temporarily remove PyQt6.QtGui from sys.modules to simulate ImportError
        # and ensure it's not re-imported during reload
        with mock.patch.dict(sys.modules, {"PyQt6.QtGui": None, "PyQt6": None}):
            # Explicitly delete Qt-dependent attributes if they exist from previous imports
            for attr in [
                "COLOR_HIGH_BIT_JPEG",
                "COLOR_LOSSLESS_JPEG",
                "COLOR_UNCOMMON_COLOR_JPEG",
                "COLOR_DEFAULT_ERROR",
                "COLOR_SVG_ERROR",
                "COLOR_TEXT",
                "PLACEHOLDER_FONT_SIZE",
            ]:
                if hasattr(constants, attr):
                    delattr(constants, attr)

            # Reload the constants module to re-run the import logic
            importlib.reload(constants)

            self.assertFalse(constants.QT_AVAILABLE)
            self.assertFalse(hasattr(constants, "COLOR_HIGH_BIT_JPEG"))
            self.assertFalse(hasattr(constants, "COLOR_LOSSLESS_JPEG"))
            self.assertFalse(hasattr(constants, "COLOR_UNCOMMON_COLOR_JPEG"))
            self.assertFalse(hasattr(constants, "COLOR_DEFAULT_ERROR"))
            self.assertFalse(hasattr(constants, "COLOR_SVG_ERROR"))
            self.assertFalse(hasattr(constants, "COLOR_TEXT"))
            self.assertFalse(hasattr(constants, "PLACEHOLDER_FONT_SIZE"))

    def test_constants_immutability(self):
        """Test that constants are properly defined and accessible"""
        # Test basic constants that should always be available
        assert isinstance(constants.BYTE_UNITS, list)
        assert isinstance(constants.UNIT_CONVERSION_FACTOR, int)
        assert isinstance(constants.SVG_SIZE_THRESHOLD_LOW, int)
        assert isinstance(constants.SVG_SIZE_THRESHOLD_HIGH, int)
        assert isinstance(constants.LARGE_IMAGE_THRESHOLD, int)
        assert isinstance(constants.PREVIEW_QUALITY_LEVELS, list)
        assert isinstance(constants.DEFAULT_THUMBNAIL_SIZE, tuple)

    def test_size_threshold_relationships(self):
        """Test relationships between size thresholds"""
        assert constants.SVG_SIZE_THRESHOLD_LOW < constants.SVG_SIZE_THRESHOLD_HIGH
        assert constants.LARGE_IMAGE_THRESHOLD < constants.SVG_SIZE_THRESHOLD_HIGH

    def test_preview_quality_levels_order(self):
        """Test preview quality levels are in ascending order"""
        levels = constants.PREVIEW_QUALITY_LEVELS
        assert len(levels) == 3
        assert levels[0] < levels[1] < levels[2]
        assert levels[2] == 1.0  # Maximum quality should be 1.0
