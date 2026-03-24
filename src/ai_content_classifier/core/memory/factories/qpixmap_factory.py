"""
QPixmap factory implementation for object pooling and memory management.

This module provides a factory class for creating and managing PyQt6 QPixmap objects
with intelligent pooling and size-based grouping for optimal memory reuse.
"""

import sys
from typing import Optional

from PyQt6.QtGui import QColor, QImage, QPixmap  # pylint: disable=no-name-in-module

from ai_content_classifier.core.memory.factories.factory_interface import ObjectFactory


class QPixmapFactory(ObjectFactory[QPixmap]):
    """
    An implementation of `ObjectFactory` for creating and managing PyQt6 QPixmap objects.
    This factory is optimized for applications that frequently create and manipulate
    pixmaps of similar sizes, such as image viewers, thumbnail generators, or graphics applications.

    The factory supports different pixel formats and provides intelligent size-based grouping
    for optimal memory pool reuse.
    """

    def __init__(
        self,
        default_format: QImage.Format = QImage.Format.Format_ARGB32,
        reset_color: Optional[QColor] = None,
    ):
        """
        Initializes the QPixmapFactory.

        Args:
            default_format (QImage.Format): The default pixel format for created pixmaps.
                                           Defaults to Format_ARGB32 for full color + alpha.
            reset_color (QColor): The color to use when resetting pixmaps. If None, uses
                                transparent black. Defaults to None.
        """
        self.default_format = default_format
        self.reset_color = reset_color or QColor(0, 0, 0, 0)  # Transparent black

    def create(
        self, width: int, height: int, pixel_format: Optional[QImage.Format] = None
    ) -> QPixmap:
        """
        Creates a new QPixmap with the specified dimensions and format.

        Args:
            width (int): The width of the pixmap in pixels.
            height (int): The height of the pixmap in pixels.
            pixel_format (QImage.Format): The pixel format.
                    If None, uses the factory's default format.

        Returns:
            QPixmap: A new QPixmap instance filled with the reset color.

        Raises:
            ValueError: If width or height is negative or zero.
        """
        if width <= 0 or height <= 0:
            raise ValueError(
                f"Invalid dimensions: {width}x{height}. Both must be positive."
            )

        effective_format = pixel_format or self.default_format

        # Create QImage first with the desired format, then convert to QPixmap
        image = QImage(width, height, effective_format)
        image.fill(self.reset_color)
        pixmap = QPixmap.fromImage(image)

        return pixmap

    def reset(self, obj: QPixmap) -> bool:
        """
        Resets a QPixmap by filling it with the factory's reset color.
        This prepares the pixmap for reuse by clearing any previous content.

        Args:
            obj (QPixmap): The QPixmap object to reset.

        Returns:
            bool: True if the pixmap was successfully reset, False otherwise.
        """
        try:
            if obj.isNull():
                return False

            obj.fill(self.reset_color)
            return True

        except (AttributeError, RuntimeError) as exc:
            # Handle Qt-specific exceptions during fill operation
            # AttributeError: if object doesn't have expected methods
            # RuntimeError: if Qt object is already destroyed
            print(f"Warning: Failed to reset QPixmap: {exc}")
            return False

    def validate(self, obj: QPixmap) -> bool:
        """
        Validates a QPixmap to ensure it is usable for the pool.
        Checks that the pixmap is not null, has valid dimensions, and is not detached incorrectly.

        Args:
            obj (QPixmap): The QPixmap object to validate.

        Returns:
            bool: True if the pixmap is valid and ready for reuse, False otherwise.
        """
        try:
            return (
                isinstance(obj, QPixmap)
                and not obj.isNull()
                and obj.width() > 0
                and obj.height() > 0
                and obj.depth() > 0  # Ensure it has a valid bit depth
            )
        except (AttributeError, RuntimeError):
            # Handle Qt-specific exceptions during validation
            # AttributeError: if object doesn't have expected methods
            # RuntimeError: if Qt object is already destroyed
            return False

    def get_key(
        self, width: int, height: int, pixel_format: Optional[QImage.Format] = None
    ) -> str:
        """
        Generates a unique key for QPixmap objects based on their characteristics.
        Groups pixmaps by size ranges and format for optimal pool reuse.

        Args:
            width (int): The width of the pixmap.
            height (int): The height of the pixmap.
            pixel_format (QImage.Format): The pixel format.

        Returns:
            str: A string key representing the pixmap category for pooling.
        """
        effective_format = pixel_format or self.default_format

        # Group by size buckets for better reuse (round to nearest 32 pixels)
        width_bucket = ((width + 16) // 32) * 32
        height_bucket = ((height + 16) // 32) * 32

        # Include format in the key to ensure compatible pixmaps are grouped
        format_name = (
            effective_format.name
            if hasattr(effective_format, "name")
            else str(effective_format)
        )

        return f"qpixmap_{width_bucket}x{height_bucket}_{format_name}"

    def destroy(self, obj: QPixmap) -> None:
        """
        Properly cleans up a QPixmap object before destruction.
        In Qt, QPixmap uses implicit sharing, so explicit cleanup helps with memory management.

        Args:
            obj (QPixmap): The QPixmap object to destroy.
        """
        try:
            # Force detachment from shared data and clear
            if not obj.isNull():
                obj.detach()  # Ensure we have our own copy before clearing
                obj = QPixmap()  # Replace with null pixmap
        except (AttributeError, RuntimeError):
            # Ignore exceptions during cleanup to prevent crashes
            # AttributeError: if object doesn't have expected methods
            # RuntimeError: if Qt object is already destroyed
            pass

    def estimate_size(self, obj: QPixmap) -> int:
        """
        Estimates the memory size of the QPixmap in bytes.
        Uses the pixmap's dimensions and bit depth for accurate calculation.

        Args:
            obj (QPixmap): The QPixmap object for which to estimate the size.

        Returns:
            int: The estimated size of the pixmap in bytes.
        """
        try:
            if obj.isNull():
                return 0

            width = obj.width()
            height = obj.height()
            depth = obj.depth()

            # Calculate bytes per pixel based on bit depth
            bytes_per_pixel = max(1, depth // 8)

            # Total size = width * height * bytes_per_pixel
            base_size = width * height * bytes_per_pixel

            # Add overhead for Qt's internal structures (estimated 10% overhead)
            total_size = int(base_size * 1.1)

            return total_size

        except (AttributeError, RuntimeError):
            # Fallback to system estimate if Qt-specific calculation fails
            # AttributeError: if object doesn't have expected methods
            # RuntimeError: if Qt object is already destroyed
            return sys.getsizeof(obj)
