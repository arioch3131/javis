# operations/enhanced_reader.py
"""
Enhanced reader wrapping legacy reader with optimizations.
"""

import hashlib
from typing import Any, List, Optional

from sqlalchemy.orm import Session

from ai_content_classifier.repositories.content_repository import ContentFilter
from ai_content_classifier.services.database.content_reader import (
    ContentItem,
    ContentReader,
)


class EnhancedContentReader:
    """
    Enhanced reader with cache and metrics.
    Wraps existing ContentReader for full compatibility.
    """

    def __init__(self, database_service, query_optimizer, metrics):
        self.database_service = database_service
        self.query_optimizer = query_optimizer
        self.metrics = metrics

        # Keep legacy reader for compatibility
        self._legacy_reader = ContentReader(database_service)

    def find_items(
        self,
        content_filter: Optional[ContentFilter] = None,
        sort_by: Optional[str] = None,
        sort_desc: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
        eager_load: bool = False,
        custom_filter: Optional[List[Any]] = None,
        session: Optional[Session] = None,
    ) -> List[ContentItem]:
        """
        find_items method with optional cache.
        Same signature for compatibility.
        """

        # If an external session is provided, use legacy behavior (no cache).
        if session is not None:
            return self._legacy_reader.find_items(
                content_filter,
                sort_by,
                sort_desc,
                limit,
                offset,
                eager_load,
                custom_filter,
                session,
            )

        # Create a cache key based on settings
        cache_key = self._build_cache_key(
            "find_items",
            content_filter,
            sort_by,
            sort_desc,
            limit,
            offset,
            eager_load,
            custom_filter,
        )

        # Build query callable.
        def query_builder(session):
            return self._legacy_reader.find_items(
                content_filter,
                sort_by,
                sort_desc,
                limit,
                offset,
                eager_load,
                custom_filter,
                session,
            )

        # Execute with cache
        results = self.query_optimizer.execute_cached(
            query_builder, cache_key=cache_key
        )

        # Update metrics
        self.metrics.visible_items = len(results)

        return results

    def count_all_items(self, session: Optional[Session] = None) -> int:
        """Count items with cache when no external session is provided."""

        if session is not None:
            return self._legacy_reader.count_all_items(session)

        def query_builder(session):
            return self._legacy_reader.count_all_items(session)

        count = self.query_optimizer.execute_cached(
            query_builder, cache_key="count_all_items"
        )

        self.metrics.total_files = count
        return count

    def get_unique_categories(self, session: Optional[Session] = None) -> List[str]:
        """Return unique categories with cache when no external session is provided."""
        if session is not None:
            return self._legacy_reader.get_unique_categories(session)

        def query_builder(session):
            return self._legacy_reader.get_unique_categories(session)

        return self.query_optimizer.execute_cached(
            query_builder, cache_key="unique_categories"
        )

    def get_unique_years(self, session: Optional[Session] = None) -> List[int]:
        """Return unique years with cache when no external session is provided."""
        if session is not None:
            return self._legacy_reader.get_unique_years(session)

        def query_builder(session):
            return self._legacy_reader.get_unique_years(session)

        return self.query_optimizer.execute_cached(
            query_builder, cache_key="unique_years"
        )

    def get_unique_extensions(self, session: Optional[Session] = None) -> List[str]:
        """Return unique extensions with cache when no external session is provided."""
        if session is not None:
            return self._legacy_reader.get_unique_extensions(session)

        def query_builder(session):
            return self._legacy_reader.get_unique_extensions(session)

        return self.query_optimizer.execute_cached(
            query_builder, cache_key="unique_extensions"
        )

    def __getattr__(self, name):
        """
        Automatic delegation to legacy reader for all
        other methods. Ensures full compatibility.
        """
        return getattr(self._legacy_reader, name)

    def _build_cache_key(self, *args) -> str:
        """Build a unique cache key"""
        import json

        key_data = json.dumps(args, default=str, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()
