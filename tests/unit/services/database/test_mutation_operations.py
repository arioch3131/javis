from unittest.mock import MagicMock

from sqlalchemy.exc import SQLAlchemyError

from ai_content_classifier.models.content_models import ContentItem
from ai_content_classifier.services.database.types import DatabaseOperationCode
from ai_content_classifier.services.database.write_operations.mutation_operations import (
    ClearAllContentOperation,
    ClearContentCategoryOperation,
    CreateContentItemOperation,
    DeleteContentByPathsOperation,
    SaveItemBatchOperation,
    UpdateContentCategoryOperation,
    UpdateMetadataBatchOperation,
)


def _build_writer_and_session():
    writer = MagicMock()
    writer.logger = MagicMock()
    session = MagicMock()
    query = MagicMock()
    session.query.return_value = query
    query.filter.return_value = query
    query.first.return_value = None
    writer.database_service.Session.return_value = session
    return writer, session, query


def _content_item(path: str = "/tmp/a.jpg") -> ContentItem:
    return ContentItem(
        path=path,
        filename=path.split("/")[-1],
        directory="/tmp",
        content_type="image",
    )


class TestCreateContentItemOperation:
    def test_invalid_input(self):
        writer, _, _ = _build_writer_and_session()
        writer._validate_content_creation_params.side_effect = ValueError("bad input")

        result = CreateContentItemOperation().execute(writer, "", "image")

        assert result.success is False
        assert result.code == DatabaseOperationCode.INVALID_INPUT

    def test_update_existing_item(self):
        writer, session, query = _build_writer_and_session()
        existing = _content_item("/tmp/existing.jpg")
        query.first.return_value = existing

        result = CreateContentItemOperation().execute(
            writer, "/tmp/existing.jpg", "image", refresh=True
        )

        assert result.success is True
        assert result.data["created"] is False
        session.commit.assert_called_once()
        session.refresh.assert_called_once_with(existing)

    def test_create_new_item(self):
        writer, session, query = _build_writer_and_session()
        query.first.return_value = None
        writer._extract_file_info.return_value = {
            "filename": "x.jpg",
            "directory": "/tmp",
            "file_size": 1,
        }
        new_item = _content_item("/tmp/new.jpg")
        writer._create_typed_content_item.return_value = new_item
        writer._compute_hash_if_exists.return_value = "hash"

        result = CreateContentItemOperation().execute(writer, "/tmp/new.jpg", "image")

        assert result.success is True
        assert result.data["created"] is True
        session.add.assert_called_once_with(new_item)
        session.commit.assert_called_once()

    def test_create_handles_sqlalchemy_error(self):
        writer, session, _ = _build_writer_and_session()
        session.query.side_effect = SQLAlchemyError("db down")

        result = CreateContentItemOperation().execute(writer, "/tmp/a.jpg", "image")

        assert result.success is False
        assert result.code == DatabaseOperationCode.DB_ERROR
        session.rollback.assert_called_once()

    def test_create_handles_unexpected_error(self):
        writer, session, _ = _build_writer_and_session()
        session.query.side_effect = RuntimeError("boom")

        result = CreateContentItemOperation().execute(writer, "/tmp/a.jpg", "image")

        assert result.success is False
        assert result.code == DatabaseOperationCode.UNKNOWN_ERROR
        session.rollback.assert_called_once()


