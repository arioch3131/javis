from types import SimpleNamespace
from unittest.mock import MagicMock

from ai_content_classifier.controllers.categorization_controller import (
    CategorizationController,
    CategorizationWorker,
)
from ai_content_classifier.services.file.operations import FileOperationDataKey
from ai_content_classifier.services.file.types import (
    FileOperationCode,
    FileOperationResult,
)


def test_worker_is_image_file_helper():
    worker = CategorizationWorker(
        llm_service=MagicMock(),
        content_database_service=MagicMock(),
        file_paths=[],
        categories=[],
        config={},
    )
    assert worker._is_image_file("/tmp/a.jpg") is True
    assert worker._is_image_file("/tmp/a.pdf") is False


def test_worker_run_success_and_failure_paths():
    llm_service = MagicMock()
    llm_service.classify_image.return_value = SimpleNamespace(
        category="Work",
        confidence=0.9,
        extraction_method="llm",
        extraction_details="ok",
    )
    llm_service.classify_document.side_effect = RuntimeError("doc error")

    db_service = MagicMock()
    worker = CategorizationWorker(
        llm_service=llm_service,
        content_database_service=db_service,
        file_paths=["/tmp/a.jpg", "/tmp/b.pdf"],
        categories=["Work", "Personal"],
        config={"save_results": True, "confidence_threshold": 0.3},
    )

    progress = []
    finished = []
    worker.progress_updated.connect(lambda p, s, f: progress.append((p, s, f)))
    worker.finished.connect(lambda payload: finished.append(payload))

    worker.run()

    assert progress[-1] == (2, 1, 1)
    assert len(finished) == 1
    assert finished[0]["successful"] == 1
    assert finished[0]["failed"] == 1
    db_service.update_content_category.assert_called_once()


def test_controller_file_selection_and_filters():
    llm_controller = MagicMock()
    settings_manager = MagicMock()
    file_manager = MagicMock()
    file_manager.current_files = [
        ("/tmp/a.jpg", "/tmp"),
        ("/tmp/b.pdf", "/tmp"),
        ("/tmp/c.bin", "/tmp"),
    ]
    db_service = MagicMock()
    db_service.get_content_by_path.side_effect = [
        None,
        SimpleNamespace(category="Work"),
        None,
    ]

    controller = CategorizationController(
        llm_controller=llm_controller,
        settings_manager=settings_manager,
        file_manager=file_manager,
        content_database_service=db_service,
    )

    files = controller._get_current_view_files()
    assert files == ["/tmp/a.jpg", "/tmp/b.pdf", "/tmp/c.bin"]

    analyzed = controller._analyze_file_types(files)
    assert analyzed == {"Images": 1, "Documents": 1, "Others": 1}

    filtered = controller._filter_files_by_config(
        files,
        {
            "process_images": True,
            "process_documents": True,
            "only_uncategorized": True,
        },
    )
    assert filtered == ["/tmp/a.jpg", "/tmp/c.bin"]


def test_controller_finish_flow_emits_and_refreshes():
    llm_controller = MagicMock()
    settings_manager = MagicMock()
    file_manager = MagicMock()
    file_manager.current_files = [("/tmp/stale.jpg", "/tmp")]
    refreshed_files = [("/tmp/a.jpg", "/tmp")]
    file_manager.refresh_file_list.return_value = FileOperationResult(
        success=True,
        code=FileOperationCode.OK,
        message="ok",
        data={FileOperationDataKey.FILE_LIST.value: refreshed_files},
    )
    db_service = MagicMock()

    controller = CategorizationController(
        llm_controller=llm_controller,
        settings_manager=settings_manager,
        file_manager=file_manager,
        content_database_service=db_service,
    )
    controller.progress_dialog = MagicMock()
    controller.worker = MagicMock()

    completed = []
    controller.categorization_completed.connect(
        lambda payload: completed.append(payload)
    )
    file_manager.files_updated = MagicMock()

    results_payload = {
        "results": [
            {
                "file_path": "/tmp/a.jpg",
                "category": "Work",
                "confidence": 0.8,
                "processing_time": 0.2,
                "status": "success",
            }
        ],
        "total_processed": 1,
        "successful": 1,
        "failed": 0,
    }

    controller._on_categorization_finished(
        results_payload,
        {"save_results": False, "export_csv": False, "show_report": False},
        parent_widget=None,
    )

    assert len(completed) == 1
    file_manager.refresh_file_list.assert_called_once()
    file_manager.files_updated.emit.assert_called_once_with(refreshed_files)
    assert controller.worker is None


