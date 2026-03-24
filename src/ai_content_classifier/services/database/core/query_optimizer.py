# core/query_optimizer.py
"""Query optimizer with optional omni-cache integration."""

import hashlib
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session
from ai_content_classifier.services.shared.cache_runtime import get_cache_runtime


class QueryOptimizer:
    """Optimize queries with smart cache"""

    def __init__(
        self,
        database_service,
        cache_pool: Optional[Any] = None,
        metrics=None,
        cache_ttl_seconds: int = 300,
    ):
        self.database_service = database_service
        self.cache = cache_pool
        self.metrics = metrics  # PerformanceMetrics
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache_runtime = get_cache_runtime()

    def execute_cached(
        self,
        query_builder: Callable,
        cache_key: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Any:
        """
        Execute query with automatic caching.
        """
        # Si session externe, pas de cache
        if session is not None:
            return self._execute_query(query_builder, session)

        # Generate key when not provided
        if not cache_key:
            cache_key = self._generate_cache_key(query_builder)

        omni_key = f"query:{cache_key}"
        cached_data = self._cache_runtime.get(omni_key, default=None, adapter="memory")
        if cached_data is not None:
            self._record_cache_hit()
            return cached_data

        self._record_cache_miss()
        result = self._execute_query(query_builder, None)
        self._cache_runtime.set(
            omni_key, result, ttl=self.cache_ttl_seconds, adapter="memory"
        )

        return result

    def _execute_query(self, query_builder: Callable, session: Optional[Session]):
        """Execute query"""
        external_session = session is not None
        session = session or self.database_service.Session()

        try:
            query = query_builder(session)

            # Si c'est un objet Query SQLAlchemy
            if hasattr(query, "all"):
                return query.all()
            # If it is already a result
            return query

        finally:
            if not external_session:
                session.close()

    def _generate_cache_key(self, query_builder: Callable) -> str:
        """Generate unique query key"""
        import inspect

        # Utiliser le code source de la fonction
        try:
            source = inspect.getsource(query_builder)
            key_data = f"query_{hashlib.md5(source.encode()).hexdigest()}"
        except (OSError, TypeError):
            # Fallback si on ne peut pas obtenir le source
            key_data = f"query_{id(query_builder)}"

        return key_data

    def _record_cache_hit(self) -> None:
        if self.metrics is not None and hasattr(self.metrics, "cache_hits"):
            self.metrics.cache_hits += 1

    def _record_cache_miss(self) -> None:
        if self.metrics is not None and hasattr(self.metrics, "cache_misses"):
            self.metrics.cache_misses += 1
