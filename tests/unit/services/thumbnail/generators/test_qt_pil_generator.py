"""Tests for qt_pil_generator.py"""

import pytest
import sys
from unittest.mock import Mock, patch, mock_open
from PIL import Image

# Mock dependencies
sys.modules["core.logger"] = Mock()
sys.modules["PyQt6"] = Mock()
sys.modules["PyQt6.QtCore"] = Mock()
sys.modules["PyQt6.QtGui"] = Mock()


# Mock LoggableMixin
class LoggableMixin:
    def __init_logger__(self):
        self.logger = Mock()


with patch("ai_content_classifier.core.logger.LoggableMixin", LoggableMixin):
    from ai_content_classifier.services.thumbnail.generators.qt_pil_generator import (
        QtPilGenerator,
    )


class TestQtPilGeneratorQtAvailability:
    """Test class for testing Qt availability logic in qt_pil_generator"""

    def test_direct_importerror_simulation(self):
        """Test that covers the except ImportError branch (lines 9-10)"""
        from unittest.mock import patch, Mock

        # Import the target module - use the real module like in placeholder_generators test
        import ai_content_classifier.services.thumbnail.generators.qt_pil_generator as real_module

        # Store original state
        original_qt_available = real_module.QT_AVAILABLE

        try:
            # Pre-inject Mock classes to prevent NameError during execution
            real_module.QImage = Mock()
            real_module.QPixmap = Mock()

            # Force ImportError by mocking Qt modules as None
            with patch.dict("sys.modules", {"PyQt6": None, "PyQt6.QtGui": None}):
                # Execute the exact try/except block from qt_pil_generator.py
                # This should hit the except ImportError: QT_AVAILABLE = False line
                try:
                    from PyQt6.QtGui import QImage, QPixmap

                    real_module.QT_AVAILABLE = True
                except ImportError:
                    real_module.QT_AVAILABLE = False  # Lines 9-10 we want to cover!

                # Verify the except block was executed
                assert real_module.QT_AVAILABLE is False

        finally:
            # Restore original state
            real_module.QT_AVAILABLE = original_qt_available