class TestSaveItemBatchOperation:
    def test_empty_batch(self):
        writer, _, _ = _build_writer_and_session()
        result = SaveItemBatchOperation().execute(writer, [])
        assert result.success is True
        assert result.data["saved_count"] == 0

    def test_partial_success(self):
        writer, session, query = _build_writer_and_session()
        existing = _content_item("/tmp/existing.jpg")
        query.first.side_effect = [existing, None, None]

        def is_valid(item):
            return (
                isinstance(item, dict)
                and bool(item.get("path"))
                and bool(item.get("content_type"))
            )

        writer._is_valid_item_data.side_effect = is_valid
        created = _content_item("/tmp/new.jpg")
        writer._create_content_item_from_data.side_effect = [None, created]

        items = [
            {"oops": True},
            {"path": "/tmp/existing.jpg", "content_type": "image"},
            {"path": "/tmp/fail.jpg", "content_type": "image"},
            {"path": "/tmp/new.jpg", "content_type": "image"},
        ]
        result = SaveItemBatchOperation().execute(writer, items)

        assert result.success is True
        assert result.code == DatabaseOperationCode.PARTIAL_SUCCESS
        assert result.data["saved_count"] == 2
        assert result.data["ignored_count"] == 1
        assert "/tmp/fail.jpg" in result.data["failed_paths"]
        session.commit.assert_called_once()

    def test_all_failed_is_invalid_input(self):
        writer, _, query = _build_writer_and_session()
        query.first.return_value = None
        writer._is_valid_item_data.return_value = True
        writer._create_content_item_from_data.return_value = None

        result = SaveItemBatchOperation().execute(
            writer, [{"path": "/tmp/fail.jpg", "content_type": "image"}]
        )

        assert result.success is False
        assert result.code == DatabaseOperationCode.INVALID_INPUT

    def test_batch_db_error(self):
        writer, session, _ = _build_writer_and_session()
        session.query.side_effect = SQLAlchemyError("db fail")
        result = SaveItemBatchOperation().execute(
            writer, [{"path": "/tmp/a.jpg", "content_type": "image"}]
        )
        assert result.code == DatabaseOperationCode.DB_ERROR

    def test_batch_unknown_error(self):
        writer, session, query = _build_writer_and_session()
        query.first.return_value = None
        writer._is_valid_item_data.return_value = True
        writer._create_content_item_from_data.return_value = _content_item("/tmp/a.jpg")
        session.commit.side_effect = RuntimeError("boom")
        result = SaveItemBatchOperation().execute(
            writer, [{"path": "/tmp/a.jpg", "content_type": "image"}]
        )
        assert result.code == DatabaseOperationCode.UNKNOWN_ERROR


class TestUpdateMetadataBatchOperation:
    def test_empty_updates(self):
        writer, _, _ = _build_writer_and_session()
        result = UpdateMetadataBatchOperation().execute(writer, [])
        assert result.success is True
        assert result.data["updated_count"] == 0

    def test_not_found_partial_and_success_paths(self):
        writer, session, _ = _build_writer_and_session()
        op = UpdateMetadataBatchOperation()

        writer._process_metadata_updates.return_value = ([], [1, 2])
        not_found = op.execute(writer, [(1, {}), (2, {})], refresh=False)
        assert not_found.code == DatabaseOperationCode.NOT_FOUND

        one_item = _content_item("/tmp/one.jpg")
        writer._process_metadata_updates.return_value = ([one_item], [2])
        partial = op.execute(writer, [(1, {}), (2, {})], refresh=False)
        assert partial.code == DatabaseOperationCode.PARTIAL_SUCCESS

        writer._process_metadata_updates.return_value = ([one_item], [])
        ok = op.execute(writer, [(1, {})], refresh=True)
        assert ok.code == DatabaseOperationCode.OK
        session.refresh.assert_called_with(one_item)

    def test_update_metadata_errors(self):
        writer, session, _ = _build_writer_and_session()
        op = UpdateMetadataBatchOperation()
        writer._process_metadata_updates.side_effect = SQLAlchemyError("db")
        db_err = op.execute(writer, [(1, {})])
        assert db_err.code == DatabaseOperationCode.DB_ERROR

        writer._process_metadata_updates.side_effect = RuntimeError("boom")
        unknown = op.execute(writer, [(1, {})])
        assert unknown.code == DatabaseOperationCode.UNKNOWN_ERROR


