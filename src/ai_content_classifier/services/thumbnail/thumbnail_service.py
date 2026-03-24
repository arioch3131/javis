"""
Improved Thumbnail service for the AI Content Classifier application.

This service is responsible for generating thumbnails of images and documents,
with optimizations for different file types, memory management, progressive loading,
improved error handling, and dependency management.
"""

import os
import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional, Tuple, Union

try:
    from PyQt6.QtGui import QPixmap
    from ai_content_classifier.services.thumbnail.generators import (
        PlaceholderGenerator,
        QtPilGenerator,
        SvgGenerator,
    )
    from ai_content_classifier.core.memory.factories.qpixmap_factory import (
        QPixmapFactory,
    )

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    QPixmap = None
    QtPilGenerator = None
    SvgGenerator = None
    PlaceholderGenerator = None
    QPixmapFactory = None

from ai_content_classifier.core.logger import LoggableMixin
from ai_content_classifier.core.memory.config import MemoryConfigFactory, MemoryPreset
from ai_content_classifier.core.memory.factories import (
    PILImageFactory,
    PilThumbnailFactory,
    QtThumbnailFactory,
)
from ai_content_classifier.services.shared.cache_runtime import (
    SmartPoolHandle,
    get_cache_runtime,
)
from ai_content_classifier.services.shared.dependency_manager import (
    get_dependency_manager,
)
from ai_content_classifier.services.thumbnail.config import ThumbnailConfig
from ai_content_classifier.services.thumbnail.constants import (
    BYTE_UNITS,
    UNIT_CONVERSION_FACTOR,
)
from ai_content_classifier.services.thumbnail.generators import (
    PilGenerator,
    SimplePlaceholderGenerator,
)
from ai_content_classifier.services.thumbnail.types import ThumbnailResult


