# views/main_window/main.py - COMPATIBILITY CORRECTIONS
"""
MainWindow - refactored main shell with compatibility helpers.
"""

import os
import re
import unicodedata
from typing import Callable
from ai_content_classifier.core.logger import get_logger
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QShowEvent
from PyQt6.QtWidgets import QApplication, QMainWindow, QTreeWidgetItem
from ai_content_classifier.services.database.content_database_service import (
    ContentDatabaseService,
)
from ai_content_classifier.services.theme.theme_service import get_theme_service
from ai_content_classifier.views.main_window.menu_builder import MenuBuilder
from ai_content_classifier.views.main_window.ui_builder import UIBuilder
from ai_content_classifier.views.widgets.base.theme_mixin import ThemeMixin
from ai_content_classifier.views.widgets.common.operation_state import (
    OperationViewState,
)


class SortableFileItem(QTreeWidgetItem):
    """Tree item with numeric sorting support for selected columns."""

    def __lt__(self, other):
        tree = self.treeWidget()
        if tree is None:
            return super().__lt__(other)

        column = tree.sortColumn()
        if column == 1:
            # Numeric sort on size bytes.
            left = self.data(1, Qt.ItemDataRole.UserRole) or 0
            right = other.data(1, Qt.ItemDataRole.UserRole) or 0
            return int(left) < int(right)
        if column == 5:
            # Numeric sort on duplicate count.
            left = self.data(5, Qt.ItemDataRole.UserRole) or 0
            right = other.data(5, Qt.ItemDataRole.UserRole) or 0
            return int(left) < int(right)

        return super().__lt__(other)


