"""
This file contains constants used by the thumbnail service.
"""

try:
    from PyQt6.QtGui import QColor

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

# Constants
BYTE_UNITS = ["B", "KB", "MB", "GB", "TB"]
UNIT_CONVERSION_FACTOR = 1024

# Size thresholds
SVG_SIZE_THRESHOLD_LOW = 1 * 1024 * 1024  # 1MB
SVG_SIZE_THRESHOLD_HIGH = 5 * 1024 * 1024  # 5MB
LARGE_IMAGE_THRESHOLD = 4 * 1024 * 1024  # 4MB

# Progressive loading constants
PREVIEW_QUALITY_LEVELS = [0.1, 0.3, 1.0]  # 10%, 30%, 100% quality

# Default thumbnail size if none specified
DEFAULT_THUMBNAIL_SIZE = (128, 128)

# Error placeholder colors - only used with Qt
if QT_AVAILABLE:
    COLOR_HIGH_BIT_JPEG = QColor(0, 100, 150, 200)  # Blue-green for high-bit JPEGs
    COLOR_LOSSLESS_JPEG = QColor(150, 50, 100, 200)  # Purple for lossless JPEGs
    COLOR_UNCOMMON_COLOR_JPEG = QColor(
        150, 100, 0, 200
    )  # Orange for uncommon color JPEG
    COLOR_DEFAULT_ERROR = QColor(50, 50, 50, 200)  # Dark gray semi-transparent
    COLOR_SVG_ERROR = QColor(0, 0, 150, 150)  # Blue for SVG errors
    COLOR_TEXT = QColor(255, 255, 255)  # White text
    PLACEHOLDER_FONT_SIZE = 8
