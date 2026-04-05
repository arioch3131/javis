"""Tests for pil_generator.py"""

import pytest
import sys

from unittest.mock import Mock, patch, mock_open
from PIL import Image

# Mock dependencies
sys.modules["core.logger"] = Mock()


# Mock LoggableMixin
class LoggableMixin:
    def __init_logger__(self):
        self.logger = Mock()


with patch("ai_content_classifier.core.logger.LoggableMixin", LoggableMixin):
    from ai_content_classifier.services.thumbnail.generators.pil_generator import (
        PilGenerator,
    )


class TestPilGenerator:
    @pytest.fixture
    def generator(self):
        return PilGenerator()

    @pytest.fixture
    def mock_image(self):
        img = Mock(spec=Image.Image)
        img.format = "JPEG"
        img.info = {}
        img.copy.return_value = Mock(spec=Image.Image)
        return img

    def test_init(self, generator):
        """Test generator initialization"""
        assert generator is not None
        assert hasattr(generator, "logger")

    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.ImageOps.exif_transpose"
    )
    def test_generate_success(self, mock_transpose, mock_open, generator, mock_image):
        """Test successful thumbnail generation"""
        mock_open.return_value = mock_image
        mock_transpose.return_value = mock_image  # Return same image after transpose

        result = generator.generate("test.jpg", (100, 100))

        assert result is not None
        mock_open.assert_called_once_with("test.jpg")
        mock_image.thumbnail.assert_called_once()
        mock_image.copy.assert_called_once()
        mock_image.close.assert_called_once()

    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.ImageOps.exif_transpose"
    )
    @patch("builtins.open", new_callable=mock_open, read_data=b"image_data")
    def test_generate_image_open_error_with_fallback(
        self, mock_builtin_open, mock_transpose, mock_image_open, generator, mock_image
    ):
        """Test fallback when Image.open fails initially"""
        # First call raises IOError, second call (in fallback) succeeds
        mock_image_open.side_effect = [IOError("Test error"), mock_image]
        mock_transpose.return_value = mock_image

        result = generator.generate("test.jpg", (100, 100))

        assert result is not None
        assert mock_image_open.call_count == 2
        mock_image.load.assert_called_once()

    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.Image.open"
    )
    @patch("builtins.open")
    def test_generate_all_open_methods_fail(
        self, mock_builtin_open, mock_image_open, generator
    ):
        """Test when all image opening methods fail"""
        mock_image_open.side_effect = IOError("Test error")
        mock_builtin_open.side_effect = Exception("File error")

        result = generator.generate("test.jpg", (100, 100))

        assert result is None

    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.Image.open"
    )
    def test_generate_null_image_after_opening(self, mock_open, generator):
        """Test when PIL image is None after opening"""
        mock_open.return_value = None

        result = generator.generate("test.jpg", (100, 100))

        assert result is None

    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.Image.open"
    )
    def test_generate_progressive_jpeg_conversion(self, mock_open, generator):
        """Test progressive JPEG conversion to baseline"""
        mock_image = Mock(spec=Image.Image)
        mock_image.format = "JPEG"
        mock_image.info = {"progressive": True}
        mock_image.copy.return_value = Mock(spec=Image.Image)

        # Mock the converted image
        converted_image = Mock(spec=Image.Image)
        converted_image.format = "JPEG"
        converted_image.info = {}
        converted_image.copy.return_value = Mock(spec=Image.Image)

        mock_open.side_effect = [mock_image, converted_image]

        with patch("io.BytesIO") as mock_bytesio:
            mock_buffer = Mock()
            mock_bytesio.return_value = mock_buffer

            result = generator.generate("test.jpg", (100, 100))

        assert result is not None
        mock_image.save.assert_called_once()
        mock_image.close.assert_called()

    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.Image.open"
    )
    def test_generate_progressive_jpeg_conversion_error(self, mock_open, generator):
        """Test error during progressive JPEG conversion"""
        mock_image = Mock(spec=Image.Image)
        mock_image.format = "JPEG"
        mock_image.info = {"progressive": True}
        mock_image.save.side_effect = Exception("Save error")
        mock_image.copy.return_value = Mock(spec=Image.Image)

        mock_open.return_value = mock_image

        result = generator.generate("test.jpg", (100, 100))

        assert result is not None  # Should continue despite conversion error

    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.ImageOps.exif_transpose"
    )
    def test_generate_exif_transpose_success(
        self, mock_transpose, mock_open, generator, mock_image
    ):
        """Test successful EXIF orientation correction"""
        transposed_image = Mock(spec=Image.Image)
        transposed_image.format = "JPEG"
        transposed_image.info = {}
        transposed_image.copy.return_value = Mock(spec=Image.Image)

        mock_open.return_value = mock_image
        mock_transpose.return_value = transposed_image

        result = generator.generate("test.jpg", (100, 100))

        assert result is not None
        mock_transpose.assert_called_once_with(mock_image)

    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.ImageOps.exif_transpose"
    )
    def test_generate_exif_transpose_error(
        self, mock_transpose, mock_open, generator, mock_image
    ):
        """Test error during EXIF orientation correction"""
        mock_open.return_value = mock_image
        mock_transpose.side_effect = Exception("Transpose error")

        result = generator.generate("test.jpg", (100, 100))

        assert result is not None  # Should continue despite transpose error

    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.ImageOps.exif_transpose"
    )
    def test_generate_with_quality_factor(
        self, mock_transpose, mock_open, generator, mock_image
    ):
        """Test thumbnail generation with quality factor"""
        mock_open.return_value = mock_image
        mock_transpose.return_value = mock_image

        result = generator.generate("test.jpg", (100, 100), 0.5)

        assert result is not None
        # Should call thumbnail with (50, 50) due to quality_factor=0.5
        mock_image.thumbnail.assert_called_once()
        args = mock_image.thumbnail.call_args[0]
        assert args[0] == (50, 50)

    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.ImageOps.exif_transpose"
    )
    def test_generate_with_very_small_quality_factor(
        self, mock_transpose, mock_open, generator, mock_image
    ):
        """Test thumbnail generation with very small quality factor"""
        mock_open.return_value = mock_image
        mock_transpose.return_value = mock_image

        result = generator.generate("test.jpg", (100, 100), 0.001)

        assert result is not None
        # Should ensure minimum size of 1x1
        mock_image.thumbnail.assert_called_once()
        args = mock_image.thumbnail.call_args[0]
        assert args[0] == (1, 1)

    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.ImageOps.exif_transpose"
    )
    def test_generate_thumbnail_lanczos_fallback_to_bicubic(
        self, mock_transpose, mock_open, generator, mock_image
    ):
        """Test thumbnail resampling fallback from LANCZOS to BICUBIC"""
        mock_open.return_value = mock_image
        mock_transpose.return_value = mock_image
        mock_image.thumbnail.side_effect = [Exception("LANCZOS error"), None]

        result = generator.generate("test.jpg", (100, 100))

        assert result is not None
        assert mock_image.thumbnail.call_count == 2

    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.ImageOps.exif_transpose"
    )
    def test_generate_thumbnail_all_resampling_methods_fail_use_nearest(
        self, mock_transpose, mock_open, generator, mock_image
    ):
        """Test thumbnail resampling fallback to NEAREST when all others fail"""
        mock_open.return_value = mock_image
        mock_transpose.return_value = mock_image
        mock_image.thumbnail.side_effect = [
            Exception("LANCZOS error"),
            Exception("BICUBIC error"),
            None,
        ]

        result = generator.generate("test.jpg", (100, 100))

        assert result is not None
        assert mock_image.thumbnail.call_count == 3

    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.Image.open"
    )
    def test_generate_general_exception(self, mock_open, generator):
        """Test handling of general exception during generation"""
        mock_open.side_effect = Exception("General error")

        result = generator.generate("test.jpg", (100, 100))

        assert result is None

    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.Image.open"
    )
    def test_generate_non_jpeg_image(self, mock_open, generator):
        """Test generation with non-JPEG image"""
        mock_image = Mock(spec=Image.Image)
        mock_image.format = "PNG"
        mock_image.info = {}
        mock_image.copy.return_value = Mock(spec=Image.Image)

        mock_open.return_value = mock_image

        result = generator.generate("test.png", (100, 100))

        assert result is not None
        # Should not attempt JPEG-specific operations
        mock_image.save.assert_not_called()

    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.ImageOps.exif_transpose"
    )
    @patch("builtins.open", new_callable=mock_open, read_data=b"image_data")
    def test_generate_unicode_encode_error_fallback(
        self, mock_builtin_open, mock_transpose, mock_image_open, generator, mock_image
    ):
        """Test fallback when UnicodeEncodeError occurs"""
        mock_image_open.side_effect = [
            UnicodeEncodeError("utf-8", "", 0, 1, "test"),
            mock_image,
        ]
        mock_transpose.return_value = mock_image

        result = generator.generate("test.jpg", (100, 100))

        assert result is not None

    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.Image.open"
    )
    @patch(
        "ai_content_classifier.services.thumbnail.generators.pil_generator.ImageOps.exif_transpose"
    )
    @patch("builtins.open", new_callable=mock_open, read_data=b"image_data")
    def test_generate_unicode_decode_error_fallback(
        self, mock_builtin_open, mock_transpose, mock_image_open, generator, mock_image
    ):
        """Test fallback when UnicodeDecodeError occurs"""
        mock_image_open.side_effect = [
            UnicodeDecodeError("utf-8", b"", 0, 1, "test"),
            mock_image,
        ]
        mock_transpose.return_value = mock_image

        result = generator.generate("test.jpg", (100, 100))

        assert result is not None
