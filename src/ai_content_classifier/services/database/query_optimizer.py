"""Query optimizer with optional omni-cache integration."""

import hashlib
from threading import RLock
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from ai_content_classifier.services.shared.cache_runtime import get_cache_runtime


class QueryOptimizer:
    """Optimize queries with smart cache."""

    def __init__(
        self,
        database_service,
        cache_pool: Optional[Any] = None,
        metrics=None,
        cache_ttl_seconds: int = 300,
    ):
        self.database_service = database_service
        self.cache = cache_pool
        self.metrics = metrics
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache_runtime = get_cache_runtime()
        self._cache_keys: set[str] = set()
        self._cache_keys_lock = RLock()

    def execute_cached(
        self,
        query_builder: Callable,
        cache_key: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Any:
        """Execute query with automatic caching."""
        if session is not None:
            return self._execute_query(query_builder, session)

        if not cache_key:
            cache_key = self._generate_cache_key(query_builder)

        omni_key = f"query:{cache_key}"
        cached_data = self._cache_runtime.get(omni_key, default=None, adapter="memory")
        if cached_data is not None:
            self._record_cache_hit()
            return cached_data

        self._record_cache_miss()
        result = self._execute_query(query_builder, None)
        cached = self._cache_runtime.set(
            omni_key, result, ttl=self.cache_ttl_seconds, adapter="memory"
        )
        if cached:
            with self._cache_keys_lock:
                self._cache_keys.add(omni_key)

        return result

    def invalidate_all(self) -> None:
        """Invalidate all query cache entries created by this optimizer."""
        with self._cache_keys_lock:
            keys = list(self._cache_keys)
            self._cache_keys.clear()

        for key in keys:
            self._cache_runtime.delete(key, adapter="memory")

    def _execute_query(self, query_builder: Callable, session: Optional[Session]):
        """Execute query."""
        external_session = session is not None
        session = session or self.database_service.Session()

        try:
            query = query_builder(session)
            if hasattr(query, "all"):
                return query.all()
            return query
        except Exception:
            if not external_session:
                try:
                    session.rollback()
                except Exception:
                    pass
            raise
        finally:
            if not external_session:
                session.close()

    def _generate_cache_key(self, query_builder: Callable) -> str:
        """Generate unique query key."""
        import inspect

        try:
            source = inspect.getsource(query_builder)
            key_data = f"query_{hashlib.md5(source.encode()).hexdigest()}"
        except (OSError, TypeError):
            key_data = f"query_{id(query_builder)}"

        return key_data

    def _record_cache_hit(self) -> None:
        if self.metrics is not None and hasattr(self.metrics, "cache_hits"):
            self.metrics.cache_hits += 1

    def _record_cache_miss(self) -> None:
        if self.metrics is not None and hasattr(self.metrics, "cache_misses"):
            self.metrics.cache_misses += 1
