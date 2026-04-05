"""
UIBuilder - main window layout builder with compatibility hooks.
"""

from typing import Any, Dict

from ai_content_classifier.core.logger import LoggableMixin
from ai_content_classifier.services.theme.theme_service import get_theme_service
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class EmptyStateWidget(QFrame):
    def __init__(self, title: str, subtitle: str, action_text: str, parent=None):
        super().__init__(parent)
        self.setObjectName("resultsEmptyState")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("emptyStateTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.subtitle_label = QLabel(subtitle, self)
        self.subtitle_label.setObjectName("emptyStateSubtitle")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        layout.addWidget(self.subtitle_label)

        self.action_button = QPushButton(action_text, self)
        self.action_button.setObjectName("emptyStateAction")
        self.action_button.setMaximumWidth(180)
        layout.addWidget(self.action_button, alignment=Qt.AlignmentFlag.AlignCenter)

    def update_copy(self, title: str, subtitle: str, action_text: str):
        self.title_label.setText(title)
        self.subtitle_label.setText(subtitle)
        self.action_button.setText(action_text)


class UIBuilder(LoggableMixin):
    WIDE_WIDTH = 1320
    MEDIUM_WIDTH = 1160
    COMPACT_WIDTH = 940
    TALL_HEIGHT = 820
    MEDIUM_HEIGHT = 700

    def __init__(self, main_window):
        self.__init_logger__()
        self.main_window = main_window
        self.widgets: Dict[str, QWidget] = {}
        self.layouts: Dict[str, Any] = {}
        self.dock_widgets: Dict[str, QWidget] = {}
        self._empty_state_action = "scan"
        self._responsive_mode = "wide"

    def build_main_interface(self):
        self.create_central_widget()
        self.create_main_widgets()
        self.setup_main_layout()
        self.create_dock_widgets()
        self.finalize_interface()
        self._expose_widgets_on_main_window()

    def _expose_widgets_on_main_window(self):
        critical_widgets = {
            "thumbnail_grid_widget": "thumbnail_grid_widget",
            "file_list_widget": "file_list_widget",
            "columns_widget": "columns_widget",
            "adaptive_preview_widget": "adaptive_preview_widget",
            "filter_sidebar": "filter_sidebar",
            "active_filters_bar": "active_filters_bar",
            "progress_panel": "progress_panel",
            "log_console_widget": "log_console_widget",
            "auto_organize_dialog": "auto_organize_dialog",
            "results_count_label": "results_count_label",
            "results_empty_state": "results_empty_state",
            "search_input": "search_input",
            "sort_combo": "sort_combo",
        }
        for attr_name, widget_key in critical_widgets.items():
            widget = self.widgets.get(widget_key)
            if widget is not None and not hasattr(self.main_window, attr_name):
                setattr(self.main_window, attr_name, widget)

    def _theme_metrics(self):
        return get_theme_service().get_theme_definition().metrics

    def create_central_widget(self):
        metrics = self._theme_metrics()
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.main_window.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(
            metrics.spacing_lg,
            metrics.spacing_lg,
            metrics.spacing_lg,
            metrics.spacing_md,
        )
        main_layout.setSpacing(metrics.spacing_md)

        self.widgets["central_widget"] = central_widget
        self.layouts["main_layout"] = main_layout

    def create_main_widgets(self):
        self.widgets["action_bar"] = self._create_action_bar()
        (
            self.widgets["workspace_shell"],
            self.widgets["main_splitter"],
        ) = self._create_content_area()
        self.widgets["status_container"] = self._create_detailed_status_bar()

    def _create_action_bar(self) -> QFrame:
        metrics = self._theme_metrics()
        bar = QFrame()
        bar.setObjectName("topActionBar")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(
            metrics.spacing_lg,
            metrics.spacing_md,
            metrics.spacing_lg,
            metrics.spacing_md,
        )
        layout.setSpacing(metrics.spacing_sm)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        title = QLabel("Javis", bar)
        title.setObjectName("topActionTitle")
        title_col.addWidget(title)
        self.widgets["action_bar_title"] = title

        subtitle = QLabel(
            "Scan, filter, review and organize content from one workspace.", bar
        )
        subtitle.setObjectName("topActionSubtitle")
        title_col.addWidget(subtitle)
        self.widgets["action_bar_subtitle"] = subtitle

        layout.addLayout(title_col)

        llm_status = QLabel("LLM offline", bar)
        llm_status.setObjectName("llmStatus")
        llm_status.setProperty("statusTone", "neutral")
        layout.addWidget(llm_status)

        self.main_window.llm_status_label = llm_status

        layout.addStretch(1)

        self.widgets["scan_folder_button"] = self._create_action_button(
            "Scan Folder",
            lambda: getattr(
                self.main_window, "handle_open_folder_request", lambda: None
            )(),
            primary=True,
        )
        layout.addWidget(self.widgets["scan_folder_button"])

        self.widgets["advanced_scan_button"] = self._create_action_button(
            "Advanced Scan",
            lambda: getattr(self.main_window, "handle_scan_request", lambda: None)(),
        )
        layout.addWidget(self.widgets["advanced_scan_button"])

        self.widgets["categorize_button"] = self._create_action_button(
            "Categorize",
            lambda: getattr(
                self.main_window, "handle_categorization_request", lambda: None
            )(),
        )
        self.widgets["categorize_button"].setEnabled(False)
        layout.addWidget(self.widgets["categorize_button"])

        self.widgets["organize_button"] = self._create_action_button(
            "Organize",
            lambda: getattr(
                self.main_window, "handle_auto_organize_request", lambda: None
            )(),
        )
        self.widgets["organize_button"].setEnabled(False)
        layout.addWidget(self.widgets["organize_button"])

        self.widgets["settings_button"] = self._create_action_button(
            "Settings",
            lambda: getattr(
                self.main_window, "handle_settings_request", lambda: None
            )(),
            subtle=True,
        )
        layout.addWidget(self.widgets["settings_button"])

        return bar

    def _create_action_button(self, text, callback, primary=False, subtle=False):
        metrics = self._theme_metrics()
        button = QPushButton(text)
        button.clicked.connect(callback)
        if primary:
            button.setObjectName("primaryActionButton")
        elif subtle:
            button.setObjectName("subtleActionButton")
        else:
            button.setObjectName("secondaryActionButton")
        button.setMinimumHeight(metrics.control_height + 2)
        return button

    def _create_content_area(self) -> tuple[QFrame, QSplitter]:
        metrics = self._theme_metrics()
        workspace_shell = QFrame()
        workspace_shell.setObjectName("workspaceShell")
        shell_layout = QVBoxLayout(workspace_shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        outer_splitter = QSplitter(Qt.Orientation.Vertical)
        outer_splitter.setObjectName("mainSplitter")

        top_row_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_row_splitter.setObjectName("topRowSplitter")

        sidebar = self._create_left_panel()
        center = self._create_center_panel()
        preview = self._create_right_panel()
        sidebar.setMinimumWidth(metrics.sidebar_width_compact)
        center.setMinimumWidth(420)
        preview.setMinimumHeight(max(180, metrics.preview_height_medium - 40))
        preview.hide()

        top_row_splitter.addWidget(sidebar)
        top_row_splitter.addWidget(center)
        top_row_splitter.setSizes([metrics.sidebar_width_wide, 1080])
        top_row_splitter.setCollapsible(0, True)
        top_row_splitter.setStretchFactor(0, 0)
        top_row_splitter.setStretchFactor(1, 1)

        outer_splitter.addWidget(top_row_splitter)
        outer_splitter.setSizes([560])
        outer_splitter.setStretchFactor(0, 1)
        shell_layout.addWidget(outer_splitter, 1)

        self.widgets["top_row_splitter"] = top_row_splitter
        self.widgets["left_panel"] = sidebar
        self.widgets["center_panel"] = center
        self.widgets["right_panel"] = preview
        self.widgets["preview_panel"] = preview
        self.dock_widgets["sidebar_dock"] = sidebar

        return workspace_shell, outer_splitter

    def _create_left_panel(self) -> QFrame:
        metrics = self._theme_metrics()
        panel = QFrame()
        panel.setObjectName("sidebarPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(metrics.spacing_sm + 2)

        from ai_content_classifier.views.widgets.specialized.filter_sidebar import (
            FilterSidebar,
        )

        filter_sidebar = FilterSidebar(panel)
        filter_sidebar.file_type_selected.connect(self.main_window.filter_changed.emit)
        filter_sidebar.category_requested.connect(
            lambda: getattr(
                self.main_window, "handle_filter_by_category_request", lambda: None
            )()
        )
        filter_sidebar.date_requested.connect(
            lambda: getattr(
                self.main_window, "handle_filter_by_year_request", lambda: None
            )()
        )
        filter_sidebar.extension_requested.connect(
            lambda: getattr(
                self.main_window, "handle_filter_by_extension_request", lambda: None
            )()
        )
        filter_sidebar.clear_requested.connect(
            lambda: getattr(
                self.main_window, "handle_filter_reset_request", lambda: None
            )()
        )
        layout.addWidget(filter_sidebar, 1)

        self.widgets["filter_sidebar"] = filter_sidebar
        self.main_window.filter_sidebar = filter_sidebar
        self.main_window.files_count_label = None
        self.main_window.size_total_label = None
        self.main_window.categories_count_label = None
        self.main_window.history_list = None

        return panel

    def _create_center_panel(self) -> QFrame:
        metrics = self._theme_metrics()
        panel = QFrame()
        panel.setObjectName("resultsPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(metrics.spacing_sm + 2)

        layout.addWidget(self._create_content_toolbar())

        results_frame = QFrame(panel)
        results_frame.setObjectName("resultsFrame")
        results_layout = QVBoxLayout(results_frame)
        results_layout.setContentsMargins(
            metrics.spacing_lg,
            metrics.spacing_lg,
            metrics.spacing_lg,
            metrics.spacing_lg,
        )
        results_layout.setSpacing(metrics.spacing_md)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(metrics.spacing_sm)

        title = QLabel("Results", results_frame)
        title.setObjectName("resultsSectionTitle")
        header_layout.addWidget(title)

        header_layout.addStretch()

        results_count = QLabel("0 files", results_frame)
        results_count.setObjectName("resultsCountLabel")
        header_layout.addWidget(results_count)

        results_layout.addLayout(header_layout)

        results_stack = QStackedWidget(results_frame)
        results_stack.setObjectName("resultsStack")

        empty_state = EmptyStateWidget(
            "No folder scanned yet",
            "Start with Scan Folder to browse your content library.",
            "Scan Folder",
            results_stack,
        )
        empty_state.action_button.clicked.connect(self._on_empty_state_action)
        results_stack.addWidget(empty_state)

        content_stack = QStackedWidget(results_stack)
        content_stack.setObjectName("contentStack")
        self._add_thumbnail_grid_mode(content_stack)
        self._add_list_view_mode(content_stack)
        self._add_columns_view_mode(content_stack)
        results_stack.addWidget(content_stack)

        results_layout.addWidget(results_stack, 1)
        layout.addWidget(results_frame, 1)

        self.widgets["results_stack"] = results_stack
        self.widgets["results_empty_state"] = empty_state
        self.widgets["results_count_label"] = results_count
        self.widgets["content_stack"] = content_stack

        return panel

    def _create_content_toolbar(self) -> QFrame:
        metrics = self._theme_metrics()
        toolbar = QFrame()
        toolbar.setObjectName("browseToolbar")

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(
            metrics.spacing_lg,
            metrics.spacing_md,
            metrics.spacing_lg,
            metrics.spacing_md,
        )
        layout.setSpacing(metrics.spacing_sm + 2)

        view_group = QButtonGroup(toolbar)
        self.main_window.view_mode_button_group = view_group
        view_buttons = []

        for button_id, text in enumerate(("Grid", "List", "Columns")):
            button = QPushButton(text, toolbar)
            button.setObjectName("viewModeButton")
            button.setCheckable(True)
            if button_id == 0:
                button.setChecked(True)
            view_group.addButton(button, button_id)
            layout.addWidget(button)
            view_buttons.append(button)

        search_input = QLineEdit(toolbar)
        search_input.setObjectName("resultsSearchInput")
        search_input.setPlaceholderText("Search files, folders or categories")
        search_input.setClearButtonEnabled(True)
        search_input.textChanged.connect(
            lambda text: getattr(
                self.main_window, "set_search_query", lambda _text: None
            )(text)
        )
        layout.addWidget(search_input, 1)

        sort_label = QLabel("Sort", toolbar)
        sort_label.setObjectName("resultsSortLabel")
        layout.addWidget(sort_label)
        self.widgets["sort_label"] = sort_label

        sort_combo = QComboBox(toolbar)
        sort_combo.setObjectName("resultsSortCombo")
        sort_combo.addItems(["Name", "Recently Modified", "Largest", "Category"])
        sort_combo.setMinimumContentsLength(8)
        sort_combo.currentTextChanged.connect(
            lambda text: getattr(self.main_window, "set_sort_mode", lambda _text: None)(
                text
            )
        )
        layout.addWidget(sort_combo)

        size_label = QLabel("Size", toolbar)
        size_label.setObjectName("thumbnailSizeLabel")
        layout.addWidget(size_label)
        self.widgets["size_slider_label"] = size_label

        size_slider = QSlider(Qt.Orientation.Horizontal, toolbar)
        size_slider.setObjectName("sizeSlider")
        size_slider.setRange(64, 256)
        size_slider.setValue(128)
        size_slider.setMaximumWidth(metrics.thumbnail_slider_width_wide)
        layout.addWidget(size_slider)

        self.widgets["search_input"] = search_input
        self.widgets["sort_combo"] = sort_combo
        self.widgets["view_mode_buttons"] = view_buttons
        self.widgets["size_slider"] = size_slider
        self.main_window.size_slider = size_slider

        return toolbar

    def _create_right_panel(self) -> QFrame:
        metrics = self._theme_metrics()
        panel = QFrame()
        panel.setObjectName("previewPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(metrics.spacing_sm + 2)

        from ai_content_classifier.views.widgets.specialized.adaptive_preview_widget import (
            AdaptivePreviewWidget,
        )

        preview_widget = AdaptivePreviewWidget(panel)
        layout.addWidget(preview_widget, 1)

        self.widgets["adaptive_preview_widget"] = preview_widget
        self.main_window.adaptive_preview_widget = preview_widget

        return panel

    def _add_thumbnail_grid_mode(self, stack: QStackedWidget):
        from ai_content_classifier.views.widgets.specialized.ultra_optimized_grid import (
            UltraOptimizedThumbnailGridWidget,
        )

        grid_widget = UltraOptimizedThumbnailGridWidget()
        grid_widget.setObjectName("thumbnailGridMode")
        stack.addWidget(grid_widget)
        self.widgets["thumbnail_grid_widget"] = grid_widget
        self.main_window.thumbnail_grid_widget = grid_widget

    def _add_list_view_mode(self, stack: QStackedWidget):
        from ai_content_classifier.views.widgets.specialized.file_list_widget import (
            FileListWidget,
        )

        list_widget = FileListWidget()
        list_widget.setObjectName("fileListMode")
        stack.addWidget(list_widget)
        self.widgets["file_list_widget"] = list_widget
        self.main_window.file_list_widget = list_widget

    def _add_columns_view_mode(self, stack: QStackedWidget):
        from PyQt6.QtWidgets import QTreeWidget

        columns_widget = QTreeWidget()
        columns_widget.setObjectName("columnsMode")
        columns_widget.setHeaderLabels(
            ["Name", "Size", "Date", "Category", "Type", "Duplicates"]
        )
        columns_widget.setAlternatingRowColors(True)
        columns_widget.setSortingEnabled(True)
        stack.addWidget(columns_widget)

        self.widgets["columns_widget"] = columns_widget
        self.main_window.columns_widget = columns_widget

    def _create_detailed_status_bar(self) -> QFrame:
        metrics = self._theme_metrics()
        status_container = QFrame()
        status_container.setObjectName("statusContainer")

        layout = QHBoxLayout(status_container)
        layout.setContentsMargins(
            metrics.spacing_lg,
            metrics.spacing_sm + 2,
            metrics.spacing_lg,
            metrics.spacing_sm + 2,
        )
        layout.setSpacing(metrics.spacing_lg)

        main_status = QLabel("Ready", status_container)
        main_status.setObjectName("mainStatus")
        main_status.setProperty("statusTone", "neutral")
        layout.addWidget(main_status)

        files_status = QLabel("Files 0", status_container)
        files_status.setObjectName("filesStatus")
        files_status.setProperty("statusTone", "neutral")
        layout.addWidget(files_status)

        progress_status = QLabel("Metadata idle", status_container)
        progress_status.setObjectName("progressStatus")
        progress_status.setProperty("statusTone", "neutral")
        layout.addWidget(progress_status)

        self.main_window.main_status_label = main_status
        self.main_window.files_status_label = files_status
        self.main_window.progress_status_label = progress_status

        return status_container

    def create_dock_widgets(self):
        self._create_log_console_dock()
        self._create_progress_dock()

    def _create_progress_dock(self):
        from PyQt6.QtWidgets import QDockWidget
        from ai_content_classifier.views.widgets.common.progress_panel import (
            ProgressPanel,
        )

        progress_dock = QDockWidget("Operations", self.main_window)
        progress_dock.setObjectName("progressDock")
        progress_widget = ProgressPanel(
            parent=progress_dock,
            title="Current Operation",
            show_details=True,
            show_log=False,
        )
        progress_widget.set_show_progress_bar(False)
        progress_dock.setWidget(progress_widget)
        self.main_window.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea, progress_dock
        )
        progress_dock.hide()

        self.dock_widgets["progress_dock"] = progress_dock
        self.widgets["progress_panel"] = progress_widget
        self.main_window.progress_panel = progress_widget

    def _create_log_console_dock(self):
        from PyQt6.QtWidgets import QDockWidget
        from ai_content_classifier.views.widgets.log_console_widget import (
            LogConsoleWidget,
        )

        log_dock = QDockWidget("Activity Log", self.main_window)
        log_dock.setObjectName("logDock")
        log_widget = LogConsoleWidget(log_dock)
        log_dock.setWidget(log_widget)
        self.main_window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)
        log_dock.hide()

        self.dock_widgets["log_dock"] = log_dock
        self.widgets["log_console_widget"] = log_widget
        self.main_window.log_console_widget = log_widget

    def setup_main_layout(self):
        main_layout = self.layouts["main_layout"]
        main_layout.addWidget(self.widgets["action_bar"])
        main_layout.addWidget(self.widgets["workspace_shell"], 1)
        main_layout.addWidget(self.widgets["status_container"])

    def finalize_interface(self):
        self.main_window.resize(1440, 920)
        if hasattr(self.main_window, "_fit_to_screen"):
            self.main_window._fit_to_screen()
        self._connect_ui_signals()
        self._show_results_empty_state(
            "No folder scanned yet",
            "Start with Scan Folder to browse your content library.",
            "Scan Folder",
        )
        self.apply_responsive_layout(
            self.main_window.width(), self.main_window.height()
        )

    def _connect_ui_signals(self):
        if hasattr(self.main_window, "view_mode_button_group"):
            self.main_window.view_mode_button_group.idClicked.connect(
                self._on_view_mode_changed
            )
        if hasattr(self.main_window, "size_slider"):
            self.main_window.size_slider.valueChanged.connect(self._on_size_changed)

    def _on_view_mode_changed(self, mode_id: int):
        mode_names = ["grid", "list", "columns"]
        if "content_stack" in self.widgets:
            self.widgets["content_stack"].setCurrentIndex(mode_id)
        if 0 <= mode_id < len(mode_names):
            self.main_window.view_mode_changed.emit(mode_names[mode_id])

    def _on_size_changed(self, size: int):
        if hasattr(self.main_window, "thumbnail_grid_widget") and hasattr(
            self.main_window.thumbnail_grid_widget, "set_thumbnail_size"
        ):
            self.main_window.thumbnail_grid_widget.set_thumbnail_size(size)

    def _show_results_empty_state(
        self,
        title: str,
        subtitle: str,
        action_text: str,
        action_key: str = "scan",
    ):
        empty_state = self.widgets.get("results_empty_state")
        results_stack = self.widgets.get("results_stack")
        if empty_state and results_stack:
            self._empty_state_action = action_key
            empty_state.update_copy(title, subtitle, action_text)
            results_stack.setCurrentIndex(0)

    def _on_empty_state_action(self):
        if self._empty_state_action == "clear_filters":
            getattr(self.main_window, "handle_filter_reset_request", lambda: None)()
            return
        getattr(self.main_window, "handle_open_folder_request", lambda: None)()

    def show_results_content(self, show_content: bool):
        results_stack = self.widgets.get("results_stack")
        if not results_stack:
            return
        results_stack.setCurrentIndex(1 if show_content else 0)

    def get_widget(self, name: str) -> QWidget:
        return self.widgets.get(name)

    def get_dock_widget(self, name: str):
        return self.dock_widgets.get(name)

    def set_view_mode(self, mode: str):
        mode_indices = {"grid": 0, "list": 1, "columns": 2}
        mode_id = mode_indices.get(mode, 0)
        if hasattr(self.main_window, "view_mode_button_group"):
            button = self.main_window.view_mode_button_group.button(mode_id)
            if button:
                button.setChecked(True)
        if "content_stack" in self.widgets:
            self.widgets["content_stack"].setCurrentIndex(mode_id)

    def show_dock_widget(self, name: str, show: bool):
        widget = self.get_dock_widget(name)
        if widget:
            widget.setVisible(show)

    def get_interface_state(self) -> Dict[str, Any]:
        state = {
            "view_mode": 0,
            "thumbnail_size": 128,
            "splitter_sizes": [],
            "dock_states": {},
            "filters_visible": False,
            "preview_visible": False,
            "responsive_mode": self._responsive_mode,
        }

        if hasattr(self.main_window, "view_mode_button_group"):
            checked_button = self.main_window.view_mode_button_group.checkedButton()
            if checked_button:
                state["view_mode"] = self.main_window.view_mode_button_group.id(
                    checked_button
                )
        if hasattr(self.main_window, "size_slider"):
            state["thumbnail_size"] = self.main_window.size_slider.value()
        if "main_splitter" in self.widgets:
            state["splitter_sizes"] = self.widgets["main_splitter"].sizes()
        for name, widget in self.dock_widgets.items():
            state["dock_states"][name] = widget.isVisible()
        if "filter_sidebar" in self.widgets:
            state["filters_visible"] = self.widgets["filter_sidebar"].isVisible()
        if "preview_panel" in self.widgets:
            state["preview_visible"] = False
        return state

    def apply_responsive_layout(self, width: int, height: int) -> str:
        """Adapts the main shell layout to the current window size."""
        mode = self._compute_responsive_mode(width, height)
        self._responsive_mode = mode
        self._update_action_bar_for_mode(mode)
        self._update_toolbar_for_mode(mode)
        self._update_splitters_for_mode(mode, width, height)
        return mode

    def _compute_responsive_mode(self, width: int, height: int) -> str:
        if width >= self.WIDE_WIDTH and height >= self.TALL_HEIGHT:
            return "wide"
        if width >= self.MEDIUM_WIDTH and height >= self.MEDIUM_HEIGHT:
            return "medium"
        if width >= self.COMPACT_WIDTH:
            return "compact"
        return "small"

    def _update_action_bar_for_mode(self, mode: str) -> None:
        subtitle = self.widgets.get("action_bar_subtitle")
        if subtitle:
            subtitle.setVisible(mode == "wide")

        button_texts = {
            "wide": {
                "scan_folder_button": "Scan Folder",
                "advanced_scan_button": "Advanced Scan",
                "categorize_button": "Categorize",
                "organize_button": "Organize",
                "settings_button": "Settings",
            },
            "medium": {
                "scan_folder_button": "Scan Folder",
                "advanced_scan_button": "Advanced",
                "categorize_button": "Categorize",
                "organize_button": "Organize",
                "settings_button": "Settings",
            },
            "compact": {
                "scan_folder_button": "Scan",
                "advanced_scan_button": "More",
                "categorize_button": "Classify",
                "organize_button": "Organize",
                "settings_button": "Prefs",
            },
            "small": {
                "scan_folder_button": "Scan",
                "advanced_scan_button": "More",
                "categorize_button": "Classify",
                "organize_button": "Organize",
                "settings_button": "Prefs",
            },
        }

        for widget_name, text in button_texts[mode].items():
            button = self.widgets.get(widget_name)
            if button:
                button.setText(text)

        settings_button = self.widgets.get("settings_button")
        if settings_button:
            settings_button.setVisible(mode != "small")

    def _update_toolbar_for_mode(self, mode: str) -> None:
        metrics = self._theme_metrics()
        search_input = self.widgets.get("search_input")
        sort_combo = self.widgets.get("sort_combo")
        sort_label = self.widgets.get("sort_label")
        size_slider = self.widgets.get("size_slider")
        size_label = self.widgets.get("size_slider_label")
        view_mode_buttons = self.widgets.get("view_mode_buttons", [])

        if search_input:
            placeholder = (
                "Search files, folders or categories"
                if mode in {"wide", "medium"}
                else "Search files"
            )
            search_input.setPlaceholderText(placeholder)
            if mode == "wide":
                search_input.setMinimumWidth(280)
            elif mode == "medium":
                search_input.setMinimumWidth(220)
            elif mode == "compact":
                search_input.setMinimumWidth(180)
            else:
                search_input.setMinimumWidth(140)

        if sort_combo:
            sort_combo.setVisible(True)
            if mode == "wide":
                sort_combo.setMaximumWidth(220)
            elif mode == "medium":
                sort_combo.setMaximumWidth(180)
            elif mode == "compact":
                sort_combo.setMaximumWidth(150)
            else:
                sort_combo.setMaximumWidth(120)

        if sort_label:
            sort_label.setVisible(mode in {"wide", "medium", "compact"})

        if size_label:
            size_label.setVisible(mode != "small")
            size_label.setText("Size" if mode in {"wide", "medium"} else "Thumbs")

        if size_slider:
            size_slider.setVisible(True)
            if mode == "wide":
                size_slider.setMaximumWidth(metrics.thumbnail_slider_width_wide)
            elif mode == "medium":
                size_slider.setMaximumWidth(metrics.thumbnail_slider_width_medium)
            elif mode == "compact":
                size_slider.setMaximumWidth(metrics.thumbnail_slider_width_compact)
            else:
                size_slider.setMaximumWidth(metrics.thumbnail_slider_width_small)

        button_labels = {
            "wide": ("Grid", "List", "Columns"),
            "medium": ("Grid", "List", "Columns"),
            "compact": ("Grid", "List", "Cols"),
            "small": ("G", "L", "C"),
        }
        for button, text in zip(view_mode_buttons, button_labels[mode], strict=False):
            button.setText(text)

    def _update_splitters_for_mode(self, mode: str, width: int, height: int) -> None:
        metrics = self._theme_metrics()
        top_row_splitter = self.widgets.get("top_row_splitter")
        outer_splitter = self.widgets.get("main_splitter")
        left_panel = self.widgets.get("left_panel")
        filter_sidebar = self.widgets.get("filter_sidebar")

        if not top_row_splitter or not outer_splitter or not left_panel:
            return

        sidebar_visible = mode in {"wide", "medium", "compact"}
        sidebar_compact = mode == "compact"

        left_panel.setVisible(sidebar_visible)
        if filter_sidebar and hasattr(filter_sidebar, "set_compact_mode"):
            filter_sidebar.set_compact_mode(sidebar_compact)

        if sidebar_visible:
            if mode == "wide":
                sidebar_width = metrics.sidebar_width_wide
            elif mode == "medium":
                sidebar_width = metrics.sidebar_width_medium
            else:
                sidebar_width = metrics.sidebar_width_compact
            top_row_splitter.setSizes([sidebar_width, max(420, width - sidebar_width)])
        else:
            top_row_splitter.setSizes([0, max(420, width)])

        outer_splitter.setSizes([max(320, height)])
