from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from ai_content_classifier.services.database.content_database_service import (
    ContentDatabaseService,
)
from ai_content_classifier.services.database.content_reader import ContentReader
from ai_content_classifier.services.database.content_writer import ContentWriter
from ai_content_classifier.services.database.types import (
    DatabaseOperationCode,
    DatabaseOperationResult,
)


class TestContentDatabaseService:
    @pytest.fixture
    def mock_database_service(self):
        mock_db_service = MagicMock()
        mock_db_service.Session = MagicMock(return_value=MagicMock())
        return mock_db_service

    @pytest.fixture
    def mock_query_optimizer(self):
        return MagicMock()

    @pytest.fixture
    def mock_performance_metrics(self):
        return MagicMock()

    @pytest.fixture
    def mock_reader(self):
        return MagicMock(spec=ContentReader)

    @pytest.fixture
    def mock_writer(self):
        return MagicMock(spec=ContentWriter)

    @pytest.fixture(autouse=True)
    def setup_mocks(
        self,
        mock_database_service,
        mock_query_optimizer,
        mock_performance_metrics,
        mock_reader,
        mock_writer,
    ):
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "ai_content_classifier.services.database.content_database_service.ContentReader",
                    return_value=mock_reader,
                )
            )
            stack.enter_context(
                patch(
                    "ai_content_classifier.services.database.content_database_service.ContentWriter",
                    return_value=mock_writer,
                )
            )
            self.service = ContentDatabaseService(
                database_service=mock_database_service,
                query_optimizer=mock_query_optimizer,
                metrics=mock_performance_metrics,
            )
            self.mock_db_service = mock_database_service
            self.mock_query_optimizer = mock_query_optimizer
            self.mock_reader = mock_reader
            self.mock_writer = mock_writer

    def _ok_result(self, **data):
        return DatabaseOperationResult(
            success=True,
            code=DatabaseOperationCode.OK,
            message="ok",
            data=data,
        )

    def test_create_content_item_delegates_and_invalidates_cache(self):
        self.mock_writer.create_content_item.return_value = self._ok_result(
            item=MagicMock()
        )

        result = self.service.create_content_item("/tmp/a.jpg", "image")

        assert result.success is True
        self.mock_writer.create_content_item.assert_called_once()
        self.mock_query_optimizer.invalidate_all.assert_called_once()

    def test_create_content_item_does_not_invalidate_cache_on_failure(self):
        self.mock_writer.create_content_item.return_value = DatabaseOperationResult(
            success=False,
            code=DatabaseOperationCode.DB_ERROR,
            message="db fail",
            data={},
        )

        result = self.service.create_content_item("/tmp/a.jpg", "image")

        assert result.success is False
        self.mock_query_optimizer.invalidate_all.assert_not_called()

    def test_read_delegation(self):
        expected = [MagicMock(), MagicMock()]
        expected_result = self._ok_result(items=expected)
        self.mock_reader.find_items.return_value = expected_result

        got = self.service.find_items(limit=2)

        assert got == expected_result
        assert got.data["items"] == expected
        self.mock_reader.find_items.assert_called_once()

    def test_get_unique_signatures_accept_optional_session(self):
        session = MagicMock()

        self.service.get_unique_categories(session=session)
        self.service.get_unique_years(session=session)
        self.service.get_unique_extensions(session=session)

        self.mock_reader.get_unique_categories.assert_called_once_with(session)
        self.mock_reader.get_unique_years.assert_called_once_with(session)
        self.mock_reader.get_unique_extensions.assert_called_once_with(session)

    def test_read_methods_delegate_and_return_operation_result(self):
        self.mock_reader.count_all_items.return_value = self._ok_result(count=10)
        self.mock_reader.get_items_pending_metadata.return_value = self._ok_result(
            items=[]
        )
        self.mock_reader.find_duplicates.return_value = self._ok_result(duplicates={})
        self.mock_reader.get_statistics.return_value = self._ok_result(
            statistics={"total_items": 10}
        )
        self.mock_reader.get_content_by_path.return_value = self._ok_result(item=None)
        self.mock_reader.get_uncategorized_items.return_value = self._ok_result(
            items=[]
        )

        assert self.service.count_all_items().data["count"] == 10
        assert self.service.get_items_pending_metadata().success is True
        assert self.service.find_duplicates().success is True
        assert self.service.get_statistics().data["statistics"]["total_items"] == 10
        assert self.service.get_content_by_path("/tmp/x").success is True
        assert self.service.get_uncategorized_items().success is True

    def test_force_database_sync_uses_context_manager(self):
        session = MagicMock()
        context_manager = MagicMock()
        context_manager.__enter__.return_value = session
        context_manager.__exit__.return_value = None
        self.mock_db_service.get_session.return_value = context_manager

        self.service.force_database_sync()

        self.mock_db_service.get_session.assert_called_once()
        session.execute.assert_called_once()

    def test_misc_service_helpers_and_read_wrappers(self):
        self.mock_writer.repos = MagicMock()
        self.mock_writer.repos.create_unit_of_work.return_value = "uow"
        assert self.service.create_unit_of_work() == "uow"

        with patch(
            "ai_content_classifier.services.database.content_database_service.utils.serialize_metadata_for_json",
            return_value={"k": "v"},
        ) as serialize:
            assert self.service.serialize_metadata_for_json({"k": "v"}) == {"k": "v"}
            serialize.assert_called_once()

        with patch(
            "ai_content_classifier.services.database.content_database_service.utils.compute_file_hash",
            return_value="hash",
        ) as compute:
            assert self.service.compute_file_hash("/tmp/a.jpg") == "hash"
            compute.assert_called_once_with("/tmp/a.jpg")

    def test_clear_all_content_returns_operation_result(self):
        self.mock_writer.clear_all_content.return_value = self._ok_result(
            deleted_count=7
        )

        result = self.service.clear_all_content()

        assert result.success is True
        assert result.data["deleted_count"] == 7
        self.mock_query_optimizer.invalidate_all.assert_called_once()

    def test_delete_content_by_paths_returns_operation_result(self):
        self.mock_writer.delete_content_by_paths.return_value = self._ok_result(
            deleted_count=2, normalized_paths=["/a", "/b"]
        )

        result = self.service.delete_content_by_paths(["/a", "/b"])

        assert result.code == DatabaseOperationCode.OK
        assert result.data["deleted_count"] == 2

    def test_update_content_path_delegates_and_invalidates_cache(self):
        self.mock_writer.update_content_path.return_value = self._ok_result(
            updated=True, source_path="/a", target_path="/b", file_hash="hash"
        )

        result = self.service.update_content_path("/a", "/b")

        assert result.success is True
        assert result.data["updated"] is True
        self.mock_writer.update_content_path.assert_called_once_with(
            source_path="/a",
            target_path="/b",
            session=None,
        )
        self.mock_query_optimizer.invalidate_all.assert_called_once()
