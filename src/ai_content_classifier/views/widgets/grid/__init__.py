"""
Ultra-optimized thumbnail grid package.

This package contains all components for the high-performance thumbnail grid:
- grid_core: Main grid logic with virtualization
- thumbnail_item: Individual thumbnail widget

File type utilities are now centralized in services.file_type_service
"""

# Import file utilities from the centralized service
from ai_content_classifier.services.file.file_type_service import (
    format_file_size,
    get_file_category,
    is_audio_file,
    is_document_file,
    is_image_file,
    is_video_file,
    validate_file_path,
)

from .grid_core import UltraOptimizedThumbnailGrid
from .thumbnail_item import OptimizedThumbnailItem

# Public API - export the grid components and utilities
__all__ = [
    "UltraOptimizedThumbnailGrid",
    "OptimizedThumbnailItem",
    "is_image_file",
    "is_document_file",
    "is_video_file",
    "is_audio_file",
    "get_file_category",
    "format_file_size",
    "validate_file_path",
]