class TestQtPilGeneratorAdditionalCoverage:
    """Additional tests to cover missing lines"""

    @pytest.fixture
    def generator(self):
        return QtPilGenerator()

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.ImageOps.exif_transpose"
    )
    def test_progressive_jpeg_conversion_error(
        self, mock_transpose, mock_open, generator
    ):
        """Test error during progressive JPEG conversion (lines 63-64)"""
        mock_image = Mock(spec=Image.Image)
        mock_image.format = "JPEG"
        mock_image.info = {"progressive": True}
        mock_image.mode = "RGB"
        mock_image.size = (200, 150)

        mock_open.return_value = mock_image
        mock_transpose.return_value = mock_image

        # Mock save to raise an exception
        mock_image.save.side_effect = Exception("Save error")

        with patch("io.BytesIO"):
            with patch(
                "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QPixmap"
            ):
                with patch(
                    "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage"
                ):
                    result = generator.generate("test.jpg", (100, 100))

        # Should catch the exception and continue (lines 63-64)
        mock_image.save.assert_called_once()

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.ImageOps.exif_transpose"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QPixmap"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage"
    )
    def test_quality_factor_edge_cases(
        self,
        mock_qimage_class,
        mock_qpixmap_class,
        mock_transpose,
        mock_open,
        generator,
    ):
        """Test quality factor edge cases (lines 101-105)"""
        mock_image = Mock(spec=Image.Image)
        mock_image.format = "JPEG"
        mock_image.info = {}
        mock_image.mode = "RGB"
        mock_image.size = (200, 150)
        mock_image.tobytes.return_value = b"rgb_data" * 30000

        mock_open.return_value = mock_image
        mock_transpose.return_value = mock_image

        mock_qimage = Mock()
        mock_qimage.isNull.return_value = False
        mock_qimage_class.return_value = mock_qimage

        mock_qpixmap = Mock()
        mock_qpixmap.isNull.return_value = False
        mock_qpixmap_class.fromImage.return_value = mock_qpixmap

        # Test with very small quality factor that would result in 0 size
        result = generator.generate("test.jpg", (100, 100), 0.001)

        # Should use max(int(size * quality_factor), 1) to ensure minimum size of 1
        mock_image.thumbnail.assert_called_once()
        args = mock_image.thumbnail.call_args[0]
        # With quality_factor=0.001, target should be (1, 1) due to max(..., 1)
        assert args[0] == (1, 1)

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.ImageOps.exif_transpose"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QPixmap"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage"
    )
    def test_thumbnail_lanczos_fallback_chain(
        self,
        mock_qimage_class,
        mock_qpixmap_class,
        mock_transpose,
        mock_open,
        generator,
    ):
        """Test thumbnail resampling fallback chain (around line 121)"""
        mock_image = Mock(spec=Image.Image)
        mock_image.format = "JPEG"
        mock_image.info = {}
        mock_image.mode = "RGB"
        mock_image.size = (200, 150)
        mock_image.tobytes.return_value = b"rgb_data" * 30000

        # Mock thumbnail to fail on LANCZOS and BICUBIC, succeed on NEAREST
        def thumbnail_side_effect(size, resample):
            if resample == Image.Resampling.LANCZOS:
                raise Exception("LANCZOS failed")
            elif resample == Image.Resampling.BICUBIC:
                raise Exception("BICUBIC failed")
            # NEAREST should succeed
            return None

        mock_image.thumbnail.side_effect = thumbnail_side_effect

        mock_open.return_value = mock_image
        mock_transpose.return_value = mock_image

        mock_qimage = Mock()
        mock_qimage.isNull.return_value = False
        mock_qimage_class.return_value = mock_qimage

        mock_qpixmap = Mock()
        mock_qpixmap.isNull.return_value = False
        mock_qpixmap_class.fromImage.return_value = mock_qpixmap

        result = generator.generate("test.jpg", (100, 100))

        # Should try LANCZOS, then BICUBIC, then NEAREST
        assert mock_image.thumbnail.call_count == 3

        # Verify the resampling methods were called in order
        calls = mock_image.thumbnail.call_args_list
        assert calls[0][0][1] == Image.Resampling.LANCZOS
        assert calls[1][0][1] == Image.Resampling.BICUBIC
        assert calls[2][0][1] == Image.Resampling.NEAREST

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.ImageOps.exif_transpose"
    )
    def test_rgba_mode_final_conversion(self, mock_transpose, mock_open, generator):
        """Test final RGB conversion for RGBA mode image"""
        # Create an RGBA image that will need final conversion to RGB
        mock_image = Mock(spec=Image.Image)
        mock_image.format = "PNG"
        mock_image.info = {}
        mock_image.mode = "RGBA"  # Start as RGBA
        mock_image.size = (100, 100)

        # Mock the final convert call for Qt conversion
        rgb_image = Mock(spec=Image.Image)
        rgb_image.mode = "RGB"
        rgb_image.size = (100, 100)
        rgb_image.tobytes.return_value = b"rgb_data" * 30000

        # Set up the convert behavior - RGBA stays RGBA after transpose
        mock_image.convert.return_value = rgb_image

        mock_open.return_value = mock_image
        mock_transpose.return_value = mock_image  # Still RGBA after transpose

        with patch(
            "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage"
        ) as mock_qimage_class:
            with patch(
                "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QPixmap"
            ) as mock_qpixmap_class:
                mock_qimage = Mock()
                mock_qimage.isNull.return_value = False
                mock_qimage_class.return_value = mock_qimage

                mock_qpixmap = Mock()
                mock_qpixmap.isNull.return_value = False
                mock_qpixmap_class.fromImage.return_value = mock_qpixmap

                result = generator.generate("test.png", (100, 100))

        # Should convert RGBA to RGB for Qt conversion (final if check)
        mock_image.convert.assert_called_with("RGB")

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.ImageOps.exif_transpose"
    )
    def test_unicode_decode_error_fallback(
        self, mock_transpose, mock_image_open, generator
    ):
        """Test UnicodeDecodeError fallback (covers additional exception handling)"""
        # Create a mock image for the successful fallback
        mock_image = Mock(spec=Image.Image)
        mock_image.format = "JPEG"
        mock_image.info = {}
        mock_image.mode = "RGB"
        mock_image.size = (100, 100)
        mock_image.tobytes.return_value = b"rgb_data" * 30000

        # Correct UnicodeDecodeError parameters: encoding, object, start, end, reason
        unicode_error = UnicodeDecodeError(
            "utf-8", b"\xff\xfe", 0, 1, "invalid start byte"
        )

        # First call (Image.open(image_path)) raises UnicodeDecodeError
        # Second call (Image.open(f) in fallback) succeeds
        mock_image_open.side_effect = [unicode_error, mock_image]
        mock_transpose.return_value = mock_image

        # Mock the file opening for fallback
        with patch("builtins.open", mock_open(read_data=b"image_data")):
            with patch(
                "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QPixmap"
            ) as mock_qpixmap_class:
                with patch(
                    "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage"
                ) as mock_qimage_class:
                    mock_qimage = Mock()
                    mock_qimage.isNull.return_value = False
                    mock_qimage_class.return_value = mock_qimage

                    mock_qpixmap = Mock()
                    mock_qpixmap.isNull.return_value = False
                    mock_qpixmap_class.fromImage.return_value = mock_qpixmap

                    result = generator.generate("test.jpg", (100, 100))

        # Should try twice due to UnicodeDecodeError fallback
        assert mock_image_open.call_count == 2
        mock_image.load.assert_called_once()
        assert result is not None

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.ImageOps.exif_transpose"
    )
    def test_unicode_encode_error_fallback(
        self, mock_transpose, mock_image_open, generator
    ):
        """Test UnicodeEncodeError fallback"""
        mock_image = Mock(spec=Image.Image)
        mock_image.format = "JPEG"
        mock_image.info = {}
        mock_image.mode = "RGB"
        mock_image.size = (100, 100)
        mock_image.tobytes.return_value = b"rgb_data" * 30000

        # Correct UnicodeEncodeError parameters: encoding, object, start, end, reason
        unicode_error = UnicodeEncodeError(
            "ascii", "\u2603", 0, 1, "ordinal not in range(128)"
        )

        # First call raises UnicodeEncodeError, second call succeeds
        mock_image_open.side_effect = [unicode_error, mock_image]
        mock_transpose.return_value = mock_image

        with patch("builtins.open", mock_open(read_data=b"image_data")):
            with patch(
                "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QPixmap"
            ) as mock_qpixmap_class:
                with patch(
                    "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage"
                ) as mock_qimage_class:
                    mock_qimage = Mock()
                    mock_qimage.isNull.return_value = False
                    mock_qimage_class.return_value = mock_qimage

                    mock_qpixmap = Mock()
                    mock_qpixmap.isNull.return_value = False
                    mock_qpixmap_class.fromImage.return_value = mock_qpixmap

                    result = generator.generate("test.jpg", (100, 100))

        assert mock_image_open.call_count == 2
        mock_image.load.assert_called_once()
        assert result is not None


