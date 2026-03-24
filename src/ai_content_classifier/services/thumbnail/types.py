"""
This file contains the data structures for the thumbnail service.
"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ThumbnailResult:
    """Data class representing the result of a thumbnail operation.

    Attributes:
        success (bool): Whether the thumbnail was successfully created
        path (str): Path to the original file
        thumbnail: The thumbnail image (PIL.Image or QPixmap depending on mode)
        size_str (str): Human-readable file size
        file_size (int): File size in bytes
        error_message (Optional[str]): Error message if the operation failed
        format (str): Format of the original image
        quality (float): Quality factor of the thumbnail (1.0 for full quality)
    """

    success: bool
    path: str
    thumbnail: Any  # Can be PIL.Image or QPixmap
    size_str: str
    file_size: int
    error_message: Optional[str] = None
    format: str = ""
    quality: float = 1.0
