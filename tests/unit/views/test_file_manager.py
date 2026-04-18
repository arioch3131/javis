import sys
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock


for module_name in ("PyQt6", "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets"):
    module_obj = sys.modules.get(module_name)
    if isinstance(module_obj, Mock):
        del sys.modules[module_name]

from ai_content_classifier.views.managers.file_manager import FileManager  # noqa: E402
from ai_content_classifier.services.file.types import (  # noqa: E402
    FileOperationCode,
    FileOperationResult,
    FilterType,
)
from ai_content_classifier.services.file.operations import FileOperationDataKey  # noqa: E402
from ai_content_classifier.services.filtering.types import FilterOperationCode  # noqa: E402


def test_progress_dialog_cancel_routes_through_file_manager():
    manager = FileManager.__new__(FileManager)
    manager.scan_progress_dialog = MagicMock()
    manager.scan_worker = MagicMock()
    manager.cancel_current_scan = MagicMock()

    manager._connect_progress_dialog_signals()

    manager.scan_progress_dialog.cancel_requested.connect.assert_called_once_with(
        manager.cancel_current_scan
    )


def test_connect_worker_signals_quits_thread_when_worker_finishes():
    manager = FileManager.__new__(FileManager)
    manager.logger = MagicMock()
    manager.worker_thread = MagicMock()
    manager.scan_worker = MagicMock()
    manager.scan_progress_dialog = None
    manager._on_thread_finished = MagicMock()
    manager._on_scan_finished = MagicMock()
    manager._on_scan_error = MagicMock()
    manager._on_scan_completed = MagicMock()
    manager._on_scan_progress = MagicMock()
    manager._on_scan_status = MagicMock()
    manager._on_file_processed = MagicMock()
    manager._on_file_found = MagicMock()
    manager._connect_progress_dialog_signals = MagicMock()

    manager._connect_worker_signals()

    manager.scan_worker.finished.connect.assert_any_call(manager.worker_thread.quit)


def test_cancel_current_scan_only_requests_cancellation():
    manager = FileManager.__new__(FileManager)
    manager.logger = MagicMock()
    manager.is_scan_active = True
    manager.scan_worker = MagicMock()
    manager.worker_thread = MagicMock()
    manager.should_cancel_scan = False
    manager._stop_scan_ui_refresh_worker = MagicMock()
    manager._cleanup_worker_and_thread = MagicMock()

    manager.cancel_current_scan()

    assert manager.should_cancel_scan is True
    manager.scan_worker.cancel_scan.assert_called_once_with()
    manager.worker_thread.quit.assert_not_called()
    manager._stop_scan_ui_refresh_worker.assert_not_called()
    manager._cleanup_worker_and_thread.assert_not_called()


def test_create_scan_progress_dialog_prefers_main_window_operations_surface():
    manager = FileManager.__new__(FileManager)
    manager.main_window = MagicMock()
    manager.scan_progress_dialog = None

    manager._create_scan_progress_dialog("/tmp")

    assert manager.scan_progress_dialog is None


def test_push_scan_operation_state_updates_main_window_operations_panel():
    manager = FileManager.__new__(FileManager)
    manager.main_window = MagicMock()
    manager._scan_operation_log = ["[00:08:13] Scan started"]
    manager.scan_progress_dialog = None

    progress = type(
        "Progress",
        (),
        {
            "files_found": 24,
            "files_processed": 0,
            "total_files_scanned": 3942,
            "current_directory": "/tmp",
            "current_file": "/tmp/example.png",
            "scan_speed": 58.7,
            "estimated_total_files": 0,
            "errors": 0,
        },
    )()

    manager._push_scan_operation_state(progress=progress)

    operation_state = manager.main_window.show_operation_state.call_args.args[0]
    assert operation_state.kind == "scan"
    assert operation_state.summary == "3942 files scanned"
    assert operation_state.title == "Scanning: /tmp"
    assert operation_state.primary_action == "cancel"
    assert operation_state.current_item == "Root directory: /tmp"
    assert any(
        detail.label == "Scanned" and detail.value == "/tmp"
        for detail in operation_state.details
    )


