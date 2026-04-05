from types import SimpleNamespace
from unittest.mock import MagicMock

from ai_content_classifier.services.file.scan_pipeline_service import (
    ScanPipelineService,
)


def _build_service():
    scanner = MagicMock()
    db_service = MagicMock()
    metadata_service = MagicMock()
    thumbnail_service = MagicMock()
    service = ScanPipelineService(
        scanner=scanner,
        db_service=db_service,
        metadata_service=metadata_service,
        thumbnail_service=thumbnail_service,
        batch_size=1,
        max_workers=1,
        queue_maxsize=4,
    )
    service.logger = MagicMock()
    return service, scanner, db_service, metadata_service, thumbnail_service


def test_run_pipeline_processes_files_and_emits_callbacks():
    service, scanner, db, metadata_service, thumbnail_service = _build_service()

    def scan_directory(directory, allowed_extensions, progress_callback):
        _ = allowed_extensions
        progress_callback(
            SimpleNamespace(
                files_found=2,
                total_files_scanned=2,
                directories_scanned=1,
                current_directory=directory,
                current_file="/tmp/a.jpg",
                scan_speed=10.0,
            )
        )
        yield "/tmp/a.jpg", "/tmp"
        progress_callback(
            SimpleNamespace(
                files_found=2,
                total_files_scanned=2,
                directories_scanned=1,
                current_directory=directory,
                current_file="/tmp/b.pdf",
                scan_speed=10.0,
            )
        )
        yield "/tmp/b.pdf", "/tmp"

    scanner.scan_directory.side_effect = scan_directory
    db.get_content_by_path.return_value = None
    db.create_content_item.return_value = MagicMock()
    metadata_service.get_all_metadata.return_value = {"k": "v"}
    thumbnail_service.create_thumbnail.return_value = SimpleNamespace(success=True)

    progress_events = []
    processed_events = []
    processed = service.run_pipeline(
        directory="/tmp",
        progress_callback=progress_events.append,
        file_processed_callback=lambda *args: processed_events.append(args),
    )

    assert processed == [("/tmp/a.jpg", "/tmp"), ("/tmp/b.pdf", "/tmp")]
    assert len(progress_events) >= 2
    assert len(processed_events) == 2
    db.create_content_item.assert_called()


def test_cancel_requests_scanner_cancellation():
    service, scanner, *_ = _build_service()
    service.cancel()
    assert service._is_cancelled is True
    scanner.cancel_scan.assert_called_once()


def test_process_single_file_existing_item_short_circuit():
    service, _, db, metadata_service, thumbnail_service = _build_service()
    db.get_content_by_path.return_value = MagicMock()

    result = service._process_single_file("/tmp/existing.jpg", "/tmp")

    assert result["success"] is True
    assert result["metadata_success"] is False
    assert result["thumbnail_success"] is False
    metadata_service.get_all_metadata.assert_not_called()
    thumbnail_service.create_thumbnail.assert_not_called()
    db.create_content_item.assert_not_called()


def test_process_single_file_error_path_sets_error():
    service, _, db, metadata_service, thumbnail_service = _build_service()
    db.get_content_by_path.return_value = None
    metadata_service.get_all_metadata.return_value = {"error": "bad metadata"}
    thumbnail_service.create_thumbnail.return_value = SimpleNamespace(success=False)
    db.create_content_item.side_effect = RuntimeError("insert failed")

    result = service._process_single_file("/tmp/a.jpg", "/tmp")

    assert result["success"] is False
    assert result["metadata_success"] is False
    assert result["thumbnail_success"] is False
    assert "insert failed" in result["error"]


def test_is_image_file_and_determine_content_type():
    service, *_ = _build_service()

    assert service._is_image_file("/tmp/a.JPG") is True
    assert service._is_image_file("/tmp/a.pdf") is False

    assert service._determine_content_type("/tmp/a.jpg") == "image"
    assert service._determine_content_type("/tmp/a.pdf") == "document"
    assert service._determine_content_type("/tmp/a.mp4") == "video"
    assert service._determine_content_type("/tmp/a.mp3") == "audio"
    assert service._determine_content_type("/tmp/a.unknown") == "content_item"
