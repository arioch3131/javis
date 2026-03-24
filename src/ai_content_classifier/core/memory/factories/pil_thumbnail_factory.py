"""Factory for generating PIL Image thumbnails with caching support."""

import os
from typing import Optional

from PIL import Image

from ai_content_classifier.core.memory.factories.factory_interface import ObjectFactory


class PilThumbnailFactory(ObjectFactory[Image.Image]):
    """Factory to generate PIL Image thumbnails."""

    def __init__(self, format_handlers, pil_generator, placeholder_generator, logger):
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

    def get_key(self, *args, **kwargs) -> str:
        """Generate cache key for thumbnail."""
        image_path, size, quality_factor = self._extract_inputs(*args, **kwargs)
        if image_path is None or not size:
            return "thumbnail_invalid_key"
        return f"{image_path}_{size[0]}x{size[1]}_{quality_factor}"

    def create(self, *args, **kwargs) -> Optional[Image.Image]:
        """Create thumbnail image with fallback to placeholder on failure."""
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
                    f"PIL Thumbnail generation failed for {image_path}, using placeholder."
                )
                thumbnail = self.placeholder_generator.generate(image_path, size)
            return thumbnail
        except (OSError, IOError, ValueError) as e:
            self.logger.error(
                f"Exception in PilThumbnailFactory create for {image_path}: {e}"
            )
            return self.placeholder_generator.generate(image_path, size)

    def validate(self, obj: Image.Image) -> bool:
        """Validate that object is a PIL Image."""
        return isinstance(obj, Image.Image)

    def reset(self, obj: Image.Image) -> bool:
        """Reset object state (thumbnails are immutable)."""
        return True  # Thumbnails are immutable

    def estimate_size(self, obj: Image.Image) -> int:
        """Estimate memory size of PIL Image object."""
        try:
            return obj.width * obj.height * len(obj.getbands())
        except AttributeError:
            return 1024  # Fallback size
