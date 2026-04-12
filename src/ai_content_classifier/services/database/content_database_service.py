"""Content Database Service Module.
This module provides a high-level API for managing content items and their metadata
within the application's database. It leverages a repository pattern for efficient
batch operations, flexible querying, and robust error handling, ensuring data
consistency and integrity.
"""

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_content_classifier.core.logger import LoggableMixin
from ai_content_classifier.models.content_models import ContentItem
from ai_content_classifier.repositories.content_repository import (
    ContentFilter,
    ContentRepositoryFactory,
    UnitOfWork,
)
from ai_content_classifier.services.database.operations.enhanced_reader import (
    EnhancedContentReader,
)
from ai_content_classifier.services.database.content_writer import ContentWriter
from ai_content_classifier.services.database.database_service import DatabaseService
from ai_content_classifier.services.database.core.query_optimizer import QueryOptimizer
from ai_content_classifier.core.memory.metrics.performance_metrics import (
    PerformanceMetrics,
)
from ai_content_classifier.services.database import utils


class ContentDatabaseService(LoggableMixin):
    """A comprehensive service for managing content items and their associated data in the database.
    This service acts as an abstraction layer over the content repositories, providing
    a simplified and robust interface for common database operations such as creating,
    updating, querying, and deleting content items, including batch processing and
    metadata management.

    Attributes:
        database_service (DatabaseService): An instance of `DatabaseService` for managing
                                            database connections and sessions.
        reader (ContentReader): An instance of `ContentReader` for read-only operations.
        writer (ContentWriter): An instance of `ContentWriter` for write operations.
    """

    def __init__(
        self,
        database_service: "DatabaseService",
        query_optimizer: QueryOptimizer,  # New dependency
        metrics: PerformanceMetrics,  # New dependency
    ):
        """
        Initializes the `ContentDatabaseService`.

        Args:
            database_service (DatabaseService): The database service instance to be used
                                                for all database interactions.
        """
        self.__init_logger__()
        self.database_service = database_service
        self.query_optimizer = query_optimizer  # Assign new dependency
        self.metrics = metrics  # Assign new dependency
        self.repos = ContentRepositoryFactory(database_service)
        self.reader = EnhancedContentReader(
            database_service, query_optimizer, metrics
        )  # Use EnhancedContentReader
        self.writer = ContentWriter(database_service, self.repos)

    def create_unit_of_work(self) -> UnitOfWork:
        return self.writer.repos.create_unit_of_work()

    def _invalidate_query_cache(self) -> None:
        """Invalidate cached query results after write operations."""
        try:
            if hasattr(self.query_optimizer, "invalidate_all"):
                self.query_optimizer.invalidate_all()
        except Exception as e:
            self.logger.debug(f"Query cache invalidation failed: {e}")

    def serialize_metadata_for_json(
        self, metadata: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        return utils.serialize_metadata_for_json(metadata)

    def force_database_sync(self) -> None:
        try:
            session = self.database_service.Session()
            try:
                session.execute(text("PRAGMA wal_checkpoint(PASSIVE);"))
                session.commit()
                self.logger.debug("Database synchronization forced.")
            except Exception as e:
                self.logger.debug(
                    f"Database sync failed (this is normal for non-SQLite or specific configurations): {e}"
                )
            finally:
                session.close()
        except Exception as e:
            self.logger.debug(
                f"Could not force database sync due to session acquisition error: {e}"
            )

    def count_all_items(self, session: Optional[Session] = None) -> int:
        return self.reader.count_all_items(session)

    def create_content_item(
        self,
        path: str,
        content_type: str,
        extract_basic_info: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        refresh: bool = True,
        session: Optional[Session] = None,
    ) -> ContentItem:
        item = self.writer.create_content_item(
            path, content_type, extract_basic_info, metadata, refresh, session
        )
        self._invalidate_query_cache()
        return item

    def save_item_batch(
        self,
        items: List[Dict[str, Any]],
        refresh: bool = True,
        session: Optional[Session] = None,
    ) -> List[ContentItem]:
        saved_items = self.writer.save_item_batch(items, refresh, session)
        if saved_items:
            self._invalidate_query_cache()
        return saved_items

    def update_metadata_batch(
        self,
        metadata_updates: List[Tuple[int, Dict[str, Any]]],
        refresh: bool = False,
        session: Optional[Session] = None,
    ) -> int:
        updated_count = self.writer.update_metadata_batch(
            metadata_updates, refresh, session
        )
        if updated_count > 0:
            self._invalidate_query_cache()
        return updated_count

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
    ) -> List[ContentItem]:
        return self.reader.get_items_pending_metadata(
            content_type, limit, eager_load, session
        )

    def find_duplicates(
        self, session: Optional[Session] = None
    ) -> Dict[str, List[ContentItem]]:
        return self.reader.find_duplicates(session)

    def get_statistics(self, session: Optional[Session] = None) -> Dict[str, Any]:
        return self.reader.get_statistics(session)

    def get_content_by_path(
        self, file_path: str, session: Optional[Session] = None
    ) -> Optional[ContentItem]:
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
    ) -> Optional[ContentItem]:
        item = self.writer.update_content_category(
            file_path,
            category,
            confidence,
            extraction_method,
            extraction_details,
            session,
        )
        if item is not None:
            self._invalidate_query_cache()
        return item

    def get_uncategorized_items(
        self, content_type: Optional[str] = None, session: Optional[Session] = None
    ) -> List[ContentItem]:
        return self.reader.get_uncategorized_items(content_type, session)

    def clear_content_category(
        self, file_path: str, session: Optional[Session] = None
    ) -> Optional[ContentItem]:
        item = self.writer.clear_content_category(file_path, session)
        if item is not None:
            self._invalidate_query_cache()
        return item

    def get_unique_categories(self) -> List[str]:
        return self.reader.get_unique_categories()

    def get_unique_years(self) -> List[int]:
        return self.reader.get_unique_years()

    def get_unique_extensions(self) -> List[str]:
        return self.reader.get_unique_extensions()

    def clear_all_content(self, session: Optional[Session] = None) -> int:
        """Deletes all content items from the database."""
        external_session = session is not None
        session = session or self.database_service.Session()
        try:
            num_deleted = session.query(ContentItem).delete(synchronize_session="fetch")
            if not external_session:
                session.commit()
            self.logger.info(f"Successfully deleted {num_deleted} content items.")
            if num_deleted > 0:
                self._invalidate_query_cache()
            return num_deleted
        except SQLAlchemyError as e:
            if not external_session:
                session.rollback()
            self.logger.error(f"Error clearing all content items: {e}")
            raise
        finally:
            if not external_session:
                session.close()

    def delete_content_by_paths(
        self, file_paths: List[str], session: Optional[Session] = None
    ) -> int:
        """Deletes content items matching the provided file paths."""
        normalized_paths = [
            str(path) for path in dict.fromkeys(file_paths or []) if path
        ]
        if not normalized_paths:
            return 0

        external_session = session is not None
        session = session or self.database_service.Session()
        try:
            num_deleted = (
                session.query(ContentItem)
                .filter(ContentItem.path.in_(normalized_paths))
                .delete(synchronize_session="fetch")
            )
            if not external_session:
                session.commit()
            self.logger.info(
                f"Successfully deleted {num_deleted} content items by path."
            )
            if num_deleted > 0:
                self._invalidate_query_cache()
            return int(num_deleted)
        except SQLAlchemyError as e:
            if not external_session:
                session.rollback()
            self.logger.error(f"Error deleting content items by path: {e}")
            raise
        finally:
            if not external_session:
                session.close()
