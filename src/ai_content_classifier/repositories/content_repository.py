from contextlib import contextmanager
from types import TracebackType
from typing import TYPE_CHECKING, Any, Generator, Generic, List, Optional, Type, TypeVar

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_content_classifier.core.logger import LoggableMixin
from ai_content_classifier.models.content_models import (
    Audio,
    ContentItem,
    Document,
    Image,
    Video,
)

if TYPE_CHECKING:
    from ai_content_classifier.services.database.database_service import DatabaseService

# Generic type for ContentItem subclasses
T = TypeVar("T", bound=ContentItem)


class UnitOfWork:
    """
    Unit of Work pattern to manage database transactions.

    This class provides a way to work with a session that stays open
    for multiple operations, and manages the commit/rollback process.
    """

    def __init__(self, db_service: "DatabaseService"):
        """Initialize with a database service."""
        self.db_service = db_service
        self._session: Session | None = None

    def __enter__(self) -> Session:
        """Start a new session when entering the context."""
        self._session = self.db_service.Session()
        return self._session

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Close the session when exiting the context."""
        if self._session is None:
            return
        try:
            if exc_type is not None:
                # An exception occurred, rollback
                self._session.rollback()
            else:
                # No exception, commit
                self._session.commit()
        finally:
            self._session.close()
            self._session = None


class ContentFilter:
    """Class for building complex content filters."""

    def __init__(self) -> None:
        self.criteria: list[Any] = []

    def by_type(self, content_type: str) -> "ContentFilter":
        """Filter by content type."""
        self.criteria.append(ContentItem.content_type == content_type)
        return self

    def build(self) -> List[Any]:
        """Build filter criteria."""
        return self.criteria


class ContentRepository(Generic[T], LoggableMixin):
    """
    Improved generic repository for ContentItem models with better session management.
    """

    def __init__(self, database_service: "DatabaseService", model_class: Type[T]):
        """
        Initialize the repository.

        Args:
            database_service: Database service instance
            model_class: The model class this repository handles
        """
        self.__init_logger__()
        self.database_service = database_service
        self.model_class = model_class

    def create_unit_of_work(self) -> UnitOfWork:
        """
        Create a new unit of work for transaction management.

        Returns:
            UnitOfWork: A new unit of work context manager
        """
        return UnitOfWork(self.database_service)

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """
        Get a database session (maintained for backwards compatibility).

        Yields:
            Session: A SQLAlchemy database session
        """
        with self.database_service.get_session() as session:
            yield session

    def count(self, filter_criteria: Optional[List] = None) -> int:
        """Count items matching criteria."""
        with self.session() as session:
            query = session.query(func.count(self.model_class.id))
            if filter_criteria:
                query = query.filter(*filter_criteria)
            result = query.scalar()
            return int(result or 0)

    def save(self, item: T, refresh: bool = True) -> T:
        """
        Save an item to the database with option to refresh it.

        Args:
            item: The item to save
            refresh: Whether to refresh the item from database after save

        Returns:
            The saved (and optionally refreshed) item
        """
        with self.session() as session:
            try:
                is_new = item.id is None

                if is_new:  # New item
                    session.add(item)
                    self.logger.debug(f"Created new {self.model_class.__name__} record")
                else:  # Existing item
                    item = session.merge(item)
                    self.logger.debug(
                        f"Updated {self.model_class.__name__} record (id={item.id})"
                    )

                session.commit()

                if refresh and item.id is not None:
                    # Utiliser session.get() au lieu de session.query().get()
                    refreshed_item = session.get(self.model_class, item.id)
                    if refreshed_item is not None:
                        return refreshed_item

                return item
            except SQLAlchemyError as e:
                session.rollback()
                self.logger.error(f"Error saving {self.model_class.__name__}: {e}")
                raise

    def delete(self, item_id: int) -> bool:
        """Delete an item by ID."""
        with self.session() as session:
            try:
                item = (
                    session.query(self.model_class)
                    .filter(self.model_class.id == item_id)
                    .first()
                )
                if item:
                    session.delete(item)
                    session.commit()
                    self.logger.debug(
                        f"Deleted {self.model_class.__name__} (id={item_id})"
                    )
                    return True
                return False
            except SQLAlchemyError as e:
                session.rollback()
                self.logger.error(f"Error deleting {self.model_class.__name__}: {e}")
                raise


class ContentRepositoryFactory(LoggableMixin):
    """Factory for creating type-specific repositories."""

    def __init__(self, database_service: "DatabaseService"):
        """Initialize the factory."""
        self.__init_logger__()
        self.database_service = database_service

        # Initialize repositories
        self._content_repo = ContentRepository(database_service, ContentItem)
        self._image_repo = ContentRepository(database_service, Image)
        self._document_repo = ContentRepository(database_service, Document)
        self._video_repo = ContentRepository(database_service, Video)
        self._audio_repo = ContentRepository(database_service, Audio)

    def create_unit_of_work(self) -> UnitOfWork:
        """Create a new unit of work for transaction management."""
        return UnitOfWork(self.database_service)

    @property
    def content(self) -> ContentRepository[ContentItem]:
        """Get the generic content repository."""
        return self._content_repo

    @property
    def images(self) -> ContentRepository[Image]:
        """Get the image repository."""
        return self._image_repo
