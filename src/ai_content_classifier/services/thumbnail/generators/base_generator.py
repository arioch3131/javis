from abc import ABC, abstractmethod
from typing import Tuple, Union

from PIL import Image

from ai_content_classifier.core.logger import LoggableMixin


class BaseThumbnailGenerator(ABC, LoggableMixin):
    """Abstract base class for thumbnail generators."""

    def __init__(self):
        self.__init_logger__()

    @abstractmethod
    def generate(
        self, image_path: str, size: Tuple[int, int], quality_factor: float = 1.0
    ) -> Union[Image.Image, None]:
        """Generate a thumbnail for the given image.

        Args:
            image_path (str): Path to the image file
            size (Tuple[int, int]): Thumbnail size
            quality_factor (float): Quality factor for progressive loading (0.1 to 1.0)

        Returns:
            Union[Image.Image, None]: The generated thumbnail, or None on error.
        """
        pass  # pragma: no cover