class ThumbnailService(LoggableMixin):
    """
    Enhanced service for generating thumbnails of images with memory optimization and caching.

    This service provides methods to create thumbnails for various image formats,
    with optimizations for memory usage, progressive loading, dependency management,
    improved error handling, and specific file types.
    It supports both PIL-based and Qt-based thumbnails.

    Attributes:
        config (ThumbnailConfig): Service configuration
        use_qt (bool): Whether Qt is available and enabled
        memory_pool (SmartPoolHandle): SmartPool for reusable PIL images or QPixmaps
        cache (SmartPoolHandle): SmartPool-backed cache for generated thumbnails
        executor (ThreadPoolExecutor): Executor for asynchronous operations
        dependency_manager: Manager for optional dependencies
    """

    def __init__(self, config: Optional[ThumbnailConfig] = None, **legacy_kwargs):
        """
        Initialize the ThumbnailService.

        Args:
            config: ThumbnailConfig instance. If None, uses default config.
            **legacy_kwargs: Legacy parameters for backward compatibility.
                            Will be used to override config values if provided.
        """
        # Initialize the LoggableMixin
        super().__init__()

        # Handle legacy parameters and create config
        self.config = self._create_config(config, legacy_kwargs)

        # Setup logger
        self._setup_logger(propagate=self.config.propagate_logs)

        # Get dependency manager
        self.dependency_manager = get_dependency_manager()
        self._cache_runtime = get_cache_runtime()
        self.memory_pool: Optional[SmartPoolHandle] = None
        self.cache: Optional[SmartPoolHandle] = None

        # Check dependencies and determine Qt availability
        self._check_dependencies()

        # Initialize generators based on availability
        self._initialize_generators()

        # Set up format handlers
        self._format_handlers = self._get_format_handlers()

        # Setup memory pool for reusable image objects
        self._setup_memory_pool()

        # Setup cache for generated thumbnails
        self._setup_cache()

        # Setup executor
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_workers)

        # Statistics
        self._stats = {
            "thumbnails_created": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
            "retries": 0,
        }

        self.logger.info(
            f"ThumbnailService initialized with size {self.config.thumbnail_size}, "
            f"using {'Qt' if self.use_qt else 'PIL'}, "
            f"caching: {self.config.enable_caching}, "
            f"progressive: {self.config.enable_progressive_loading}"
        )

    def _create_config(
        self, config: Optional[ThumbnailConfig], legacy_kwargs: dict
    ) -> ThumbnailConfig:
        """Create configuration from provided config and legacy kwargs."""
        if config is None:
            config = ThumbnailConfig()

        # Handle legacy parameters
        legacy_mapping = {
            "thumbnail_size": "thumbnail_size",
            "enable_progressive_loading": "enable_progressive_loading",
            "use_qt": "use_qt",
            "max_pool_size": "max_pool_size",
            "max_cache_size": "max_cache_size",
            "max_workers": "max_workers",
            "propagate": "propagate_logs",
        }

        changes = {}
        for legacy_key, config_key in legacy_mapping.items():
            if legacy_key in legacy_kwargs:
                changes[config_key] = legacy_kwargs[legacy_key]

        if changes:
            config = config.copy(**changes)

        return config

    def _setup_logger(self, propagate: bool = False):
        """Setup logger with proper configuration."""
        if hasattr(self, "logger") and self.logger:
            return

        try:
            if hasattr(super(), "_setup_logger"):
                super()._setup_logger(propagate=propagate)
            else:
                import logging

                self.logger = logging.getLogger(self.__class__.__name__)
                self.logger.propagate = propagate
        except Exception:
            import logging

            self.logger = logging.getLogger(self.__class__.__name__)
            self.logger.propagate = propagate

    def _check_dependencies(self):
        """Check available dependencies and determine Qt usage."""
        # Check PIL availability
        pil_available = self.dependency_manager.is_available("pillow")
        if not pil_available:
            raise RuntimeError(
                "PIL/Pillow is required for thumbnail generation. "
                "Install with: pip install Pillow"
            )

        # Check Qt availability
        qt_available = QT_AVAILABLE and self.config.use_qt

        if self.config.use_qt and not QT_AVAILABLE:
            self.logger.warning(
                "Qt requested but not available. Falling back to PIL only."
            )

        self.use_qt = qt_available

        # Log dependency status
        available_deps = []
        if pil_available:
            pil_version = self.dependency_manager.get_version("pillow")
            available_deps.append(f"PIL {pil_version or 'unknown'}")

        if qt_available:
            available_deps.append("Qt")

        self.logger.info(f"Available dependencies: {', '.join(available_deps)}")

    def _initialize_generators(self):
        """Initialize thumbnail generators based on available dependencies."""
        if self.use_qt:
            self.pil_generator = QtPilGenerator()
            self.svg_generator = SvgGenerator()
            self.placeholder_generator = PlaceholderGenerator()
        else:
            self.pil_generator = PilGenerator()
            self.svg_generator = None
            self.placeholder_generator = SimplePlaceholderGenerator()

    def _setup_memory_pool(self):
        """Setup memory pool for reusable image objects."""
        if self.use_qt:
            pool_factory = QPixmapFactory()
        else:
            pool_factory = PILImageFactory()

        pool_config = MemoryConfigFactory.create_preset(MemoryPreset.IMAGE_PROCESSING)
        self.memory_pool = SmartPoolHandle(
            runtime=self._cache_runtime,
            name=f"thumbnail_memory_pool_{id(self)}",
            factory=pool_factory,
            initial_size=max(1, min(5, self.config.max_pool_size)),
            min_size=0,
            max_size=max(1, self.config.max_pool_size),
            max_size_per_key=max(1, pool_config.max_size),
            max_age_seconds=int(pool_config.ttl_seconds),
            cleanup_interval=max(1, int(pool_config.cleanup_interval)),
            enable_background_cleanup=pool_config.enable_background_cleanup,
            enable_performance_metrics=pool_config.enable_performance_metrics,
            enable_auto_tuning=False,
            auto_wrap_objects=False,
        )

    def _setup_cache(self):
        """Setup cache for generated thumbnails."""
        if not self.config.enable_caching:
            self.cache = None
            return

        memory_config = MemoryConfigFactory.create_preset(self.config.memory_preset)

        if self.use_qt:
            thumbnail_factory = QtThumbnailFactory(
                format_handlers=self._get_format_handlers(),
                pil_generator=self.pil_generator,
                placeholder_generator=self.placeholder_generator,
                logger=self.logger,
            )
        else:
            thumbnail_factory = PilThumbnailFactory(
                format_handlers=self._get_format_handlers(),
                pil_generator=self.pil_generator,
                placeholder_generator=self.placeholder_generator,
                logger=self.logger,
            )

        self.cache = self._create_thumbnail_cache_handle(
            thumbnail_factory=thumbnail_factory,
            memory_config=memory_config,
        )

        self.logger.info(
            f"Cache configured with preset {self.config.memory_preset.value}: "
            f"max_size={memory_config.max_size}, ttl={memory_config.ttl_seconds}s, "
            f"logging={memory_config.enable_logging}"
        )

    def _create_thumbnail_cache_handle(
        self, *, thumbnail_factory, memory_config
    ) -> SmartPoolHandle:
        """Create the SmartPool adapter used for thumbnail object caching."""
        max_cache_size = min(self.config.max_cache_size, memory_config.max_size)
        adapter_kwargs = {
            "runtime": self._cache_runtime,
            "name": f"thumbnail_cache_{id(self)}",
            "factory": thumbnail_factory,
            "initial_size": 0,
            "min_size": 0,
            "max_size": max(1, max_cache_size),
            "max_size_per_key": max(1, max_cache_size),
            "max_age_seconds": int(memory_config.ttl_seconds),
            "cleanup_interval": max(1, int(memory_config.cleanup_interval)),
            "enable_background_cleanup": memory_config.enable_background_cleanup,
            "enable_performance_metrics": memory_config.enable_performance_metrics,
            "enable_auto_tuning": False,
            "auto_wrap_objects": False,
        }

        try:
            return SmartPoolHandle(**adapter_kwargs)
        except Exception:
            # Temporary compatibility path while older omni-cache versions still
            # reject initial_size=0 for lazily populated pools.
            return SmartPoolHandle(**{**adapter_kwargs, "initial_size": 1})

    def _get_format_handlers(self) -> Dict[str, Callable]:
        """Get format handlers for different file types."""
        handlers = {}

        # Standard image formats
        if hasattr(self, "pil_generator") and self.pil_generator:
            image_formats = [
                ".jpg",
                ".jpeg",
                ".png",
                ".gif",
                ".bmp",
                ".tiff",
                ".tif",
                ".webp",
            ]
            for fmt in image_formats:
                handlers[fmt] = self.pil_generator.generate

        # SVG handler (only if Qt is available)
        if self.use_qt and hasattr(self, "svg_generator") and self.svg_generator:
            handlers[".svg"] = self.svg_generator.generate

        return handlers

    def safe_get_file_size(self, path: str) -> int:
        """
        Safely get file size with error handling.

        Args:
            path: File path

        Returns:
            File size in bytes, or 0 if error/not found
        """
        try:
            return os.path.getsize(path) if os.path.exists(path) else 0
        except (OSError, IOError) as e:
            self.logger.debug(f"Error getting file size for {path}: {e}")
            return 0

    def safe_file_exists(self, path: str) -> bool:
        """
        Safely check if file exists with error handling.

        Args:
            path: File path

        Returns:
            True if file exists and is accessible
        """
        try:
            return os.path.isfile(path)
        except (OSError, IOError) as e:
            self.logger.debug(f"Error checking file existence for {path}: {e}")
            return False

    def _format_file_size(self, size_bytes: int) -> str:
        """
        Format file size in human-readable format.

        Args:
            size_bytes: File size in bytes

        Returns:
            Formatted file size string
        """
        if size_bytes <= 0:
            return "0 B"

        size_value = float(size_bytes)
        unit_index = 0

        while size_value >= UNIT_CONVERSION_FACTOR and unit_index < len(BYTE_UNITS) - 1:
            size_value /= UNIT_CONVERSION_FACTOR
            unit_index += 1

        return f"{size_value:.1f} {BYTE_UNITS[unit_index]}"

    def _create_error_result(
        self,
        image_path: str,
        error_message: str,
        size: Optional[Tuple[int, int]] = None,
    ) -> ThumbnailResult:
        """
        Create an error result with optional placeholder.

        Args:
            image_path: Path to the image file
            error_message: Error description
            size: Thumbnail size

        Returns:
            ThumbnailResult with error information
        """
        thumb_size = size or self.config.thumbnail_size
        file_size = self.safe_get_file_size(image_path)

        placeholder = None
        if self.config.fallback_to_placeholder and self.placeholder_generator:
            try:
                placeholder = self.placeholder_generator.generate(
                    image_path, thumb_size
                )
            except Exception as e:
                self.logger.debug(f"Error creating placeholder for {image_path}: {e}")

        return ThumbnailResult(
            success=False,
            path=image_path,
            thumbnail=placeholder,
            size_str=self._format_file_size(file_size),
            file_size=file_size,
            error_message=error_message,
        )

    def _retry_operation(self, operation: Callable, *args, **kwargs):
        """
        Retry an operation with exponential backoff.

        Args:
            operation: Function to retry
            *args: Arguments for the operation
            **kwargs: Keyword arguments for the operation

        Returns:
            Result of the operation

        Raises:
            Last exception if all retries fail
        """
        last_exception = None

        for attempt in range(self.config.max_retries + 1):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                self._stats["retries"] += 1

                if attempt < self.config.max_retries:
                    delay = self.config.retry_delay * (2**attempt)
                    self.logger.debug(
                        f"Retry {attempt + 1}/{self.config.max_retries} "
                        f"after {delay}s: {e}"
                    )
                    time.sleep(delay)
                else:
                    break

        raise last_exception

    def create_thumbnail(
        self,
        image_path: str,
        size: Optional[Tuple[int, int]] = None,
        quality_factor: float = 1.0,
    ) -> ThumbnailResult:
        """
        Create a thumbnail for the given image path.

        Args:
            image_path: Path to the image file
            size: Desired thumbnail size (width, height)
            quality_factor: Quality factor for the thumbnail (0.0 to 1.0)

        Returns:
            ThumbnailResult: Result containing the thumbnail and metadata
        """
        try:
            # Validate inputs first
            if not isinstance(image_path, str) or not image_path.strip():
                return self._create_error_result(image_path, "Invalid image path", size)

            thumb_size = size or self.config.thumbnail_size

            # Validate size before checking file existence
            if not isinstance(thumb_size, tuple) or len(thumb_size) != 2:
                return self._create_error_result(
                    image_path, "Invalid thumbnail size", size
                )

            if any(s <= 0 for s in thumb_size):
                return self._create_error_result(
                    image_path, "Thumbnail size must be positive", size
                )

            # Now check if file exists
            if not self.safe_file_exists(image_path):
                return self._create_error_result(
                    image_path, f"File not found: {image_path}", size
                )

            # Use cache if enabled
            thumbnail = None
            if self.cache:
                try:
                    obj_id, cache_key, cached_thumbnail = self.cache.acquire(
                        image_path=image_path,
                        size=thumb_size,
                        quality_factor=quality_factor,
                    )
                    try:
                        thumbnail = (
                            cached_thumbnail.copy()
                            if hasattr(cached_thumbnail, "copy")
                            else cached_thumbnail
                        )
                    finally:
                        self.cache.release(obj_id, cache_key, cached_thumbnail)
                    if thumbnail is not None:
                        self._stats["cache_hits"] += 1
                    else:
                        self._stats["cache_misses"] += 1
                except Exception as e:
                    self.logger.warning(f"Cache error for {image_path}: {e}")
                    self._stats["cache_misses"] += 1

            # Fallback path: direct generation (works when cache disabled or misses/fails).
            if thumbnail is None:
                try:
                    handler = self._format_handlers.get(
                        os.path.splitext(image_path)[1].lower(),
                        self.pil_generator.generate,
                    )
                    thumbnail = self._retry_operation(
                        handler, image_path, thumb_size, quality_factor
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Direct thumbnail generation failed for {image_path}: {e}"
                    )

            # Get file information
            file_size = self.safe_get_file_size(image_path)
            size_str = self._format_file_size(file_size)
            file_ext = os.path.splitext(image_path)[1].lower()

            # Update statistics
            self._stats["thumbnails_created"] += 1

            return ThumbnailResult(
                success=bool(thumbnail),
                path=image_path,
                thumbnail=thumbnail,
                size_str=size_str,
                file_size=file_size,
                quality=quality_factor,
                format=file_ext,
                error_message=None if thumbnail else "Thumbnail creation failed",
            )

        except Exception as e:
            self.logger.error(f"Error creating thumbnail for {image_path}: {e}")
            self._stats["errors"] += 1

            return self._create_error_result(image_path, str(e), size)

    def create_thumbnail_async(
        self,
        image_path: str,
        callback: Callable[[ThumbnailResult], None],
        size: Optional[Tuple[int, int]] = None,
    ) -> None:
        """
        Create a thumbnail asynchronously.

        Args:
            image_path: Path to the image file
            callback: Callback function to call with the result
            size: Desired thumbnail size (width, height)
        """

        def _process_thumbnail():
            if (
                self.config.enable_progressive_loading
                and self.safe_file_exists(image_path)
                and self.safe_get_file_size(image_path)
                > self.config.large_image_threshold
                and not image_path.lower().endswith(".svg")
            ):
                # Progressive loading for large images
                for quality in self.config.quality_levels:
                    try:
                        result = self.create_thumbnail(
                            image_path=image_path, size=size, quality_factor=quality
                        )
                        callback(result)
                        if quality >= 1.0:
                            break
                    except Exception as e:
                        self.logger.error(f"Progressive loading error: {e}")
                        result = self._create_error_result(image_path, str(e), size)
                        callback(result)
                        break
            else:
                # Standard loading
                result = self.create_thumbnail(image_path=image_path, size=size)
                callback(result)

        self.executor.submit(_process_thumbnail)

    def create_thumbnails_batch(
        self, image_paths: List[str], size: Optional[Tuple[int, int]] = None
    ) -> Dict[str, ThumbnailResult]:
        """
        Create thumbnails for multiple images in batch.

        Args:
            image_paths: List of image file paths
            size: Desired thumbnail size (width, height)

        Returns:
            Dict mapping image paths to ThumbnailResults
        """
        results = {}
        for path in image_paths:
            try:
                result = self.create_thumbnail(image_path=path, size=size)
                results[path] = result
            except Exception as e:
                self.logger.error(f"Batch processing error for {path}: {e}")
                results[path] = self._create_error_result(path, str(e), size)

        return results

    def create_thumbnails_batch_async(
        self,
        image_paths: List[str],
        callback: Callable[[str, ThumbnailResult], None],
        batch_callback: Optional[Callable[[Dict[str, ThumbnailResult]], None]] = None,
        size: Optional[Tuple[int, int]] = None,
    ) -> None:
        """
        Create thumbnails for multiple images asynchronously.

        Args:
            image_paths: List of image file paths
            callback: Callback for each thumbnail completion
            batch_callback: Callback for batch completion
            size: Desired thumbnail size (width, height)
        """
        all_results: Dict[str, ThumbnailResult] = {}
        remaining = len(image_paths)
        lock = threading.Lock()

        def _on_thumbnail_done(path: str, result: ThumbnailResult):
            nonlocal remaining
            with lock:
                all_results[path] = result
                remaining -= 1
                callback(path, result)
                if remaining == 0 and batch_callback:
                    batch_callback(all_results)

        for path in image_paths:
            self.create_thumbnail_async(
                image_path=path,
                callback=lambda result, p=path: _on_thumbnail_done(p, result),
                size=size,
            )

    def create_thumbnail_for_virtualization(
        self,
        image_path: str,
        size: Optional[Tuple[int, int]] = None,
        priority: bool = False,
    ) -> Optional[str]:
        """
        Optimized version for virtualization that returns the path
        to the saved thumbnail rather than the object.

        Args:
            image_path: Path to the image file
            size: Desired thumbnail size (width, height)
            priority: Priority flag (not currently used)

        Returns:
            Optional[str]: Path to the saved thumbnail file, or None if failed
        """
        try:
            file_hash = hashlib.md5(image_path.encode()).hexdigest()
            thumbnail_filename = f"{file_hash}.png"

            thumbnail_dir = os.path.join(os.path.dirname(__file__), "..", "thumbnails")
            os.makedirs(thumbnail_dir, exist_ok=True)
            thumbnail_path = os.path.join(thumbnail_dir, thumbnail_filename)

            # Check if thumbnail already exists
            if os.path.exists(thumbnail_path):
                return thumbnail_path

            # Create thumbnail
            result = self.create_thumbnail(image_path, size)

            if result.success and result.thumbnail:
                success = False

                if hasattr(result.thumbnail, "save"):
                    if (
                        self.use_qt
                        and QPixmap
                        and isinstance(result.thumbnail, QPixmap)
                    ):
                        success = result.thumbnail.save(thumbnail_path, "PNG")
                    else:  # PIL Image
                        result.thumbnail.save(thumbnail_path, "PNG")
                        success = True

                if success:
                    return thumbnail_path

            return None

        except Exception as e:
            self.logger.error(
                f"Error creating virtualized thumbnail for {image_path}: {e}"
            )
            return None

    def clear_cache(self) -> None:
        """Clear the thumbnail cache."""
        if self.cache:
            self.cache.clear()
            self.logger.info("Thumbnail cache cleared")

    def clear_memory_pool(self) -> None:
        """Clear the image memory pool."""
        if self.memory_pool:
            self.memory_pool.shutdown()
            self.logger.info("Image memory pool cleared")

    def get_stats(self) -> Dict[str, Union[int, float, str]]:
        """
        Get service statistics.

        Returns:
            Dict with various statistics
        """
        stats = self._stats.copy()

        # Add cache statistics if available
        if self.cache:
            cache_stats = (
                self.cache.get_stats() if hasattr(self.cache, "get_stats") else {}
            )
            stats.update({f"cache_{k}": v for k, v in cache_stats.items()})

        # Add dependency information
        stats.update(
            {
                "qt_available": self.use_qt,
                "pil_available": self.dependency_manager.is_available("pillow"),
                "config_progressive_loading": self.config.enable_progressive_loading,
                "config_caching": self.config.enable_caching,
            }
        )

        return stats

    def get_supported_formats(self) -> List[str]:
        """
        Get list of supported image formats.

        Returns:
            List of supported file extensions
        """
        return list(self._format_handlers.keys())

    def shutdown(self) -> None:
        """Shutdown the service and free resources."""
        self.logger.info("Shutting down ThumbnailService...")

        # Shutdown executor
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=True)

        # Clear resources
        self.clear_cache()
        if self.cache and hasattr(self.cache, "shutdown"):
            self.cache.shutdown()
        self.clear_memory_pool()

        self.logger.info("ThumbnailService shut down successfully")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()
