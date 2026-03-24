# services/shared/dependency_manager.py
"""
Global optional dependency manager.

This centralized service manages the detection and availability of all optional
dependencies used by the application:
- Extraction libraries (PyPDF2, pdfminer, docx, etc.)
- Image libraries (PIL/Pillow)
- Metadata libraries (hachoir, exifread, etc.)
- System utilities (magic, psutil, etc.)

It provides intelligent fallbacks and information on available capabilities.
"""

import importlib
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional

from ai_content_classifier.core.logger import LoggableMixin
from ai_content_classifier.services.shared.cache_runtime import get_cache_runtime


class DependencyCategory(Enum):
    """Dependency categories for organization."""

    PDF_EXTRACTION = "pdf_extraction"
    DOCUMENT_PROCESSING = "document_processing"
    IMAGE_PROCESSING = "image_processing"
    METADATA_EXTRACTION = "metadata_extraction"
    SYSTEM_UTILITIES = "system_utilities"
    MACHINE_LEARNING = "machine_learning"
    COMPRESSION = "compression"
    SECURITY = "security"


class DependencyPriority(Enum):
    """Dependency priority for fallbacks."""

    CRITICAL = 1  # Essential
    HIGH = 2  # Highly recommended
    MEDIUM = 3  # Useful
    LOW = 4  # Optional
    FALLBACK = 5  # Last resort


@dataclass
class DependencyInfo:
    """Complete information about a dependency."""

    name: str
    module_path: str
    category: DependencyCategory
    priority: DependencyPriority
    description: str = ""

    # Dependency state
    is_available: bool = False
    version: Optional[str] = None
    import_error: Optional[str] = None
    last_checked: float = 0.0

    # Useful metadata
    install_command: str = ""
    documentation_url: str = ""
    alternatives: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)

    # Custom test function (optional)
    test_function: Optional[Callable[[], bool]] = None


