"""
Qt thumbnail factory for generating QPixmap thumbnails from image files.

This module provides a factory class for creating and managing QPixmap thumbnails
with caching support and error handling.
"""

import os
from typing import Optional

from PyQt6.QtGui import QPixmap  # pylint: disable=no-name-in-module

from ai_content_classifier.core.memory.factories.factory_interface import ObjectFactory


class QtThumbnailFactory(ObjectFactory[QPixmap]):
    """Factory to generate QPixmap thumbnails with caching and error handling."""

    def __init__(self, format_handlers, pil_generator, placeholder_generator, logger):
        """
        Initialize the QtThumbnailFactory.

        Args:
            format_handlers: Dictionary mapping file extensions to handler functions
            pil_generator: Generator for PIL-based thumbnails
            placeholder_generator: Generator for placeholder thumbnails
            logger: Logger instance for error and warning messages
        """
        self.format_handlers = format_handlers
        self.pil_generator = pil_generator
        self.placeholder_generator = placeholder_generator
        self.logger = logger

    @staticmethod
    def _extract_inputs(*args, **kwargs):
        """Support both positional and keyword-based calls from pool adapters."""
        if args and len(args) >= 3:
            return args[0], args[1], args[2]
        return (
            kwargs.get("image_path"),
            kwargs.get("size"),
            kwargs.get("quality_factor", 1.0),
        )

    def get_key(self, *args, **kwargs) -> str:  # type: ignore[override]
        image_path, size, quality_factor = self._extract_inputs(*args, **kwargs)
        if not image_path or not size:
            return "thumbnail_invalid_key"
        return f"{image_path}_{size[0]}x{size[1]}_{quality_factor}"

    def create(self, *args, **kwargs) -> Optional[QPixmap]:
        """
        Create a QPixmap thumbnail from an image file.

        Args:
            image_path: Path to the image file
            size: Tuple of (width, height) for the thumbnail
            quality_factor: Quality factor for thumbnail generation

        Returns:
            QPixmap thumbnail or None if creation fails
        """
        image_path, size, quality_factor = self._extract_inputs(*args, **kwargs)
        if not image_path or not size:
            return None

        try:  # pylint: disable=duplicate-code
            handler = self.format_handlers.get(
                os.path.splitext(image_path)[1].lower(), self.pil_generator.generate
            )
            thumbnail = handler(image_path, size, quality_factor)
            if thumbnail is None:
                self.logger.warning(
                    "QT Thumbnail generation failed for %s, using placeholder.",
                    image_path,
                )
                thumbnail = self.placeholder_generator.generate(image_path, size)
            return thumbnail
        except (OSError, ValueError, RuntimeError) as e:
            self.logger.error(
                "Exception in QtThumbnailFactory create for %s: %s", image_path, e
            )
            return self.placeholder_generator.generate(image_path, size)

    def validate(self, obj: QPixmap) -> bool:
        """
        Validate that the object is a valid QPixmap.

        Args:
            obj: QPixmap object to validate

        Returns:
            True if the object is a valid QPixmap, False otherwise
        """
        return isinstance(obj, QPixmap) and not obj.isNull()

    def reset(self, obj: QPixmap) -> bool:  # pylint: disable=unused-argument
        """
        Reset method for the thumbnail object.

        Since thumbnails are immutable, this always returns True.

        Args:
            obj: QPixmap object (unused as thumbnails are immutable)

        Returns:
            Always True as thumbnails don't need resetting
        """
        return True  # Thumbnails are immutable

    def estimate_size(self, obj: QPixmap) -> int:
        """
        Estimate the memory size of a QPixmap object.

        Args:
            obj: QPixmap object to estimate size for

        Returns:
            Estimated size in bytes
        """
        try:
            return obj.width() * obj.height() * (obj.depth() // 8)
        except (AttributeError, RuntimeError):
            return 1024  # Fallback size
