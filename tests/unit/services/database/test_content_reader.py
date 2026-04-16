from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from ai_content_classifier.models.content_models import ContentItem, datetime_utcnow
from ai_content_classifier.repositories.content_repository import ContentFilter
from ai_content_classifier.services.database.content_reader import ContentReader
from ai_content_classifier.services.database.database_service import DatabaseService
from ai_content_classifier.services.database.types import DatabaseOperationCode


class TestContentReader:
    @pytest.fixture
    def mock_content_item(self):
        item = MagicMock(spec=ContentItem)
        item.id = 1
        item.path = "/test/path.jpg"
        item.filename = "path.jpg"
        item.directory = "/test"
        item.content_type = "image"
        item.metadata_extracted = True
        item.category = "test_category"
        item.file_hash = "test_hash_123"
        item.date_created = datetime_utcnow()
        item.date_modified = datetime_utcnow()
        item.content_metadata = {}
        return item

    @pytest.fixture
    def mock_db_session(self):
        session = MagicMock()
        query = MagicMock()
        session.query.return_value = query

        query.filter.return_value = query
        query.options.return_value = query
        query.distinct.return_value = query
        query.group_by.return_value = query
        query.having.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query
        query.offset.return_value = query

        query.all.return_value = []
        query.first.return_value = None
        query.scalar.return_value = 0
        session.close.return_value = None
        session.expunge.return_value = None
        return session

    @pytest.fixture
    def mock_database_service(self, mock_db_session):
        db_service = MagicMock(spec=DatabaseService)
        db_service.Session = MagicMock(return_value=mock_db_session)
        return db_service

    @pytest.fixture
    def mock_content_filter(self):
        content_filter = MagicMock(spec=ContentFilter)
        content_filter.criteria = []
        content_filter.build.return_value = []
        return content_filter

    @pytest.fixture
    def reader(self, mock_database_service):
        with patch.object(ContentReader, "__init_logger__"):
            reader = ContentReader(mock_database_service)
            reader.logger = MagicMock()
            return reader

    def test_find_items_returns_operation_result(
        self, reader, mock_db_session, mock_content_item
    ):
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        result = reader.find_items()

        assert result.success is True
        assert result.code == DatabaseOperationCode.OK
        assert result.data["items"] == [mock_content_item]

    def test_find_items_handles_error_result(self, reader, mock_db_session):
        mock_db_session.query.return_value.all.side_effect = SQLAlchemyError("db fail")

        result = reader.find_items()

        assert result.success is False
        assert result.code == DatabaseOperationCode.DB_ERROR
        assert "error" in result.data

    def test_find_items_with_filters(
        self, reader, mock_db_session, mock_content_filter
    ):
        mock_content_filter.build.return_value = [ContentItem.content_type == "image"]

        result = reader.find_items(content_filter=mock_content_filter)

        assert result.success is True
        mock_db_session.query.return_value.filter.assert_called_once()

    def test_find_items_with_sort_and_limit(self, reader, mock_db_session):
        mock_db_session.query.return_value.all.return_value = []
        result = reader.find_items(sort_by="path", sort_desc=True, limit=5, offset=2)
        assert result.success is True
        assert mock_db_session.query.return_value.limit.call_count >= 1
        assert mock_db_session.query.return_value.offset.call_count >= 1

    def test_count_all_items_returns_operation_result(self, reader, mock_db_session):
        mock_db_session.query.return_value.scalar.return_value = 12

        result = reader.count_all_items()

        assert result.success is True
        assert result.code == DatabaseOperationCode.OK
        assert result.data["count"] == 12

    def test_count_all_items_failure_result(self, reader):
        reader._count_all_items_operation.execute = MagicMock(
            side_effect=RuntimeError("boom")
        )

        result = reader.count_all_items()

        assert result.success is False
        assert result.code == DatabaseOperationCode.DB_ERROR
        assert result.data["count"] == 0

    def test_get_items_pending_metadata_returns_operation_result(
        self, reader, mock_db_session, mock_content_item
    ):
        mock_content_item.metadata_extracted = False
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        result = reader.get_items_pending_metadata()

        assert result.success is True
        assert result.data["items"] == [mock_content_item]

    def test_find_duplicates_returns_operation_result(
        self, reader, mock_db_session, mock_content_item
    ):
        mock_db_session.query.return_value.all.side_effect = [
            [("hash1",)],
            [mock_content_item],
        ]
        mock_content_item.file_hash = "hash1"

        result = reader.find_duplicates()

        assert result.success is True
        assert "hash1" in result.data["duplicates"]

    def test_get_statistics_returns_operation_result(self, reader, mock_db_session):
        mock_db_session.query.return_value.scalar.side_effect = [10, 7]
        mock_db_session.query.return_value.all.return_value = [("image", 6), ("doc", 4)]

        result = reader.get_statistics()

        assert result.success is True
        assert result.data["statistics"]["total_items"] == 10

    def test_get_content_by_path_found(
        self, reader, mock_db_session, mock_content_item
    ):
        mock_db_session.query.return_value.first.return_value = mock_content_item

        result = reader.get_content_by_path("/test/path.jpg")

        assert result.success is True
        assert result.code == DatabaseOperationCode.OK
        assert result.data["item"] == mock_content_item

    def test_get_content_by_path_not_found(self, reader, mock_db_session):
        mock_db_session.query.return_value.first.return_value = None

        result = reader.get_content_by_path("/missing")

        assert result.success is False
        assert result.code == DatabaseOperationCode.NOT_FOUND
        assert result.data["item"] is None

    def test_get_uncategorized_items_returns_operation_result(
        self, reader, mock_db_session, mock_content_item
    ):
        mock_content_item.category = None
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        result = reader.get_uncategorized_items()

        assert result.success is True
        assert result.data["items"] == [mock_content_item]

    def test_get_unique_categories_returns_operation_result(
        self, reader, mock_db_session
    ):
        mock_db_session.query.return_value.all.return_value = [
            ("image",),
            ("document",),
        ]

        result = reader.get_unique_categories()

        assert result.success is True
        assert result.data["categories"] == ["image", "document"]

    def test_get_unique_years_returns_operation_result(self, reader, mock_db_session):
        mock_db_session.query.return_value.all.return_value = [("2022",), ("2023",)]

        result = reader.get_unique_years()

        assert result.success is True
        assert result.data["years"] == [2022, 2023]

    def test_get_unique_extensions_returns_operation_result(
        self, reader, mock_db_session
    ):
        mock_db_session.query.return_value.all.return_value = [
            ("/tmp/a.jpg",),
            ("/tmp/b.pdf",),
        ]

        result = reader.get_unique_extensions()

        assert result.success is True
        assert result.data["extensions"] == [".jpg", ".pdf"]

    def test_external_session_is_not_closed(self, reader, mock_db_session):
        result = reader.find_items(session=mock_db_session)

        assert result.success is True
        mock_db_session.close.assert_not_called()

    def test_extract_year_helper_covers_edge_cases(self, reader):
        assert reader._extract_year(None) is None
        assert reader._extract_year("") is None
        assert reader._extract_year("taken in 2020") == 2020
        assert reader._extract_year("year=1899") is None

    def test_get_unique_years_supports_datetime_and_metadata(
        self, reader, mock_db_session
    ):
        dt = datetime_utcnow()
        mock_db_session.query.return_value.all.return_value = [
            (
                "/tmp/a.jpg",
                None,
                dt,
                None,
                None,
                {"DateTimeOriginal": "2018:01:01 00:00:00"},
            )
        ]

        result = reader.get_unique_years()

        assert result.success is True
        assert 2018 in result.data["years"]
        assert dt.year in result.data["years"]

    def test_error_result_contains_error_key(self, reader):
        result = reader._error_result("oops", RuntimeError("boom"))
        assert result.success is False
        assert result.code == DatabaseOperationCode.DB_ERROR
        assert "error" in result.data
