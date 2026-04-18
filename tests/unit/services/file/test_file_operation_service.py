import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ai_content_classifier.services.file.file_operation_service import (
    FileOperationService,
)
from ai_content_classifier.services.file.operations import FileOperationDataKey
from ai_content_classifier.services.file.types import (
    FileOperationCode,
    FileOperationResult,
    ScanStatistics,
)
from ai_content_classifier.services.database.types import (
    DatabaseOperationCode,
    DatabaseOperationResult,
)
from ai_content_classifier.services.filtering.types import FilterOperationCode


def _db_ok(**data):
    return DatabaseOperationResult(
        success=True,
        code=DatabaseOperationCode.OK,
        message="ok",
        data=data,
    )


class TestFileOperationService:
    @pytest.fixture
    def service(self):
        db_service = MagicMock()
        config_service = MagicMock()
        metadata_service = MagicMock()
        thumbnail_service = MagicMock()

        svc = FileOperationService(
            db_service=db_service,
            config_service=config_service,
            metadata_service=metadata_service,
            thumbnail_service=thumbnail_service,
        )
        svc.logger = MagicMock()
        return svc

    def test_process_scan_results_success(self, service):
        completed = []
        updated = []
        stats_cb = []
        service.set_callbacks(
            on_scan_completed=completed.append,
            on_files_updated=updated.append,
            on_stats_updated=stats_cb.append,
        )
        file_list = [("/a.jpg", "/"), ("/b.pdf", "/")]
        result = service.process_scan_results(file_list)
        assert result.success is True
        assert isinstance(result, FileOperationResult)
        assert service.current_files == file_list
        assert service.last_scan_stats.files_found == 2
        assert completed == [file_list]
        assert updated == [file_list]
        assert len(stats_cb) == 1

    def test_process_scan_results_exception(self, service):
        errors = []
        service.set_callbacks(
            on_scan_error=errors.append, on_scan_completed=lambda _x: 1 / 0
        )
        result = service.process_scan_results([("/a.jpg", "/")])
        assert result.success is False
        assert len(errors) == 1
        assert "processing scan results" in errors[0].lower()

    def test_process_scan_results_operation_failure_notifies_error_callback(
        self, service
    ):
        errors = []
        service.set_callbacks(on_scan_error=errors.append)
        service._process_scan_results_operation.execute = MagicMock(
            return_value=FileOperationResult(
                success=False,
                code=FileOperationCode.UNKNOWN_ERROR,
                message="scan failed",
                data={},
            )
        )

        result = service.process_scan_results([("/a.jpg", "/")])

        assert result.success is False
        assert errors == ["scan failed"]

    def test_process_file_result_updates_stats_and_callback(self, service):
        processed = []
        service.set_callbacks(on_file_processed=processed.append)
        result = service.process_file_result(
            "/a.jpg", metadata_ok=True, thumbnail_ok=False, error_message="e"
        )
        assert result.success is True
        assert service.last_scan_stats.metadata_extracted == 1
        assert service.last_scan_stats.thumbnails_generated == 0
        assert service.last_scan_stats.errors == 1
        assert processed[0].file_path == "/a.jpg"

    def test_process_file_result_callback_exception_is_caught(self, service):
        service.set_callbacks(on_file_processed=lambda _x: 1 / 0)
        result = service.process_file_result(
            "/a.jpg", metadata_ok=False, thumbnail_ok=True
        )
        assert result.success is False
        service.logger.error.assert_called()

    def test_process_file_result_rejects_invalid_operation_payload(self, service):
        service._process_file_result_operation.execute = MagicMock(
            return_value=FileOperationResult(
                success=True,
                code=FileOperationCode.OK,
                message="ok",
                data={FileOperationDataKey.FILE_PROCESSING_RESULT.value: "invalid"},
            )
        )

        result = service.process_file_result(
            "/a.jpg", metadata_ok=True, thumbnail_ok=True
        )

        assert result.success is False
        assert result.code == FileOperationCode.UNKNOWN_ERROR

    def test_refresh_file_list_success(self, service):
        valid_item = SimpleNamespace(path="/ok.jpg", directory="/ok")
        invalid_item = SimpleNamespace(path="/missing-dir")
        service.db_service.find_items.return_value = _db_ok(
            items=[valid_item, invalid_item]
        )
        service.db_service.count_all_items.return_value = _db_ok(count=2)
        updated = []
        service.set_callbacks(on_files_updated=updated.append)

        result = service.refresh_file_list()
        assert result.success is True
        assert result.data[FileOperationDataKey.FILE_LIST.value] == [("/ok.jpg", "/ok")]
        service.db_service.force_database_sync.assert_called_once()
        service.db_service.count_all_items.assert_called_once()
        updated.assert_called if False else None
        assert updated == [[("/ok.jpg", "/ok")]]
        assert service._current_content_by_path["/ok.jpg"] is valid_item

    def test_refresh_file_list_exception(self, service):
        errors = []
        service.set_callbacks(on_scan_error=errors.append)
        service.db_service.find_items.side_effect = RuntimeError("db fail")
        result = service.refresh_file_list()
        assert result.success is False
        assert result.data[FileOperationDataKey.FILE_LIST.value] == []
        assert len(errors) == 1

    def test_refresh_file_list_operation_failure_notifies_error_callback(self, service):
        errors = []
        service.set_callbacks(on_scan_error=errors.append)
        service._refresh_file_list_operation.execute = MagicMock(
            return_value=FileOperationResult(
                success=False,
                code=FileOperationCode.UNKNOWN_ERROR,
                message="refresh failed",
                data={},
            )
        )

        result = service.refresh_file_list()

        assert result.success is False
        assert errors == ["refresh failed"]

    def test_utilities(self, service):
        service.thumbnail_service.get_thumbnail_path.return_value = "/thumb.png"
        assert service.get_thumbnail_path("/a.jpg") == "/thumb.png"
        service.thumbnail_service.get_thumbnail_path.side_effect = RuntimeError("e")
        assert service.get_thumbnail_path("/a.jpg") is None

        service.metadata_service.get_all_metadata.return_value = {"k": "v"}
        assert service.get_file_metadata("/a.jpg") == {"k": "v"}
        service.metadata_service.get_all_metadata.side_effect = RuntimeError("e")
        assert service.get_file_metadata("/a.jpg") == {}

    def test_get_file_count_by_type_properties_and_cleanup(self, service):
        service._current_files = [("/a.jpg", "/"), ("/b.pdf", "/")]
        service.db_service.find_items.side_effect = RuntimeError("db unavailable")
        counts = service.get_file_count_by_type()
        assert counts["All Files"] == 2
        assert counts["Images"] == 1
        assert "multi_category" not in counts

        assert service.file_count == 2
        assert service.current_files == [("/a.jpg", "/"), ("/b.pdf", "/")]

        service.cleanup()
        service.thumbnail_service.cleanup.assert_called_once()
        service.metadata_service.clear_cache.assert_called_once()
        assert service.file_count == 0
        assert isinstance(service.last_scan_stats, ScanStatistics)

    def test_get_file_count_by_type_handles_internal_exception(self, service):
        service._current_files = [("/a.jpg", "/")]
        service._run_filter_criteria = MagicMock(side_effect=RuntimeError("boom"))

        counts = service.get_file_count_by_type()

        assert counts == {}

    def test_clear_current_files_resets_state_and_stats(self, service):
        service._current_files = [("/a.jpg", "/")]
        service._current_content_by_path = {"/a.jpg": SimpleNamespace(path="/a.jpg")}
        service._last_scan_stats.files_found = 42

        service.clear_current_files()

        assert service.current_files == []
        assert service.last_scan_stats.files_found == 0

    def test_resolve_thumbnail_cache_dir_for_platforms(self, service):
        with patch(
            "ai_content_classifier.services.file.file_operation_service.sys.platform",
            "win32",
        ):
            win_path = service._resolve_thumbnail_cache_dir()
        with patch(
            "ai_content_classifier.services.file.file_operation_service.sys.platform",
            "darwin",
        ):
            mac_path = service._resolve_thumbnail_cache_dir()
        with patch(
            "ai_content_classifier.services.file.file_operation_service.sys.platform",
            "linux",
        ):
            linux_path = service._resolve_thumbnail_cache_dir()

        assert win_path.endswith("thumbnails")
        assert mac_path.endswith("thumbnails")
        assert linux_path.endswith("thumbnails")

    def test_clear_thumbnail_disk_cache_runtime_and_fallback_paths(self, service):
        runtime = MagicMock()
        with patch(
            "ai_content_classifier.services.file.file_operation_service.get_cache_runtime",
            return_value=runtime,
        ):
            runtime.clear.return_value = True
            service.clear_thumbnail_disk_cache()
            runtime.clear.assert_called_with(adapter="thumbnail_disk")

        runtime = MagicMock()
        with (
            patch(
                "ai_content_classifier.services.file.file_operation_service.get_cache_runtime",
                return_value=runtime,
            ),
            patch(
                "ai_content_classifier.services.file.file_operation_service.os.path.isdir",
                return_value=False,
            ),
        ):
            runtime.clear.side_effect = RuntimeError("cache down")
            service.clear_thumbnail_disk_cache()

        runtime = MagicMock()
        with (
            patch(
                "ai_content_classifier.services.file.file_operation_service.get_cache_runtime",
                return_value=runtime,
            ),
            patch(
                "ai_content_classifier.services.file.file_operation_service.os.path.isdir",
                return_value=True,
            ),
            patch(
                "ai_content_classifier.services.file.file_operation_service.shutil.rmtree",
                side_effect=OSError("cannot remove"),
            ),
        ):
            runtime.clear.return_value = False
            service.clear_thumbnail_disk_cache()

    def test_cleanup_handles_dependency_exceptions(self, service):
        service.thumbnail_service.cleanup.side_effect = RuntimeError("fail")

        service.cleanup()

        service.logger.error.assert_called()

    def test_run_filter_criteria_maps_database_error_code(self, service):
        service._content_filter_service.apply_filters = MagicMock(
            return_value=SimpleNamespace(
                success=False,
                code=FilterOperationCode.DATABASE_ERROR,
                message="db issue",
                data={"error": "db issue"},
            )
        )

        result = service._run_filter_criteria(
            criteria=[],
            base_items=[("/tmp/a.jpg", "/tmp")],
            allow_db_fallback=False,
        )

        assert result.success is False
        assert result.code == FileOperationCode.DATABASE_ERROR
        assert result.data[FileOperationDataKey.FILTERED_FILES.value] == [
            ("/tmp/a.jpg", "/tmp")
        ]

    def test_open_file_returns_file_not_found_when_path_missing(self, service):
        result = service.open_file("")
        assert result.success is False
        assert result.code == FileOperationCode.FILE_NOT_FOUND

    def test_open_file_returns_file_not_found_when_path_is_directory(self, service):
        with patch(
            "ai_content_classifier.services.file.operations.open_file_operation.os.path.isfile",
            return_value=False,
        ):
            result = service.open_file("/tmp/existing-directory")

        assert result.success is False
        assert result.code == FileOperationCode.FILE_NOT_FOUND

    def test_open_file_returns_file_not_found_when_path_is_broken_symlink(
        self, service
    ):
        with patch(
            "ai_content_classifier.services.file.operations.open_file_operation.os.path.isfile",
            return_value=False,
        ):
            result = service.open_file("/tmp/broken-link")

        assert result.success is False
        assert result.code == FileOperationCode.FILE_NOT_FOUND

    def test_open_file_linux_success(self, service):
        with (
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.os.path.isfile",
                return_value=True,
            ),
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.sys.platform",
                "linux",
            ),
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    args=["xdg-open", "/tmp/example.txt"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
            ) as run_mock,
        ):
            result = service.open_file("/tmp/example.txt")

        assert result.success is True
        assert result.code == FileOperationCode.OK
        run_mock.assert_called_once()

    def test_open_file_no_default_app_when_open_command_missing(self, service):
        with (
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.os.path.isfile",
                return_value=True,
            ),
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.sys.platform",
                "linux",
            ),
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.subprocess.run",
                side_effect=FileNotFoundError("xdg-open not found"),
            ),
        ):
            result = service.open_file("/tmp/example.txt")

        assert result.success is False
        assert result.code == FileOperationCode.NO_DEFAULT_APP

    def test_open_file_windows_permission_error_maps_to_access_denied(self, service):
        with (
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.os.path.isfile",
                return_value=True,
            ),
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.sys.platform",
                "win32",
            ),
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.os.startfile",
                side_effect=PermissionError("denied"),
                create=True,
            ),
        ):
            result = service.open_file("C:\\tmp\\example.txt")

        assert result.success is False
        assert result.code == FileOperationCode.ACCESS_DENIED

    def test_open_file_windows_success(self, service):
        with (
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.os.path.isfile",
                return_value=True,
            ),
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.sys.platform",
                "win32",
            ),
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.os.startfile",
                return_value=None,
                create=True,
            ) as startfile_mock,
        ):
            result = service.open_file("C:\\tmp\\example.txt")

        assert result.success is True
        assert result.code == FileOperationCode.OK
        startfile_mock.assert_called_once_with("C:\\tmp\\example.txt")

    def test_open_file_windows_without_startfile_returns_unknown_error(self, service):
        with (
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.os.path.isfile",
                return_value=True,
            ),
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.sys.platform",
                "win32",
            ),
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.os.startfile",
                new=None,
                create=True,
            ),
        ):
            result = service.open_file("C:\\tmp\\example.txt")

        assert result.success is False
        assert result.code == FileOperationCode.UNKNOWN_ERROR
        assert "not supported" in result.message.lower()

    def test_open_file_unsupported_platform_returns_unknown_error(self, service):
        with (
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.os.path.isfile",
                return_value=True,
            ),
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.sys.platform",
                "plan9",
            ),
        ):
            result = service.open_file("/tmp/example.txt")

        assert result.success is False
        assert result.code == FileOperationCode.UNKNOWN_ERROR
        assert "plan9" in result.message

    def test_open_file_darwin_maps_permission_denied_from_open_command(self, service):
        with (
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.os.path.isfile",
                return_value=True,
            ),
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.sys.platform",
                "darwin",
            ),
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    args=["open", "/tmp/example.txt"],
                    returncode=1,
                    stdout="",
                    stderr="Permission denied",
                ),
            ),
        ):
            result = service.open_file("/tmp/example.txt")

        assert result.success is False
        assert result.code == FileOperationCode.ACCESS_DENIED

    def test_open_file_linux_maps_no_default_app_from_return_code(self, service):
        with (
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.os.path.isfile",
                return_value=True,
            ),
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.sys.platform",
                "linux",
            ),
            patch(
                "ai_content_classifier.services.file.operations.open_file_operation.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    args=["xdg-open", "/tmp/example.txt"],
                    returncode=2,
                    stdout="",
                    stderr="",
                ),
            ),
        ):
            result = service.open_file("/tmp/example.txt")

        assert result.success is False
        assert result.code == FileOperationCode.NO_DEFAULT_APP

    def test_open_file_oserror_winerror_mappings(self, service):
        scenarios = [
            (5, FileOperationCode.ACCESS_DENIED),
            (2, FileOperationCode.FILE_NOT_FOUND),
            (3, FileOperationCode.FILE_NOT_FOUND),
            (1155, FileOperationCode.NO_DEFAULT_APP),
            (9999, FileOperationCode.UNKNOWN_ERROR),
        ]
        for winerror, expected_code in scenarios:
            with (
                patch(
                    "ai_content_classifier.services.file.operations.open_file_operation.os.path.isfile",
                    return_value=True,
                ),
                patch(
                    "ai_content_classifier.services.file.operations.open_file_operation.sys.platform",
                    "win32",
                ),
                patch(
                    "ai_content_classifier.services.file.operations.open_file_operation.os.startfile",
                    side_effect=OSError("boom"),
                    create=True,
                ) as startfile_mock,
            ):
                startfile_mock.side_effect.winerror = winerror
                result = service.open_file("C:\\tmp\\example.txt")
            assert result.success is False
            assert result.code == expected_code

    def test_map_open_command_failure_unknown_error_fallback(self, service):
        process = subprocess.CompletedProcess(
            args=["xdg-open", "/tmp/example.txt"],
            returncode=1,
            stdout="failure",
            stderr="",
        )
        result = service._open_file_operation._map_open_command_failure(
            process=process,
            command="xdg-open",
            file_path="/tmp/example.txt",
        )
        assert result.success is False
        assert result.code == FileOperationCode.UNKNOWN_ERROR
        assert result.data["return_code"] == 1
