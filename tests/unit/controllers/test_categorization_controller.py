from types import SimpleNamespace
from unittest.mock import MagicMock

from ai_content_classifier.controllers.categorization_controller import (
    CategorizationController,
    CategorizationWorker,
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
    file_manager.refresh_file_list.return_value = refreshed_files
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
    controller.categorization_completed.connect(lambda payload: completed.append(payload))
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
