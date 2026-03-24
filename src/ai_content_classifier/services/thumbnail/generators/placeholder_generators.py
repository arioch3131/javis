import os
from typing import Optional, Tuple

from PIL import Image

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPainter, QPixmap

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

from ai_content_classifier.services.thumbnail import constants
from ai_content_classifier.services.thumbnail.generators import BaseThumbnailGenerator


class SimplePlaceholderGenerator(BaseThumbnailGenerator):
    """Simple PIL-based placeholder generator for when Qt is not available."""

    def generate(
        self, image_path: str, size: Tuple[int, int], quality_factor: float = 1.0
    ) -> Optional[Image.Image]:
        """Generate a simple PIL placeholder image."""
        try:
            # Create a simple colored placeholder
            placeholder = Image.new("RGB", size, color=(128, 128, 128))
            return placeholder
        except Exception as e:
            self.logger.error(
                f"Error creating simple placeholder for {image_path}: {e}"
            )
            return None


class PlaceholderGenerator(BaseThumbnailGenerator):
    """Generator for creating placeholder thumbnails when generation fails."""

    def generate(
        self, image_path: str, size: Tuple[int, int], quality_factor: float = 1.0
    ) -> Optional[QPixmap]:
        if not QT_AVAILABLE:
            return None

        pixmap = QPixmap(size[0], size[1])
        basename = os.path.basename(image_path)
        file_ext = os.path.splitext(image_path)[1].lower()
        is_jpeg = file_ext in (".jpg", ".jpeg")

        file_type = "unknown"
        if is_jpeg:
            try:
                with open(image_path, "rb") as f:
                    header = f.read(2048)
                    if b"Adobe" in header and (
                        b"\x0c" in header[:200] or b"\x0b" in header[:200]
                    ):
                        file_type = "high_bit_jpeg"
                    elif b"\xff\xc3" in header:
                        file_type = "lossless_jpeg"
                    elif b"color" in header.lower() and b"conversion" in header.lower():
                        file_type = "uncommon_color_jpeg"
            except Exception:
                pass

        color_map = {
            "high_bit_jpeg": constants.COLOR_HIGH_BIT_JPEG,
            "lossless_jpeg": constants.COLOR_LOSSLESS_JPEG,
            "uncommon_color_jpeg": constants.COLOR_UNCOMMON_COLOR_JPEG,
        }
        pixmap.fill(color_map.get(file_type, constants.COLOR_DEFAULT_ERROR))

        painter = QPainter(pixmap)
        painter.setPen(constants.COLOR_TEXT)
        font = painter.font()
        font.setPointSize(constants.PLACEHOLDER_FONT_SIZE)
        painter.setFont(font)

        try:
            size_bytes = os.path.getsize(image_path)
            size_str = self._format_file_size(size_bytes)
        except Exception:
            size_str = "Unknown size"

        message_map = {
            "high_bit_jpeg": "High Bit-Depth JPEG",
            "lossless_jpeg": "Lossless JPEG (SOF3)",
            "uncommon_color_jpeg": "Uncommon Color JPEG",
        }
        message = message_map.get(file_type, "Unreadable File")

        rect = pixmap.rect()
        painter.drawText(
            rect, Qt.AlignmentFlag.AlignCenter, f"{message}\n{basename}\n{size_str}"
        )
        painter.end()
        return pixmap

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes <= 0:
            return "0 B"
        size_value = float(size_bytes)
        unit_index = 0
        while (
            size_value >= constants.UNIT_CONVERSION_FACTOR
            and unit_index < len(constants.BYTE_UNITS) - 1
        ):
            size_value /= constants.UNIT_CONVERSION_FACTOR
            unit_index += 1
        return f"{size_value:.1f} {constants.BYTE_UNITS[unit_index]}"