def test_append_scan_operation_log_preserves_latest_scan_snapshot():
    manager = FileManager.__new__(FileManager)
    manager.main_window = MagicMock()
    manager._scan_operation_log = []
    manager._scan_operation_snapshot = {
        "files_found": 24,
        "files_processed": 0,
        "total_files_scanned": 3942,
        "current_directory": "/tmp",
        "current_file": "/tmp/example.png",
        "scan_speed": 58.7,
        "estimated_total": 0,
        "errors": 0,
    }
    manager.scan_progress_dialog = None

    manager._append_scan_operation_log("Scan started")

    operation_state = manager.main_window.show_operation_state.call_args.args[0]
    assert operation_state.summary == "3942 files scanned"
    assert any(
        detail.label == "Rate" and detail.value == "58.7 items/s"
        for detail in operation_state.details
    )
    assert any(
        detail.label == "Scanned" and detail.value == "/tmp"
        for detail in operation_state.details
    )


def test_push_scan_operation_state_uses_integrated_start_time_for_elapsed():
    manager = FileManager.__new__(FileManager)
    manager.main_window = MagicMock()
    manager._scan_operation_log = []
    manager._scan_operation_snapshot = {}
    manager.scan_progress_dialog = None
    manager._scan_operation_started_at = time.time() - 65

    manager._push_scan_operation_state()

    operation_state = manager.main_window.show_operation_state.call_args.args[0]
    assert any(
        detail.label == "Elapsed" and detail.value == "01:05"
        for detail in operation_state.details
    )


def test_push_scan_operation_state_uses_completed_title_when_finished():
    manager = FileManager.__new__(FileManager)
    manager.main_window = MagicMock()
    manager._scan_operation_log = []
    manager._scan_operation_snapshot = {}
    manager.scan_progress_dialog = None

    manager._push_scan_operation_state(
        state="completed",
        progress={
            "files_found": 24,
            "files_processed": 24,
            "total_files_scanned": 24,
            "estimated_total": 24,
        },
    )

    operation_state = manager.main_window.show_operation_state.call_args.args[0]
    assert operation_state.title == "Scan completed"
    assert operation_state.summary == "24 files found"
    assert operation_state.secondary_action == "close"


def test_push_scan_operation_state_title_shows_root_plus_first_subdirectory():
    manager = FileManager.__new__(FileManager)
    manager.main_window = MagicMock()
    manager._scan_operation_log = []
    manager._scan_operation_snapshot = {
        "scan_root_directory": "/data/source",
    }
    manager.scan_progress_dialog = None

    progress = type(
        "Progress",
        (),
        {
            "files_found": 10,
            "files_processed": 1,
            "total_files_scanned": 32,
            "current_directory": "/data/source/projects/2026/april",
            "current_file": "/data/source/projects/2026/april/report.pdf",
            "scan_speed": 8.4,
            "estimated_total_files": 0,
            "errors": 0,
        },
    )()

    manager._push_scan_operation_state(progress=progress)

    operation_state = manager.main_window.show_operation_state.call_args.args[0]
    assert operation_state.title == "Scanning: /data/source/projects"


def test_refresh_and_emit_visible_files_emits_refreshed_list_when_no_filters():
    manager = FileManager.__new__(FileManager)
    manager.file_service = MagicMock()
    manager.file_service.refresh_file_list.return_value = FileOperationResult(
        success=True,
        code=FileOperationCode.OK,
        message="ok",
        data={FileOperationDataKey.FILE_LIST.value: [("/tmp/a.png", "/tmp")]},
    )
    manager.files_updated = MagicMock()
    manager._active_filters = {
        "file_type": [],
        "category": [],
        "year": [],
        "extension": [],
    }

    result = manager.refresh_and_emit_visible_files()

    assert result.success is True
    assert result.data[FileOperationDataKey.FILE_LIST.value] == [("/tmp/a.png", "/tmp")]
    manager.files_updated.emit.assert_called_once_with([("/tmp/a.png", "/tmp")])