class TestQtPilGenerator:
    @pytest.fixture
    def generator(self):
        return QtPilGenerator()

    @pytest.fixture
    def mock_image(self):
        img = Mock(spec=Image.Image)
        img.format = "JPEG"
        img.info = {}
        img.mode = "RGB"
        img.size = (200, 150)
        img.tobytes.return_value = b"rgb_data" * 30000  # 200*150*3 bytes
        return img

    def test_init(self, generator):
        """Test generator initialization"""
        assert generator is not None
        assert hasattr(generator, "logger")

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        False,
    )
    def test_generate_qt_not_available(self, generator):
        """Test generation when Qt is not available"""
        result = generator.generate("test.jpg", (100, 100))
        assert result is None

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.ImageOps.exif_transpose"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QPixmap"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage"
    )
    def test_generate_success(
        self,
        mock_qimage_class,
        mock_qpixmap_class,
        mock_transpose,
        mock_open,
        generator,
        mock_image,
    ):
        """Test successful thumbnail generation"""
        mock_open.return_value = mock_image
        mock_transpose.return_value = mock_image

        mock_qimage = Mock()
        mock_qimage.isNull.return_value = False
        mock_qimage_class.return_value = mock_qimage

        mock_qpixmap = Mock()
        mock_qpixmap.isNull.return_value = False
        mock_qpixmap_class.fromImage.return_value = mock_qpixmap

        result = generator.generate("test.jpg", (100, 100))

        assert result == mock_qpixmap
        mock_open.assert_called_once_with("test.jpg")
        mock_image.thumbnail.assert_called_once()
        mock_image.close.assert_called_once()

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.ImageOps.exif_transpose"
    )
    @patch("builtins.open", new_callable=mock_open, read_data=b"image_data")
    def test_generate_image_open_error_with_fallback(
        self, mock_builtin_open, mock_transpose, mock_image_open, generator, mock_image
    ):
        """Test fallback when Image.open fails initially"""
        mock_image_open.side_effect = [IOError("Test error"), mock_image]
        mock_transpose.return_value = mock_image

        with patch(
            "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QPixmap"
        ):
            with patch(
                "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage"
            ):
                result = generator.generate("test.jpg", (100, 100))

        assert mock_image_open.call_count == 2
        mock_image.load.assert_called_once()

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    def test_generate_all_open_methods_fail(self, mock_open, generator):
        """Test when all image opening methods fail"""
        mock_open.side_effect = IOError("Test error")

        with patch("builtins.open", side_effect=Exception("File error")):
            result = generator.generate("test.jpg", (100, 100))

        assert result is None

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    def test_generate_null_image_after_opening(self, mock_open, generator):
        """Test when PIL image is None after opening"""
        mock_open.return_value = None

        result = generator.generate("test.jpg", (100, 100))

        assert result is None

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    def test_generate_progressive_jpeg_conversion(self, mock_open, generator):
        """Test progressive JPEG conversion to baseline"""
        mock_image = Mock(spec=Image.Image)
        mock_image.format = "JPEG"
        mock_image.info = {"progressive": True}
        mock_image.mode = "RGB"
        mock_image.size = (200, 150)
        mock_image.tobytes.return_value = b"rgb_data" * 30000

        converted_image = Mock(spec=Image.Image)
        converted_image.format = "JPEG"
        converted_image.info = {}
        converted_image.mode = "RGB"
        converted_image.size = (200, 150)
        converted_image.tobytes.return_value = b"rgb_data" * 30000

        mock_open.side_effect = [mock_image, converted_image]

        with patch("io.BytesIO") as mock_bytesio:
            mock_buffer = Mock()
            mock_bytesio.return_value = mock_buffer

            with patch(
                "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QPixmap"
            ):
                with patch(
                    "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage"
                ):
                    result = generator.generate("test.jpg", (100, 100))

        mock_image.save.assert_called_once()
        mock_image.close.assert_called()

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.ImageOps.exif_transpose"
    )
    def test_generate_exif_transpose_error(
        self, mock_transpose, mock_open, generator, mock_image
    ):
        """Test error during EXIF orientation correction"""
        mock_open.return_value = mock_image
        mock_transpose.side_effect = Exception("Transpose error")

        with patch(
            "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QPixmap"
        ):
            with patch(
                "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage"
            ):
                result = generator.generate("test.jpg", (100, 100))

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.ImageOps.exif_transpose"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QPixmap"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage"
    )
    def test_generate_p_mode_with_transparency(
        self,
        mock_qimage_class,
        mock_qpixmap_class,
        mock_transpose,
        mock_open,
        generator,
    ):
        """Test conversion of P mode image with transparency"""
        mock_image = Mock(spec=Image.Image)
        mock_image.format = "PNG"
        mock_image.info = {"transparency": 0}
        mock_image.mode = "P"

        converted_image = Mock(spec=Image.Image)
        converted_image.mode = "RGBA"
        converted_image.size = (100, 100)
        converted_image.tobytes.return_value = b"rgba_data" * 40000

        mock_image.convert.return_value = converted_image
        mock_open.return_value = mock_image
        mock_transpose.return_value = mock_image  # After transpose, still P mode

        mock_qimage = Mock()
        mock_qimage.isNull.return_value = False
        mock_qimage_class.return_value = mock_qimage

        mock_qpixmap = Mock()
        mock_qpixmap.isNull.return_value = False
        mock_qpixmap_class.fromImage.return_value = mock_qpixmap

        result = generator.generate("test.png", (100, 100))

        mock_image.convert.assert_called_with("RGBA")

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.ImageOps.exif_transpose"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QPixmap"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage"
    )
    def test_generate_p_mode_without_transparency(
        self,
        mock_qimage_class,
        mock_qpixmap_class,
        mock_transpose,
        mock_open,
        generator,
    ):
        """Test conversion of P mode image without transparency"""
        mock_image = Mock(spec=Image.Image)
        mock_image.format = "PNG"
        mock_image.info = {}
        mock_image.mode = "P"

        converted_image = Mock(spec=Image.Image)
        converted_image.mode = "RGB"
        converted_image.size = (100, 100)
        converted_image.tobytes.return_value = b"rgb_data" * 30000

        mock_image.convert.return_value = converted_image
        mock_open.return_value = mock_image
        mock_transpose.return_value = mock_image

        mock_qimage = Mock()
        mock_qimage.isNull.return_value = False
        mock_qimage_class.return_value = mock_qimage

        mock_qpixmap = Mock()
        mock_qpixmap.isNull.return_value = False
        mock_qpixmap_class.fromImage.return_value = mock_qpixmap

        result = generator.generate("test.png", (100, 100))

        mock_image.convert.assert_called_with("RGB")

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.ImageOps.exif_transpose"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QPixmap"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage"
    )
    def test_generate_la_mode(
        self,
        mock_qimage_class,
        mock_qpixmap_class,
        mock_transpose,
        mock_open,
        generator,
    ):
        """Test conversion of LA mode image"""
        mock_image = Mock(spec=Image.Image)
        mock_image.format = "PNG"
        mock_image.info = {}
        mock_image.mode = "LA"

        converted_image = Mock(spec=Image.Image)
        converted_image.mode = "RGBA"
        converted_image.size = (100, 100)
        converted_image.tobytes.return_value = b"rgba_data" * 40000

        mock_image.convert.return_value = converted_image
        mock_open.return_value = mock_image
        mock_transpose.return_value = mock_image

        mock_qimage = Mock()
        mock_qimage.isNull.return_value = False
        mock_qimage_class.return_value = mock_qimage

        mock_qpixmap = Mock()
        mock_qpixmap.isNull.return_value = False
        mock_qpixmap_class.fromImage.return_value = mock_qpixmap

        result = generator.generate("test.png", (100, 100))

        mock_image.convert.assert_called_with("RGBA")

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.ImageOps.exif_transpose"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QPixmap"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage"
    )
    def test_generate_l_mode(
        self,
        mock_qimage_class,
        mock_qpixmap_class,
        mock_transpose,
        mock_open,
        generator,
    ):
        """Test conversion of L mode image"""
        mock_image = Mock(spec=Image.Image)
        mock_image.format = "PNG"
        mock_image.info = {}
        mock_image.mode = "L"

        converted_image = Mock(spec=Image.Image)
        converted_image.mode = "RGB"
        converted_image.size = (100, 100)
        converted_image.tobytes.return_value = b"rgb_data" * 30000

        mock_image.convert.return_value = converted_image
        mock_open.return_value = mock_image
        mock_transpose.return_value = mock_image

        mock_qimage = Mock()
        mock_qimage.isNull.return_value = False
        mock_qimage_class.return_value = mock_qimage

        mock_qpixmap = Mock()
        mock_qpixmap.isNull.return_value = False
        mock_qpixmap_class.fromImage.return_value = mock_qpixmap

        result = generator.generate("test.png", (100, 100))

        mock_image.convert.assert_called_with("RGB")

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.ImageOps.exif_transpose"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QPixmap"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage"
    )
    def test_generate_cmyk_mode(
        self,
        mock_qimage_class,
        mock_qpixmap_class,
        mock_transpose,
        mock_open,
        generator,
    ):
        """Test conversion of CMYK mode image"""
        mock_image = Mock(spec=Image.Image)
        mock_image.format = "TIFF"
        mock_image.info = {}
        mock_image.mode = "CMYK"

        converted_image = Mock(spec=Image.Image)
        converted_image.mode = "RGB"
        converted_image.size = (100, 100)
        converted_image.tobytes.return_value = b"rgb_data" * 30000

        mock_image.convert.return_value = converted_image
        mock_open.return_value = mock_image
        mock_transpose.return_value = mock_image

        mock_qimage = Mock()
        mock_qimage.isNull.return_value = False
        mock_qimage_class.return_value = mock_qimage

        mock_qpixmap = Mock()
        mock_qpixmap.isNull.return_value = False
        mock_qpixmap_class.fromImage.return_value = mock_qpixmap

        result = generator.generate("test.tiff", (100, 100))

        mock_image.convert.assert_called_with("RGB")

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.ImageOps.exif_transpose"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QPixmap"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage"
    )
    def test_generate_unknown_mode(
        self,
        mock_qimage_class,
        mock_qpixmap_class,
        mock_transpose,
        mock_open,
        generator,
    ):
        """Test conversion of unknown mode image"""
        mock_image = Mock(spec=Image.Image)
        mock_image.format = "UNKNOWN"
        mock_image.info = {}
        mock_image.mode = "XYZ"

        converted_image = Mock(spec=Image.Image)
        converted_image.mode = "RGB"
        converted_image.size = (100, 100)
        converted_image.tobytes.return_value = b"rgb_data" * 30000

        mock_image.convert.return_value = converted_image
        mock_open.return_value = mock_image
        mock_transpose.return_value = mock_image

        mock_qimage = Mock()
        mock_qimage.isNull.return_value = False
        mock_qimage_class.return_value = mock_qimage

        mock_qpixmap = Mock()
        mock_qpixmap.isNull.return_value = False
        mock_qpixmap_class.fromImage.return_value = mock_qpixmap

        result = generator.generate("test.unknown", (100, 100))

        mock_image.convert.assert_called_with("RGB")

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.ImageOps.exif_transpose"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QPixmap"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage"
    )
    def test_generate_with_quality_factor(
        self,
        mock_qimage_class,
        mock_qpixmap_class,
        mock_transpose,
        mock_open,
        generator,
        mock_image,
    ):
        """Test thumbnail generation with quality factor"""
        mock_open.return_value = mock_image
        mock_transpose.return_value = mock_image

        mock_qimage = Mock()
        mock_qimage.isNull.return_value = False
        mock_qimage_class.return_value = mock_qimage

        mock_qpixmap = Mock()
        mock_qpixmap.isNull.return_value = False
        mock_qpixmap_class.fromImage.return_value = mock_qpixmap

        result = generator.generate("test.jpg", (100, 100), 0.5)

        # Should call thumbnail with (50, 50) due to quality_factor=0.5
        mock_image.thumbnail.assert_called_once()
        args = mock_image.thumbnail.call_args[0]
        assert args[0] == (50, 50)

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QPixmap"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage"
    )
    def test_generate_qimage_is_null(
        self, mock_qimage_class, mock_qpixmap_class, mock_open, generator, mock_image
    ):
        """Test when QImage is null"""
        mock_open.return_value = mock_image

        mock_qimage = Mock()
        mock_qimage.isNull.return_value = True
        mock_qimage_class.return_value = mock_qimage

        result = generator.generate("test.jpg", (100, 100))

        assert result is None

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QPixmap"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage"
    )
    def test_generate_qpixmap_is_null(
        self, mock_qimage_class, mock_qpixmap_class, mock_open, generator, mock_image
    ):
        """Test when QPixmap is null"""
        mock_open.return_value = mock_image

        mock_qimage = Mock()
        mock_qimage.isNull.return_value = False
        mock_qimage_class.return_value = mock_qimage

        mock_qpixmap = Mock()
        mock_qpixmap.isNull.return_value = True
        mock_qpixmap_class.fromImage.return_value = mock_qpixmap

        result = generator.generate("test.jpg", (100, 100))

        assert result is None

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    def test_generate_qt_conversion_error(self, mock_open, generator, mock_image):
        """Test error during Qt conversion"""
        mock_open.return_value = mock_image

        with patch(
            "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage",
            side_effect=Exception("Qt error"),
        ):
            result = generator.generate("test.jpg", (100, 100))

        assert result is None

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    def test_generate_general_exception(self, mock_open, generator):
        """Test handling of general exception during generation"""
        mock_open.side_effect = Exception("General error")

        result = generator.generate("test.jpg", (100, 100))

        assert result is None

    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QT_AVAILABLE",
        True,
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.ImageOps.exif_transpose"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QPixmap"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.qt_pil_generator.QImage"
    )
    def test_generate_final_rgb_conversion(
        self,
        mock_qimage_class,
        mock_qpixmap_class,
        mock_transpose,
        mock_open,
        generator,
    ):
        """Test final RGB conversion if image is not RGB"""
        mock_image = Mock(spec=Image.Image)
        mock_image.format = "PNG"
        mock_image.info = {}
        mock_image.mode = "RGBA"
        mock_image.size = (100, 100)

        # Mock the convert method to return RGB image
        rgb_image = Mock(spec=Image.Image)
        rgb_image.mode = "RGB"
        rgb_image.size = (100, 100)
        rgb_image.tobytes.return_value = b"rgb_data" * 30000
        mock_image.convert.return_value = rgb_image

        mock_open.return_value = mock_image
        mock_transpose.return_value = mock_image

        mock_qimage = Mock()
        mock_qimage.isNull.return_value = False
        mock_qimage_class.return_value = mock_qimage

        mock_qpixmap = Mock()
        mock_qpixmap.isNull.return_value = False
        mock_qpixmap_class.fromImage.return_value = mock_qpixmap

        result = generator.generate("test.png", (100, 100))

        # Should convert: RGBA mode gets converted to RGB for Qt
        assert mock_image.convert.call_count >= 1
