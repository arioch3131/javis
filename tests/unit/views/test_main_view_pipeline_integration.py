import sys
from unittest.mock import MagicMock, Mock

# Some thumbnail tests monkeypatch PyQt6 modules in sys.modules.
# Ensure real Qt modules are imported for this pipeline integration test.
for module_name in ("PyQt6", "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets"):
    module_obj = sys.modules.get(module_name)
    if isinstance(module_obj, Mock):
        del sys.modules[module_name]

from ai_content_classifier.views.events.event_bus import EventBus  # noqa: E402
from ai_content_classifier.views.events.event_types import EventType  # noqa: E402
from ai_content_classifier.views.main_view import MainView  # noqa: E402


def _build_main_view_for_pipeline_test(scan_config: dict) -> MainView:
    """
    Builds a minimal MainView test instance without running full UI initialization.
    """
    view = MainView.__new__(MainView)
    view.logger = MagicMock()
    view.main_window = MagicMock()
    view.event_bus = EventBus()

    view._pipeline_state = {
        "active": False,
        "awaiting_categorization": False,
        "scan_config": {},
        "scan_files": [],
    }

    view.file_manager = MagicMock()
    view.file_manager.get_current_scan_config.return_value = scan_config

    view.settings_manager = MagicMock()
    view.settings_manager.get_unified_categories.return_value = ["Work", "Personal"]

    categorization_controller = MagicMock()
    categorization_controller.start_automatic_categorization.return_value = True

    auto_organization_controller = MagicMock()
    auto_organization_controller.start_organization.return_value = True

    view.ui_event_handler = MagicMock()
    view.ui_event_handler.categorization_controller = categorization_controller
    view.ui_event_handler.auto_organization_controller = auto_organization_controller
    return view


def test_pipeline_scan_to_categorize_to_organize_integration():
    """
    Integration-oriented orchestration test:
    SCAN_COMPLETED -> automatic categorization -> automatic organization.
    """
    scan_config = {
        "ai_processing": True,
        "auto_categorize": True,
        "auto_organize": True,
        "categories": ["Work", "Personal", "Archive"],
        "confidence_threshold": 0.66,
        "file_types": {"images": True, "documents": True},
        "target_directory": "/tmp/organized",
        "organization_structure": "By Category",
        "organization_action": "copy",
    }

    view = _build_main_view_for_pipeline_test(scan_config)

    published_events = []
    view.event_bus.subscribe(
        EventType.CATEGORIZATION_STARTED, lambda evt: published_events.append(evt)
    )
    view.event_bus.subscribe(
        EventType.CATEGORIZATION_COMPLETED, lambda evt: published_events.append(evt)
    )

    scan_files = [("/tmp/a.jpg", "/tmp"), ("/tmp/b.pdf", "/tmp")]
    scan_event = type(
        "Evt",
        (),
        {"payload": {"file_list": scan_files}},
    )()

    # 1) Scan completed => auto categorization should start.
    view._on_scan_completed_event(scan_event)

    cat_controller = view.ui_event_handler.categorization_controller
    cat_controller.start_automatic_categorization.assert_called_once()
    cat_call = cat_controller.start_automatic_categorization.call_args.kwargs
    assert cat_call["file_paths"] == ["/tmp/a.jpg", "/tmp/b.pdf"]
    assert cat_call["categories"] == ["Work", "Personal", "Archive"]

    # 2) Categorization completed => auto organization should start.
    view._on_categorization_completed_for_pipeline(
        {"total_processed": 2, "successful": 2, "failed": 0}
    )

    org_controller = view.ui_event_handler.auto_organization_controller
    org_controller.start_organization.assert_called_once_with(
        file_list=scan_files,
        config_dict={
            "target_directory": "/tmp/organized",
            "organization_structure": "By Category",
            "organization_action": "copy",
        },
    )

    event_types = [evt.event_type for evt in published_events]
    assert EventType.CATEGORIZATION_STARTED in event_types
    assert EventType.CATEGORIZATION_COMPLETED in event_types


def test_pipeline_scan_to_organize_without_categorization():
    scan_config = {
        "ai_processing": True,
        "auto_categorize": False,
        "auto_organize": True,
        "target_directory": "/tmp/organized",
        "organization_structure": "By Category",
        "organization_action": "copy",
    }

    view = _build_main_view_for_pipeline_test(scan_config)
    scan_files = [("/tmp/a.jpg", "/tmp"), ("/tmp/b.pdf", "/tmp")]
    scan_event = type("Evt", (), {"payload": {"file_list": scan_files}})()

    view._on_scan_completed_event(scan_event)

    view.ui_event_handler.categorization_controller.start_automatic_categorization.assert_not_called()
    view.ui_event_handler.auto_organization_controller.start_organization.assert_called_once_with(
        file_list=scan_files,
        config_dict={
            "target_directory": "/tmp/organized",
            "organization_structure": "By Category",
            "organization_action": "copy",
        },
    )
