import pytest
from unittest.mock import patch, MagicMock
from contextlib import ExitStack
from sqlalchemy.exc import SQLAlchemyError

from ai_content_classifier.services.database.content_database_service import (
    ContentDatabaseService,
)
from ai_content_classifier.repositories.content_repository import (
    ContentRepositoryFactory,
)
from ai_content_classifier.services.database.operations.enhanced_reader import (
    EnhancedContentReader,
)
from ai_content_classifier.services.database.content_writer import ContentWriter


class TestContentDatabaseService:
    @pytest.fixture
    def mock_database_service(self):
        mock_db_service = MagicMock()
        # Mock the Session attribute to return a mock session
        mock_db_service.Session = MagicMock(return_value=MagicMock())
        return mock_db_service

    @pytest.fixture
    def mock_query_optimizer(self):
        return MagicMock()

    @pytest.fixture
    def mock_performance_metrics(self):
        return MagicMock()

    @pytest.fixture
    def mock_content_repository_factory(self):
        mock_factory = MagicMock(
            spec=ContentRepositoryFactory
        )  # Use spec for better mocking
        mock_factory.return_value.create_unit_of_work.return_value = MagicMock()
        return mock_factory

    @pytest.fixture
    def mock_enhanced_content_reader(self):
        return MagicMock(spec=EnhancedContentReader)  # Use spec

    @pytest.fixture
    def mock_content_writer(self):
        return MagicMock(spec=ContentWriter)  # Use spec

    @pytest.fixture(autouse=True)
    def setup_mocks(
        self,
        mock_database_service,
        mock_query_optimizer,
        mock_performance_metrics,
        mock_content_repository_factory,
        mock_enhanced_content_reader,
        mock_content_writer,
    ):
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "ai_content_classifier.services.database.content_database_service.ContentRepositoryFactory",
                    mock_content_repository_factory,
                )
            )
            stack.enter_context(
                patch(
                    "ai_content_classifier.services.database.content_database_service.EnhancedContentReader",
                    mock_enhanced_content_reader,
                )
            )
            stack.enter_context(
                patch(
                    "ai_content_classifier.services.database.content_database_service.ContentWriter",
                    mock_content_writer,
                )
            )
            self.service = ContentDatabaseService(
                database_service=mock_database_service,
                query_optimizer=mock_query_optimizer,
                metrics=mock_performance_metrics,
            )
            self.service.logger = MagicMock()
            self.mock_db_service = mock_database_service
            self.mock_query_optimizer = mock_query_optimizer
            self.mock_performance_metrics = mock_performance_metrics
            self.mock_content_repository_factory = mock_content_repository_factory
            self.mock_enhanced_content_reader = mock_enhanced_content_reader
            self.mock_content_writer = mock_content_writer

    def test_initialization(
        self,
        mock_database_service,
        mock_query_optimizer,
        mock_performance_metrics,
        mock_content_repository_factory,
        mock_enhanced_content_reader,
        mock_content_writer,
    ):
        assert self.service.database_service == mock_database_service
        assert self.service.query_optimizer == mock_query_optimizer
        assert self.service.metrics == mock_performance_metrics
        mock_content_repository_factory.assert_called_once_with(mock_database_service)
        mock_enhanced_content_reader.assert_called_once_with(
            mock_database_service, mock_query_optimizer, mock_performance_metrics
        )
        mock_content_writer.assert_called_once_with(
            mock_database_service, self.service.repos
        )
        assert self.service.reader == mock_enhanced_content_reader.return_value
        assert self.service.writer == mock_content_writer.return_value
        # self.service.logger.assert_called_once() # Removed as it checks if the logger object itself was called, not its methods

    def test_create_unit_of_work(self):
        unit_of_work = self.service.create_unit_of_work()
        self.mock_content_writer.return_value.repos.create_unit_of_work.assert_called_once()
        assert (
            unit_of_work
            == self.mock_content_writer.return_value.repos.create_unit_of_work.return_value
        )

    @patch("ai_content_classifier.services.database.utils.serialize_metadata_for_json")
    def test_serialize_metadata_for_json(self, mock_serialize_metadata_for_json):
        metadata = {"key": "value"}
        self.service.serialize_metadata_for_json(metadata)
        mock_serialize_metadata_for_json.assert_called_once_with(metadata)

    @patch("ai_content_classifier.services.database.content_database_service.text")
    def test_force_database_sync_success(self, mock_text):
        mock_session = self.mock_db_service.Session.return_value
        self.service.force_database_sync()
        self.mock_db_service.Session.assert_called_once()
        mock_session.execute.assert_called_once_with(mock_text.return_value)
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
        self.service.logger.debug.assert_called_with("Database synchronization forced.")

    @patch("ai_content_classifier.services.database.content_database_service.text")
    def test_force_database_sync_exception_during_execute(self, mock_text):
        mock_session = self.mock_db_service.Session.return_value
        mock_session.execute.side_effect = Exception("Test execute error")
        self.service.force_database_sync()
        self.service.logger.debug.assert_called_with(
            "Database sync failed (this is normal for non-SQLite or specific configurations): Test execute error"
        )

    def test_force_database_sync_exception_during_session_acquisition(self):
        self.mock_db_service.Session.side_effect = Exception("Test session error")
        self.service.force_database_sync()
        self.service.logger.debug.assert_called_with(
            "Could not force database sync due to session acquisition error: Test session error"
        )

    def test_count_all_items(self):
        mock_session = MagicMock()
        self.service.count_all_items(mock_session)
        self.mock_enhanced_content_reader.return_value.count_all_items.assert_called_once_with(
            mock_session
        )

    def test_create_content_item(self):
        path = "/test/path.jpg"
        content_type = "image/jpeg"
        self.service.create_content_item(path, content_type)
        self.mock_content_writer.return_value.create_content_item.assert_called_once_with(
            path, content_type, True, None, True, None
        )
        self.mock_query_optimizer.invalidate_all.assert_called_once()

    def test_save_item_batch(self):
        items = [{"path": "/a.txt"}]
        self.mock_content_writer.return_value.save_item_batch.return_value = [
            MagicMock()
        ]
        self.service.save_item_batch(items)
        self.mock_content_writer.return_value.save_item_batch.assert_called_once_with(
            items, True, None
        )
        self.mock_query_optimizer.invalidate_all.assert_called_once()

    def test_update_metadata_batch(self):
        updates = [(1, {"title": "new"})]
        self.mock_content_writer.return_value.update_metadata_batch.return_value = 1
        self.service.update_metadata_batch(updates)
        self.mock_content_writer.return_value.update_metadata_batch.assert_called_once_with(
            updates, False, None
        )
        self.mock_query_optimizer.invalidate_all.assert_called_once()

    def test_find_items(self):
        self.service.find_items()
        self.mock_enhanced_content_reader.return_value.find_items.assert_called_once()

    def test_get_items_pending_metadata(self):
        self.service.get_items_pending_metadata()
        self.mock_enhanced_content_reader.return_value.get_items_pending_metadata.assert_called_once()

    def test_find_duplicates(self):
        self.service.find_duplicates()
        self.mock_enhanced_content_reader.return_value.find_duplicates.assert_called_once()

    def test_get_statistics(self):
        self.service.get_statistics()
        self.mock_enhanced_content_reader.return_value.get_statistics.assert_called_once()

    def test_get_content_by_path(self):
        path = "/test/file.txt"
        self.service.get_content_by_path(path)
        self.mock_enhanced_content_reader.return_value.get_content_by_path.assert_called_once_with(
            path, None
        )

    @patch("ai_content_classifier.services.database.utils.compute_file_hash")
    def test_compute_file_hash(self, mock_compute_file_hash):
        file_path = "/test/file.txt"
        self.service.compute_file_hash(file_path)
        mock_compute_file_hash.assert_called_once_with(file_path)

    def test_update_content_category(self):
        file_path = "/test/file.txt"
        category = "test_category"
        confidence = 0.9
        extraction_method = "llm"
        extraction_details = "details"
        self.mock_content_writer.return_value.update_content_category.return_value = (
            MagicMock()
        )
        self.service.update_content_category(
            file_path, category, confidence, extraction_method, extraction_details
        )
        self.mock_content_writer.return_value.update_content_category.assert_called_once_with(
            file_path, category, confidence, extraction_method, extraction_details, None
        )
        self.mock_query_optimizer.invalidate_all.assert_called_once()

    def test_get_uncategorized_items(self):
        self.service.get_uncategorized_items(content_type="image")
        self.mock_enhanced_content_reader.return_value.get_uncategorized_items.assert_called_once_with(
            "image", None
        )

    def test_clear_content_category(self):
        file_path = "/test/file.txt"
        self.mock_content_writer.return_value.clear_content_category.return_value = (
            MagicMock()
        )
        self.service.clear_content_category(file_path)
        self.mock_content_writer.return_value.clear_content_category.assert_called_once_with(
            file_path, None
        )
        self.mock_query_optimizer.invalidate_all.assert_called_once()

    def test_get_unique_categories(self):
        self.service.get_unique_categories()
        self.mock_enhanced_content_reader.return_value.get_unique_categories.assert_called_once_with()

    def test_get_unique_years(self):
        self.service.get_unique_years()
        self.mock_enhanced_content_reader.return_value.get_unique_years.assert_called_once_with()

    def test_get_unique_extensions(self):
        self.service.get_unique_extensions()
        self.mock_enhanced_content_reader.return_value.get_unique_extensions.assert_called_once_with()

    def test_clear_all_content_success(self):
        mock_session = self.mock_db_service.Session.return_value
        mock_session.query.return_value.delete.return_value = 7

        deleted = self.service.clear_all_content()

        assert deleted == 7
        mock_session.query.return_value.delete.assert_called_once_with(
            synchronize_session="fetch"
        )
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
        self.mock_query_optimizer.invalidate_all.assert_called_once()

    def test_clear_all_content_with_external_session(self):
        external_session = MagicMock()
        external_session.query.return_value.delete.return_value = 2

        deleted = self.service.clear_all_content(session=external_session)

        assert deleted == 2
        external_session.commit.assert_not_called()
        external_session.close.assert_not_called()

    def test_clear_all_content_sqlalchemy_error(self):
        mock_session = self.mock_db_service.Session.return_value
        mock_session.query.return_value.delete.side_effect = SQLAlchemyError("db error")

        with pytest.raises(SQLAlchemyError):
            self.service.clear_all_content()

        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    def test_delete_content_by_paths_empty_input(self):
        deleted = self.service.delete_content_by_paths([])
        assert deleted == 0
        self.mock_db_service.Session.assert_not_called()

    def test_delete_content_by_paths_success_with_normalization(self):
        mock_session = self.mock_db_service.Session.return_value
        mock_query = mock_session.query.return_value
        mock_filtered = mock_query.filter.return_value
        mock_filtered.delete.return_value = 3

        deleted = self.service.delete_content_by_paths(["/a", "/a", "", None, "/b"])

        assert deleted == 3
        mock_filtered.delete.assert_called_once_with(synchronize_session="fetch")
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
        self.mock_query_optimizer.invalidate_all.assert_called_once()

    def test_delete_content_by_paths_with_external_session(self):
        external_session = MagicMock()
        external_filtered = external_session.query.return_value.filter.return_value
        external_filtered.delete.return_value = 1

        deleted = self.service.delete_content_by_paths(["/x"], session=external_session)

        assert deleted == 1
        external_session.commit.assert_not_called()
        external_session.close.assert_not_called()

    def test_delete_content_by_paths_sqlalchemy_error(self):
        mock_session = self.mock_db_service.Session.return_value
        mock_session.query.return_value.filter.return_value.delete.side_effect = (
            SQLAlchemyError("db error")
        )

        with pytest.raises(SQLAlchemyError):
            self.service.delete_content_by_paths(["/x"])

        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()
