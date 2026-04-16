"""High-level content DB facade with unified operation result contracts."""

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from ai_content_classifier.core.logger import LoggableMixin
from ai_content_classifier.core.memory.metrics.performance_metrics import (
    PerformanceMetrics,
)
from ai_content_classifier.repositories.content_repository import (
    ContentFilter,
    ContentRepositoryFactory,
    UnitOfWork,
)
from ai_content_classifier.services.database import utils
from ai_content_classifier.services.database.content_reader import ContentReader
from ai_content_classifier.services.database.content_writer import ContentWriter
from ai_content_classifier.services.database.database_service import DatabaseService
from ai_content_classifier.services.database.query_optimizer import QueryOptimizer
from ai_content_classifier.services.database.types import (
    DatabaseOperationResult,
)


class ContentDatabaseService(LoggableMixin):
    """Thin facade delegating reads to ``ContentReader`` and writes to ``ContentWriter``."""

    def __init__(
        self,
        database_service: "DatabaseService",
        query_optimizer: QueryOptimizer,
        metrics: PerformanceMetrics,
    ):
        self.__init_logger__()
        self.database_service = database_service
        self.query_optimizer = query_optimizer
        self.metrics = metrics
        self.repos = ContentRepositoryFactory(database_service)
        self.reader = ContentReader(database_service, query_optimizer, metrics)
        self.writer = ContentWriter(database_service, self.repos)

    def create_unit_of_work(self) -> UnitOfWork:
        return self.writer.repos.create_unit_of_work()

    def _invalidate_query_cache(self) -> None:
        """Invalidate cached query results after successful write operations."""
        try:
            if hasattr(self.query_optimizer, "invalidate_all"):
                self.query_optimizer.invalidate_all()
        except Exception as exc:
            self.logger.debug(f"Query cache invalidation failed: {exc}")

    def _invalidate_on_success(self, result: DatabaseOperationResult) -> None:
        if result.success:
            self._invalidate_query_cache()

    def serialize_metadata_for_json(
        self, metadata: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        return utils.serialize_metadata_for_json(metadata)

    def force_database_sync(self) -> None:
        try:
            with self.database_service.get_session() as session:
                session.execute(text("PRAGMA wal_checkpoint(PASSIVE);"))
            self.logger.debug("Database synchronization forced.")
        except Exception as exc:
            self.logger.debug(
                "Database sync failed (this is normal for non-SQLite or specific configurations): "
                f"{exc}"
            )

    def count_all_items(
        self, session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        return self.reader.count_all_items(session)

    def create_content_item(
        self,
        path: str,
        content_type: str,
        extract_basic_info: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        refresh: bool = True,
        session: Optional[Session] = None,
    ) -> DatabaseOperationResult:
        result = self.writer.create_content_item(
            path, content_type, extract_basic_info, metadata, refresh, session
        )
        self._invalidate_on_success(result)
        return result

    def save_item_batch(
        self,
        items: List[Dict[str, Any]],
        refresh: bool = True,
        session: Optional[Session] = None,
    ) -> DatabaseOperationResult:
        result = self.writer.save_item_batch(items, refresh, session)
        self._invalidate_on_success(result)
        return result

    def update_metadata_batch(
        self,
        metadata_updates: List[Tuple[int, Dict[str, Any]]],
        refresh: bool = False,
        session: Optional[Session] = None,
    ) -> DatabaseOperationResult:
        result = self.writer.update_metadata_batch(metadata_updates, refresh, session)
        self._invalidate_on_success(result)
        return result

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
    ) -> DatabaseOperationResult:
        return self.reader.find_items(
            content_filter,
            sort_by,
            sort_desc,
            limit,
            offset,
            eager_load,
            custom_filter,
            session,
        )

    def get_items_pending_metadata(
        self,
        content_type: Optional[str] = None,
        limit: Optional[int] = None,
        eager_load: bool = False,
        session: Optional[Session] = None,
    ) -> DatabaseOperationResult:
        return self.reader.get_items_pending_metadata(
            content_type, limit, eager_load, session
        )

    def find_duplicates(
        self, session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        return self.reader.find_duplicates(session)

    def get_statistics(
        self, session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        return self.reader.get_statistics(session)

    def get_content_by_path(
        self, file_path: str, session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        return self.reader.get_content_by_path(file_path, session)

    def compute_file_hash(self, file_path: str) -> Optional[str]:
        return utils.compute_file_hash(file_path)

    def update_content_category(
        self,
        file_path: str,
        category: str,
        confidence: float,
        extraction_method: str,
        extraction_details: str,
        session: Optional[Session] = None,
    ) -> DatabaseOperationResult:
        result = self.writer.update_content_category(
            file_path,
            category,
            confidence,
            extraction_method,
            extraction_details,
            session,
        )
        self._invalidate_on_success(result)
        return result

    def get_uncategorized_items(
        self, content_type: Optional[str] = None, session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        return self.reader.get_uncategorized_items(content_type, session)

    def clear_content_category(
        self, file_path: str, session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        result = self.writer.clear_content_category(file_path, session)
        self._invalidate_on_success(result)
        return result

    def get_unique_categories(
        self, session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        return self.reader.get_unique_categories(session)

    def get_unique_years(
        self, session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        return self.reader.get_unique_years(session)

    def get_unique_extensions(
        self, session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        return self.reader.get_unique_extensions(session)

    def clear_all_content(
        self, session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        result = self.writer.clear_all_content(session)
        self._invalidate_on_success(result)
        return result

    def delete_content_by_paths(
        self, file_paths: List[str], session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        result = self.writer.delete_content_by_paths(file_paths, session)
        self._invalidate_on_success(result)
        return result
