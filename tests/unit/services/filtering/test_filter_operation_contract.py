from types import SimpleNamespace
from unittest.mock import MagicMock

from ai_content_classifier.services.database.types import (
    DatabaseOperationCode,
    DatabaseOperationResult,
)
from ai_content_classifier.services.filtering import (
    ContentFilterService,
    FilterCriterion,
)
from ai_content_classifier.services.filtering.types import FilterOperationCode


def _db_ok(*, items):
    return DatabaseOperationResult(
        success=True,
        code=DatabaseOperationCode.OK,
        message="ok",
        data={"items": items},
    )


def _assert_contract_data_shape(data: dict) -> None:
    assert set(data.keys()) == {"filtered_files", "applied_filters", "error"}


def test_contract_no_criteria_exact_payload():
    service = ContentFilterService(db_service=MagicMock(), logger=MagicMock())
    scope = {"base_items": [("/tmp/a.jpg", "/tmp")]}

    result = service.apply_filters(criteria=[], scope=scope)

    assert result.success is True
    assert result.code == FilterOperationCode.OK
    assert result.message == "No filters applied."
    _assert_contract_data_shape(result.data)
    assert result.data["filtered_files"] == [("/tmp/a.jpg", "/tmp")]
    assert result.data["applied_filters"] == []
    assert result.data["error"] is None


def test_contract_unknown_filter_exact_payload():
    service = ContentFilterService(db_service=MagicMock(), logger=MagicMock())
    scope = {"base_items": [("/tmp/a.jpg", "/tmp")]}

    result = service.apply_filters(
        criteria=[FilterCriterion(key="does_not_exist", op="eq", value="x")],
        scope=scope,
    )

    assert result.success is False
    assert result.code == FilterOperationCode.UNKNOWN_FILTER
    assert result.message == "Unknown filter key 'does_not_exist'."
    _assert_contract_data_shape(result.data)
    assert result.data["filtered_files"] == [("/tmp/a.jpg", "/tmp")]
    assert result.data["applied_filters"] == [
        {"key": "does_not_exist", "op": "eq", "value": "x"}
    ]
    assert result.data["error"] == "Unknown filter key 'does_not_exist'."


def test_contract_validation_error_exact_payload():
    service = ContentFilterService(db_service=MagicMock(), logger=MagicMock())
    scope = {"base_items": [("/tmp/a.jpg", "/tmp")]}

    result = service.apply_filters(
        criteria=[FilterCriterion(key="extension", op="range", value=".jpg")],
        scope=scope,
    )

    assert result.success is False
    assert result.code == FilterOperationCode.VALIDATION_ERROR
    assert result.message == "Unsupported operator 'range' for 'extension'."
    _assert_contract_data_shape(result.data)
    assert result.data["filtered_files"] == [("/tmp/a.jpg", "/tmp")]
    assert result.data["applied_filters"] == [
        {"key": "extension", "op": "range", "value": ".jpg"}
    ]
    assert result.data["error"] == "Unsupported operator 'range' for 'extension'."


def test_contract_database_error_exact_payload_without_fallback():
    db_service = MagicMock()
    db_service.find_items.return_value = DatabaseOperationResult(
        success=False,
        code=DatabaseOperationCode.DB_ERROR,
        message="db down",
        data={"error": "connection refused"},
    )
    service = ContentFilterService(db_service=db_service, logger=MagicMock())
    scope = {"base_items": [("/tmp/a.jpg", "/tmp")]}

    result = service.apply_filters(
        criteria=[FilterCriterion(key="category", op="in", value=["Work"])],
        scope=scope,
        allow_db_fallback=False,
    )

    assert result.success is False
    assert result.code == FilterOperationCode.DATABASE_ERROR
    assert result.message == "db down (connection refused)"
    _assert_contract_data_shape(result.data)
    assert result.data["filtered_files"] == [("/tmp/a.jpg", "/tmp")]
    assert result.data["applied_filters"] == [
        {"key": "category", "op": "in", "value": ["Work"]}
    ]
    assert result.data["error"] == "db down (connection refused)"


def test_contract_success_after_filtering_exact_payload():
    db_service = MagicMock()
    db_service.find_items.return_value = _db_ok(
        items=[SimpleNamespace(path="/tmp/a.jpg", directory="/tmp", category="Work")]
    )
    service = ContentFilterService(db_service=db_service, logger=MagicMock())

    result = service.apply_filters(
        criteria=[FilterCriterion(key="category", op="in", value=["Work"])],
        scope={"base_items": [("/tmp/a.jpg", "/tmp"), ("/tmp/b.jpg", "/tmp")]},
    )

    assert result.success is True
    assert result.code == FilterOperationCode.OK
    assert result.message == "Filters applied."
    _assert_contract_data_shape(result.data)
    assert result.data["filtered_files"] == [("/tmp/a.jpg", "/tmp")]
    assert result.data["applied_filters"] == [
        {"key": "category", "op": "in", "value": ["Work"]}
    ]
    assert result.data["error"] is None


class _ExplodingPlugin:
    key = "boom"

    def validate(self, criterion):
        return None

    def to_db_clause(self, criterion):
        return []

    def apply_memory(self, items, criterion, context):
        raise RuntimeError("explode-now")


def test_contract_unknown_error_exact_payload():
    service = ContentFilterService(db_service=MagicMock(), logger=MagicMock())
    service.registry.register(_ExplodingPlugin())
    scope = {"base_items": [("/tmp/a.jpg", "/tmp")]}

    result = service.apply_filters(
        criteria=[FilterCriterion(key="boom", op="eq", value=1)],
        scope=scope,
    )

    assert result.success is False
    assert result.code == FilterOperationCode.UNKNOWN_ERROR
    assert result.message == "Unable to apply filters due to an unexpected error."
    _assert_contract_data_shape(result.data)
    assert result.data["filtered_files"] == [("/tmp/a.jpg", "/tmp")]
    assert result.data["applied_filters"] == [{"key": "boom", "op": "eq", "value": 1}]
    assert result.data["error"] == "explode-now"
