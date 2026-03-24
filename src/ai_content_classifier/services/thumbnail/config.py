"""
Configuration for the thumbnail service.
"""

from dataclasses import dataclass
from typing import Tuple

from ai_content_classifier.core.memory.config import MemoryPreset


@dataclass
class ThumbnailConfig:
    """Configuration for the ThumbnailService.

    This dataclass centralizes all configuration options for thumbnail generation,
    making it easier to manage and validate settings.

    Attributes:
        thumbnail_size: Default size for thumbnails (width, height)
        enable_caching: Whether thumbnail caching is enabled
        enable_progressive_loading: Whether progressive loading is enabled for large images
        use_qt: Whether to use Qt for thumbnail generation (if available)
        max_pool_size: Maximum size of the memory pool for reusable objects
        max_cache_size: Maximum number of thumbnails to cache
        max_workers: Maximum number of worker threads for async operations
        propagate_logs: Whether to propagate logs to parent loggers
        memory_preset: Memory management preset for the cache
        quality_levels: Quality levels for progressive loading
        large_image_threshold: File size threshold for progressive loading (bytes)
        svg_size_threshold_low: Lower threshold for SVG rendering optimizations (bytes)
        svg_size_threshold_high: Upper threshold for SVG rendering optimizations (bytes)
        cache_ttl: Cache time-to-live in seconds (0 = no expiration)
        enable_exif_rotation: Whether to auto-rotate images based on EXIF data
        fallback_to_placeholder: Whether to generate placeholders on errors
        jpeg_baseline_conversion: Whether to convert progressive JPEGs to baseline
        resampling_method: Preferred PIL resampling method
    """

    # Core settings
    thumbnail_size: Tuple[int, int] = (128, 128)
    enable_caching: bool = True
    enable_progressive_loading: bool = False
    use_qt: bool = False

    # Resource limits
    max_pool_size: int = 10
    max_cache_size: int = 200
    max_workers: int = 2

    # Logging
    propagate_logs: bool = False

    # Memory management
    memory_preset: MemoryPreset = MemoryPreset.HIGH_THROUGHPUT

    # Progressive loading settings
    quality_levels: Tuple[float, ...] = (0.1, 0.3, 1.0)
    large_image_threshold: int = 4 * 1024 * 1024  # 4MB

    # SVG settings
    svg_size_threshold_low: int = 1 * 1024 * 1024  # 1MB
    svg_size_threshold_high: int = 5 * 1024 * 1024  # 5MB

    # Cache settings
    cache_ttl: int = 0  # No expiration by default

    # Image processing options
    enable_exif_rotation: bool = True
    fallback_to_placeholder: bool = True
    jpeg_baseline_conversion: bool = True
    resampling_method: str = "LANCZOS"  # LANCZOS, BICUBIC, NEAREST

    # Error handling
    max_retries: int = 2
    retry_delay: float = 0.1

    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate_config()

    def _validate_config(self):
        """Validate configuration values."""
        # Validate thumbnail size
        if not isinstance(self.thumbnail_size, tuple) or len(self.thumbnail_size) != 2:
            raise ValueError("thumbnail_size must be a tuple of (width, height)")

        if any(size <= 0 for size in self.thumbnail_size):
            raise ValueError("thumbnail_size dimensions must be positive")

        if any(size > 4096 for size in self.thumbnail_size):
            raise ValueError("thumbnail_size dimensions too large (max 4096)")

        # Validate resource limits
        if self.max_pool_size <= 0:
            raise ValueError("max_pool_size must be positive")

        if self.max_cache_size <= 0:
            raise ValueError("max_cache_size must be positive")

        if self.max_workers <= 0:
            raise ValueError("max_workers must be positive")

        # Validate quality levels
        if not all(0.0 <= level <= 1.0 for level in self.quality_levels):
            raise ValueError("quality_levels must be between 0.0 and 1.0")

        if not self.quality_levels or self.quality_levels[-1] != 1.0:
            raise ValueError("quality_levels must end with 1.0 (full quality)")

        # Validate thresholds
        if self.large_image_threshold <= 0:
            raise ValueError("large_image_threshold must be positive")

        if self.svg_size_threshold_low <= 0 or self.svg_size_threshold_high <= 0:
            raise ValueError("SVG thresholds must be positive")

        if self.svg_size_threshold_low > self.svg_size_threshold_high:
            raise ValueError(
                "svg_size_threshold_low must be <= svg_size_threshold_high"
            )

        # Validate resampling method
        valid_methods = ["LANCZOS", "BICUBIC", "NEAREST", "BILINEAR"]
        if self.resampling_method not in valid_methods:
            raise ValueError(f"resampling_method must be one of {valid_methods}")

        # Validate retry settings
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")

        if self.retry_delay < 0:
            raise ValueError("retry_delay must be non-negative")

    def copy(self, **changes) -> "ThumbnailConfig":
        """Create a copy of the config with optional changes.

        Args:
            **changes: Fields to modify in the copy

        Returns:
            New ThumbnailConfig instance with changes applied
        """
        # Get current values as dict
        current_values = {
            field.name: getattr(self, field.name)
            for field in self.__dataclass_fields__.values()
        }

        # Apply changes
        current_values.update(changes)

        return ThumbnailConfig(**current_values)
