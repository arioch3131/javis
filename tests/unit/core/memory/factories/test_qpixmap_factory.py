import unittest
import sys
from unittest.mock import Mock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QColor, QImage
from ai_content_classifier.core.memory.factories.qpixmap_factory import QPixmapFactory


class TestQPixmapFactory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up QApplication for the entire test class."""
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.factory = QPixmapFactory()

    def test_init_default_values(self):
        """Test initialization with default values."""
        factory = QPixmapFactory()
        self.assertEqual(factory.default_format, QImage.Format.Format_ARGB32)
        self.assertEqual(factory.reset_color, QColor(0, 0, 0, 0))

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        custom_color = QColor(255, 0, 0, 128)
        factory = QPixmapFactory(
            default_format=QImage.Format.Format_RGB32, reset_color=custom_color
        )
        self.assertEqual(factory.default_format, QImage.Format.Format_RGB32)
        self.assertEqual(factory.reset_color, custom_color)

    def test_create_valid_dimensions(self):
        """Test creating a QPixmap with valid dimensions."""
        pixmap = self.factory.create(100, 50)
        self.assertIsInstance(pixmap, QPixmap)
        self.assertFalse(pixmap.isNull())
        self.assertEqual(pixmap.width(), 100)
        self.assertEqual(pixmap.height(), 50)
        # Check if filled with reset color (black, alpha may vary by format)
        image = pixmap.toImage()
        pixel_color = image.pixelColor(0, 0)
        self.assertEqual(pixel_color.red(), 0)
        self.assertEqual(pixel_color.green(), 0)
        self.assertEqual(pixel_color.blue(), 0)
        # Note: alpha value may vary depending on the pixmap format

    def test_create_with_specific_format(self):
        """Test creating a QPixmap with a specified format."""
        pixmap = self.factory.create(10, 10, pixel_format=QImage.Format.Format_RGB888)
        self.assertIsInstance(pixmap, QPixmap)
        self.assertFalse(pixmap.isNull())
        self.assertEqual(pixmap.width(), 10)
        self.assertEqual(pixmap.height(), 10)
        # RGB888 format doesn't support alpha, so we only check RGB values
        image = pixmap.toImage()
        pixel_color = image.pixelColor(0, 0)
        self.assertEqual(pixel_color.red(), 0)
        self.assertEqual(pixel_color.green(), 0)
        self.assertEqual(pixel_color.blue(), 0)
        # Alpha may not be 0 for RGB888 format, so we don't check it

    def test_create_invalid_dimensions(self):
        """Test creating a QPixmap with invalid dimensions."""
        with self.assertRaises(ValueError):
            self.factory.create(0, 50)
        with self.assertRaises(ValueError):
            self.factory.create(100, 0)
        with self.assertRaises(ValueError):
            self.factory.create(-10, 50)
        with self.assertRaises(ValueError):
            self.factory.create(100, -50)

    def test_reset_valid_pixmap(self):
        """Test resetting a valid QPixmap."""
        pixmap = self.factory.create(10, 10)
        # Fill with a different color to ensure reset works
        pixmap.fill(QColor(255, 0, 0))
        self.assertTrue(self.factory.reset(pixmap))
        image = pixmap.toImage()
        pixel_color = image.pixelColor(0, 0)
        # After reset, should be back to reset color (black, alpha may vary by format)
        self.assertEqual(pixel_color.red(), 0)
        self.assertEqual(pixel_color.green(), 0)
        self.assertEqual(pixel_color.blue(), 0)
        # Note: alpha value may vary depending on the pixmap format

    def test_reset_null_pixmap(self):
        """Test resetting a null QPixmap."""
        pixmap = QPixmap()
        self.assertFalse(self.factory.reset(pixmap))

    def test_reset_exception_handling(self):
        """Test reset method's exception handling."""
        mock_pixmap = Mock(spec=QPixmap)
        mock_pixmap.isNull.return_value = False
        mock_pixmap.fill.side_effect = RuntimeError("Fill failed")
        self.assertFalse(self.factory.reset(mock_pixmap))

    def test_validate_valid_pixmap(self):
        """Test validating a valid QPixmap."""
        pixmap = self.factory.create(10, 10)
        self.assertTrue(self.factory.validate(pixmap))

    def test_validate_null_pixmap(self):
        """Test validating a null QPixmap."""
        pixmap = QPixmap()
        self.assertFalse(self.factory.validate(pixmap))

    def test_validate_invalid_dimensions(self):
        """Test validating a QPixmap with invalid dimensions."""
        pixmap = QPixmap(0, 0)  # Create a pixmap with invalid dimensions
        self.assertFalse(self.factory.validate(pixmap))

    def test_validate_non_qpixmap_object(self):
        """Test validating a non-QPixmap object."""
        self.assertFalse(self.factory.validate("not a pixmap"))

    def test_validate_exception_handling(self):
        """Test validate method's exception handling."""
        mock_pixmap = Mock(spec=QPixmap)
        mock_pixmap.isNull.side_effect = RuntimeError("isNull failed")
        self.assertFalse(self.factory.validate(mock_pixmap))

    def test_get_key(self):
        """Test key generation logic."""
        # Test with specific calculations (round to nearest 32):
        # width=100: (100 + 16) // 32 * 32 = 116 // 32 * 32 = 3 * 32 = 96
        # height=200: (200 + 16) // 32 * 32 = 216 // 32 * 32 = 6 * 32 = 192
        key1 = self.factory.get_key(100, 200, QImage.Format.Format_ARGB32)
        self.assertEqual(key1, "qpixmap_96x192_Format_ARGB32")

        # width=10: (10 + 16) // 32 * 32 = 26 // 32 * 32 = 0 * 32 = 0
        # height=10: (10 + 16) // 32 * 32 = 26 // 32 * 32 = 0 * 32 = 0
        key2 = self.factory.get_key(10, 10, QImage.Format.Format_RGB888)
        self.assertEqual(key2, "qpixmap_0x0_Format_RGB888")

        # width=32: (32 + 16) // 32 * 32 = 48 // 32 * 32 = 1 * 32 = 32
        # height=32: (32 + 16) // 32 * 32 = 48 // 32 * 32 = 1 * 32 = 32
        key3 = self.factory.get_key(32, 32)  # Using default format
        self.assertEqual(key3, "qpixmap_32x32_Format_ARGB32")

    def test_destroy(self):
        """Test destroy method."""
        pixmap = self.factory.create(10, 10)
        # No direct way to assert detachment, but ensure no exceptions
        try:
            self.factory.destroy(pixmap)
        except Exception as e:
            self.fail(f"destroy() raised an exception: {e}")

    def test_destroy_null_pixmap(self):
        """Test destroying a null pixmap."""
        pixmap = QPixmap()
        try:
            self.factory.destroy(pixmap)
        except Exception as e:
            self.fail(f"destroy() raised an exception for null pixmap: {e}")

    def test_destroy_exception_handling(self):
        """Test destroy method's exception handling."""
        mock_pixmap = Mock(spec=QPixmap)
        mock_pixmap.isNull.return_value = False
        mock_pixmap.detach.side_effect = RuntimeError("Detach failed")
        try:
            self.factory.destroy(mock_pixmap)
        except Exception as e:
            self.fail(f"destroy() should handle exceptions, but raised {e}")

    def test_estimate_size(self):
        """Test size estimation.

        Note: Qt may optimize pixel formats internally for performance reasons.
        For example, a Grayscale8 format might be stored as 32-bit internally.
        Therefore, we use flexible ranges rather than exact values.
        """
        pixmap_rgb32 = self.factory.create(
            10, 10, pixel_format=QImage.Format.Format_RGB32
        )
        size_rgb32 = self.factory.estimate_size(pixmap_rgb32)
        # For 10x10 pixels, Qt may optimize formats, expect reasonable range
        self.assertGreaterEqual(size_rgb32, 100)  # At least 1 byte per pixel
        self.assertLessEqual(
            size_rgb32, 1000
        )  # At most ~10 bytes per pixel with overhead

        pixmap_rgb888 = self.factory.create(
            10, 10, pixel_format=QImage.Format.Format_RGB888
        )
        size_rgb888 = self.factory.estimate_size(pixmap_rgb888)
        # For RGB888, expect reasonable range
        self.assertGreaterEqual(size_rgb888, 100)
        self.assertLessEqual(size_rgb888, 1000)

        pixmap_grayscale = self.factory.create(
            10, 10, pixel_format=QImage.Format.Format_Grayscale8
        )
        size_grayscale = self.factory.estimate_size(pixmap_grayscale)
        # Qt may optimize grayscale to 32-bit internally, so expect reasonable range
        self.assertGreaterEqual(size_grayscale, 100)
        self.assertLessEqual(size_grayscale, 1000)

    def test_estimate_size_null_pixmap(self):
        """Test size estimation for a null pixmap."""
        pixmap = QPixmap()
        self.assertEqual(self.factory.estimate_size(pixmap), 0)

    def test_estimate_size_exception_handling(self):
        """Test estimate_size method's exception handling."""
        mock_pixmap = Mock(spec=QPixmap)
        mock_pixmap.isNull.return_value = False
        mock_pixmap.width.side_effect = AttributeError("Width access failed")
        # Should fall back to sys.getsizeof, which will return a non-zero value for a mock object
        self.assertGreater(self.factory.estimate_size(mock_pixmap), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
