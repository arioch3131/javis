from unittest.mock import MagicMock

from ai_content_classifier.services.file.file_operation_service import (
    FileOperationService,
)
from ai_content_classifier.services.file.operations import FileOperationDataKey
from ai_content_classifier.services.database.types import (
    DatabaseOperationCode,
    DatabaseOperationResult,
)


def _db_ok(**data):
    return DatabaseOperationResult(
        success=True,
        code=DatabaseOperationCode.OK,
        message="ok",
        data=data,
    )


def test_remove_files_from_database_updates_current_files_and_callbacks():
    db_service = MagicMock()
    db_service.delete_content_by_paths.return_value = _db_ok(deleted_count=2)
    service = FileOperationService(
        db_service=db_service,
        config_service=MagicMock(),
        metadata_service=MagicMock(),
        thumbnail_service=MagicMock(),
    )
    service._current_files = [
        ("/tmp/a.png", "/tmp"),
        ("/tmp/b.png", "/tmp"),
        ("/tmp/c.png", "/tmp"),
    ]
    on_files_updated = MagicMock()
    on_stats_updated = MagicMock()
    service.set_callbacks(
        on_files_updated=on_files_updated, on_stats_updated=on_stats_updated
    )

    result = service.remove_files_from_database(["/tmp/a.png", "/tmp/c.png"])

    assert result.success is True
    assert result.data[FileOperationDataKey.DELETED_COUNT.value] == 2
    db_service.delete_content_by_paths.assert_called_once_with(
        ["/tmp/a.png", "/tmp/c.png"]
    )
    assert service.current_files == [("/tmp/b.png", "/tmp")]
    on_files_updated.assert_called_once_with([("/tmp/b.png", "/tmp")])
    on_stats_updated.assert_called_once()


def test_remove_files_from_database_ignores_empty_input():
    service = FileOperationService(
        db_service=MagicMock(),
        config_service=MagicMock(),
        metadata_service=MagicMock(),
        thumbnail_service=MagicMock(),
    )

    result = service.remove_files_from_database([])

    assert result.success is True
    assert result.data[FileOperationDataKey.DELETED_COUNT.value] == 0
    service.db_service.delete_content_by_paths.assert_not_called()