class DependencyManager(LoggableMixin):
    """
    Centralized manager for optional dependencies.

    This service checks the availability of optional libraries,
    provides information on available capabilities, and offers
    intelligent fallbacks as needed.
    """

    def __init__(self) -> None:
        """Initializes the dependency manager."""
        super().__init__()
        self.__init_logger__()

        # Thread safety
        self._lock = threading.RLock()

        # Dependency registry
        self._dependencies: Dict[str, DependencyInfo] = {}

        # Check cache
        self._cache_ttl = 300  # 5 minutes
        self._availability_cache = get_cache_runtime().memory_cache(
            "shared:dependency_manager:availability",
            default_ttl=self._cache_ttl,
        )

        # Statistics
        self._stats = {
            "checks_performed": 0,
            "cache_hits": 0,
            "successful_imports": 0,
            "failed_imports": 0,
        }

        # Initialize with known dependencies
        self._register_standard_dependencies()

        # Initial check
        self._initial_check()

        self.logger.info(
            f"DependencyManager initialized with {len(self._dependencies)} dependencies"
        )

    def _register_standard_dependencies(self) -> None:
        """Registers the application's standard dependencies."""

        standard_deps = [
            # === PDF EXTRACTION ===
            DependencyInfo(
                name="pdfminer",
                module_path="pdfminer.high_level",
                category=DependencyCategory.PDF_EXTRACTION,
                priority=DependencyPriority.MEDIUM,
                description="Robust PDF extraction (slower)",
                install_command="pip install pdfminer.six",
                capabilities=["pdf_text_extraction", "pdf_layout_analysis"],
            ),
            # === DOCUMENT PROCESSING ===
            DependencyInfo(
                name="docx",
                module_path="docx",
                category=DependencyCategory.DOCUMENT_PROCESSING,
                priority=DependencyPriority.HIGH,
                description="Word DOCX document processing",
                install_command="pip install python-docx",
                capabilities=[
                    "docx_text_extraction",
                    "docx_metadata",
                    "docx_structure",
                ],
            ),
            DependencyInfo(
                name="striprtf",
                module_path="striprtf.striprtf",
                category=DependencyCategory.DOCUMENT_PROCESSING,
                priority=DependencyPriority.MEDIUM,
                description="RTF text extraction",
                install_command="pip install striprtf",
                capabilities=["rtf_text_extraction"],
            ),
            DependencyInfo(
                name="textract",
                module_path="textract",
                category=DependencyCategory.DOCUMENT_PROCESSING,
                priority=DependencyPriority.FALLBACK,
                description="Universal extraction (slow)",
                install_command="pip install textract",
                capabilities=["universal_text_extraction", "legacy_formats"],
            ),
            # === IMAGE PROCESSING ===
            DependencyInfo(
                name="pillow",
                module_path="PIL",
                category=DependencyCategory.IMAGE_PROCESSING,
                priority=DependencyPriority.CRITICAL,
                description="Image processing",
                install_command="pip install Pillow",
                capabilities=[
                    "image_processing",
                    "image_metadata",
                    "format_conversion",
                ],
            ),
            # === METADATA EXTRACTION ===
            DependencyInfo(
                name="hachoir",
                module_path="hachoir.parser",
                category=DependencyCategory.METADATA_EXTRACTION,
                priority=DependencyPriority.HIGH,
                description="Universal metadata extraction",
                install_command="pip install hachoir",
                capabilities=["universal_metadata", "binary_analysis"],
            ),
            DependencyInfo(
                name="exifread",
                module_path="exifread",
                category=DependencyCategory.METADATA_EXTRACTION,
                priority=DependencyPriority.MEDIUM,
                description="Advanced EXIF reading",
                install_command="pip install ExifRead",
                capabilities=["exif_extraction", "camera_metadata"],
            ),
            # === SYSTEM UTILITIES ===
            DependencyInfo(
                name="magic",
                module_path="magic",
                category=DependencyCategory.SYSTEM_UTILITIES,
                priority=DependencyPriority.HIGH,
                description="Accurate MIME type detection",
                install_command="pip install python-magic",
                capabilities=["mime_detection", "file_analysis"],
            ),
            DependencyInfo(
                name="psutil",
                module_path="psutil",
                category=DependencyCategory.SYSTEM_UTILITIES,
                priority=DependencyPriority.MEDIUM,
                description="System and process monitoring",
                install_command="pip install psutil",
                capabilities=["memory_monitoring", "process_info"],
            ),
            # === COMPRESSION ===
            DependencyInfo(
                name="lzma",
                module_path="lzma",
                category=DependencyCategory.COMPRESSION,
                priority=DependencyPriority.LOW,
                description="LZMA compression (standard library)",
                capabilities=["lzma_compression"],
            ),
            # === SECURITY ===
            DependencyInfo(
                name="cryptography",
                module_path="cryptography",
                category=DependencyCategory.SECURITY,
                priority=DependencyPriority.LOW,
                description="Advanced cryptography",
                install_command="pip install cryptography",
                capabilities=["encryption", "secure_hashing"],
            ),
        ]

        # Register all dependencies
        for dep in standard_deps:
            self._dependencies[dep.name] = dep

    def _initial_check(self) -> None:
        """Initial check of all dependencies."""

        with self._lock:
            self.logger.info("Initial dependency check...")

            for name in self._dependencies:
                self._check_dependency_internal(name)

            available_count = sum(
                1 for dep in self._dependencies.values() if dep.is_available
            )
            total_count = len(self._dependencies)

            self.logger.info(f"Available dependencies: {available_count}/{total_count}")

    def is_available(self, dependency_name: str) -> bool:
        """
        Checks if a dependency is available.

        Args:
            dependency_name: Name of the dependency

        Returns:
            True if the dependency is available
        """
        return self._check_dependency_internal(dependency_name)

    def get_version(self, dependency_name: str) -> Optional[str]:
        """
        Gets the version of a dependency.

        Args:
            dependency_name: Name of the dependency

        Returns:
            Version of the dependency or None
        """
        with self._lock:
            if dependency_name in self._dependencies:
                dep = self._dependencies[dependency_name]
                if dep.is_available:
                    return dep.version
        return None

    def get_fallback_chain(
        self, category: DependencyCategory, capability: Optional[str] = None
    ) -> List[str]:
        """
        Gets a fallback chain for a category.

        Args:
            category: The desired category
            capability: Specific capability required

        Returns:
            Ordered list of available dependencies (best first)
        """
        with self._lock:
            candidates = []

            for name, dep in self._dependencies.items():
                if (
                    dep.category == category
                    and dep.is_available
                    and (capability is None or capability in dep.capabilities)
                ):
                    candidates.append((name, dep.priority.value))

            # Sort by priority
            candidates.sort(key=lambda x: x[1])
            return [name for name, _ in candidates]

    def _check_dependency_internal(self, dependency_name: str) -> bool:
        """Internal check of a dependency with cache."""

        if dependency_name not in self._dependencies:
            return False

        # Check the cache
        cache_key = dependency_name
        cached_result = self._availability_cache.get(cache_key, default=None)
        if cached_result is not None:
            self._stats["cache_hits"] += 1
            return bool(cached_result)

        # Actual check
        with self._lock:
            dep = self._dependencies[dependency_name]
            result = self._perform_dependency_check(dep)

            # Cache the result
            self._availability_cache.set(cache_key, result)
            self._stats["checks_performed"] += 1

            return result

    def _perform_dependency_check(self, dep: DependencyInfo) -> bool:
        """Performs the actual check of a dependency."""

        try:
            # Custom test if provided
            if dep.test_function:
                success = dep.test_function()
                if success:
                    dep.is_available = True
                    dep.import_error = None
                    self._stats["successful_imports"] += 1
                else:
                    dep.is_available = False
                    dep.import_error = "Custom test failed"
                    self._stats["failed_imports"] += 1

                dep.last_checked = time.time()
                return success

            # Standard import
            module = importlib.import_module(dep.module_path)

            # Try to get the version
            version = None
            for version_attr in ["__version__", "version", "VERSION"]:
                if hasattr(module, version_attr):
                    version = getattr(module, version_attr)
                    if isinstance(version, str):
                        break
                    elif hasattr(version, "__str__"):
                        version = str(version)
                        break

            # Success
            dep.is_available = True
            dep.version = version
            dep.import_error = None
            dep.last_checked = time.time()

            self._stats["successful_imports"] += 1
            self.logger.debug(f"Dependency OK: {dep.name} v{version or 'unknown'}")

            return True

        except ImportError as e:
            dep.is_available = False
            dep.version = None
            dep.import_error = str(e)
            dep.last_checked = time.time()

            self._stats["failed_imports"] += 1
            self.logger.debug(f"Missing dependency: {dep.name} - {str(e)}")

            return False

        except Exception as e:
            dep.is_available = False
            dep.import_error = f"Unexpected error: {str(e)}"
            dep.last_checked = time.time()

            self._stats["failed_imports"] += 1
            self.logger.warning(f"Error checking {dep.name}: {e}")

            return False

    @lru_cache(maxsize=32)
    def get_pdf_extractors(self) -> List[str]:
        """Gets the available PDF extractors in order of preference."""
        return self.get_fallback_chain(
            DependencyCategory.PDF_EXTRACTION, "pdf_text_extraction"
        )

    @lru_cache(maxsize=32)
    def get_document_processors(self) -> List[str]:
        """Gets the available document processors."""
        return self.get_fallback_chain(
            DependencyCategory.DOCUMENT_PROCESSING, "docx_text_extraction"
        )

    @lru_cache(maxsize=32)
    def get_metadata_extractors(self) -> List[str]:
        """Gets the available metadata extractors."""
        return self.get_fallback_chain(DependencyCategory.METADATA_EXTRACTION)

    def get_missing_dependencies(
        self, category: Optional[DependencyCategory] = None
    ) -> List[DependencyInfo]:
        """
        Gets the missing dependencies.

        Args:
            category: Specific category (all if None)

        Returns:
            List of missing dependencies
        """
        with self._lock:
            missing = []

            for dep in self._dependencies.values():
                if not dep.is_available and (
                    category is None or dep.category == category
                ):
                    missing.append(dep)

            return missing

    def clear_cache(self) -> None:
        """Clears the check cache."""
        with self._lock:
            self._availability_cache.clear()
            # Clear LRU caches
            self.get_pdf_extractors.cache_clear()
            self.get_document_processors.cache_clear()
            self.get_metadata_extractors.cache_clear()

            self.logger.info("Dependency cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Returns the manager's statistics."""

        with self._lock:
            available_count = sum(
                1 for dep in self._dependencies.values() if dep.is_available
            )

            return {
                "total_dependencies": len(self._dependencies),
                "available_dependencies": available_count,
                "availability_ratio": available_count / max(len(self._dependencies), 1),
                "checks_performed": self._stats["checks_performed"],
                "cache_hits": self._stats["cache_hits"],
                "cache_hit_ratio": self._stats["cache_hits"]
                / max(self._stats["checks_performed"], 1),
                "successful_imports": self._stats["successful_imports"],
                "failed_imports": self._stats["failed_imports"],
                "cache_size": self._availability_cache.size(),
            }


# === GLOBAL INSTANCE ===

# Global instance shared between all services
_global_dependency_manager: Optional[DependencyManager] = None
_manager_lock = threading.Lock()


def get_dependency_manager() -> DependencyManager:
    """
    Gets the global instance of the dependency manager.

    Returns:
        DependencyManager instance (singleton)
    """
    global _global_dependency_manager

    with _manager_lock:
        if _global_dependency_manager is None:
            _global_dependency_manager = DependencyManager()

        return _global_dependency_manager


def reset_dependency_manager() -> None:
    """Resets the global manager (for testing)."""
    global _global_dependency_manager

    with _manager_lock:
        _global_dependency_manager = None
