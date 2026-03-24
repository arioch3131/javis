from unittest.mock import MagicMock

from ai_content_classifier.controllers.auto_organization_controller import (
    AutoOrganizationController,
    OrganizationConfig,
    OrganizationResult,
    OrganizationWorker,
)


def test_worker_collects_results_and_reports_progress():
    service = MagicMock()
    service.organize_single_file.side_effect = [
        OrganizationResult(True, "/a", "/t/a", "copy"),
        OrganizationResult(False, "/b", "", "copy", error_message="err"),
    ]
    config = OrganizationConfig("/target", "By Category", "copy")
    worker = OrganizationWorker(service, ["/a", "/b"], config)

    progress = []
    organized = []
    completed = []
    worker.progress_updated.connect(lambda p, t: progress.append((p, t)))
    worker.file_organized.connect(lambda s, t, a: organized.append((s, t, a)))
    worker.organization_completed.connect(lambda results: completed.append(results))

    worker.run()

    assert progress == [(1, 2), (2, 2)]
    assert organized == [("/a", "/t/a", "copy")]
    assert len(completed) == 1
    assert len(completed[0]) == 2


def test_start_organization_rejects_when_already_running():
    controller = AutoOrganizationController(content_database_service=MagicMock())
    controller.is_organizing = True

    errors = []
    controller.organization_error.connect(lambda msg: errors.append(msg))
    ok = controller.start_organization([], {})

    assert ok is False
    assert len(errors) == 1


def test_start_organization_rejects_invalid_config():
    controller = AutoOrganizationController(content_database_service=MagicMock())
    controller.service = MagicMock()
    controller.service.validate_config.return_value = (False, "bad config")

    errors = []
    controller.organization_error.connect(lambda msg: errors.append(msg))

    ok = controller.start_organization(
        [("/a.txt", "/")],
        {"target_directory": "/tmp/t", "organization_structure": "By Category"},
    )

    assert ok is False
    assert len(errors) == 1
    assert "Configuration invalide" in errors[0]


def test_generate_preview_success_and_supported_helpers():
    controller = AutoOrganizationController(content_database_service=MagicMock())
    controller.service = MagicMock()
    controller.service.structure_handlers = {"By Category": object(), "By Year": object()}
    controller.service.validate_config.return_value = (True, None)
    controller.service.get_organization_preview.return_value = {"structure": {}}

    emitted = []
    controller.preview_ready.connect(lambda payload: emitted.append(payload))
    controller.generate_preview(
        [("/a.txt", "/")],
        {"target_directory": "/tmp/t", "organization_structure": "By Category"},
    )

    assert len(emitted) == 1
    assert emitted[0]["config"]["target_directory"] == "/tmp/t"
    assert controller.get_supported_structures() == ["By Category", "By Year"]


def test_completion_and_cancel_cleanup_paths():
    controller = AutoOrganizationController(content_database_service=MagicMock())
    controller.service = MagicMock()
    controller.update_timer.stop = MagicMock()

    worker = MagicMock()
    worker.config = OrganizationConfig("/tmp/t", "By Category", "copy")
    worker.should_cancel = True
    controller.current_worker = worker
    controller.is_organizing = True

    controller.service.calculate_statistics.return_value = {
        "successful": 1,
        "total_files": 1,
    }

    completed = []
    controller.organization_completed.connect(lambda payload: completed.append(payload))
    controller._on_organization_completed([OrganizationResult(True, "/a", "/b", "copy")])

    assert len(completed) == 1
    assert completed[0]["cancelled"] is True
    assert controller.is_organizing is False
    assert controller.current_worker is None

    # Cancellation path
    worker2 = MagicMock()
    worker2.wait.return_value = False
    controller.current_worker = worker2
    controller.is_organizing = True

    cancelled = []
    controller.organization_cancelled.connect(lambda: cancelled.append(True))
    controller.cancel_organization()

    assert cancelled == [True]
    worker2.cancel.assert_called_once()
    worker2.terminate.assert_called_once()


def test_start_organization_updates_integrated_operations_host():
    controller = AutoOrganizationController(content_database_service=MagicMock())
    controller.service = MagicMock()
    controller.service.validate_config.return_value = (True, None)
    controller.service.prepare_target_structure.return_value = True
    controller.bind_main_window(MagicMock())

    ok = controller.start_organization(
        [("/a.txt", "/")],
        {"target_directory": "/tmp/t", "organization_structure": "By Category"},
    )

    assert ok is True
    controller.main_window.set_operation_action_handlers.assert_called_once()
    controller.main_window.show_operation_state.assert_called()
    controller.current_worker.cancel()
    controller.current_worker.wait()


def test_completed_organization_exposes_open_folder_action():
    controller = AutoOrganizationController(content_database_service=MagicMock())
    controller.service = MagicMock()
    controller.bind_main_window(MagicMock())
    controller.current_worker = MagicMock()
    controller.current_worker.config = OrganizationConfig("/tmp/t", "By Category", "copy")
    controller.current_worker.should_cancel = False
    controller.is_organizing = True
    controller._organization_started_at = 100.0
    controller._organization_snapshot = {
        "processed": 1,
        "total": 1,
        "successful": 1,
        "failed": 0,
        "state": "running",
        "target_directory": "/tmp/t",
    }
    controller.service.calculate_statistics.return_value = {
        "successful": 1,
        "failed": 0,
        "total_files": 1,
        "target_directory": "/tmp/t",
    }

    controller._on_organization_completed([OrganizationResult(True, "/a", "/tmp/t/a", "copy")])

    payload = controller.main_window.show_operation_state.call_args.args[0]
    assert payload.kind == "organization"
    assert payload.title == "Organization completed"
    assert payload.secondary_action == "open_target"
    assert payload.secondary_action_label == "Open folder"
