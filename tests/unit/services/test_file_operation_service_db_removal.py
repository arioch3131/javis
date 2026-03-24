from unittest.mock import MagicMock

from ai_content_classifier.services.file.file_operation_service import FileOperationService


def test_remove_files_from_database_updates_current_files_and_callbacks():
    db_service = MagicMock()
    db_service.delete_content_by_paths.return_value = 2
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
    service.set_callbacks(on_files_updated=on_files_updated, on_stats_updated=on_stats_updated)

    deleted = service.remove_files_from_database(["/tmp/a.png", "/tmp/c.png"])

    assert deleted == 2
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

    deleted = service.remove_files_from_database([])

    assert deleted == 0
    service.db_service.delete_content_by_paths.assert_not_called()
