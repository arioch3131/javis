from unittest.mock import MagicMock

from ai_content_classifier.controllers.auto_organization_controller import (
    AutoOrganizationController,
    OrganizationConfig,
    OrganizationWorker,
)
from ai_content_classifier.services.auto_organization import (
    AutoOrganizationDataKey,
    AutoOrganizationOperationCode,
    AutoOrganizationOperationResult,
)


def test_worker_collects_results_and_reports_progress():
    service = MagicMock()
    service.organize_single_file.side_effect = [
        AutoOrganizationOperationResult(
            success=True,
            code=AutoOrganizationOperationCode.OK,
            message="ok",
            data={
                AutoOrganizationDataKey.SOURCE_PATH.value: "/a",
                AutoOrganizationDataKey.TARGET_PATH.value: "/t/a",
                AutoOrganizationDataKey.ACTION.value: "copy",
                AutoOrganizationDataKey.ERROR.value: None,
            },
        ),
        AutoOrganizationOperationResult(
            success=False,
            code=AutoOrganizationOperationCode.FILESYSTEM_ERROR,
            message="err",
            data={
                AutoOrganizationDataKey.SOURCE_PATH.value: "/b",
                AutoOrganizationDataKey.TARGET_PATH.value: "",
                AutoOrganizationDataKey.ACTION.value: "copy",
                AutoOrganizationDataKey.ERROR.value: "err",
            },
        ),
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
    controller.service.structure_handlers = {
        "By Category": object(),
        "By Year": object(),
    }
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
    controller._on_organization_completed(
        [
            AutoOrganizationOperationResult(
                success=True,
                code=AutoOrganizationOperationCode.OK,
                message="ok",
                data={
                    AutoOrganizationDataKey.SOURCE_PATH.value: "/a",
                    AutoOrganizationDataKey.TARGET_PATH.value: "/b",
                    AutoOrganizationDataKey.ACTION.value: "copy",
                    AutoOrganizationDataKey.ERROR.value: None,
                },
            )
        ]
    )

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
    controller.current_worker.config = OrganizationConfig(
        "/tmp/t", "By Category", "copy"
    )
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

    controller._on_organization_completed(
        [
            AutoOrganizationOperationResult(
                success=True,
                code=AutoOrganizationOperationCode.OK,
                message="ok",
                data={
                    AutoOrganizationDataKey.SOURCE_PATH.value: "/a",
                    AutoOrganizationDataKey.TARGET_PATH.value: "/tmp/t/a",
                    AutoOrganizationDataKey.ACTION.value: "copy",
                    AutoOrganizationDataKey.ERROR.value: None,
                },
            )
        ]
    )

    payload = controller.main_window.show_operation_state.call_args.args[0]
    assert payload.kind == "organization"
    assert payload.title == "Organization completed"
    assert payload.secondary_action == "open_target"
    assert payload.secondary_action_label == "Open folder"


def test_worker_cancel_and_error_signal_paths():
    service = MagicMock()
    service.organize_single_file.side_effect = RuntimeError("explode")
    config = OrganizationConfig("/target", "By Category", "copy")
    worker = OrganizationWorker(service, ["/a"], config)

    completed = []
    worker.organization_completed.connect(lambda results: completed.append(results))
    worker.run()
    assert len(completed[0]) == 1
    assert completed[0][0].success is False

    worker2 = OrganizationWorker(service, ["/a", "/b"], config)
    worker2.cancel()
    done = []
    worker2.organization_completed.connect(lambda results: done.append(results))
    worker2.run()
    assert done == [[]]


def test_generate_preview_error_paths_and_integrated_host_helpers():
    controller = AutoOrganizationController(content_database_service=MagicMock())
    controller.service = MagicMock()
    controller.service.validate_config.return_value = (False, "bad")

    emitted = []
    controller.preview_ready.connect(lambda payload: emitted.append(payload))
    controller.generate_preview(
        [("/a.txt", "/")],
        {"target_directory": "/tmp/t", "organization_structure": "By Category"},
    )
    assert "Configuration invalide" in emitted[-1]["error"]

    controller.service.validate_config.side_effect = RuntimeError("boom")
    controller.generate_preview(
        [("/a.txt", "/")],
        {"target_directory": "/tmp/t", "organization_structure": "By Category"},
    )
    assert emitted[-1]["error"] == "boom"

    assert controller.has_integrated_operations_host() is False
    controller.bind_main_window(MagicMock())
    assert controller.has_integrated_operations_host() is True


def test_controller_internal_state_handlers_and_formatters(monkeypatch):
    controller = AutoOrganizationController(content_database_service=MagicMock())
    controller.bind_main_window(MagicMock())
    controller._organization_started_at = 100.0
    controller._organization_snapshot = {
        "processed": 2,
        "total": 5,
        "successful": 2,
        "failed": 0,
        "state": "running",
        "target_directory": "/tmp/t",
    }

    controller._on_progress_updated(3, 5)
    controller._on_file_organized("/tmp/source.txt", "/tmp/t/source.txt", "copy")
    controller._on_organization_error("bad")
    assert controller.main_window.show_operation_state.called

    controller._on_worker_finished()
    assert controller.is_organizing is False

    assert controller._format_rate(0, "files") == "0.0 files/s"
    assert controller._format_rate(0.5, "files").endswith("files/min")
    assert controller._format_rate(2.0, "files").endswith("files/s")
    assert controller._format_elapsed() != ""

    controller._organization_started_at = None
    assert controller._format_elapsed() == "00:00"

    monkeypatch.setattr(
        "ai_content_classifier.controllers.auto_organization_controller.time.time",
        lambda: 100.0 + 3661,
    )
    controller._organization_started_at = 100.0
    assert controller._format_elapsed() == "1:01:01"


def test_push_operation_state_variants_and_periodic_update():
    controller = AutoOrganizationController(content_database_service=MagicMock())
    controller.bind_main_window(MagicMock())

    for state in ["running", "cancelling", "failed", "completed"]:
        controller._organization_snapshot = {
            "processed": 1,
            "total": 2,
            "successful": 1,
            "failed": 0,
            "state": state,
            "target_directory": "/tmp/t",
        }
        controller._push_operation_state()

    payload = controller.main_window.show_operation_state.call_args.args[0]
    assert payload.kind == "organization"
    assert payload.operation_id == "organization"

    controller.is_organizing = True
    controller._periodic_update()
    assert controller.main_window.show_operation_state.called

    controller.is_organizing = False
    count = controller.main_window.show_operation_state.call_count
    controller._periodic_update()
    assert controller.main_window.show_operation_state.call_count == count


def test_open_target_directory_dispatch_and_error(monkeypatch):
    controller = AutoOrganizationController(content_database_service=MagicMock())
    controller._organization_snapshot = {"target_directory": "/tmp/t"}

    calls = []
    monkeypatch.setattr(
        "ai_content_classifier.controllers.auto_organization_controller.subprocess.run",
        lambda args, check=False: calls.append((args, check)),
    )

    monkeypatch.setattr(
        "ai_content_classifier.controllers.auto_organization_controller.platform.system",
        lambda: "Windows",
    )
    controller._open_target_directory()
    monkeypatch.setattr(
        "ai_content_classifier.controllers.auto_organization_controller.platform.system",
        lambda: "Darwin",
    )
    controller._open_target_directory()
    monkeypatch.setattr(
        "ai_content_classifier.controllers.auto_organization_controller.platform.system",
        lambda: "Linux",
    )
    controller._open_target_directory()
    assert calls[0][0][0] == "explorer"
    assert calls[1][0][0] == "open"
    assert calls[2][0][0] == "xdg-open"

    monkeypatch.setattr(
        "ai_content_classifier.controllers.auto_organization_controller.subprocess.run",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("fail")),
    )
    controller._open_target_directory()