def test_controller_uses_integrated_operations_when_main_window_is_available():
    llm_controller = MagicMock()
    settings_manager = MagicMock()
    file_manager = MagicMock()
    file_manager.main_window = MagicMock()
    file_manager.current_files = [("/tmp/a.jpg", "/tmp")]
    db_service = MagicMock()

    controller = CategorizationController(
        llm_controller=llm_controller,
        settings_manager=settings_manager,
        file_manager=file_manager,
        content_database_service=db_service,
    )

    controller._execute_categorization(
        ["/tmp/a.jpg"],
        {
            "categories": ["Work", "Personal"],
            "process_images": True,
            "process_documents": True,
            "preview_mode": False,
        },
        parent_widget=None,
    )

    assert controller.progress_dialog is None
    file_manager.main_window.set_operation_action_handlers.assert_called_once()
    file_manager.main_window.show_operation_state.assert_called()
    controller.worker.stop()
    controller.worker.wait()


def test_controller_pushes_categorization_operation_state():
    llm_controller = MagicMock()
    settings_manager = MagicMock()
    file_manager = MagicMock()
    file_manager.main_window = MagicMock()
    db_service = MagicMock()

    controller = CategorizationController(
        llm_controller=llm_controller,
        settings_manager=settings_manager,
        file_manager=file_manager,
        content_database_service=db_service,
    )
    controller._categorization_started_at = 100.0
    controller._categorization_operation_snapshot = {
        "total_files": 10,
        "processed": 4,
        "successful": 3,
        "failed": 1,
        "current_file": "/tmp/example.jpg",
        "state": "running",
    }

    controller._push_categorization_operation_state()

    payload = file_manager.main_window.show_operation_state.call_args.args[0]
    assert payload.kind == "categorization"
    assert payload.summary == "4 / 10 files"
    assert payload.primary_action == "cancel"
    assert payload.secondary_action == "pause"
    file_manager.main_window.set_main_status_chip.assert_called_with(
        "Working...", is_busy=True
    )
    file_manager.main_window.set_progress_status_chip.assert_called_with(
        "Categorization: 4/10 files (40.0%)",
        is_busy=True,
    )
    file_manager.main_window.update_progress_bar.assert_called_with(40)


def test_worker_duplicate_cache_reuse_and_preview_break(monkeypatch):
    llm_service = MagicMock()
    llm_service.classify_document.return_value = SimpleNamespace(
        category="Work",
        confidence=0.2,
        extraction_method="llm",
        extraction_details="low confidence",
    )
    db_service = MagicMock()
    db_service.find_duplicates.return_value = {
        "hash-a": [
            SimpleNamespace(
                category="Work",
                content_metadata={"classification": {"confidence": 0.77}},
            )
        ]
    }
    db_service.get_content_by_path.side_effect = [
        SimpleNamespace(file_hash="hash-a"),
        None,
    ]

    worker = CategorizationWorker(
        llm_service=llm_service,
        content_database_service=db_service,
        file_paths=["/tmp/a.txt", "/tmp/b.txt"],
        categories=["Work"],
        config={
            "save_results": True,
            "preview_mode": True,
            "preview_count": 2,
            "confidence_threshold": 0.5,
        },
    )
    worker._wait_if_paused = lambda: None
    worker.run()

    assert len(worker.results) == 2
    assert worker.results[0]["category"] == "Work"
    assert worker.results[1]["category"] == "Uncertain"


def test_worker_duplicate_cache_handles_errors():
    worker = CategorizationWorker(
        llm_service=MagicMock(),
        content_database_service=MagicMock(),
        file_paths=[],
        categories=["Work"],
        config={"save_results": False},
    )
    worker.content_database_service.find_duplicates.side_effect = RuntimeError("boom")
    logs = []
    worker.log_message.connect(lambda message: logs.append(message))
    worker._build_hash_category_cache()
    assert logs

    worker.content_database_service.get_content_by_path.side_effect = RuntimeError("db")
    assert worker._try_reuse_duplicate_category("/tmp/a.txt") is None


