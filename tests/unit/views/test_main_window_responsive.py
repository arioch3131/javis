import sys
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel

from ai_content_classifier.views.presenters.status_presenter import StatusPresenter
from ai_content_classifier.views.main_window.main import MainWindow
from ai_content_classifier.views.main_window.ui_builder import UIBuilder


def _build_builder_with_responsive_widgets() -> UIBuilder:
    builder = UIBuilder(MagicMock())
    filter_sidebar = MagicMock()
    view_mode_buttons = [MagicMock(), MagicMock(), MagicMock()]
    builder.widgets = {
        "action_bar_subtitle": MagicMock(),
        "scan_folder_button": MagicMock(),
        "advanced_scan_button": MagicMock(),
        "categorize_button": MagicMock(),
        "organize_button": MagicMock(),
        "settings_button": MagicMock(),
        "view_mode_buttons": view_mode_buttons,
        "search_input": MagicMock(),
        "sort_label": MagicMock(),
        "sort_combo": MagicMock(),
        "size_slider": MagicMock(),
        "size_slider_label": MagicMock(),
        "top_row_splitter": MagicMock(),
        "main_splitter": MagicMock(),
        "left_panel": MagicMock(),
        "right_panel": MagicMock(),
        "filter_sidebar": filter_sidebar,
    }
    return builder