class TestCategoryAndDeleteOperations:
    def test_update_content_category_all_paths(self):
        writer, session, query = _build_writer_and_session()
        op = UpdateContentCategoryOperation()

        invalid = op.execute(writer, "", "Work", 0.9, "m", "d")
        assert invalid.code == DatabaseOperationCode.INVALID_INPUT

        query.first.return_value = None
        missing = op.execute(writer, "/tmp/missing.jpg", "Work", 0.9, "m", "d")
        assert missing.code == DatabaseOperationCode.NOT_FOUND

        item = _content_item("/tmp/found.jpg")
        item.content_metadata = None
        query.first.return_value = item
        ok = op.execute(writer, "/tmp/found.jpg", "Work", 0.9, "m", "d")
        assert ok.code == DatabaseOperationCode.OK
        assert item.category == "Work"

        session.query.side_effect = SQLAlchemyError("db")
        db_err = op.execute(writer, "/tmp/found.jpg", "Work", 0.9, "m", "d")
        assert db_err.code == DatabaseOperationCode.DB_ERROR

        session.query.side_effect = RuntimeError("boom")
        unknown = op.execute(writer, "/tmp/found.jpg", "Work", 0.9, "m", "d")
        assert unknown.code == DatabaseOperationCode.UNKNOWN_ERROR

    def test_clear_content_category_all_paths(self):
        writer, session, query = _build_writer_and_session()
        op = ClearContentCategoryOperation()

        invalid = op.execute(writer, "")
        assert invalid.code == DatabaseOperationCode.INVALID_INPUT

        query.first.return_value = None
        missing = op.execute(writer, "/tmp/missing.jpg")
        assert missing.code == DatabaseOperationCode.NOT_FOUND

        item = _content_item("/tmp/found.jpg")
        item.content_metadata = {"classification": {"x": 1}}
        query.first.return_value = item
        ok = op.execute(writer, "/tmp/found.jpg")
        assert ok.code == DatabaseOperationCode.OK
        assert item.category is None

        session.query.side_effect = SQLAlchemyError("db")
        assert (
            op.execute(writer, "/tmp/found.jpg").code == DatabaseOperationCode.DB_ERROR
        )

        session.query.side_effect = RuntimeError("boom")
        assert (
            op.execute(writer, "/tmp/found.jpg").code
            == DatabaseOperationCode.UNKNOWN_ERROR
        )

    def test_clear_all_content_and_delete_by_paths(self):
        writer, session, query = _build_writer_and_session()

        query.delete.return_value = 3
        clear_ok = ClearAllContentOperation().execute(writer)
        assert clear_ok.code == DatabaseOperationCode.OK
        assert clear_ok.data["deleted_count"] == 3

        query.delete.side_effect = SQLAlchemyError("db")
        clear_db = ClearAllContentOperation().execute(writer)
        assert clear_db.code == DatabaseOperationCode.DB_ERROR

        query.delete.side_effect = RuntimeError("boom")
        clear_unknown = ClearAllContentOperation().execute(writer)
        assert clear_unknown.code == DatabaseOperationCode.UNKNOWN_ERROR

        delete_op = DeleteContentByPathsOperation()
        empty = delete_op.execute(writer, [])
        assert empty.code == DatabaseOperationCode.OK

        query.delete.side_effect = None
        query.delete.return_value = 1
        partial = delete_op.execute(writer, ["/tmp/a.jpg", "/tmp/b.jpg"])
        assert partial.code == DatabaseOperationCode.PARTIAL_SUCCESS
        assert partial.data["ignored_count"] == 1

        query.delete.return_value = 2
        ok = delete_op.execute(writer, ["/tmp/a.jpg", "/tmp/b.jpg"])
        assert ok.code == DatabaseOperationCode.OK

        query.delete.side_effect = SQLAlchemyError("db")
        db_err = delete_op.execute(writer, ["/tmp/a.jpg"])
        assert db_err.code == DatabaseOperationCode.DB_ERROR

        query.delete.side_effect = RuntimeError("boom")
        unknown = delete_op.execute(writer, ["/tmp/a.jpg"])
        assert unknown.code == DatabaseOperationCode.UNKNOWN_ERROR
