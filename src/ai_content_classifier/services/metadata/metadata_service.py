"""
Metadata extraction service module with corrected cache implementation.
"""

import importlib
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from ai_content_classifier.core.logger import LoggableMixin
from ai_content_classifier.services.metadata.extractors.base_extractor import (
    BaseMetadataExtractor,
)
from ai_content_classifier.services.shared.cache_runtime import get_cache_runtime


class MetadataService(LoggableMixin):
    """
    Main metadata extraction service that uses
    appropriate specialized extractors based on file type.
    """

    DEFAULT_CACHE_SIZE = 256

    DEFAULT_EXTRACTORS = [
        "ai_content_classifier.services.metadata.extractors.pillow_extractor.PillowImageExtractor",
        "ai_content_classifier.services.metadata.extractors.pypdf_extractor.PyPDFExtractor",
        "ai_content_classifier.services.metadata.extractors.text_metadata_extractor.TextMetadataExtractor",
        "ai_content_classifier.services.metadata.extractors.hachoir_extractor.HachoirExtractor",
    ]

    def __init__(
        self,
        extractors: Optional[List[str]] = None,
        cache_ttl_seconds: int = 1800,
    ):
        """
        Initialize the metadata service.

        Args:
            extractors: Optional list of extractor class paths to load
        """
        self.__init_logger__()
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache_runtime = get_cache_runtime()
        self._metadata_cache = self._cache_runtime.memory_cache(
            "metadata:entries",
            default_ttl=cache_ttl_seconds,
        )
        self.extractors: List[BaseMetadataExtractor] = []

        # Load extractors
        extractor_paths = extractors or self.DEFAULT_EXTRACTORS
        self._load_extractors(extractor_paths)

        self.logger.info(
            f"Metadata service initialized with {len(self.extractors)} extractors"
        )

    def _load_extractors(self, extractor_paths: List[str]) -> None:
        """Load extractors from their module paths."""
        for extractor_path in extractor_paths:
            try:
                module_path, class_name = extractor_path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                extractor_class = getattr(module, class_name)
                extractor = extractor_class()
                self.extractors.append(extractor)
                self.logger.debug(f"Loaded extractor: {class_name}")

            except (ImportError, AttributeError, ValueError) as e:
                self.logger.error(
                    f"Failed to load extractor {extractor_path}: {str(e)}"
                )

    def _validate_file_exists(self, file_path: str) -> bool:
        """Validate that the file exists and is accessible."""
        if not file_path or not isinstance(file_path, str):
            self.logger.error("Invalid file path: empty or not a string")
            return False

        if not os.path.isfile(file_path):
            self.logger.error(f"File not found: {file_path}")
            return False

        if not os.access(file_path, os.R_OK):
            self.logger.error(f"File not readable: {file_path}")
            return False

        return True

    def _find_suitable_extractor(
        self, file_path: str
    ) -> Optional[BaseMetadataExtractor]:
        """Find the most appropriate extractor for the file."""
        for extractor in self.extractors:
            try:
                if extractor.can_handle(file_path):
                    self.logger.debug(
                        f"Selected extractor for {file_path}: {extractor.__class__.__name__}"
                    )
                    return extractor
            except Exception as e:
                self.logger.warning(
                    f"Extractor {extractor.__class__.__name__} failed during can_handle: {str(e)}"
                )

        self.logger.warning(f"No suitable extractor found for: {file_path}")
        return None

    def _extract_metadata_for_file(self, file_path: str) -> Dict[str, Any]:
        """
        Extract metadata for a file without using cache.
        This is the core extraction logic separated from caching.
        """
        # Validate file exists
        if not self._validate_file_exists(file_path):
            return {"error": f"File not found or not accessible: {file_path}"}

        # Find the appropriate extractor
        extractor = self._find_suitable_extractor(file_path)
        if not extractor:
            return {
                "error": f"No suitable extractor available for this file type: {file_path}"
            }

        try:
            # Extract metadata
            metadata = extractor.get_metadata(file_path)

            # Add extraction metadata
            metadata["_extracted_by"] = extractor.__class__.__name__
            metadata["_extraction_time"] = datetime.now().isoformat()
            metadata["_file_path"] = file_path

            # Normalize year using strict priority:
            # 1) metadata date/year when available
            # 2) filesystem mtime fallback
            normalized_year = self._extract_year_from_metadata(metadata)
            if normalized_year is None:
                normalized_year = datetime.fromtimestamp(
                    os.path.getmtime(file_path)
                ).year

            metadata["year"] = int(normalized_year)
            metadata["year_taken"] = int(normalized_year)

            return metadata

        except Exception as e:
            self.logger.error(f"Error extracting metadata from {file_path}: {str(e)}")
            return {"error": str(e)}

    def _extract_year_from_metadata(self, metadata: Dict[str, Any]) -> Optional[int]:
        """Extract a valid year from metadata values."""
        for key in (
            "year",
            "year_taken",
            "creation_date",
            "date_created",
            "date",
            "created",
            "timestamp",
            "DateTimeOriginal",
            "datetime_original",
        ):
            if key not in metadata:
                continue
            year = self._extract_year_value(metadata.get(key))
            if year is not None:
                return year
        return None

    def _extract_year_value(self, raw_value: Any) -> Optional[int]:
        """Parse a year in [1900, 2100] from mixed metadata values."""
        if raw_value is None:
            return None

        if isinstance(raw_value, datetime):
            year = raw_value.year
            return year if 1900 <= year <= 2100 else None

        if isinstance(raw_value, int):
            return raw_value if 1900 <= raw_value <= 2100 else None

        text = str(raw_value).strip()
        if not text:
            return None

        match = re.search(r"(19\d{2}|20\d{2}|2100)", text)
        if not match:
            return None

        year = int(match.group(1))
        return year if 1900 <= year <= 2100 else None

    def get_all_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract all available metadata from the file using cache.
        """
        cache_key = self._build_cache_key(file_path)

        cached_metadata = self._metadata_cache.get(cache_key, default=None)
        if self._is_valid_cached_metadata(cached_metadata, file_path):
            return dict(cached_metadata)

        try:
            metadata = self._extract_metadata_for_file(file_path)
            self._metadata_cache.set(cache_key, metadata)
            return metadata

        except Exception as e:
            # Fallback to direct extraction
            self.logger.debug(
                "Metadata cache path failed, using direct extraction: %s", e
            )
            metadata = self._extract_metadata_for_file(file_path)
            self._metadata_cache.set(cache_key, metadata)
            return metadata

    def clear_cache(self) -> None:
        """Clear the metadata cache."""
        self._metadata_cache.clear()
        self.logger.info("Metadata cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the current cache state."""
        cache_stats = self._metadata_cache.get_stats()
        omni_stats: Dict[str, Any] = {}
        runtime_manager = self._cache_runtime.manager
        if runtime_manager is not None:
            try:
                omni_stats = runtime_manager.get_adapter_stats("memory")
            except Exception:
                omni_stats = {}

        return {
            "cache_size": self._metadata_cache.size(),
            "max_cache_size": self.DEFAULT_CACHE_SIZE,
            "cache_hits": cache_stats.get("hits", 0),
            "cache_misses": cache_stats.get("misses", 0),
            "total_objects": self._metadata_cache.size(),
            "active_objects": 0,
            "extractors_count": len(self.extractors),
            "extractors": [ext.__class__.__name__ for ext in self.extractors],
            "omni_cache_available": self._cache_runtime.is_available(),
            "omni_cache_stats": omni_stats,
        }

    def _build_cache_key(self, file_path: str) -> str:
        """Build stable metadata cache key."""
        normalized_path = os.path.abspath(os.path.normpath(file_path))
        return f"metadata:{normalized_path}"

    @staticmethod
    def _is_valid_cached_metadata(cached_metadata: Any, file_path: str) -> bool:
        return bool(
            cached_metadata
            and isinstance(cached_metadata, dict)
            and cached_metadata.get("_extraction_time") is not None
            and cached_metadata.get("_file_path") == file_path
            and not cached_metadata.get("error")
        )
