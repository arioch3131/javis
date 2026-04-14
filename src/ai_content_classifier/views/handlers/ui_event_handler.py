# handlers/ui_event_handler.py
"""
UI Event Handler - Centralized management of user interface events.

Responsibilities:
- Processing UI events
- Delegating to appropriate managers and controllers
- Validating user input
- Integration avec AutoOrganizationController
"""

import os
from typing import List, Optional, Tuple

from ai_content_classifier.controllers.auto_organization_controller import (
    AutoOrganizationController,
)
from ai_content_classifier.controllers.categorization_controller import (
    CategorizationController,
)
from ai_content_classifier.controllers.llm_controller import LLMController
from ai_content_classifier.core.logger import get_logger
from PyQt6.QtCore import QModelIndex, QObject, Qt
from PyQt6.QtWidgets import QDialog, QFileDialog, QMessageBox, QTreeWidgetItem
from ai_content_classifier.services.content_database_service import (
    ContentDatabaseService,
)
from ai_content_classifier.views.main_window import MainWindow
from ai_content_classifier.views.managers.file_manager import FileManager
from ai_content_classifier.views.managers.settings_manager import SettingsManager
from ai_content_classifier.services.file.operations import FileOperationDataKey
from ai_content_classifier.views.widgets.dialogs import (
    AdvancedScanDialog,
    AutoOrganizeDialog,
    BasicScanTypeDialog,
)
from ai_content_classifier.views.widgets.dialogs.selection.selection_dialog import (
    create_category_selection_dialog,
    create_extension_selection_dialog,
    create_year_selection_dialog,
)


