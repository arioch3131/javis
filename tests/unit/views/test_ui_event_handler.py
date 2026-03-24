from unittest.mock import MagicMock

import ai_content_classifier.views.handlers.ui_event_handler as ui_event_handler_module
from ai_content_classifier.views.handlers.ui_event_handler import UIEventHandler
from PyQt6.QtCore import Qt


def test_build_basic_scan_config_respects_selected_file_types():
    handler = UIEventHandler.__new__(UIEventHandler)

    config = handler._build_basic_scan_config(
        "/tmp/input",
        {"documents": True, "images": False},
    )

    assert config["directory"] == "/tmp/input"
    assert config["file_types"] == {
        "documents": True,
        "images": False,
        "videos": False,
        "audio": False,
        "others": False,
    }
    assert config["extract_metadata"] is True
    assert config["generate_thumbnails"] is True
    assert config["ai_processing"] is False


def test_handle_scan_request_fallback_uses_file_type_selection(monkeypatch):
    handler = UIEventHandler.__new__(UIEventHandler)
    handler.logger = MagicMock()
    handler.main_window = MagicMock()
    handler._prompt_basic_scan_file_types = MagicMock(
        return_value={"documents": False, "images": True}
    )
    handler.on_advanced_scan_requested = MagicMock()

    monkeypatch.setattr(
        ui_event_handler_module.QFileDialog,
        "getExistingDirectory",
        lambda *args, **kwargs: "/tmp/photos",
    )

    handler.handle_scan_request_fallback()

    handler.on_advanced_scan_requested.assert_called_once()
    config = handler.on_advanced_scan_requested.call_args.args[0]
    assert config["directory"] == "/tmp/photos"
    assert config["file_types"]["images"] is True
    assert config["file_types"]["documents"] is False


def test_handle_scan_request_fallback_stops_when_file_type_dialog_is_cancelled(
    monkeypatch,
):
    handler = UIEventHandler.__new__(UIEventHandler)
    handler.logger = MagicMock()
    handler.main_window = MagicMock()
    handler._prompt_basic_scan_file_types = MagicMock(return_value=None)
    handler.on_advanced_scan_requested = MagicMock()

    monkeypatch.setattr(
        ui_event_handler_module.QFileDialog,
        "getExistingDirectory",
        lambda *args, **kwargs: "/tmp/photos",
    )

    handler.handle_scan_request_fallback()

    handler.on_advanced_scan_requested.assert_not_called()


def test_get_current_files_list_prefers_displayed_main_window_files():
    handler = UIEventHandler.__new__(UIEventHandler)
    handler.logger = MagicMock()
    handler.main_window = MagicMock()
    handler.main_window.current_files = [
        ("/tmp/visible.png", "/tmp", "Cats", "image"),
    ]
    handler.file_manager = MagicMock()
    handler.file_manager.current_files = [
        ("/tmp/all.png", "/tmp"),
    ]

    files = handler._get_current_files_list()

    assert files == [("/tmp/visible.png", "/tmp")]


def test_handle_remove_filtered_results_request_uses_displayed_files(monkeypatch):
    handler = UIEventHandler.__new__(UIEventHandler)
    handler.logger = MagicMock()
    handler.main_window = MagicMock()
    handler.file_manager = MagicMock()
    handler.file_manager.remove_files_from_database.return_value = 1
    handler._get_current_files_list = MagicMock(return_value=[("/tmp/visible.png", "/tmp")])

    monkeypatch.setattr(
        ui_event_handler_module.QMessageBox,
        "question",
        lambda *args, **kwargs: ui_event_handler_module.QMessageBox.StandardButton.Yes,
    )
    info_mock = MagicMock()
    monkeypatch.setattr(ui_event_handler_module.QMessageBox, "information", info_mock)

    handler.handle_remove_filtered_results_request()

    handler.file_manager.remove_files_from_database.assert_called_once_with(
        ["/tmp/visible.png"]
    )
    info_mock.assert_called_once()