class TestMainWindowShellStructure:
    @classmethod
    def setup_class(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_content_area_keeps_preview_widget_out_of_main_shell(self):
        builder = UIBuilder(MagicMock())

        workspace_shell, main_splitter = builder._create_content_area()
        top_row_splitter = builder.widgets["top_row_splitter"]

        assert workspace_shell.objectName() == "workspaceShell"
        assert main_splitter.orientation() == Qt.Orientation.Vertical
        assert top_row_splitter.orientation() == Qt.Orientation.Horizontal
        assert builder.widgets["left_panel"].objectName() == "sidebarPanel"
        assert builder.widgets["center_panel"].objectName() == "resultsPanel"
        assert builder.widgets["preview_panel"].objectName() == "previewPanel"
        assert main_splitter.count() == 1
        assert not builder.widgets["preview_panel"].isVisible()

    def test_action_bar_exposes_llm_status_chip(self):
        main_window = MagicMock()
        builder = UIBuilder(main_window)

        action_bar = builder._create_action_bar()

        assert action_bar.objectName() == "topActionBar"
        assert main_window.llm_status_label.objectName() == "llmStatus"
        assert main_window.llm_status_label.text() == "LLM offline"


def test_apply_responsive_layout_hides_secondary_panels_on_small_windows():
    builder = _build_builder_with_responsive_widgets()

    mode = builder.apply_responsive_layout(820, 620)

    assert mode == "small"
    builder.widgets["action_bar_subtitle"].setVisible.assert_called_with(False)
    builder.widgets["settings_button"].setVisible.assert_called_with(False)
    builder.widgets["sort_label"].setVisible.assert_called_with(False)
    builder.widgets["left_panel"].setVisible.assert_called_with(False)
    builder.widgets["filter_sidebar"].set_compact_mode.assert_called_with(False)
    builder.widgets["top_row_splitter"].setSizes.assert_called_once()
    builder.widgets["main_splitter"].setSizes.assert_called_once()
    assert [button.setText.call_args.args[0] for button in builder.widgets["view_mode_buttons"]] == ["G", "L", "C"]


def test_apply_responsive_layout_keeps_sidebar_in_wide_mode():
    builder = _build_builder_with_responsive_widgets()

    mode = builder.apply_responsive_layout(1440, 920)

    assert mode == "wide"
    builder.widgets["action_bar_subtitle"].setVisible.assert_called_with(True)
    builder.widgets["settings_button"].setVisible.assert_called_with(True)
    builder.widgets["sort_label"].setVisible.assert_called_with(True)
    builder.widgets["left_panel"].setVisible.assert_called_with(True)
    builder.widgets["filter_sidebar"].set_compact_mode.assert_called_with(False)
    builder.widgets["sort_combo"].setVisible.assert_called_with(True)
    assert builder.widgets["scan_folder_button"].setText.call_args.args[0] == "Scan Folder"


def test_apply_responsive_layout_uses_compact_sidebar_before_hiding_it():
    builder = _build_builder_with_responsive_widgets()

    mode = builder.apply_responsive_layout(980, 760)

    assert mode == "compact"
    builder.widgets["left_panel"].setVisible.assert_called_with(True)
    builder.widgets["filter_sidebar"].set_compact_mode.assert_called_with(True)
    builder.widgets["sort_label"].setVisible.assert_called_with(True)
    builder.widgets["size_slider_label"].setText.assert_called_with("Thumbs")
    assert builder.widgets["advanced_scan_button"].setText.call_args.args[0] == "More"
    assert builder.widgets["categorize_button"].setText.call_args.args[0] == "Classify"
    assert [button.setText.call_args.args[0] for button in builder.widgets["view_mode_buttons"]] == [
        "Grid",
        "List",
        "Cols",
    ]


def test_apply_responsive_layout_hides_header_subtitle_in_medium_mode():
    builder = _build_builder_with_responsive_widgets()

    mode = builder.apply_responsive_layout(1200, 820)

    assert mode == "medium"
    builder.widgets["action_bar_subtitle"].setVisible.assert_called_with(False)
    assert builder.widgets["scan_folder_button"].setText.call_args.args[0] == "Scan Folder"


def test_update_file_statistics_tolerates_missing_optional_stats_labels():
    window = MainWindow.__new__(MainWindow)
    window.files_status_label = MagicMock()
    window.files_count_label = None
    window.categories_count_label = None
    window.size_total_label = None
    window.results_count_label = MagicMock()
    window._format_size_bytes = MagicMock(return_value="1.0 KB")

    window._update_file_statistics([("/tmp/example.txt", "example.txt", "Other", "")])

    window.files_status_label.setText.assert_called_once_with("Files 1")
    window.results_count_label.setText.assert_called_once_with("1 files")


def test_switching_view_mode_repopulates_newly_active_view():
    window = MainWindow.__new__(MainWindow)
    window.current_files = [("/tmp/example.txt", "dir", "Other", "document")]
    window.current_view_mode = "grid"
    window.view_mode_changed = MagicMock()
    window.logger = MagicMock()
    window.ui_builder = MagicMock()
    window.ui_builder.get_widget.return_value = MagicMock()
    window._update_active_view_data = MagicMock()

    action = MagicMock()
    action.objectName.return_value = "view_list"

    window._on_view_mode_triggered(action)

    window._update_active_view_data.assert_called_once_with(window.current_files)


def test_set_connection_status_uses_neutral_offline_chip():
    window = MainWindow.__new__(MainWindow)
    window.llm_status_label = QLabel()

    window.set_connection_status(False, "Disconnected")

    assert window.llm_status_label.text() == "LLM offline"
    assert window.llm_status_label.property("statusTone") == "neutral"
    assert window.llm_status_label.toolTip() == "Disconnected"


def test_status_presenter_updates_main_and_progress_chips():
    main_window = MagicMock()
    presenter = StatusPresenter(main_window)

    presenter.update_status("Scanning...", is_busy=True)

    main_window.set_main_status_chip.assert_called_once_with("Scanning...", is_busy=True)
    main_window.set_progress_status_chip.assert_called_once_with(
        "Scanning...",
        is_busy=True,
    )


def test_status_presenter_labels_metadata_processing_progress():
    main_window = MagicMock()
    presenter = StatusPresenter(main_window)

    presenter.update_scan_progress(1200, 1236, 97.1)

    main_window.set_main_status_chip.assert_called_once_with(
        "Metadata processed: 1200/1236 files (97.1%)",
        is_busy=True,
    )
    main_window.set_progress_status_chip.assert_called_once_with(
        "Metadata processed: 1200/1236 files (97.1%)",
        is_busy=True,
    )