class UIEventHandler(QObject):
    """
    Centralized UI event handler with integration of new controllers.

    This handler receives all user interface events
    and delegates them to the appropriate managers and controllers.
    """

    def __init__(
        self,
        main_window: MainWindow,
        settings_manager: SettingsManager,
        file_manager: FileManager,
        llm_controller: LLMController,
        content_database_service: ContentDatabaseService,
    ):
        super().__init__()
        self.logger = get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        self.main_window = main_window
        self.settings_manager = settings_manager
        self.file_manager = file_manager
        self.llm_controller = llm_controller
        self.content_database_service = content_database_service

        # The CategorizationController now needs the full llm_controller
        # and the settings_manager to retrieve categories.
        self.categorization_controller = CategorizationController(
            llm_controller=self.llm_controller,
            settings_manager=self.settings_manager,
            file_manager=self.file_manager,
            content_database_service=self.content_database_service,
            parent=self,
        )

        # ✅ NOUVEAU: Controller d'organisation automatique
        self.auto_organization_controller = AutoOrganizationController(
            content_database_service=self.content_database_service, parent=self
        )
        self.auto_organization_controller.bind_main_window(self.main_window)

        self.logger.info("UIEventHandler initialized with AutoOrganizationController")

    def _get_preselected_filter_values(self, filter_type: str) -> List[str]:
        """Returns current active values for a given filter type as strings."""
        if not hasattr(self, "file_manager") or self.file_manager is None:
            return []

        get_active_filters = getattr(self.file_manager, "get_active_filters", None)
        if get_active_filters is None:
            return []

        active_filters = get_active_filters() or {}
        values = active_filters.get(filter_type, [])
        return [str(value) for value in values]

    def handle_scan_request(self):
        """Handles the directory scan request - NOUVELLE VERSION AVANCÉE."""
        self.logger.info("Opening advanced scan dialog")

        try:
            # Create and show advanced dialog
            scan_dialog = AdvancedScanDialog(
                self.llm_controller,
                self.auto_organization_controller,
                self.settings_manager,
                self.main_window,
            )

            # Connectr le signal de scan
            scan_dialog.scan_requested.connect(self.on_advanced_scan_requested)

            # Afficher le dialog
            if scan_dialog.exec() == QDialog.DialogCode.Accepted:
                self.logger.info("Advanced scan dialog accepted")
            else:
                self.logger.debug("Advanced scan dialog cancelled by user")

        except Exception as e:
            self.logger.error(f"Error opening advanced scan dialog: {e}")
            # Fallback to the legacy system
            self.handle_scan_request_fallback()

    def handle_open_folder_request(self):
        """Open folder flow: choose directory then launch a basic scan directly."""
        self.logger.info("Open folder requested")
        self.handle_scan_request_fallback()

    def handle_quick_scan_request(self, directory: Optional[str] = None):
        """
        Quick scan flow: scan the provided directory path immediately.
        If no path is provided, fallback to folder picker.
        """
        if not directory:
            self.logger.info("Quick scan requested without path, using folder picker")
            self.handle_scan_request_fallback()
            return

        if not os.path.isdir(directory):
            QMessageBox.warning(
                self.main_window,
                "Invalid Folder",
                f"The selected path is not a folder:\n{directory}",
            )
            return

        self.logger.info(f"Quick scan requested for: {directory}")
        file_types = self._prompt_basic_scan_file_types()
        if file_types is None:
            self.logger.debug("Quick scan cancelled during file type selection")
            return

        basic_config = self._build_basic_scan_config(directory, file_types)
        self.on_advanced_scan_requested(basic_config)

    def handle_scan_request_fallback(self):
        """Fallback to the legacy system de scan (QFileDialog)."""
        self.logger.info("Using fallback scan method")

        directory = QFileDialog.getExistingDirectory(
            self.main_window, "Select a directory to scan"
        )

        if directory:
            self.logger.info(f"Directory selected for scan: {directory}")
            file_types = self._prompt_basic_scan_file_types()
            if file_types is None:
                self.logger.debug("Scan cancelled during file type selection")
                return

            basic_config = self._build_basic_scan_config(directory, file_types)

            self.on_advanced_scan_requested(basic_config)
        else:
            self.logger.debug("Scan cancelled by user")

    def _prompt_basic_scan_file_types(self) -> Optional[dict]:
        """Prompts for the basic scan file groups."""
        dialog = BasicScanTypeDialog(self.main_window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.get_file_types()

    def _build_basic_scan_config(self, directory: str, file_types: dict) -> dict:
        """Builds the default basic-scan configuration."""
        return {
            "directory": directory,
            "file_types": {
                "documents": bool(file_types.get("documents", False)),
                "images": bool(file_types.get("images", False)),
                "videos": False,
                "audio": False,
                "others": False,
            },
            "extract_metadata": True,
            "generate_thumbnails": True,
            "auto_categorize": False,
            "auto_organize": False,
            "ai_processing": False,
        }

    def on_advanced_scan_requested(self, config: dict):
        """
        Handle an advanced scan request with full configuration.

        Args:
            config: Full scan configuration
        """
        self.logger.info(
            f"Advanced scan requested for: {config.get('directory', 'Unknown')}"
        )
        self.logger.debug(f"Scan configuration: {config}")

        try:
            directory = config.get("directory")
            if not directory:
                self.logger.error("No directory specified in scan config")
                return

            if config.get("preview_mode", False):
                self.handle_preview_scan(config)
            else:
                self.handle_pipeline_scan(config)

        except Exception as e:
            self.logger.error(f"Error processing advanced scan request: {e}")

    def handle_preview_scan(self, config: dict):
        """Handle un scan de preview."""
        self.logger.info("Starting preview scan")

        # TODO: Implement preview
        # For now, show a dialog with the details
        directory = config["directory"]
        file_types = [k for k, v in config.get("file_types", {}).items() if v]

        preview_text = (
            f"📁 Directory: {directory}\n"
            f"📋 File Types: {', '.join(file_types)}\n"
            f"⚙️ Processing: {'Yes' if config.get('extract_metadata') else 'No'}\n"
            f"🤖 AI: {'Yes' if config.get('ai_processing') else 'No'}"
        )

        QMessageBox.information(
            self.main_window,
            "Scan Preview",
            f"Preview scan configuration:\n\n{preview_text}\n\n"
            "This would be replaced by actual preview functionality.",
        )

    def handle_pipeline_scan(self, config: dict):
        """Starts the scan phase of the configured sequential pipeline."""
        self.logger.info("Starting configured scan pipeline")
        directory = config["directory"]
        self.file_manager.start_scan(directory, scan_config=config)

    # === NOUVELLES MÉTHODES POUR GESTION DE L'AUTO-ORGANISATION ===

    def handle_organize_request(self):
        """✅ NOUVELLE: Handle une demande d'organisation automatique pour les files actuels."""
        self.logger.info("Auto-organization request for current view")

        try:
            # Get currently displayed files
            current_files = self._get_current_files_list()

            if not current_files:
                QMessageBox.warning(
                    self.main_window,
                    "No Files to Organize",
                    "No files are currently displayed. Please scan a directory first.",
                )
                return

            # Creater et afficher le dialog d'organisation
            organize_dialog = AutoOrganizeDialog(
                file_list=current_files,
                organization_controller=self.auto_organization_controller,
                parent=self.main_window,
            )

            # Connectr les signaux
            organize_dialog.organization_completed.connect(
                self.on_organization_completed
            )

            # Afficher le dialog
            if organize_dialog.exec() == QDialog.DialogCode.Accepted:
                self.logger.info("Organization dialog completed successfully")
            else:
                self.logger.debug("Organization dialog cancelled by user")

        except Exception as e:
            self.logger.error(f"Error handling organize request: {e}")
            QMessageBox.critical(
                self.main_window,
                "Organization Error",
                f"Error opening organization dialog:\n{e}",
            )

    def _get_current_files_list(self) -> List[Tuple[str, str]]:
        """Get list of currently displayed files."""
        try:
            files = getattr(self.main_window, "current_files", None) or []
            if not files:
                files = self.file_manager.current_files

            # Convert to the expected format: List[Tuple[str, str]] (file_path, directory)
            file_list = []

            for file_data in files:
                if isinstance(file_data, (list, tuple)) and len(file_data) >= 2:
                    # Format: (file_path, directory, category, content_type)
                    file_path = file_data[0]
                    directory = (
                        file_data[1]
                        if len(file_data) > 1
                        else os.path.dirname(file_path)
                    )
                    file_list.append((file_path, directory))
                elif isinstance(file_data, str):
                    # Format: just the path
                    file_path = file_data
                    directory = os.path.dirname(file_path)
                    file_list.append((file_path, directory))

            self.logger.debug(f"Retrieved {len(file_list)} files for organization")
            return file_list

        except Exception as e:
            self.logger.error(f"Error retrieving current files list: {e}")
            return []

    def on_organization_completed(self, stats: dict):
        """Called when organization finishes successfully."""
        try:
            successful = stats.get("successful", 0)
            total = stats.get("total_files", 0)
            target_dir = stats.get("target_directory", "")

            self.logger.info(
                f"Organization completed: {successful}/{total} files organized to {target_dir}"
            )

            # Optional: Refresh display or update statistics
            if hasattr(self.main_window, "refresh_display"):
                self.main_window.refresh_display()

            # Optionnel: Proposer d'ouvrir le folder cible
            if target_dir and stats.get("open_target", False):
                self._open_directory_in_explorer(target_dir)

        except Exception as e:
            self.logger.error(f"Error handling organization completion: {e}")

    def _open_directory_in_explorer(self, directory: str):
        """Open a folder in the system file explorer."""
        try:
            import platform
            import subprocess

            system = platform.system()
            if system == "Windows":
                subprocess.run(["explorer", directory])
            elif system == "Darwin":  # macOS
                subprocess.run(["open", directory])
            else:  # Linux
                subprocess.run(["xdg-open", directory])

        except Exception as e:
            self.logger.error(f"Error opening directory in explorer: {e}")

    # === EXISTING METHODS (unchanged) ===

    def handle_clear_db_request(self):
        """Handles the request to clear the content database."""
        self.logger.info("Clear content database request received.")
        self.file_manager.clear_content_database()

    def handle_remove_filtered_results_request(self):
        """Removes the currently displayed filtered results from the database only."""
        self.logger.info("Remove filtered results from database request received.")

        current_files = self._get_current_files_list()
        if not current_files:
            QMessageBox.warning(
                self.main_window,
                "No Filtered Results",
                "No files are currently displayed. Apply a filter or scan a directory first.",
            )
            return

        file_count = len(current_files)
        answer = QMessageBox.question(
            self.main_window,
            "Remove Filtered Results",
            (
                f"Remove {file_count} displayed files from the database?\n\n"
                "This only removes database entries. The files on disk will not be deleted."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.logger.debug("Filtered database removal cancelled by user.")
            return

        operation_result = self.file_manager.remove_files_from_database(
            [file_path for file_path, _ in current_files]
        )
        deleted_count = int(
            (operation_result.data or {}).get(
                FileOperationDataKey.DELETED_COUNT.value,
                0,
            )
        )
        QMessageBox.information(
            self.main_window,
            "Database Updated",
            f"Removed {deleted_count} displayed files from the database.",
        )

    def handle_settings_request(self):
        """Handles opening the settings."""
        self.logger.info("Opening settings")
        self.settings_manager.open_settings_dialog(self.main_window)

    def handle_filter_change(self, filter_type: str):
        """Handles filter change."""
        self.logger.debug(f"Filter changed: {filter_type}")
        if filter_type == "All Files":
            self.file_manager.clear_filters()
        else:
            # For backward compatibility, if a single string is passed, assume it's a file_type filter
            self.file_manager.apply_filter({"type": "file_type", "value": filter_type})

    def handle_view_mode_change(self, mode: str):
        """Handles view mode change."""
        self.logger.debug(f"View mode changed: {mode}")

        # Enable/disable zoom actions based on view mode
        is_grid_mode = mode == "grid"
        self.main_window.enable_action("view_zoom_in", is_grid_mode)
        self.main_window.enable_action("view_zoom_out", is_grid_mode)
        self.main_window.enable_action("view_zoom_reset", is_grid_mode)

    def handle_file_selection(self, index: QModelIndex):
        """Handles file selection from a QModelIndex."""
        file_path = self.main_window.file_list_widget.get_selected_file_path(index)
        if file_path:
            self.main_window.file_selected_signal.emit(index, file_path)

    def handle_file_selection_from_path(self, file_path: str):
        """Handles file selection from path."""
        # This method is kept for compatibility if other parts of the code emit a direct file path.
        # It will create a dummy index to pass to the main signal.

        dummy_index = QModelIndex()
        self.main_window.file_selected_signal.emit(dummy_index, file_path)

    def handle_file_activation(self, index: QModelIndex):
        """Handles file activation from a QModelIndex."""
        file_path = self.main_window.file_list_widget.get_selected_file_path(index)
        if file_path:
            self.main_window.file_activated_signal.emit(file_path)

    def handle_file_activation_from_path(self, file_path: str):
        """Handles file activation from a direct file path."""
        if file_path:
            self.main_window.file_activated_signal.emit(file_path)

    def handle_columns_file_activation(self, item: QTreeWidgetItem, column: int = 0):
        """Handles file activation from the columns view."""
        del column
        file_path = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if file_path:
            self.main_window.file_activated_signal.emit(file_path)

    def handle_categorization_request(self):
        """Handles the categorization request."""
        self.logger.info("Categorization request for current view")
        self.categorization_controller.start_categorization_for_current_view(
            parent_widget=self.main_window
        )

    def handle_theme_request(self):
        """Handles the request to change the theme."""
        self.logger.info("Theme change request received.")
        try:
            from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout
            from views.widgets.dialogs.theme.theme_widgets import ThemeSelector

            dialog = QDialog(self.main_window)
            dialog.setWindowTitle("Select Application Theme")
            layout = QVBoxLayout(dialog)
            theme_selector = ThemeSelector(dialog)
            layout.addWidget(theme_selector)

            close_button = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            close_button.rejected.connect(dialog.reject)
            layout.addWidget(close_button)

            dialog.exec()
        except Exception as e:
            self.logger.error(f"Error opening theme selector: {e}")

    def handle_category_filter_request(self):
        """Handles the request to filter by category."""
        self.logger.info("Category filter request received.")
        try:
            categories = self.content_database_service.get_unique_categories()
            if not categories:
                QMessageBox.information(
                    self.main_window,
                    "No Categories",
                    "No categories found in the database.",
                )
                return

            selected_categories = self._get_preselected_filter_values("category")
            dialog = create_category_selection_dialog(
                categories,
                self.main_window,
                selected_categories=selected_categories,
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_categories = dialog.get_selected_items()
                if selected_categories:
                    filter_data = {"type": "category", "value": selected_categories}
                    self.file_manager.apply_filter(filter_data)
        except Exception as e:
            self.logger.error(f"Error opening category filter: {e}")

    def handle_year_filter_request(self):
        """Handles the request to filter by year."""
        self.logger.info("Year filter request received.")
        try:
            years = [str(y) for y in self.content_database_service.get_unique_years()]
            if not years:
                QMessageBox.information(
                    self.main_window,
                    "No Years",
                    "No creation years found in the database.",
                )
                return

            selected_years = self._get_preselected_filter_values("year")
            dialog = create_year_selection_dialog(
                years,
                self.main_window,
                selected_years=selected_years,
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_years = [int(y) for y in dialog.get_selected_items()]
                if selected_years:
                    filter_data = {"type": "year", "value": selected_years}
                    self.file_manager.apply_filter(filter_data)
        except Exception as e:
            self.logger.error(f"Error opening year filter: {e}")

    def handle_extension_filter_request(self):
        """Handles the request to filter by extension."""
        self.logger.info("Extension filter request received.")
        try:
            extensions = self.content_database_service.get_unique_extensions()
            if not extensions:
                QMessageBox.information(
                    self.main_window,
                    "No Extensions",
                    "No file extensions found in the database.",
                )
                return

            selected_extensions = self._get_preselected_filter_values("extension")
            dialog = create_extension_selection_dialog(
                extensions,
                self.main_window,
                selected_extensions=selected_extensions,
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_extensions = dialog.get_selected_items()
                if selected_extensions:
                    filter_data = {"type": "extension", "value": selected_extensions}
                    self.file_manager.apply_filter(filter_data)
        except Exception as e:
            self.logger.error(f"Error opening extension filter: {e}")

    def handle_zoom_in_request(self):
        """Handles the request to zoom in the grid view."""
        self.logger.info("Zoom in request received.")
        if (
            hasattr(self.main_window, "thumbnail_grid_widget")
            and self.main_window.thumbnail_grid_widget
        ):
            self.main_window.thumbnail_grid_widget.zoom_in()

    def handle_zoom_out_request(self):
        """Handles the request to zoom out the grid view."""
        self.logger.info("Zoom out request received.")
        if (
            hasattr(self.main_window, "thumbnail_grid_widget")
            and self.main_window.thumbnail_grid_widget
        ):
            self.main_window.thumbnail_grid_widget.zoom_out()

    def handle_zoom_reset_request(self):
        """Handles the request to reset zoom in the grid view."""
        self.logger.info("Zoom reset request received.")
        if (
            hasattr(self.main_window, "thumbnail_grid_widget")
            and self.main_window.thumbnail_grid_widget
        ):
            self.main_window.thumbnail_grid_widget.zoom_reset()

    def handle_view_sidebar_request(self):
        """Handles the request to toggle sidebar visibility."""
        self.logger.info("Toggle sidebar request received.")
        self.main_window.ui_builder.show_dock_widget(
            "sidebar_dock",
            not self.main_window.ui_builder.get_dock_widget("sidebar_dock").isVisible(),
        )