def test_handle_remove_filtered_results_request_stops_when_user_declines(monkeypatch):
    handler = UIEventHandler.__new__(UIEventHandler)
    handler.logger = MagicMock()
    handler.main_window = MagicMock()
    handler.file_manager = MagicMock()
    handler._get_current_files_list = MagicMock(return_value=[("/tmp/visible.png", "/tmp")])

    monkeypatch.setattr(
        ui_event_handler_module.QMessageBox,
        "question",
        lambda *args, **kwargs: ui_event_handler_module.QMessageBox.StandardButton.No,
    )

    handler.handle_remove_filtered_results_request()

    handler.file_manager.remove_files_from_database.assert_not_called()


def test_handle_category_filter_request_preselects_existing_categories(monkeypatch):
    handler = UIEventHandler.__new__(UIEventHandler)
    handler.logger = MagicMock()
    handler.main_window = MagicMock()
    handler.content_database_service = MagicMock()
    handler.content_database_service.get_unique_categories.return_value = ["Animals", "Space"]
    handler.file_manager = MagicMock()
    handler.file_manager.get_active_filters.return_value = {"category": ["Space"]}

    dialog = MagicMock()
    dialog.exec.return_value = ui_event_handler_module.QDialog.DialogCode.Rejected
    create_dialog = MagicMock(return_value=dialog)
    monkeypatch.setattr(
        ui_event_handler_module,
        "create_category_selection_dialog",
        create_dialog,
    )

    handler.handle_category_filter_request()

    create_dialog.assert_called_once_with(
        ["Animals", "Space"],
        handler.main_window,
        selected_categories=["Space"],
    )


def test_handle_year_filter_request_preselects_existing_years(monkeypatch):
    handler = UIEventHandler.__new__(UIEventHandler)
    handler.logger = MagicMock()
    handler.main_window = MagicMock()
    handler.content_database_service = MagicMock()
    handler.content_database_service.get_unique_years.return_value = [2023, 2024]
    handler.file_manager = MagicMock()
    handler.file_manager.get_active_filters.return_value = {"year": [2024]}

    dialog = MagicMock()
    dialog.exec.return_value = ui_event_handler_module.QDialog.DialogCode.Rejected
    create_dialog = MagicMock(return_value=dialog)
    monkeypatch.setattr(
        ui_event_handler_module,
        "create_year_selection_dialog",
        create_dialog,
    )

    handler.handle_year_filter_request()

    create_dialog.assert_called_once_with(
        ["2023", "2024"],
        handler.main_window,
        selected_years=["2024"],
    )


def test_handle_extension_filter_request_preselects_existing_extensions(monkeypatch):
    handler = UIEventHandler.__new__(UIEventHandler)
    handler.logger = MagicMock()
    handler.main_window = MagicMock()
    handler.content_database_service = MagicMock()
    handler.content_database_service.get_unique_extensions.return_value = [".jpg", ".png"]
    handler.file_manager = MagicMock()
    handler.file_manager.get_active_filters.return_value = {"extension": [".png"]}

    dialog = MagicMock()
    dialog.exec.return_value = ui_event_handler_module.QDialog.DialogCode.Rejected
    create_dialog = MagicMock(return_value=dialog)
    monkeypatch.setattr(
        ui_event_handler_module,
        "create_extension_selection_dialog",
        create_dialog,
    )

    handler.handle_extension_filter_request()

    create_dialog.assert_called_once_with(
        [".jpg", ".png"],
        handler.main_window,
        selected_extensions=[".png"],
    )


def test_handle_columns_file_activation_emits_selected_path():
    handler = UIEventHandler.__new__(UIEventHandler)
    handler.main_window = MagicMock()

    item = MagicMock()
    item.data.return_value = "/tmp/example.jpg"

    handler.handle_columns_file_activation(item)

    item.data.assert_called_once_with(0, Qt.ItemDataRole.UserRole)
    handler.main_window.file_activated_signal.emit.assert_called_once_with(
        "/tmp/example.jpg"
    )
