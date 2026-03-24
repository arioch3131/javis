from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ai_content_classifier.services.file.file_operation_service import (
    FileOperationService,
    FilterType,
    ScanStatistics,
)
from ai_content_classifier.services.file.file_type_service import FileCategory


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
        service.process_scan_results(file_list)
        assert service.current_files == file_list
        assert service.last_scan_stats.files_found == 2
        assert completed == [file_list]
        assert updated == [file_list]
        assert len(stats_cb) == 1

    def test_process_scan_results_exception(self, service):
        errors = []
        service.set_callbacks(on_scan_error=errors.append, on_scan_completed=lambda _x: 1 / 0)
        service.process_scan_results([("/a.jpg", "/")])
        assert len(errors) == 1
        assert "processing scan results" in errors[0].lower()

    def test_process_file_result_updates_stats_and_callback(self, service):
        processed = []
        service.set_callbacks(on_file_processed=processed.append)
        service.process_file_result("/a.jpg", metadata_ok=True, thumbnail_ok=False, error_message="e")
        assert service.last_scan_stats.metadata_extracted == 1
        assert service.last_scan_stats.thumbnails_generated == 0
        assert service.last_scan_stats.errors == 1
        assert processed[0].file_path == "/a.jpg"

    def test_process_file_result_callback_exception_is_caught(self, service):
        service.set_callbacks(on_file_processed=lambda _x: 1 / 0)
        service.process_file_result("/a.jpg", metadata_ok=False, thumbnail_ok=True)
        service.logger.error.assert_called()

    def test_refresh_file_list_success(self, service):
        valid_item = SimpleNamespace(path="/ok.jpg", directory="/ok")
        invalid_item = SimpleNamespace(path="/missing-dir")
        service.db_service.find_items.return_value = [valid_item, invalid_item]
        service.db_service.count_all_items.return_value = 2
        updated = []
        service.set_callbacks(on_files_updated=updated.append)

        result = service.refresh_file_list()
        assert result == [("/ok.jpg", "/ok")]
        service.db_service.force_database_sync.assert_called_once()
        service.db_service.count_all_items.assert_called_once()
        updated.assert_called if False else None
        assert updated == [[("/ok.jpg", "/ok")]]

    def test_refresh_file_list_exception(self, service):
        errors = []
        service.set_callbacks(on_scan_error=errors.append)
        service.db_service.find_items.side_effect = RuntimeError("db fail")
        result = service.refresh_file_list()
        assert result == []
        assert len(errors) == 1

    def test_apply_filter_all_files_and_multi_direct(self, service):
        service._current_files = [("/a.jpg", "/")]
        assert service.apply_filter(FilterType.ALL_FILES) == [("/a.jpg", "/")]
        assert service.apply_filter(FilterType.MULTI_CATEGORY) == [("/a.jpg", "/")]
        assert service.apply_filter(FilterType.MULTI_YEAR) == [("/a.jpg", "/")]
        assert service.apply_filter(FilterType.MULTI_EXTENSION) == [("/a.jpg", "/")]

    def test_apply_filter_uncategorized_uses_helper(self, service):
        with patch.object(service, "_filter_uncategorized", return_value=[("/u", "/")]) as helper:
            result = service.apply_filter(FilterType.UNCATEGORIZED)
        assert result == [("/u", "/")]
        helper.assert_called_once()

    def test_apply_filter_standard_types_query_database(self, service):
        fake_filter = MagicMock()
        service.db_service.find_items.return_value = [SimpleNamespace(path="/i.jpg", directory="/d")]
        with patch(
            "ai_content_classifier.services.file.file_operation_service.ContentFilter",
            return_value=fake_filter,
        ):
            result = service.apply_filter(FilterType.IMAGES)
        fake_filter.by_type.assert_called_once_with("image")
        service.db_service.find_items.assert_called_once()
        assert result == [("/i.jpg", "/d")]

    def test_apply_filter_unknown_fallbacks_to_extension_filter(self, service):
        class UnknownFilter:
            value = "unknown"

            def __eq__(self, _other):
                return False

        service.db_service.find_items.return_value = [SimpleNamespace(path="/db", directory="/")]
        with patch.object(service, "_filter_files_by_type", return_value=[("/f", "/")]) as helper:
            result = service.apply_filter(UnknownFilter())
        helper.assert_called_once()
        # Current implementation still issues a DB query when `content_filter` exists in locals().
        assert result == [("/db", "/")]

    def test_apply_filter_exception_returns_original(self, service):
        service._current_files = [("/a", "/")]
        service.db_service.find_items.side_effect = RuntimeError("oops")
        result = service.apply_filter(FilterType.IMAGES)
        assert result == [("/a", "/")]

    def test_apply_filter_to_list_for_categories(self, service):
        files = [("/a.jpg", "/"), ("/b.pdf", "/")]
        service.db_service.get_content_by_path.return_value = SimpleNamespace(category="Uncategorized")
        assert service.apply_filter_to_list(files, FilterType.ALL_FILES) == files
        assert service.apply_filter_to_list(files, FilterType.UNCATEGORIZED) == files

    def test_apply_filter_to_list_for_type_checks(self, service):
        files = [("/a.jpg", "/"), ("/b.pdf", "/")]
        with patch(
            "ai_content_classifier.services.file.file_operation_service.FileTypeService.is_image_file",
            side_effect=lambda p: p.endswith(".jpg"),
        ):
            assert service.apply_filter_to_list(files, FilterType.IMAGES) == [("/a.jpg", "/")]
        with patch(
            "ai_content_classifier.services.file.file_operation_service.FileTypeService.get_file_category",
            return_value=FileCategory.OTHER,
        ):
            assert service.apply_filter_to_list(files, FilterType.OTHER) == files

    def test_apply_multi_filters_to_list(self, service):
        files = [("/a.jpg", "/"), ("/b.pdf", "/")]
        service.db_service.get_content_by_path.side_effect = [
            SimpleNamespace(category="Work", year_taken=2020, date_created=None, date_modified=None, date_indexed=None, content_metadata=None),
            SimpleNamespace(category="Personal", year_taken=None, date_created=SimpleNamespace(year=2021), date_modified=None, date_indexed=None, content_metadata=None),
        ]
        assert service.apply_multi_category_filter_to_list(files, ["Work"]) == [("/a.jpg", "/")]

        service.db_service.get_content_by_path.side_effect = [
            SimpleNamespace(category="X", year_taken=2020, date_created=None, date_modified=None, date_indexed=None, content_metadata=None),
            SimpleNamespace(category="Y", year_taken=None, date_created=SimpleNamespace(year=2021), date_modified=None, date_indexed=None, content_metadata=None),
        ]
        assert service.apply_multi_year_filter_to_list(files, [2021]) == [("/b.pdf", "/")]
        assert service.apply_multi_extension_filter_to_list(files, ["jpg"]) == [("/a.jpg", "/")]

    def test_private_filters_and_utilities(self, service):
        service.db_service.find_items.return_value = [
            SimpleNamespace(path="/u", directory="/", category="Uncategorized")
        ]
        assert service._filter_uncategorized() == [("/u", "/")]
        service.db_service.find_items.side_effect = RuntimeError("fail")
        assert service._filter_uncategorized() == []

        service._current_files = [("/x.unk", "/")]
        with patch(
            "ai_content_classifier.services.file.file_operation_service.FileTypeService.get_file_category",
            return_value=FileCategory.OTHER,
        ):
            assert service._filter_files_by_type(FilterType.OTHER) == [("/x.unk", "/")]

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
        with patch.object(service, "_filter_files_by_type", return_value=[("/a.jpg", "/")]):
            counts = service.get_file_count_by_type()
        assert counts["All Files"] == 2
        assert "multi_category" not in counts

        assert service.file_count == 2
        assert service.current_files == [("/a.jpg", "/"), ("/b.pdf", "/")]
        assert service.current_filter == FilterType.ALL_FILES

        service.cleanup()
        service.thumbnail_service.cleanup.assert_called_once()
        service.metadata_service.clear_cache.assert_called_once()
        assert service.file_count == 0
        assert isinstance(service.last_scan_stats, ScanStatistics)