def test_controller_start_automatic_categorization_paths():
    controller = CategorizationController(
        llm_controller=MagicMock(),
        settings_manager=MagicMock(),
        file_manager=MagicMock(),
        content_database_service=MagicMock(),
    )
    controller._execute_categorization = MagicMock()

    assert controller.start_automatic_categorization([], ["Work"]) is False
    assert controller.start_automatic_categorization(["/tmp/a.txt"], []) is False
    assert (
        controller.start_automatic_categorization(
            ["/tmp/a.txt"], ["Work"], {"preview_mode": True}
        )
        is True
    )
    controller._execute_categorization.assert_called_once()


def test_controller_get_current_view_files_prefers_main_window_refresh():
    file_manager = MagicMock()
    file_manager.main_window = MagicMock()
    file_manager.main_window.current_files = [("/tmp/a.txt", "/tmp"), "/tmp/b.txt"]
    file_manager.current_files = ["/tmp/should_not_be_used.txt"]

    controller = CategorizationController(
        llm_controller=MagicMock(),
        settings_manager=MagicMock(),
        file_manager=file_manager,
        content_database_service=MagicMock(),
    )

    assert controller._get_current_view_files() == ["/tmp/a.txt", "/tmp/b.txt"]
    file_manager.main_window._refresh_displayed_files.assert_called_once()


def test_controller_format_rate_estimate_and_state_helpers():
    controller = CategorizationController(
        llm_controller=MagicMock(),
        settings_manager=MagicMock(),
        file_manager=MagicMock(),
        content_database_service=MagicMock(),
    )
    assert controller._format_rate(0, "files") == "0.0 files/s"
    assert controller._format_rate(0.5, "files").endswith("files/min")
    assert controller._format_rate(2.0, "files").endswith("files/s")

    controller._categorization_operation_snapshot = {"total_files": 10, "processed": 0}
    controller._categorization_started_at = None
    assert controller._estimate_categorization_remaining() == "calculating..."

    controller.file_manager.main_window = MagicMock()
    controller._categorization_operation_snapshot = {"processed": 1, "total_files": 4}
    controller._update_categorization_working_state()
    controller._reset_categorization_working_state()
    controller.file_manager.main_window.set_main_status_chip.assert_called()


def test_controller_save_export_and_report_helpers(tmp_path, monkeypatch):
    controller = CategorizationController(
        llm_controller=MagicMock(),
        settings_manager=MagicMock(),
        file_manager=MagicMock(),
        content_database_service=MagicMock(),
    )

    results = [
        {
            "file_path": "/tmp/a.txt",
            "category": "Work",
            "confidence": 0.9,
            "processing_time": 0.12,
            "status": "success",
            "extraction_method": "llm",
        },
        {
            "file_path": "/tmp/b.txt",
            "category": "Error",
            "confidence": 0.0,
            "processing_time": 0.01,
            "status": "failed",
        },
    ]

    controller._save_results_to_database(results)
    assert controller.content_database_service.update_content_category.call_count == 2

    output_csv = tmp_path / "out.csv"
    monkeypatch.setattr(
        "ai_content_classifier.controllers.categorization_controller.QFileDialog.getSaveFileName",
        lambda *_a, **_k: (str(output_csv), "csv"),
    )
    info_calls = []
    monkeypatch.setattr(
        "ai_content_classifier.controllers.categorization_controller.QMessageBox.information",
        lambda *args, **kwargs: info_calls.append((args, kwargs)),
    )
    controller._export_results_to_csv(results, parent_widget=None)
    assert output_csv.exists()
    assert info_calls

    monkeypatch.setattr(
        "ai_content_classifier.controllers.categorization_controller.QFileDialog.getSaveFileName",
        lambda *_a, **_k: (str(tmp_path), "csv"),
    )
    critical_calls = []
    monkeypatch.setattr(
        "ai_content_classifier.controllers.categorization_controller.QMessageBox.critical",
        lambda *args, **kwargs: critical_calls.append((args, kwargs)),
    )
    controller._export_results_to_csv(results, parent_widget=None)
    assert critical_calls

    report_calls = []
    monkeypatch.setattr(
        "ai_content_classifier.controllers.categorization_controller.QMessageBox.information",
        lambda *args, **kwargs: report_calls.append((args, kwargs)),
    )
    controller._show_results_report(
        {
            "total_processed": 2,
            "successful": 1,
            "failed": 1,
            "results": results,
        },
        {"preview_mode": True},
        parent_widget=None,
    )
    assert report_calls