class MainWindow(QMainWindow, ThemeMixin):
    """
    Main window - REFACTORED VERSION WITH COMPATIBILITY
    """

    # Main signals (kept for compatibility)
    filter_changed = pyqtSignal(str)
    view_mode_changed = pyqtSignal(str)
    active_filters_changed = pyqtSignal(dict)
    file_selected_signal = pyqtSignal(object, str)  # index, file_path
    file_activated_signal = pyqtSignal(str)
    _SCREEN_WIDTH_RATIO = 0.95
    _SCREEN_HEIGHT_RATIO = 0.92

    def __init__(self, content_database_service: ContentDatabaseService, parent=None):
        super().__init__(parent)
        self.logger = get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        # Services
        self.content_database_service = content_database_service

        # Builders (replace complex construction code)
        self.ui_builder = UIBuilder(self)
        self.menu_builder = MenuBuilder(self)

        # UI state
        self.current_view_mode = "grid"
        self.current_files = []
        self._raw_visible_files = []
        self._search_index: list[tuple[tuple, str]] = []
        self._search_index_ready = False
        self._search_query = ""
        self._pending_search_query = ""
        self._sort_mode = "Name"
        self._has_received_file_data = False
        self._screen_fit_applied = False
        self._responsive_timer = QTimer(self)
        self._responsive_timer.setSingleShot(True)
        self._responsive_timer.timeout.connect(self._apply_responsive_layout)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_search_query)

        # Initial configuration
        self.setup_window()

        self.build_interface()
        # Setup compatibility after UI and actions exist to avoid fallback warnings.
        self._setup_compatibility_layer()
        self.setup_theme(self.apply_main_theme)

    def connect_menu_handlers(self):
        """Connect menu handlers after MainView initialization."""
        self.menu_builder.connect_handlers()

        self.logger.info("MainWindow refactored version initialized")

    def _setup_compatibility_layer(self):
        """Configure the compatibility layer for main_view.py"""
        self.logger.debug("Setting up compatibility layer...")

        self._expose_actions_as_properties()
        self._expose_critical_widgets()
        self._setup_default_handlers()

        self.logger.debug("Compatibility layer configured")

    def _expose_actions_as_properties(self):
        """Expose actions as properties for compatibility."""
        # Main actions expected by main_view.py
        action_mappings = {
            "scan_action": "scan_advanced",
            "settings_action": "tools_settings",
            "clear_db_action": "tools_clear_db",
            "remove_filtered_db_action": "tools_remove_filtered_db",
            "categorize_action": "tools_categorize",
            "organize_action": "tools_organize",
        }

        for property_name, action_id in action_mappings.items():
            action = self.menu_builder.get_action(action_id)
            if action:
                setattr(self, property_name, action)
                self.logger.debug(f"Exposed action {action_id} as {property_name}")
            else:
                # Create a fallback action
                fallback_action = QAction(f"[{property_name}]", self)
                setattr(self, property_name, fallback_action)
                self.logger.warning(f"Created fallback action for {property_name}")

    def _expose_critical_widgets(self):
        """Expose critical widgets for compatibility."""
        # Ensure critical widgets are reachable

        # Thumbnail grid widget
        if not hasattr(self, "thumbnail_grid_widget"):
            self.thumbnail_grid_widget = self.ui_builder.get_widget(
                "thumbnail_grid_widget"
            )
            if not self.thumbnail_grid_widget:
                self.logger.warning("thumbnail_grid_widget not found in ui_builder")

        # File list widget
        if not hasattr(self, "file_list_widget"):
            self.file_list_widget = self.ui_builder.get_widget("file_list_widget")
            if not self.file_list_widget:
                self.logger.warning("file_list_widget not found in ui_builder")

        # Columns widget
        if not hasattr(self, "columns_widget"):
            self.columns_widget = self.ui_builder.get_widget("columns_widget")

        # Adaptive preview widget
        if not hasattr(self, "adaptive_preview_widget"):
            self.adaptive_preview_widget = self.ui_builder.get_widget(
                "adaptive_preview_widget"
            )
            if not self.adaptive_preview_widget:
                self.logger.warning("adaptive_preview_widget not found in ui_builder")

    def _setup_default_handlers(self):
        """Configure default handlers for compatibility."""
        # These methods are overridden when connected to UIEventHandler
        if not hasattr(self, "handle_scan_request"):
            self.handle_scan_request = self._default_scan_handler
        if not hasattr(self, "handle_open_folder_request"):
            self.handle_open_folder_request = self._default_open_folder_handler
        if not hasattr(self, "handle_quick_scan_request"):
            self.handle_quick_scan_request = self._default_quick_scan_handler

        if not hasattr(self, "handle_settings_request"):
            self.handle_settings_request = self._default_settings_handler

        if not hasattr(self, "handle_clear_db_request"):
            self.handle_clear_db_request = self._default_clear_db_handler

        if not hasattr(self, "handle_remove_filtered_results_request"):
            self.handle_remove_filtered_results_request = (
                self._default_remove_filtered_db_handler
            )
        if not hasattr(self, "handle_clear_thumbnail_cache_request"):
            self.handle_clear_thumbnail_cache_request = (
                self._default_clear_thumbnail_cache_handler
            )

        if not hasattr(self, "handle_categorization_request"):
            self.handle_categorization_request = self._default_categorization_handler

        if not hasattr(self, "handle_auto_organize_request"):
            self.handle_auto_organize_request = self._default_organize_handler

        # Missing handlers
        if not hasattr(self, "handle_refresh_request"):
            self.handle_refresh_request = self._default_refresh_handler

        if not hasattr(self, "handle_about_request"):
            self.handle_about_request = self._default_about_handler

        if not hasattr(self, "handle_documentation_request"):
            self.handle_documentation_request = self._default_documentation_handler

        if not hasattr(self, "handle_llm_test_request"):
            self.handle_llm_test_request = self._default_llm_test_handler

        if not hasattr(self, "handle_fullscreen_toggle"):
            self.handle_fullscreen_toggle = self._default_fullscreen_handler

        if not hasattr(self, "handle_view_sidebar"):
            self.handle_view_sidebar = self._default_view_sidebar_handler

    def _default_view_sidebar_handler(self):
        """Default handler to show/hide sidebar."""
        self.logger.debug("Default view sidebar handler called")
        sidebar_dock = self.ui_builder.get_dock_widget("sidebar_dock")
        if sidebar_dock:
            sidebar_dock.setVisible(not sidebar_dock.isVisible())

    def _default_refresh_handler(self):
        """Default handler for refresh."""
        self.logger.debug("Default refresh handler called")
        # Delegate to file_manager if available
        if hasattr(self, "file_manager") and self.file_manager:
            self.file_manager.refresh_file_list()

    def _default_remove_filtered_db_handler(self):
        """Default handler for removing displayed results from the database."""
        self.logger.debug("Default remove filtered database handler called")

    def _default_clear_thumbnail_cache_handler(self):
        """Default handler for clearing thumbnail cache."""
        self.logger.debug("Default clear thumbnail cache handler called")

    def _default_about_handler(self):
        """Default handler for About."""
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.about(self, "About Javis", "Javis\nVersion 1.0")

    def _default_documentation_handler(self):
        """Default handler for documentation."""
        self.logger.debug("Default documentation handler called")

    def _default_llm_test_handler(self):
        """Default handler for LLM test."""
        self.logger.debug("Default LLM test handler called")

    def _default_fullscreen_handler(self):
        """Default handler for fullscreen."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # Missing compatibility methods

    def set_thumbnail_generator(self, generator_func):
        """Configure thumbnail generator."""
        self.logger.debug("Thumbnail generator configured")

        # Apply to grid widget when available
        if hasattr(self, "thumbnail_grid_widget") and self.thumbnail_grid_widget:
            if hasattr(self.thumbnail_grid_widget, "set_thumbnail_generator"):
                self.thumbnail_grid_widget.set_thumbnail_generator(generator_func)

    def set_metadata_generator(self, generator_func):
        """Configure metadata generator."""
        self.logger.debug("Metadata generator configured")

        # Apply to widgets when available
        widgets_to_update = [
            getattr(self, "thumbnail_grid_widget", None),
            getattr(self, "file_list_widget", None),
            getattr(self, "columns_widget", None),
        ]

        for widget in widgets_to_update:
            if widget and hasattr(widget, "set_metadata_generator"):
                widget.set_metadata_generator(generator_func)

    # Exposed UIBuilder methods

    def get_widget(self, widget_name: str):
        """Return a widget from UIBuilder."""
        return self.ui_builder.get_widget(widget_name)

    def get_action(self, action_id: str):
        """Return an action from MenuBuilder."""
        return self.menu_builder.get_action(action_id)

    def enable_action(self, action_id: str, enabled: bool = True):
        """Enable/disable an action."""
        self.menu_builder.enable_action(action_id, enabled)

    def check_action(self, action_id: str, checked: bool = True):
        """Check/uncheck an action."""
        self.menu_builder.check_action(action_id, checked)

    # Setup window and build interface (unchanged)
    def setup_window(self):
        """Base window configuration."""
        self.setWindowTitle("Javis")
        self.setMinimumSize(680, 520)
        self.resize(1200, 800)

        self.setDockOptions(
            QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AnimatedDocks
        )

    def _fit_to_screen(self) -> None:
        """Ensure main window fits the current screen, especially on laptops."""
        try:
            screen = self.screen() or QApplication.primaryScreen()
            if screen is None:
                return
            geometry = screen.availableGeometry()
            max_width = int(geometry.width() * self._SCREEN_WIDTH_RATIO)
            max_height = int(geometry.height() * self._SCREEN_HEIGHT_RATIO)
            if self.width() > max_width or self.height() > max_height:
                self.resize(
                    min(self.width(), max_width), min(self.height(), max_height)
                )
        except Exception as e:
            self.logger.debug(f"Could not fit main window to screen: {e}")

    def showEvent(self, event: QShowEvent) -> None:
        """Apply screen-fit when the window is shown on the actual display."""
        super().showEvent(event)
        if not self._screen_fit_applied:
            self._fit_to_screen()
            self._apply_responsive_layout()
            self._screen_fit_applied = True

    def build_interface(self):
        """Build the interface via builders."""
        try:
            # 1. Main interface (widgets, layouts, docks)
            self.ui_builder.build_main_interface()

            # 2. Menus and toolbars
            self.menu_builder.create_menus_and_toolbars()
            for toolbar_name in ("main", "view", "scan"):
                toolbar = self.menu_builder.toolbars.get(toolbar_name)
                if toolbar:
                    toolbar.hide()

            # 3. Final connections
            self.connect_builder_signals()

        except Exception as e:
            self.logger.error(f"Error building interface: {e}", exc_info=True)
            raise

    def resizeEvent(self, event):
        """Recompute the shell layout when the window is resized."""
        super().resizeEvent(event)
        self._responsive_timer.start(80)

    def _apply_responsive_layout(self):
        """Apply responsive shell rules through the UI builder."""
        if not hasattr(self, "ui_builder") or self.ui_builder is None:
            return
        self.ui_builder.apply_responsive_layout(self.width(), self.height())

    def connect_builder_signals(self):
        """Connect signals between builders and MainWindow."""
        try:
            self.logger.debug("Connecting builder signals...")

            # === VIEW MODE HANDLING ===

            # 1. First try UIBuilder button group (toolbar buttons)
            if hasattr(self, "view_mode_button_group") and self.view_mode_button_group:
                if hasattr(self.view_mode_button_group, "idClicked"):
                    self.view_mode_button_group.idClicked.connect(
                        self._on_view_mode_button_clicked
                    )
                    self.logger.debug("Connectd UIBuilder button group")

            # 2. Handle MenuBuilder action group (menu actions)
            if hasattr(self, "view_mode_group") and self.view_mode_group:
                if hasattr(self.view_mode_group, "triggered"):  # QActionGroup
                    self.view_mode_group.triggered.connect(self._on_view_mode_triggered)
                    self.logger.debug("Connectd MenuBuilder action group")

            # === OTHER SIGNALS ===
            if hasattr(self, "active_filters_bar") and self.active_filters_bar:
                if hasattr(self.active_filters_bar, "filters_changed"):
                    self.active_filters_bar.filters_changed.connect(
                        self._on_active_filters_changed
                    )
                    self.logger.debug("Connectd active filters bar")

            self.logger.debug("Builder signals connectd successfully")

        except Exception as e:
            self.logger.error(f"Error connecting builder signals: {e}")
            # Do not raise exception to allow startup

    def _on_view_mode_triggered(self, action):
        """Compatibility handler for QActionGroup triggered signal."""
        try:
            # Map actions to view modes
            action_to_mode = {
                "view_grid": "grid",
                "view_list": "list",
                "view_columns": "columns",
            }

            action_name = action.objectName()
            mode = action_to_mode.get(action_name, "grid")

            self.logger.debug(
                f"View mode changed to: {mode} (from action: {action_name})"
            )

            # Update current mode
            self.current_view_mode = mode

            # Emit signal with mode name
            self.view_mode_changed.emit(mode)

            # Update stacked widget if available
            if hasattr(self, "ui_builder") and self.ui_builder:
                content_stack = self.ui_builder.get_widget("content_stack")
                if content_stack:
                    mode_to_index = {"grid": 0, "list": 1, "columns": 2}
                    index = mode_to_index.get(mode, 0)
                    content_stack.setCurrentIndex(index)
            self._update_active_view_data(self.current_files)

        except Exception as e:
            self.logger.error(f"Error in _on_view_mode_triggered: {e}")

    def _on_view_mode_changed(self, mode_id: int):
        """Handle view mode changes."""
        mode_names = ["grid", "list", "columns"]
        if 0 <= mode_id < len(mode_names):
            self.current_view_mode = mode_names[mode_id]
            self.view_mode_changed.emit(self.current_view_mode)

    def _on_active_filters_changed(self, filters: dict):
        """Handle active filters changes."""
        self.active_filters_changed.emit(filters)

    def _default_scan_handler(self):
        """Default handler for scan."""
        self.logger.debug("Default scan handler called")

    def _default_open_folder_handler(self):
        """Default handler for open folder."""
        self.logger.debug("Default open folder handler called")

    def _default_quick_scan_handler(self, path: str = ""):
        """Default handler for quick scan."""
        self.logger.debug(f"Default quick scan handler called with path: {path}")

    def _default_settings_handler(self):
        """Default handler for settings."""
        self.logger.debug("Default settings handler called")

    def _default_clear_db_handler(self):
        """Default handler for clearing DB."""
        self.logger.debug("Default clear DB handler called")

    def _default_categorization_handler(self):
        """Default handler for categorization."""
        self.logger.debug("Default categorization handler called")

    def _default_organize_handler(self):
        """Default handler for organization."""
        self.logger.debug("Default organize handler called")

    def _on_view_mode_button_clicked(self, button_id: int):
        """Handle view buttons (QButtonGroup)."""
        try:
            mode_names = ["grid", "list", "columns"]
            if 0 <= button_id < len(mode_names):
                mode = mode_names[button_id]
                self.current_view_mode = mode
                self.view_mode_changed.emit(mode)
                if hasattr(self, "ui_builder") and self.ui_builder:
                    content_stack = self.ui_builder.get_widget("content_stack")
                    if content_stack:
                        content_stack.setCurrentIndex(button_id)
                self._update_active_view_data(self.current_files)
                self.logger.debug(
                    f"View mode changed to: {mode} (button ID: {button_id})"
                )
        except Exception as e:
            self.logger.error(f"Error in _on_view_mode_button_clicked: {e}")

    # All remaining methods stay identical...
    # (apply_main_theme, set_file_data, set_categorization_enabled, etc.)

    def apply_main_theme(self, palette):
        """Apply the main theme."""
        try:
            theme = get_theme_service().get_theme_definition(palette.name)
            metrics = theme.metrics
            typography = theme.typography
            style = f"""
                QMainWindow {{
                    background-color: {palette.background};
                    color: {palette.on_background};
                }}
                QWidget#centralWidget {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:1,
                        stop:0 {palette.background},
                        stop:0.55 {palette.surface},
                        stop:1 {palette.surface_variant}
                    );
                }}
                QMenuBar {{
                    background-color: {palette.surface};
                    color: {palette.on_surface};
                    border-bottom: 1px solid {palette.outline};
                }}
                QMenuBar::item:selected {{
                    background-color: {palette.primary};
                    color: white;
                }}
                QMenu {{
                    background-color: {palette.surface};
                    color: {palette.on_surface};
                    border: 1px solid {palette.outline};
                    padding: {metrics.spacing_xs}px;
                }}
                QMenu::item {{
                    background-color: transparent;
                    color: {palette.on_surface};
                    padding: {metrics.spacing_sm}px {metrics.spacing_md}px;
                    border-radius: {metrics.radius_sm}px;
                }}
                QMenu::item:selected {{
                    background-color: {palette.primary};
                    color: #ffffff;
                }}
                QMenu::item:disabled {{
                    color: {palette.on_surface_variant};
                    background-color: transparent;
                }}
                QMenu::separator {{
                    height: 1px;
                    background: {palette.outline};
                    margin: {metrics.spacing_xs}px {metrics.spacing_sm}px;
                }}
                QFrame#topActionBar,
                QFrame#workspaceShell,
                QFrame#browseToolbar,
                QFrame#resultsFrame,
                QFrame#previewHeaderCard,
                QFrame#sidebarPanel,
                QFrame#previewPanel,
                QFrame#statusContainer,
                QFrame#filterSidebarHeader,
                QFrame#filterSidebarActions,
                QFrame#fileTypeCard {{
                    background-color: {palette.overlay_strong};
                    border: 1px solid {palette.outline};
                    border-radius: {metrics.radius_xl - 2}px;
                }}
                QFrame#filterSidebarHeader,
                QFrame#filterSidebarActions,
                QFrame#fileTypeCard {{
                    background-color: transparent;
                    border: none;
                    border-radius: 0;
                }}
                QFrame#workspaceShell {{
                    background-color: transparent;
                    border: none;
                    border-radius: 0;
                }}
                QLabel#topActionTitle,
                QLabel#resultsSectionTitle,
                QLabel#previewPanelTitle,
                QLabel#filterSidebarTitle {{
                    color: {palette.on_surface};
                    font-family: "{typography.font_family}";
                    font-size: {typography.font_size_lg + 2}px;
                    font-weight: {typography.font_weight_bold};
                }}
                QLabel#topActionSubtitle,
                QLabel#previewPanelSubtitle,
                QLabel#filterSidebarSubtitle,
                QLabel#historyHintLabel,
                QLabel#filterSidebarSummary {{
                    color: {palette.on_surface_variant};
                    font-family: "{typography.font_family}";
                    font-size: {typography.font_size_sm}px;
                }}
                QLabel#resultsCountLabel,
                QLabel#mainStatus,
                QLabel#filesStatus,
                QLabel#progressStatus,
                QLabel#llmStatus,
                QLabel#filterSidebarSectionTitle,
                QLabel#resultsSortLabel,
                QLabel#thumbnailSizeLabel {{
                    color: {palette.on_surface_variant};
                    font-family: "{typography.font_family}";
                    font-size: {typography.font_size_sm}px;
                    font-weight: {typography.font_weight_semibold};
                }}
                QLabel#mainStatus,
                QLabel#filesStatus,
                QLabel#progressStatus,
                QLabel#llmStatus {{
                    background-color: {palette.surface};
                    border: 1px solid {palette.outline};
                    border-radius: {metrics.radius_pill}px;
                    padding: {metrics.spacing_xs}px {metrics.spacing_md}px;
                }}
                QLabel#mainStatus[statusTone="active"],
                QLabel#progressStatus[statusTone="active"] {{
                    background-color: {palette.focused};
                    border-color: {palette.primary_light};
                    color: {palette.primary_dark};
                }}
                QLabel#mainStatus[statusTone="success"],
                QLabel#llmStatus[statusTone="success"] {{
                    background-color: {palette.success_light};
                    border-color: {palette.success};
                    color: {palette.on_background};
                }}
                QLabel#mainStatus[statusTone="warning"],
                QLabel#progressStatus[statusTone="warning"],
                QLabel#llmStatus[statusTone="warning"] {{
                    background-color: {palette.warning_light};
                    border-color: {palette.warning};
                    color: {palette.on_background};
                }}
                QLabel#mainStatus[statusTone="danger"],
                QLabel#progressStatus[statusTone="danger"],
                QLabel#llmStatus[statusTone="danger"] {{
                    background-color: {palette.error_container};
                    border-color: {palette.error};
                    color: {palette.error_dark};
                }}
                QPushButton#sidebarFilterButton,
                QPushButton#sidebarQuickButton {{
                    background-color: transparent;
                    color: {palette.on_surface};
                    border: 1px solid {palette.outline};
                    border-radius: {metrics.radius_pill}px;
                    padding: 0 {metrics.spacing_md}px;
                    min-height: {metrics.control_height - 2}px;
                    text-align: left;
                    font-family: "{typography.font_family}";
                    font-weight: {typography.font_weight_medium};
                }}
                QPushButton#sidebarFilterButton:checked {{
                    background-color: {palette.focused};
                    border-color: {palette.primary};
                    color: {palette.primary_dark};
                }}
                QPushButton#sidebarFilterButton:hover,
                QPushButton#sidebarQuickButton:hover {{
                    background-color: {palette.surface_variant};
                    border-color: {palette.outline_variant};
                }}
                QFrame#sidebarFilterChipHost {{
                    background-color: transparent;
                    border: none;
                }}
                QFrame#sidebarContextChip {{
                    background-color: {palette.surface_variant};
                    border: 1px solid {palette.outline};
                    border-radius: {metrics.radius_pill}px;
                }}
                QLabel#sidebarContextChipLabel {{
                    color: {palette.on_surface};
                    font-family: "{typography.font_family}";
                    font-size: {typography.font_size_sm}px;
                    font-weight: {typography.font_weight_medium};
                }}
                QToolButton#sidebarContextChipRemove {{
                    background-color: transparent;
                    color: {palette.on_surface_variant};
                    border: none;
                    padding: 0;
                    min-width: {metrics.spacing_md}px;
                }}
                QToolButton#sidebarContextChipRemove:hover {{
                    color: {palette.error};
                }}
                QLineEdit#resultsSearchInput,
                QComboBox#resultsSortCombo {{
                    background-color: {palette.surface};
                    color: {palette.on_surface};
                    border: 1px solid {palette.outline};
                    border-radius: {metrics.radius_md + 2}px;
                    padding: {metrics.spacing_sm + 2}px {metrics.spacing_md}px;
                    min-height: {metrics.control_height}px;
                }}
                QPushButton#primaryActionButton {{
                    background-color: {palette.primary};
                    color: white;
                    border: none;
                    border-radius: {metrics.radius_md + 2}px;
                    padding: 0 {metrics.spacing_md + 2}px;
                    min-height: {metrics.control_height + 2}px;
                    font-family: "{typography.font_family}";
                    font-weight: {typography.font_weight_bold};
                }}
                QPushButton#secondaryActionButton {{
                    background-color: {palette.surface};
                    color: {palette.on_surface};
                    border: 1px solid {palette.outline};
                    border-radius: {metrics.radius_md + 2}px;
                    padding: 0 {metrics.spacing_md + 2}px;
                    min-height: {metrics.control_height + 2}px;
                    font-family: "{typography.font_family}";
                    font-weight: {typography.font_weight_semibold};
                }}
                QPushButton#subtleActionButton,
                QPushButton#viewModeButton,
                QPushButton#clearFiltersButton {{
                    background-color: transparent;
                    color: {palette.on_surface};
                    border: 1px solid {palette.outline};
                    border-radius: {metrics.radius_md + 2}px;
                    padding: 0 {metrics.spacing_md + 2}px;
                    min-height: {metrics.control_height}px;
                    font-family: "{typography.font_family}";
                    font-weight: {typography.font_weight_semibold};
                }}
                QFrame#topActionBar {{
                    border-radius: {metrics.radius_lg}px;
                }}
                QPushButton#viewModeButton:checked {{
                    background-color: {palette.focused};
                    border-color: {palette.primary};
                    color: {palette.primary_dark};
                }}
                QFrame#resultsEmptyState {{
                    background-color: transparent;
                    border: {metrics.focus_width}px dashed {palette.outline_variant};
                    border-radius: {metrics.radius_xl + 4}px;
                }}
                QLabel#emptyStateTitle {{
                    color: {palette.on_surface};
                    font-family: "{typography.font_family}";
                    font-size: {typography.font_size_xl + 2}px;
                    font-weight: {typography.font_weight_bold};
                }}
                QLabel#emptyStateSubtitle {{
                    color: {palette.on_surface_variant};
                    font-family: "{typography.font_family}";
                    font-size: {typography.font_size_md + 1}px;
                }}
                QPushButton#emptyStateAction {{
                    background-color: {palette.primary};
                    color: white;
                    border: none;
                    border-radius: {metrics.radius_md + 2}px;
                    min-height: {metrics.button_height}px;
                    padding: 0 {metrics.spacing_lg + 2}px;
                    font-family: "{typography.font_family}";
                    font-weight: {typography.font_weight_bold};
                }}
                QSlider::groove:horizontal {{
                    height: {metrics.spacing_sm - 2}px;
                    background: {palette.outline};
                    border-radius: {max(3, metrics.radius_sm // 2)}px;
                }}
                QSlider::handle:horizontal {{
                    width: {metrics.spacing_lg}px;
                    margin: -{metrics.spacing_sm - 2}px 0;
                    border-radius: {metrics.radius_sm + 2}px;
                    background: {palette.primary};
                }}
                QSplitter#mainSplitter::handle,
                QSplitter#topRowSplitter::handle {{
                    background-color: {palette.outline};
                    margin: {max(1, metrics.spacing_xs - 2)}px;
                }}
            """
            self.setStyleSheet(style)

        except Exception as e:
            self.logger.error(f"Error applying main theme: {e}")

    # === COMPATIBILITY INTERFACE ===
    def set_file_data(self, file_data):
        """Compatibility interface to update files."""
        self._has_received_file_data = True
        self._raw_visible_files = list(file_data)
        self._search_index = []
        self._search_index_ready = False
        self._refresh_displayed_files()

    def set_search_query(self, search_query: str):
        self._pending_search_query = search_query.strip()
        self._search_timer.start(180)

    def _apply_search_query(self):
        self._search_query = self._pending_search_query
        self._refresh_displayed_files()

    def set_sort_mode(self, sort_mode: str):
        self._sort_mode = sort_mode or "Name"
        self._refresh_displayed_files()

    def _refresh_displayed_files(self):
        query_tokens = self._tokenize_search_query(self._search_query)
        if query_tokens:
            self._ensure_search_index()
            filtered_files = [
                file_row
                for file_row, haystack in self._search_index
                if all(token in haystack for token in query_tokens)
            ]
        else:
            filtered_files = list(self._raw_visible_files)
        filtered_files = self._sort_files(filtered_files, self._sort_mode)
        self.current_files = filtered_files

        self._update_active_view_data(filtered_files)

        if hasattr(self, "ui_builder"):
            has_results = bool(filtered_files)
            self.ui_builder.show_results_content(has_results)
            if not has_results:
                if not self._has_received_file_data:
                    self.ui_builder._show_results_empty_state(
                        "No folder scanned yet",
                        "Start with Scan Folder to browse your content library.",
                        "Scan Folder",
                        "scan",
                    )
                elif self._search_query:
                    self.ui_builder._show_results_empty_state(
                        "No files match this search",
                        "Try a broader search or clear the current filters.",
                        "Clear Filters",
                        "clear_filters",
                    )
                else:
                    self.ui_builder._show_results_empty_state(
                        "No files match the current filters",
                        "Adjust the active filters or scan another folder.",
                        "Clear Filters",
                        "clear_filters",
                    )

        self._update_file_statistics(filtered_files)

    def _ensure_search_index(self) -> None:
        """Build normalized search index lazily to keep initial loads fast."""
        if self._search_index_ready:
            return
        self._search_index = [
            (file_row, self._build_search_haystack(file_row))
            for file_row in self._raw_visible_files
        ]
        self._search_index_ready = True

    def _matches_search(self, file_row, search_query: str) -> bool:
        if not search_query:
            return True

        haystack = self._build_search_haystack(file_row)
        query_tokens = self._tokenize_search_query(search_query)
        return all(token in haystack for token in query_tokens)

    def _build_search_haystack(self, file_row) -> str:
        file_path, directory, category, content_type = file_row
        return self._normalize_search_text(
            " ".join(
                [
                    os.path.basename(file_path),
                    directory or "",
                    category or "",
                    content_type or "",
                ]
            )
        )

    @staticmethod
    def _normalize_search_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value or "")
        ascii_only = "".join(
            char for char in normalized if not unicodedata.combining(char)
        )
        lowered = ascii_only.lower()
        lowered = re.sub(r"[_\-.\\/]+", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered)
        return lowered.strip()

    def _tokenize_search_query(self, search_query: str) -> list[str]:
        normalized = self._normalize_search_text(search_query)
        return [token for token in normalized.split(" ") if token]

    def _sort_files(self, file_rows, sort_mode: str):
        if sort_mode == "Largest":
            return sorted(
                file_rows,
                key=lambda row: self._get_file_size_bytes(row[0]),
                reverse=True,
            )
        if sort_mode == "Recently Modified":
            return sorted(
                file_rows,
                key=lambda row: self._get_file_mtime(row[0]),
                reverse=True,
            )
        if sort_mode == "Category":
            return sorted(file_rows, key=lambda row: ((row[2] or "").lower(), row[0]))
        return sorted(file_rows, key=lambda row: os.path.basename(row[0]).lower())

    def _update_active_view_data(self, filtered_files) -> None:
        mode = getattr(self, "current_view_mode", "grid")
        if mode == "list":
            if hasattr(self, "file_list_widget") and hasattr(
                self.file_list_widget, "set_file_data"
            ):
                self.file_list_widget.set_file_data(filtered_files)
            return
        if mode == "columns":
            if hasattr(self, "columns_widget"):
                self._update_columns_widget(filtered_files)
            return
        if hasattr(self, "thumbnail_grid_widget") and hasattr(
            self.thumbnail_grid_widget, "set_file_data"
        ):
            self.thumbnail_grid_widget.set_file_data(filtered_files)

    def _get_file_mtime(self, file_path: str) -> float:
        try:
            return os.path.getmtime(file_path)
        except OSError:
            return 0.0

    def _update_columns_widget(self, file_data):
        """Update the columns widget."""
        if not hasattr(self, "columns_widget") or not self.columns_widget:
            return

        sorting_enabled = self.columns_widget.isSortingEnabled()
        self.columns_widget.setSortingEnabled(False)
        self.columns_widget.clear()
        duplicate_details = self._build_duplicate_details_map(file_data)

        for file_path, directory, category, content_type in file_data:
            import os

            filename = os.path.basename(file_path)
            size_bytes = self._get_file_size_bytes(file_path)
            size = self._format_file_size(file_path)
            date = self._format_file_date(file_path)
            details = duplicate_details.get(file_path, {})
            duplicate_count = int(details.get("count", 1))
            duplicate_label = f"🔁 {duplicate_count}" if duplicate_count > 1 else ""

            item = SortableFileItem(
                [filename, size, date, category, content_type, duplicate_label]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, file_path)
            item.setData(1, Qt.ItemDataRole.UserRole, int(size_bytes))
            item.setData(5, Qt.ItemDataRole.UserRole, duplicate_count)
            if duplicate_count > 1:
                related_paths = details.get("related_paths", [])
                preview_paths = related_paths[:5]
                more = max(0, len(related_paths) - len(preview_paths))
                preview_text = "\n".join(preview_paths)
                if more:
                    preview_text += f"\n... (+{more} more)"
                item.setToolTip(
                    5,
                    f"This file shares the same checksum with {duplicate_count - 1} other file(s):\n{preview_text}",
                )
            self.columns_widget.addTopLevelItem(item)

        self.columns_widget.setSortingEnabled(sorting_enabled)

    def _build_duplicate_details_map(self, file_data) -> dict:
        """
        Builds a map {file_path: {count, related_paths}} using DB-level checksums.

        For files not in a duplicate set, count defaults to 1.
        """
        duplicates_by_path: dict = {}
        file_paths = {path for path, _, _, _ in file_data}
        if not file_paths or not self.content_database_service:
            return duplicates_by_path

        try:
            duplicates_result = self.content_database_service.find_duplicates()
            if not duplicates_result.success:
                self.logger.debug(
                    "Could not load duplicates for columns view: code=%s message=%s",
                    duplicates_result.code,
                    duplicates_result.message,
                )
                return duplicates_by_path
            duplicate_groups = (duplicates_result.data or {}).get("duplicates", {})
            for items in duplicate_groups.values():
                group_paths = [getattr(item, "path", "") for item in items]
                group_paths = [p for p in group_paths if p]
                group_size = len(group_paths)
                if group_size < 2:
                    continue
                for path in group_paths:
                    if path in file_paths:
                        related = [p for p in group_paths if p != path]
                        duplicates_by_path[path] = {
                            "count": group_size,
                            "related_paths": related,
                        }
        except Exception as e:
            self.logger.debug(f"Could not compute duplicate map for columns view: {e}")

        return duplicates_by_path

    def _format_file_size(self, file_path: str) -> str:
        """Format file size."""
        try:
            size = self._get_file_size_bytes(file_path)

            for unit in ["B", "KB", "MB", "GB"]:
                if size < 1024:
                    return f"{size:.1f} {unit}"
                size /= 1024
            return f"{size:.1f} TB"
        except Exception:
            return "Unknown"

    def _get_file_size_bytes(self, file_path: str) -> int:
        """Return file size in bytes."""
        try:
            import os

            return int(os.path.getsize(file_path))
        except Exception:
            return 0

    def _format_file_date(self, file_path: str) -> str:
        """Format file date."""
        try:
            import datetime
            import os

            timestamp = os.path.getmtime(file_path)
            date = datetime.datetime.fromtimestamp(timestamp)
            return date.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "Unknown"

    def _update_file_statistics(self, file_data):
        """Update file statistics."""
        count = len(file_data)

        if hasattr(self, "files_status_label"):
            self.files_status_label.setText(f"Files {count}")

        if getattr(self, "files_count_label", None):
            self.files_count_label.setText(str(count))

        if hasattr(self, "results_count_label"):
            self.results_count_label.setText(f"{count} files")

        categories = {}
        total_size_bytes = 0
        seen_paths = set()
        for _, _, category, _ in file_data:
            categories[category] = categories.get(category, 0) + 1
        for file_path, _, _, _ in file_data:
            if file_path in seen_paths:
                continue
            seen_paths.add(file_path)
            try:
                total_size_bytes += os.path.getsize(file_path)
            except OSError:
                # Missing/inaccessible files are ignored from total size.
                continue

        if getattr(self, "categories_count_label", None):
            self.categories_count_label.setText(str(len(categories)))

        if getattr(self, "size_total_label", None):
            self.size_total_label.setText(self._format_size_bytes(total_size_bytes))

    def _format_size_bytes(self, size_bytes: int) -> str:
        """Format bytes to a human-readable string."""
        size = float(max(0, size_bytes))
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def set_categorization_enabled(self, enabled: bool):
        """Enable/disable categorization actions."""
        self.menu_builder.enable_action("tools_categorize", enabled)
        self.menu_builder.enable_action("tools_organize", enabled)
        categorize_button = self.ui_builder.get_widget("categorize_button")
        organize_button = self.ui_builder.get_widget("organize_button")
        if categorize_button:
            categorize_button.setEnabled(enabled)
        if organize_button:
            organize_button.setEnabled(enabled)

    def set_connection_status(self, is_connected: bool, message: str):
        """Update LLM connection status."""
        if hasattr(self, "llm_status_label"):
            status = "LLM online" if is_connected else "LLM offline"
            tone = "success" if is_connected else "neutral"
            self._set_status_chip(
                self.llm_status_label, status, tone=tone, tooltip=message
            )

    def set_main_status_chip(self, status_message: str, is_busy: bool = False):
        """Update main shell status."""
        normalized = status_message.strip()
        lowered = normalized.lower()

        if lowered.startswith("error"):
            text = "Attention"
            tone = "danger"
        elif is_busy:
            text = "Working"
            tone = "active"
        elif lowered in {"ready", "idle"}:
            text = "Ready"
            tone = "neutral"
        else:
            text = "Ready"
            tone = "neutral"

        self._set_status_chip(
            getattr(self, "main_status_label", None),
            text,
            tone=tone,
            tooltip=normalized or text,
        )

    def set_progress_status_chip(self, status_message: str, is_busy: bool = False):
        """Update progress status shown in the bottom bar."""
        normalized = status_message.strip()
        lowered = normalized.lower()

        if lowered.startswith("error"):
            text = normalized
            tone = "danger"
        elif is_busy:
            text = normalized
            tone = "active"
        else:
            text = "Metadata idle"
            tone = "neutral"

        self._set_status_chip(
            getattr(self, "progress_status_label", None),
            text,
            tone=tone,
            tooltip=normalized or text,
        )

    def _set_status_chip(
        self, widget, text: str, tone: str = "neutral", tooltip: str | None = None
    ):
        """Apply text, tone, and tooltip to a status label."""
        if widget is None:
            return

        widget.setText(text)
        widget.setProperty("statusTone", tone)
        widget.setToolTip(tooltip or text)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def show_progress_indicator(self, show: bool):
        """Show/hide the progress indicator."""
        progress_dock = self.ui_builder.get_dock_widget("progress_dock")
        if progress_dock:
            progress_dock.setVisible(show)

    def update_progress_bar(self, percentage: int):
        """Update the progress bar."""
        if hasattr(self, "progress_panel"):
            self.progress_panel.update_progress(percentage)

    def show_operation_state(self, state: OperationViewState):
        """Show or update current operation in the Operations dock."""
        progress_dock = self.ui_builder.get_dock_widget("progress_dock")
        if progress_dock:
            progress_dock.setVisible(True)
        if hasattr(self, "progress_panel"):
            self.progress_panel.apply_operation_state(state)

    def set_operation_action_handlers(
        self, handlers: dict[str, Callable[[], None]] | None
    ):
        """Attach action callbacks to the Operations panel."""
        if hasattr(self, "progress_panel"):
            self.progress_panel.set_operation_action_handlers(handlers)

    def clear_operation_state(self):
        """Collapse and reset the Operations surface."""
        if hasattr(self, "progress_panel"):
            self.progress_panel.reset_progress()

    def set_view_mode(self, mode: str):
        """Set the view mode."""
        if mode != self.current_view_mode:
            self.current_view_mode = mode
            self.ui_builder.set_view_mode(mode)
            self.menu_builder.check_action(f"view_{mode}", True)
        self._update_active_view_data(self.current_files)

    def show_log_console(self, show: bool = True):
        """Show/hide the log console."""
        self.ui_builder.show_dock_widget("log_dock", show)

    def cleanup(self):
        """Clean up UI resources."""
        try:
            self.logger.info("Cleaning up MainWindow...")
            self.logger.info("MainWindow cleanup complete")
        except Exception as e:
            self.logger.error(f"Error during MainWindow cleanup: {e}")

    def closeEvent(self, event):
        """Handle window close."""
        try:
            self.cleanup()
            event.accept()
        except Exception as e:
            self.logger.error(f"Error during close: {e}")
            event.accept()
