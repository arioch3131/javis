from types import SimpleNamespace
from unittest.mock import MagicMock

from ai_content_classifier.controllers.scan_controller import ScanController
from ai_content_classifier.models.config_models import ConfigKey


def _config_getter(key):
    if key == ConfigKey.DOCUMENT_EXTENSIONS:
        return [".txt"]
    if key == ConfigKey.IMAGE_EXTENSIONS:
        return [".jpg"]
    return []


def test_run_success_emits_result_and_progress():
    db_service = MagicMock()
    config_service = MagicMock()
    config_service.get.side_effect = _config_getter

    controller = ScanController(
        directory="/tmp",
        db_service=db_service,
        config_service=config_service,
        metadata_service=MagicMock(),
        thumbnail_service=MagicMock(),
    )
    controller.update_timer.start = MagicMock()
    controller.update_timer.stop = MagicMock()

    progress = SimpleNamespace(
        files_found=3,
        files_processed=10,
        metadata_extracted=2,
        thumbnails_generated=2,
        errors=0,
        estimated_total_files=0,
    )

    def _scan_and_process(**kwargs):
        kwargs["progress_callback"](progress)
        return [("/tmp/a.txt", "/tmp")]

    controller.scan_service = MagicMock()
    controller.scan_service.scan_and_process.side_effect = _scan_and_process

    emitted_results = []
    emitted_done = []
    controller.result.connect(lambda payload: emitted_results.append(payload))
    controller.finished.connect(lambda: emitted_done.append(True))

    controller.run()

    assert emitted_done == [True]
    assert emitted_results == [[("/tmp/a.txt", "/tmp")]]
    assert controller.all_files == [("/tmp/a.txt", "/tmp")]
    controller.update_timer.start.assert_called_once_with(1000)
    controller.update_timer.stop.assert_called_once()


def test_run_error_emits_error_signal_and_finishes():
    db_service = MagicMock()
    config_service = MagicMock()
    config_service.get.side_effect = _config_getter

    controller = ScanController(
        directory="/tmp",
        db_service=db_service,
        config_service=config_service,
        metadata_service=MagicMock(),
        thumbnail_service=MagicMock(),
    )
    controller.update_timer.stop = MagicMock()
    controller.scan_service = MagicMock()
    controller.scan_service.scan_and_process.side_effect = RuntimeError("scan failed")

    emitted_errors = []
    emitted_done = []
    controller.error.connect(lambda payload: emitted_errors.append(payload))
    controller.finished.connect(lambda: emitted_done.append(True))

    controller.run()

    assert emitted_done == [True]
    assert len(emitted_errors) == 1
    assert "scan failed" in str(emitted_errors[0][0])


def test_progress_helpers_and_cancel():
    db_service = MagicMock()
    config_service = MagicMock()
    config_service.get.side_effect = _config_getter

    controller = ScanController(
        directory="/tmp",
        db_service=db_service,
        config_service=config_service,
        metadata_service=MagicMock(),
        thumbnail_service=MagicMock(),
    )
    controller.scan_service = MagicMock()

    progress = SimpleNamespace(files_processed=20, files_found=8, estimated_total_files=0)
    updated = []
    controller.progress_updated.connect(lambda payload: updated.append(payload))

    controller._on_scan_progress(progress)
    controller._emit_current_progress()
    controller.cancel_scan()

    assert progress.estimated_total_files == 8
    assert len(updated) >= 2
    controller.scan_service.cancel.assert_called_once()
