import pytest

from unittest.mock import MagicMock
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from ai_content_classifier.models.content_models import ContentItem, Image

from ai_content_classifier.repositories.content_repository import (
    ContentRepository,
    ContentRepositoryFactory,
    UnitOfWork,
    ContentFilter,
)

from ai_content_classifier.services.database.database_service import DatabaseService


# Fixtures
@pytest.fixture
def mock_db_service():
    """Fixture for a mock DatabaseService."""
    db_service = MagicMock(spec=DatabaseService)
    # Create a single mock session that will be used by all contexts
    _mock_session_instance = MagicMock(spec=Session)

    # Mock Session to be a callable that returns the single mock session instance
    db_service.Session = MagicMock(return_value=_mock_session_instance)

    # Mock get_session to return a context manager that yields the single mock session instance
    mock_session_context_manager = MagicMock()
    mock_session_context_manager.__enter__.return_value = _mock_session_instance
    mock_session_context_manager.__exit__.return_value = None
    db_service.get_session.return_value = mock_session_context_manager
    return db_service


@pytest.fixture
def mock_session(mock_db_service):
    """Fixture for a mock SQLAlchemy Session."""
    # This will now return the single mock session instance created in mock_db_service
    return mock_db_service.get_session.return_value.__enter__.return_value


@pytest.fixture
def content_repository(mock_db_service):
    """Fixture for ContentRepository with a mock DatabaseService and ContentItem model."""
    return ContentRepository(mock_db_service, ContentItem)


@pytest.fixture
def image_repository(mock_db_service):
    """Fixture for ContentRepository with a mock DatabaseService and Image model."""
    return ContentRepository(mock_db_service, Image)


# Tests for UnitOfWork
class TestUnitOfWork:
    def test_unit_of_work_commit_on_exit(self, mock_db_service):
        mock_session = mock_db_service.Session.return_value
        with UnitOfWork(mock_db_service) as session:
            assert session is mock_session
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.rollback.assert_not_called()

    def test_unit_of_work_rollback_on_exception(self, mock_db_service):
        mock_session = mock_db_service.Session.return_value
        with pytest.raises(ValueError):
            with UnitOfWork(mock_db_service) as session:
                assert session is mock_session
                raise ValueError("Test error")
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.commit.assert_not_called()


# Tests for ContentFilter
class TestContentFilter:
    def test_content_filter_by_type(self):
        filters = ContentFilter().by_type("image").build()
        assert len(filters) == 1
        assert str(filters[0]) == str(ContentItem.content_type == "image")


# Tests for ContentRepository
class TestContentRepository:
    def test_create_unit_of_work(self, content_repository):
        uow = content_repository.create_unit_of_work()
        assert isinstance(uow, UnitOfWork)

    def test_session_context_manager(self, content_repository, mock_session):
        with content_repository.session() as session:
            assert session is mock_session
        mock_session.commit.assert_not_called()  # Session is managed by get_session context
        mock_session.close.assert_not_called()  # Session is managed by get_session context

    def test_count(self, content_repository, mock_session):
        # Mock the entire chain of calls for count
        mock_query_result = MagicMock()
        mock_query_result.scalar.return_value = 5
        mock_session.query.return_value = mock_query_result
        count = content_repository.count()
        assert count == 5
        mock_session.query.assert_called_once()
        mock_query_result.scalar.assert_called_once()

    def test_count_with_filter(self, content_repository, mock_session):
        mock_query_result = MagicMock()
        mock_query_result.filter.return_value.scalar.return_value = 3
        mock_session.query.return_value = mock_query_result
        filters = [ContentItem.content_type == "image"]
        count = content_repository.count(filter_criteria=filters)
        assert count == 3
        mock_query_result.filter.assert_called_once_with(*filters)
        mock_query_result.filter.return_value.scalar.assert_called_once()

    def test_save_new_item(self, content_repository, mock_session):
        new_item = MagicMock(spec=ContentItem, id=None)

        # Simulate id being set after add/commit
        def set_id_side_effect(*args, **kwargs):
            new_item.id = 1

        mock_session.add.side_effect = set_id_side_effect
        mock_session.get.return_value = new_item  # For refresh

        saved_item = content_repository.save(new_item)
        mock_session.add.assert_called_once_with(new_item)
        mock_session.commit.assert_called_once()
        mock_session.get.assert_called_once_with(content_repository.model_class, 1)
        assert saved_item is new_item

    def test_save_existing_item(self, content_repository, mock_session):
        existing_item = MagicMock(spec=ContentItem, id=1)
        mock_session.merge.return_value = existing_item
        mock_session.get.return_value = existing_item  # For refresh
        saved_item = content_repository.save(existing_item)
        mock_session.merge.assert_called_once_with(existing_item)
        mock_session.commit.assert_called_once()
        mock_session.get.assert_called_once_with(content_repository.model_class, 1)
        assert saved_item is existing_item

    def test_save_no_refresh(self, content_repository, mock_session):
        new_item = MagicMock(spec=ContentItem, id=None)

        def set_id_side_effect(*args, **kwargs):
            new_item.id = 1

        mock_session.add.side_effect = set_id_side_effect
        saved_item = content_repository.save(new_item, refresh=False)
        mock_session.add.assert_called_once_with(new_item)
        mock_session.commit.assert_called_once()
        mock_session.get.assert_not_called()
        assert saved_item is new_item

    def test_save_sqlalchemy_error(self, content_repository, mock_session):
        mock_session.add.side_effect = SQLAlchemyError("Test error")
        with pytest.raises(SQLAlchemyError, match="Test error"):
            content_repository.save(MagicMock(spec=ContentItem, id=None))
        mock_session.rollback.assert_called_once()

    def test_delete(self, content_repository, mock_session):
        mock_item = MagicMock(spec=ContentItem, id=1)
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_item
        )
        result = content_repository.delete(1)
        mock_session.delete.assert_called_once_with(mock_item)
        mock_session.commit.assert_called_once()
        assert result is True

    def test_delete_not_found(self, content_repository, mock_session):
        mock_session.query.return_value.filter.return_value.first.return_value = None
        result = content_repository.delete(1)
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()
        assert result is False

    def test_delete_sqlalchemy_error(self, content_repository, mock_session):
        mock_session.query.return_value.filter.return_value.first.side_effect = (
            SQLAlchemyError("Delete error")
        )
        with pytest.raises(SQLAlchemyError, match="Delete error"):
            content_repository.delete(1)
        mock_session.rollback.assert_called_once()


# Tests for ContentRepositoryFactory
class TestContentRepositoryFactory:
    def test_create_unit_of_work(self, mock_db_service):
        factory = ContentRepositoryFactory(mock_db_service)
        uow = factory.create_unit_of_work()
        assert isinstance(uow, UnitOfWork)

    def test_content_property(self, mock_db_service):
        factory = ContentRepositoryFactory(mock_db_service)
        repo = factory.content
        assert isinstance(repo, ContentRepository)
        assert repo.model_class is ContentItem

    def test_images_property(self, mock_db_service):
        factory = ContentRepositoryFactory(mock_db_service)
        repo = factory.images
        assert isinstance(repo, ContentRepository)
        assert repo.model_class is Image
