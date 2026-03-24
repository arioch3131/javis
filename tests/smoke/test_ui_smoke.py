import os
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ai_content_classifier.views.main_window.ui_builder import UIBuilder
from ai_content_classifier.views.widgets.dialogs.file.file_details_dialog import (
    FileDetailsDialog,
)

_APP: QApplication | None = None


def _get_app() -> QApplication:
    global _APP
    if _APP is not None:
        return _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app
    return _APP


def _build_ui_builder() -> UIBuilder:
    _get_app()
    window = MagicMock()
    builder = UIBuilder(window)
    builder.create_central_widget()
    builder.create_main_widgets()
    QApplication.processEvents()
    return builder


def test_ui_builder_smoke_builds_core_widgets():
    builder = _build_ui_builder()

    assert builder.get_widget("scan_folder_button") is not None
    assert builder.get_widget("advanced_scan_button") is not None
    assert builder.get_widget("settings_button") is not None
    assert builder.get_widget("content_stack") is not None


def test_ui_builder_smoke_primary_actions_trigger_handlers():
    _get_app()
    main_window = MagicMock()
    main_window.handle_open_folder_request = MagicMock()
    main_window.handle_scan_request = MagicMock()
    main_window.handle_settings_request = MagicMock()
    builder = UIBuilder(main_window)

    action_bar = builder._create_action_bar()
    assert action_bar is not None

    builder.get_widget("scan_folder_button").click()
    builder.get_widget("advanced_scan_button").click()
    builder.get_widget("settings_button").click()
    QApplication.processEvents()

    main_window.handle_open_folder_request.assert_called_once()
    main_window.handle_scan_request.assert_called_once()
    main_window.handle_settings_request.assert_called_once()


def test_file_details_dialog_smoke_open_and_close():
    _get_app()
    dialog = FileDetailsDialog()

    dialog.set_file_details(
        {
            "file_path": "/tmp/example.png",
            "content_type": "image",
            "metadata": {"size_formatted": "149 KB", "dimensions": "914 x 457"},
        }
    )
    dialog.show()
    QApplication.processEvents()
    dialog.close()

    assert dialog.current_file_path == "/tmp/example.png"
