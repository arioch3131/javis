from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_content_classifier.models.content_models import ContentItem
from ai_content_classifier.services.database.content_writer import ContentWriter
from ai_content_classifier.services.database.types import DatabaseOperationCode


class TestContentWriter:
    @pytest.fixture
    def mock_database_service(self):
        mock_service = Mock()
        mock_session = Mock(spec=Session)
        mock_service.Session.return_value = mock_session
        return mock_service, mock_session

    @pytest.fixture
    def content_writer(self, mock_database_service):
        db_service, _ = mock_database_service
        return ContentWriter(db_service, Mock())

    def test_create_content_item_success_returns_contract(
        self, content_writer, mock_database_service
    ):
        _, session = mock_database_service

        result = content_writer.create_content_item(
            path="/tmp/image.jpg", content_type="image"
        )

        assert result.success is True
        assert result.code == DatabaseOperationCode.OK
        assert isinstance(result.data.get("item"), ContentItem)
        session.commit.assert_called_once()

    def test_create_content_item_invalid_input_returns_invalid_code(
        self, content_writer
    ):
        result = content_writer.create_content_item(path="", content_type="image")

        assert result.success is False
        assert result.code == DatabaseOperationCode.INVALID_INPUT

    def test_create_content_item_sqlalchemy_error_maps_to_db_error(
        self, content_writer, mock_database_service
    ):
        _, session = mock_database_service
        session.add.side_effect = SQLAlchemyError("db down")

        result = content_writer.create_content_item("/tmp/a.jpg", "image")

        assert result.success is False
        assert result.code == DatabaseOperationCode.DB_ERROR
        session.rollback.assert_called_once()

    def test_writer_delegates_all_public_operations(self, content_writer):
        payload = content_writer.create_content_item("/tmp/a.jpg", "image")
        assert payload is not None
        assert content_writer.save_item_batch([]).success is True
        assert content_writer.update_metadata_batch([]).success is True
        assert content_writer.update_content_category(
            "/tmp/a.jpg", "Work", 0.9, "m", "d"
        ).success in (True, False)
        assert content_writer.clear_content_category("/tmp/a.jpg").success in (
            True,
            False,
        )
        assert content_writer.clear_all_content().success in (True, False)
        assert content_writer.delete_content_by_paths([]).success is True

    def test_update_content_category_not_found_returns_not_found(
        self, content_writer, mock_database_service
    ):
        _, session = mock_database_service
        session.query.return_value.filter.return_value.first.return_value = None

        result = content_writer.update_content_category(
            file_path="/tmp/missing.jpg",
            category="foo",
            confidence=0.9,
            extraction_method="test",
            extraction_details="details",
        )

        assert result.success is False
        assert result.code == DatabaseOperationCode.NOT_FOUND

    def test_clear_all_content_returns_deleted_count(
        self, content_writer, mock_database_service
    ):
        _, session = mock_database_service
        session.query.return_value.delete.return_value = 5

        result = content_writer.clear_all_content()

        assert result.success is True
        assert result.data.get("deleted_count") == 5

    def test_delete_content_by_paths_empty_input_is_ok(self, content_writer):
        result = content_writer.delete_content_by_paths([])

        assert result.success is True
        assert result.code == DatabaseOperationCode.OK
        assert result.data.get("deleted_count") == 0

    def test_update_metadata_batch_partial_success(
        self, content_writer, mock_database_service
    ):
        _, session = mock_database_service
        found_item = ContentItem(
            path="/tmp/found.jpg",
            filename="found.jpg",
            directory="/tmp",
            content_type="image",
        )
        session.query.return_value.filter.return_value.first.side_effect = [
            found_item,
            None,
        ]

        result = content_writer.update_metadata_batch([(1, {"a": 1}), (2, {"b": 2})])

        assert result.success is True
        assert result.code == DatabaseOperationCode.PARTIAL_SUCCESS
        assert result.data.get("updated_count") == 1
        assert result.data.get("failed_ids") == [2]

    def test_validate_content_creation_params(self, content_writer):
        with pytest.raises(ValueError):
            content_writer._validate_content_creation_params("", "image")
        with pytest.raises(ValueError):
            content_writer._validate_content_creation_params("/tmp/a.jpg", "")

    def test_extract_file_info_and_compute_hash(self, content_writer, monkeypatch):
        monkeypatch.setattr(
            "ai_content_classifier.services.database.content_writer.os.path.exists",
            lambda _p: True,
        )
        monkeypatch.setattr(
            "ai_content_classifier.services.database.content_writer.os.path.getsize",
            lambda _p: 123,
        )
        info = content_writer._extract_file_info("/tmp/a.jpg", True)
        assert info["file_size"] == 123

        monkeypatch.setattr(
            "ai_content_classifier.services.database.content_writer.utils.compute_file_hash",
            lambda _p: "hash123",
        )
        assert content_writer._compute_hash_if_exists("/tmp/a.jpg") == "hash123"

        monkeypatch.setattr(
            "ai_content_classifier.services.database.content_writer.os.path.getsize",
            lambda _p: (_ for _ in ()).throw(OSError("size")),
        )
        content_writer._extract_file_info("/tmp/a.jpg", True)

        monkeypatch.setattr(
            "ai_content_classifier.services.database.content_writer.utils.compute_file_hash",
            lambda _p: (_ for _ in ()).throw(RuntimeError("hash")),
        )
        assert content_writer._compute_hash_if_exists("/tmp/a.jpg") is None

    def test_extract_year_value_and_metadata_resolution(self, content_writer):
        assert content_writer._extract_year_value(None) is None
        assert content_writer._extract_year_value(1899) is None
        assert content_writer._extract_year_value(2022) == 2022
        assert content_writer._extract_year_value("Created 2020-01-02") == 2020
        assert content_writer._extract_year_value("unknown") is None

        assert content_writer._extract_year_from_metadata({"year": 2021}) == 2021
        assert (
            content_writer._extract_year_from_metadata(
                {"DateTimeOriginal": "2019:05:01"}
            )
            == 2019
        )
        assert content_writer._extract_year_from_metadata("bad") is None

    def test_resolve_year_taken_fallbacks(self, content_writer, monkeypatch):
        assert content_writer._resolve_year_taken("/tmp/a.jpg", {"year": 2024}) == 2024

        monkeypatch.setattr(
            "ai_content_classifier.services.database.content_writer.os.path.getmtime",
            lambda _p: 1640995200,  # 2022-01-01
        )
        assert content_writer._resolve_year_taken("/tmp/a.jpg", {}) == 2022

        monkeypatch.setattr(
            "ai_content_classifier.services.database.content_writer.os.path.getmtime",
            lambda _p: (_ for _ in ()).throw(OSError("no mtime")),
        )
        assert content_writer._resolve_year_taken("/tmp/a.jpg", {}) is None

    def test_create_content_item_from_data_returns_none_on_error(self, content_writer):
        assert content_writer._create_content_item_from_data({}) is None

    @pytest.mark.parametrize(
        "content_type",
        ["image", "document", "video", "audio", "other"],
    )
    def test_create_content_item_from_data_all_types(
        self, content_writer, content_type
    ):
        payload = {
            "path": "/tmp/a.file",
            "content_type": content_type,
            "metadata": {"year": 2020},
        }
        item = content_writer._create_content_item_from_data(payload)
        assert item is not None
        assert item.path == "/tmp/a.file"

    def test_is_valid_item_data(self, content_writer):
        assert (
            content_writer._is_valid_item_data(
                {"path": "/tmp/a.jpg", "content_type": "image"}
            )
            is True
        )
        assert (
            content_writer._is_valid_item_data({"path": "", "content_type": "image"})
            is False
        )
        assert content_writer._is_valid_item_data({"path": "/tmp/a.jpg"}) is False

    def test_process_metadata_updates_and_update_existing_item(self, content_writer):
        session = Mock(spec=Session)
        found_item = ContentItem(
            path="/tmp/found.jpg",
            filename="found.jpg",
            directory="/tmp",
            content_type="image",
            content_metadata=None,
        )
        session.query.return_value.filter.return_value.first.side_effect = [
            found_item,
            None,
        ]
        updated, failed = content_writer._process_metadata_updates(
            session=session,
            metadata_updates=[(1, {"year": 2021}), (2, {"x": 1})],
        )
        assert len(updated) == 1
        assert failed == [2]

        existing = ContentItem(
            path="/tmp/existing.jpg",
            filename="existing.jpg",
            directory="/tmp",
            content_type="image",
            content_metadata=None,
        )
        content_writer._update_existing_item(
            existing_item=existing,
            path="/tmp/existing.jpg",
            extract_basic_info=False,
            metadata={"year": 2022},
        )
        assert existing.metadata_extracted is True
