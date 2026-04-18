from types import SimpleNamespace
from unittest.mock import MagicMock

from ai_content_classifier.services.database.types import (
    DatabaseOperationCode,
    DatabaseOperationResult,
)
from ai_content_classifier.services.filtering import (
    ContentFilterService,
    FilterCriterion,
    FilterOperationCode,
)


def _db_ok(*, items):
    return DatabaseOperationResult(
        success=True,
        code=DatabaseOperationCode.OK,
        message="ok",
        data={"items": items},
    )


def test_apply_filters_combines_db_and_memory_filters():
    db_service = MagicMock()
    db_service.find_items.return_value = _db_ok(
        items=[
            SimpleNamespace(path="/tmp/a.jpg", directory="/tmp", category="Work"),
            SimpleNamespace(path="/tmp/b.pdf", directory="/tmp", category="Work"),
        ]
    )
    service = ContentFilterService(db_service=db_service, logger=MagicMock())

    result = service.apply_filters(
        criteria=[
            FilterCriterion(key="category", op="in", value=["Work"]),
            FilterCriterion(key="extension", op="in", value=[".jpg"]),
        ],
        scope={
            "base_items": [
                ("/tmp/a.jpg", "/tmp"),
                ("/tmp/b.pdf", "/tmp"),
                ("/tmp/c.jpg", "/tmp"),
            ]
        },
    )

    assert result.success is True
    assert result.code == FilterOperationCode.OK
    assert result.data["filtered_files"] == [("/tmp/a.jpg", "/tmp")]
    db_service.find_items.assert_called_once()


def test_apply_filters_returns_error_for_unknown_plugin_key():
    db_service = MagicMock()
    service = ContentFilterService(db_service=db_service, logger=MagicMock())

    result = service.apply_filters(
        criteria=[FilterCriterion(key="unknown_key", op="eq", value="x")],
        scope={"base_items": [("/tmp/a.jpg", "/tmp")]},
    )

    assert result.success is False
    assert result.code == FilterOperationCode.UNKNOWN_FILTER
    assert result.data["filtered_files"] == [("/tmp/a.jpg", "/tmp")]


def test_apply_filters_accepts_singular_file_type_aliases():
    db_service = MagicMock()
    db_service.find_items.return_value = _db_ok(
        items=[SimpleNamespace(path="/tmp/a.jpg", directory="/tmp", category="Work")]
    )
    service = ContentFilterService(db_service=db_service, logger=MagicMock())

    result = service.apply_filters(
        criteria=[FilterCriterion(key="file_type", op="eq", value="Image")],
        scope={
            "base_items": [
                ("/tmp/a.jpg", "/tmp"),
                ("/tmp/b.pdf", "/tmp"),
            ]
        },
    )

    assert result.success is True
    assert result.data["filtered_files"] == [("/tmp/a.jpg", "/tmp")]


def test_apply_filters_returns_database_error_when_fallback_disabled():
    db_service = MagicMock()
    db_service.find_items.return_value = DatabaseOperationResult(
        success=False,
        code=DatabaseOperationCode.DB_ERROR,
        message="db down",
        data={"error": "connection refused"},
    )
    service = ContentFilterService(db_service=db_service, logger=MagicMock())

    result = service.apply_filters(
        criteria=[FilterCriterion(key="category", op="in", value=["Work"])],
        scope={"base_items": [("/tmp/a.jpg", "/tmp")]},
        allow_db_fallback=False,
    )

    assert result.success is False
    assert result.code == FilterOperationCode.DATABASE_ERROR
    assert result.data["filtered_files"] == [("/tmp/a.jpg", "/tmp")]
    assert "db down" in result.message.lower()


def test_apply_filters_uses_scope_fallback_when_db_fails_by_default():
    db_service = MagicMock()
    db_service.find_items.return_value = DatabaseOperationResult(
        success=False,
        code=DatabaseOperationCode.DB_ERROR,
        message="db down",
        data={"error": "connection refused"},
    )
    service = ContentFilterService(db_service=db_service, logger=MagicMock())

    base_scope = [("/tmp/a.jpg", "/tmp"), ("/tmp/b.pdf", "/tmp")]
    result = service.apply_filters(
        criteria=[FilterCriterion(key="file_type", op="eq", value="Images")],
        scope={"base_items": base_scope},
    )

    assert result.success is True
    assert result.code == FilterOperationCode.OK
    assert result.data["filtered_files"] == [("/tmp/a.jpg", "/tmp")]