def test_clear_thumbnail_cache_delegates_to_services():
    manager = FileManager.__new__(FileManager)
    manager.logger = MagicMock()
    manager.file_service = MagicMock()
    manager.file_service.thumbnail_service = MagicMock()

    manager.clear_thumbnail_cache()

    manager.file_service.clear_thumbnail_disk_cache.assert_called_once()
    manager.file_service.thumbnail_service.clear_cache.assert_called_once()


def test_refresh_and_emit_visible_files_reapplies_filters_when_active():
    manager = FileManager.__new__(FileManager)
    manager.file_service = MagicMock()
    manager.file_service.refresh_file_list.return_value = FileOperationResult(
        success=True,
        code=FileOperationCode.OK,
        message="ok",
        data={FileOperationDataKey.FILE_LIST.value: [("/tmp/a.png", "/tmp")]},
    )
    manager.files_updated = MagicMock()
    manager._active_filters = {
        "file_type": [],
        "category": ["Animals"],
        "year": [],
        "extension": [],
    }
    manager._apply_cumulative_filters = MagicMock(
        return_value=FileOperationResult(
            success=True,
            code=FileOperationCode.OK,
            message="ok",
            data={FileOperationDataKey.FILTERED_FILES.value: [("/tmp/b.png", "/tmp")]},
        )
    )

    result = manager.refresh_and_emit_visible_files()

    assert result.success is True
    assert result.data[FileOperationDataKey.FILTERED_FILES.value] == [
        ("/tmp/b.png", "/tmp")
    ]
    manager._apply_cumulative_filters.assert_called_once()


def test_build_filter_criteria_normalizes_singular_file_type():
    manager = FileManager.__new__(FileManager)
    manager._active_filters = {
        "file_type": ["Image"],
        "category": [],
        "year": [],
        "extension": [],
    }
    manager._normalize_year_filters = lambda values: values
    manager._normalize_file_type_filter_value = (
        FileManager._normalize_file_type_filter_value.__get__(manager, FileManager)
    )

    criteria = manager._build_filter_criteria()

    assert len(criteria) == 1
    assert criteria[0].key == "file_type"
    assert criteria[0].value == FilterType.IMAGES.value


def test_apply_cumulative_filters_maps_database_error_code():
    manager = FileManager.__new__(FileManager)
    manager.logger = MagicMock()
    manager.file_service = MagicMock()
    manager.file_service.refresh_file_list.return_value = FileOperationResult(
        success=True,
        code=FileOperationCode.OK,
        message="ok",
        data={FileOperationDataKey.FILE_LIST.value: [("/tmp/a.png", "/tmp")]},
    )
    manager.content_filter_service = MagicMock()
    manager.content_filter_service.apply_filters.return_value = SimpleNamespace(
        success=False,
        code=FilterOperationCode.DATABASE_ERROR,
        message="database down",
        data={"error": "database down"},
    )
    manager.files_updated = MagicMock()
    manager.filter_applied = MagicMock()
    manager.filter_failed = MagicMock()
    manager._active_filters = {
        "file_type": [],
        "category": [],
        "year": [],
        "extension": [],
    }
    manager._build_filter_criteria = MagicMock(return_value=[])
    manager._map_filter_code_to_file_code = (
        FileManager._map_filter_code_to_file_code.__get__(manager, FileManager)
    )

    result = manager._apply_cumulative_filters()

    assert result.success is False
    assert result.code == FileOperationCode.DATABASE_ERROR
    assert result.data[FileOperationDataKey.FILTERED_FILES.value] == [
        ("/tmp/a.png", "/tmp")
    ]
    manager.filter_failed.emit.assert_called_once()
