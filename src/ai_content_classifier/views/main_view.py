# views/main_view.py
"""
Main View Controller - Restructured and clean version with exception handling.

This file contains ONLY high-level orchestration.
All specialized logic is delegated to the appropriate managers.
"""

import os
import time
from typing import Any, List, Tuple

from ai_content_classifier.app_context import ApplicationServices
from ai_content_classifier.core.logger import get_logger
from PyQt6.QtCore import QObject

from ai_content_classifier.views.handlers.signal_router import SignalRouter
from ai_content_classifier.views.events.event_bus import AppEvent, EventBus
from ai_content_classifier.views.events.event_types import EventType

# Handlers
from ai_content_classifier.views.handlers.ui_event_handler import UIEventHandler
from ai_content_classifier.views.main_window.main import MainWindow
from ai_content_classifier.views.managers.connection_manager import ConnectionManager
from ai_content_classifier.views.managers.file_manager import FileManager
from ai_content_classifier.views.managers.settings_manager import SettingsManager

# Presenters
from ai_content_classifier.views.presenters.file_presenter import FilePresenter
from ai_content_classifier.views.presenters.status_presenter import StatusPresenter


class MainView(QObject):
    """
    Main View Controller - with metadata and thumbnail services.
    ✅ Fixed version with correct initialization order and handler wiring.
    """

    def __init__(self, app, services: ApplicationServices):
        super().__init__()
        self.logger = get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        self.app = app
        self.services = services
        self.database_service = services.database_service
        self.config_service = services.config_service
        self.llm_controller = services.llm_controller
        self.performance_metrics = services.performance_metrics
        self.db_service = services.content_database_service
        self.metadata_service = services.metadata_service
        self.thumbnail_service = services.thumbnail_service
        self._pipeline_state: dict[str, Any] = {
            "active": False,
            "awaiting_categorization": False,
            "scan_config": {},
            "scan_files": [],
        }
        self._history_max_items = 300

        # ✅ ORDRE D'INITIALISATION CORRIGÉ
        try:
            # 1. UI component initialization
            self.main_window = MainWindow(content_database_service=self.db_service)
            self.event_bus = EventBus(self)

            # 2. Manager initialization
            self._init_managers()

            # 3. ✅ Handler and presenter initialization (UIEventHandler created HERE)
            self._init_handlers_and_presenters()

            # 4. ✅ Connexion des handlers MainWindow vers UIEventHandler
            self._connect_main_window_handlers()

            # 5. ✅ Signal connection (routing entre managers)
            self._connect_signals()

            # 6. Initial setup
            self._setup_initial_state()

            self.logger.info(
                "MainView initialized successfully with corrected handler connections"
            )

        except Exception as e:
            self.logger.error(f"Error initializing MainView: {e}", exc_info=True)
            raise

    def show(self):
        """Displays the main window."""
        self.main_window.show()

    def _init_managers(self):
        """Initializes managers with new services."""
        try:
            self.logger.debug("Initializing managers...")

            # === CORRECT DEPENDENCY ORDER ===

            # 1. Connection Manager (depends on llm_controller)
            self.connection_manager = ConnectionManager(self.llm_controller)

            # 2. Settings Manager (depends on config_service, llm_controller and connection_manager)
            self.settings_manager = SettingsManager(
                self.config_service, self.llm_controller, self.connection_manager
            )

            # 3. File Manager with new services
            self.file_manager = FileManager(
                db_service=self.db_service,
                config_service=self.config_service,
                metadata_service=self.metadata_service,  # 🆕 Metadata service
                thumbnail_service=self.thumbnail_service,  # 🆕 Thumbnail service
            )

            self.logger.debug("Managers initialized successfully")

        except Exception as e:
            self.logger.error(f"Error initializing managers: {e}")
            raise

    def _init_handlers_and_presenters(self):
        """Initializes handlers and presenters with new services."""
        try:
            self.logger.debug("Initializing handlers and presenters...")

            # ✅ 1. UI Event Handler (created FIRST)
            self.ui_event_handler = UIEventHandler(
                main_window=self.main_window,
                settings_manager=self.settings_manager,
                file_manager=self.file_manager,
                llm_controller=self.llm_controller,
                content_database_service=self.db_service,
            )

            # ✅ 2. Signal Router (created after UIEventHandler)
            self.signal_router = SignalRouter(
                self.main_window, event_bus=self.event_bus
            )

            # === FILE PRESENTER WITH THUMBNAIL SERVICE ===
            self.file_presenter = FilePresenter(
                self.main_window,
                self.db_service,
                config_service=self.config_service,
            )

            # Configure thumbnail service in the presenter
            self.file_presenter.set_thumbnail_service(self.thumbnail_service)
            self.file_presenter.set_metadata_service(self.metadata_service)

            # Status Presenter
            self.status_presenter = StatusPresenter(self.main_window)
            self.file_manager.bind_main_window(self.main_window)

            self.logger.debug("Handlers and presenters initialized successfully")

        except Exception as e:
            self.logger.error(f"Error initializing handlers and presenters: {e}")
            raise

    def _connect_main_window_handlers(self):
        """✅ NOUVEAU: Connect les handlers du MainWindow vers UIEventHandler."""
        try:
            self.logger.debug("Connecting MainWindow handlers to UIEventHandler...")

            # Mapping des methods MainWindow vers UIEventHandler
            handler_mappings = {
                "handle_scan_request": self.ui_event_handler.handle_scan_request,
                "handle_open_folder_request": self.ui_event_handler.handle_open_folder_request,
                "handle_quick_scan_request": self.ui_event_handler.handle_quick_scan_request,
                "handle_settings_request": lambda: (
                    self.settings_manager.open_settings_dialog(self.main_window)
                ),
                "handle_clear_db_request": self.ui_event_handler.handle_clear_db_request,
                "handle_remove_filtered_results_request": self.ui_event_handler.handle_remove_filtered_results_request,
                "handle_clear_thumbnail_cache_request": self._handle_clear_thumbnail_cache_request,
                "handle_categorization_request": self.ui_event_handler.handle_categorization_request,
                "handle_auto_organize_request": self.ui_event_handler.handle_organize_request,
                "handle_refresh_request": self._handle_refresh_request,  # ✅ Handler local
                "handle_about_request": self._handle_about_request,  # ✅ Handler local
                "handle_documentation_request": self._handle_documentation_request,  # ✅ Handler local
                "handle_logs_request": self._handle_logs_request,  # ✅ Handler local
                "handle_debug_request": self._handle_debug_request,  # ✅ Handler local
                "handle_llm_test_request": self._handle_llm_test_request,  # ✅ Handler local
                "handle_fullscreen_toggle": self._handle_fullscreen_toggle,  # ✅ Handler local
                "handle_theme_request": self.ui_event_handler.handle_theme_request,  # ✅ NOUVEAU
                "handle_filter_by_category_request": self.ui_event_handler.handle_category_filter_request,
                "handle_filter_by_year_request": self.ui_event_handler.handle_year_filter_request,
                "handle_filter_by_extension_request": self.ui_event_handler.handle_extension_filter_request,
                "handle_filter_reset_request": lambda: (
                    self.ui_event_handler.handle_filter_change("All Files")
                ),
                "handle_zoom_in_request": self.ui_event_handler.handle_zoom_in_request,
                "handle_zoom_out_request": self.ui_event_handler.handle_zoom_out_request,
                "handle_zoom_reset_request": self.ui_event_handler.handle_zoom_reset_request,
                "handle_view_sidebar_request": self.ui_event_handler.handle_view_sidebar_request,
            }

            # Connectr chaque handler
            for handler_name, handler_func in handler_mappings.items():
                setattr(self.main_window, handler_name, handler_func)
                self.logger.debug(f"Connectd {handler_name} to target handler")

            # ✅ Generator configuration (important for thumbnails)
            self.main_window.set_thumbnail_generator(
                self.file_presenter.get_or_create_thumbnail_pixmap
            )
            self.main_window.set_metadata_generator(
                self.file_presenter.get_or_create_metadata
            )

            # ✅ NEW: Connect menu handlers now that everything is ready
            self.main_window.connect_menu_handlers()

            self.logger.debug("MainWindow handlers connectd successfully")

        except Exception as e:
            self.logger.error(f"Error connecting MainWindow handlers: {e}")
            raise

    def _handle_clear_thumbnail_cache_request(self):
        """Clear thumbnail cache from tools action and surface user feedback."""
        from PyQt6.QtWidgets import QMessageBox

        try:
            if hasattr(self.file_manager, "clear_thumbnail_cache"):
                self.file_manager.clear_thumbnail_cache()
            if hasattr(self, "file_presenter") and hasattr(
                self.file_presenter, "clear_cache"
            ):
                self.file_presenter.clear_cache()
            QMessageBox.information(
                self.main_window,
                "Thumbnail Cache",
                "Thumbnail cache cleared successfully.",
            )
        except Exception as exc:
            self.logger.error(f"Error clearing thumbnail cache: {exc}", exc_info=True)
            QMessageBox.warning(
                self.main_window,
                "Thumbnail Cache",
                f"Failed to clear thumbnail cache: {exc}",
            )

    def _connect_signals(self):
        """✅ CORRIGÉ: Connect les signaux entre managers (pas les handlers UI)."""
        try:
            self.logger.debug("Connecting manager signals...")

            # ✅ SUPPRIMÉ: Plus de connexions directes des actions du menu
            # Actions are now managed by MenuBuilder -> MainWindow -> UIEventHandler

            # === CONNEXIONS DES SIGNAUX DE CHANGEMENT D'INTERFACE ===

            # View change connections (signals emitted by MainWindow)
            self.main_window.filter_changed.connect(
                self.ui_event_handler.handle_filter_change
            )
            self.main_window.view_mode_changed.connect(
                self.ui_event_handler.handle_view_mode_change
            )

            # File selection connections (signals emitted by widgets)
            if (
                hasattr(self.main_window, "file_list_widget")
                and self.main_window.file_list_widget
            ):
                if hasattr(self.main_window.file_list_widget, "clicked"):
                    self.main_window.file_list_widget.clicked.connect(
                        self.ui_event_handler.handle_file_selection
                    )
                if hasattr(self.main_window.file_list_widget, "doubleClicked"):
                    self.main_window.file_list_widget.doubleClicked.connect(
                        self.ui_event_handler.handle_file_activation
                    )

            if (
                hasattr(self.main_window, "thumbnail_grid_widget")
                and self.main_window.thumbnail_grid_widget
            ):
                if hasattr(self.main_window.thumbnail_grid_widget, "file_selected"):
                    self.main_window.thumbnail_grid_widget.file_selected.connect(
                        self.ui_event_handler.handle_file_selection_from_path
                    )
                if hasattr(self.main_window.thumbnail_grid_widget, "file_activated"):
                    self.main_window.thumbnail_grid_widget.file_activated.connect(
                        self.ui_event_handler.handle_file_activation_from_path
                    )

            if (
                hasattr(self.main_window, "columns_widget")
                and self.main_window.columns_widget
                and hasattr(self.main_window.columns_widget, "itemDoubleClicked")
            ):
                self.main_window.columns_widget.itemDoubleClicked.connect(
                    self.ui_event_handler.handle_columns_file_activation
                )

            # Connect MainWindow's file_selected_signal to FilePresenter for preview
            self.main_window.file_selected_signal.connect(
                self.file_presenter.handle_file_selection_for_preview
            )
            self.main_window.file_activated_signal.connect(
                self.file_presenter.open_file_details_dialog
            )

            # === NOUVELLES CONNEXIONS FILE MANAGER ===

            # Individual file processing
            self.file_manager.file_processed.connect(self._on_file_processed)

            # Processing statistics
            self.file_manager.processing_stats.connect(self._on_processing_stats)

            # 🔍 CONNEXIONS CRUCIALES pour l'affichage
            # NOTE: file list/filter propagation is handled by SignalRouter to avoid duplicates.
            self.file_manager.files_updated.connect(
                self._update_categorization_button_state
            )

            # Connect FilterChipsContainer to FileManager
            if (
                hasattr(self.main_window, "active_filters_bar")
                and self.main_window.active_filters_bar
            ):
                self.main_window.active_filters_bar.filters_changed.connect(
                    self.file_manager.update_filters_from_chips
                )

            # Connect sidebar filter chips as well (primary active-filters UI).
            if (
                hasattr(self.main_window, "filter_sidebar")
                and self.main_window.filter_sidebar
                and hasattr(self.main_window.filter_sidebar, "filter_chips_container")
            ):
                self.main_window.filter_sidebar.filter_chips_container.filters_changed.connect(
                    self.file_manager.update_filters_from_chips
                )

            # ✅ ROUTING DES SIGNAUX ENTRE MANAGERS (maintenant avec AutoOrganizationController)
            self.signal_router.connect_managers(
                connection_manager=self.connection_manager,
                settings_manager=self.settings_manager,
                file_manager=self.file_manager,
                status_presenter=self.status_presenter,
                file_presenter=self.file_presenter,
                auto_organization_controller=self.ui_event_handler.auto_organization_controller,  # ✅ NOUVEAU
            )

            # Pipeline hook: used to chain auto organization after categorization.
            self.ui_event_handler.categorization_controller.categorization_completed.connect(
                self._on_categorization_completed_for_pipeline
            )

            self._connect_event_handlers()

            self.logger.debug("Manager signals connectd successfully")

        except Exception as e:
            self.logger.error(f"Error connecting signals: {e}")
            raise

    def _connect_event_handlers(self):
        """Connects high-level application event handlers."""
        self.event_bus.subscribe(EventType.SCAN_ERROR, self._on_scan_error_event)
        self.event_bus.subscribe(
            EventType.SCAN_COMPLETED, self._on_scan_completed_event
        )
        self.event_bus.subscribe(
            EventType.ORGANIZATION_COMPLETED, self._on_organization_completed_event
        )
        self.event_bus.subscribe(
            EventType.ORGANIZATION_ERROR, self._on_organization_error_event
        )
        # Feed History tab from centralized event stream.
        for event_type in EventType:
            self.event_bus.subscribe(event_type, self._on_history_event)

    def _on_history_event(self, event: AppEvent):
        """Appends relevant application events to the History sidebar tab."""
        # Skip high-frequency noise.
        if event.event_type in {
            EventType.SCAN_PROGRESS,
            EventType.FILES_UPDATED,
            EventType.ORGANIZATION_PROGRESS,
        }:
            return

        payload = event.payload or {}
        label = event.event_type.value.replace("_", " ").title()

        if event.event_type == EventType.SCAN_STARTED:
            label = f"Scan started: {payload.get('directory', '-')}"
        elif event.event_type == EventType.SCAN_COMPLETED:
            label = f"Scan completed: {payload.get('file_count', 0)} files"
        elif event.event_type == EventType.SCAN_ERROR:
            label = f"Scan error: {payload.get('error_message', 'Unknown error')}"
        elif event.event_type == EventType.FILTER_APPLIED:
            label = (
                f"Filter applied: {payload.get('filtered_count', 0)} files "
                f"({payload.get('active_filters', {})})"
            )
        elif event.event_type == EventType.CATEGORIZATION_STARTED:
            label = (
                f"Categorization started: {payload.get('file_count', 0)} files, "
                f"{payload.get('category_count', 0)} categories"
            )
        elif event.event_type == EventType.CATEGORIZATION_COMPLETED:
            label = (
                f"Categorization completed: {payload.get('total_processed', 0)} "
                f"(ok={payload.get('successful', 0)}, ko={payload.get('failed', 0)})"
            )
        elif event.event_type == EventType.CATEGORIZATION_ERROR:
            label = (
                f"Categorization error: {payload.get('error_message', 'Unknown error')}"
            )
        elif event.event_type == EventType.ORGANIZATION_STARTED:
            label = "Organization started"
        elif event.event_type == EventType.ORGANIZATION_COMPLETED:
            stats = payload.get("stats", {})
            label = (
                f"Organization completed: {stats.get('successful', 0)}/"
                f"{stats.get('total_files', 0)}"
            )
        elif event.event_type == EventType.ORGANIZATION_ERROR:
            label = (
                f"Organization error: {payload.get('error_message', 'Unknown error')}"
            )
        elif event.event_type == EventType.CONNECTION_TESTED:
            label = (
                "Connection test: "
                + ("OK" if payload.get("success", False) else "FAILED")
                + f" - {payload.get('message', '')}"
            )

        timestamp = time.strftime("%H:%M:%S", time.localtime(event.timestamp))
        entry = f"[{timestamp}] {label}"
        self._append_history_entry(entry)

    def _append_history_entry(self, message: str):
        """Adds a message to history_list with retention cap."""
        if (
            not hasattr(self.main_window, "history_list")
            or not self.main_window.history_list
        ):
            return

        history_list = self.main_window.history_list
        history_list.addItem(message)
        while history_list.count() > self._history_max_items:
            history_list.takeItem(0)
        history_list.scrollToBottom()

    def _on_scan_error_event(self, event: AppEvent):
        """Global hook for scan error events."""
        self.logger.error(
            f"Global scan error event: {event.payload.get('error_message', 'Unknown error')}"
        )

    def _on_organization_error_event(self, event: AppEvent):
        """Global hook for organization error events."""
        self.logger.error(
            "Global organization error event: "
            f"{event.payload.get('error_message', 'Unknown error')}"
        )
        self._pipeline_state["active"] = False

    def _on_organization_completed_event(self, event: AppEvent):
        """Global hook for organization completion."""
        self._pipeline_state["active"] = False

    def _on_scan_completed_event(self, event: AppEvent):
        """Starts the automated scan pipeline based on scan configuration."""
        scan_config = self.file_manager.get_current_scan_config() or {}
        should_continue_pipeline = bool(
            scan_config.get("auto_categorize", False)
            or scan_config.get("auto_organize", False)
            or scan_config.get("ai_processing", False)
        )
        if not should_continue_pipeline:
            self._pipeline_state["active"] = False
            return

        scan_files = event.payload.get("file_list", []) or []
        if not scan_files:
            self.logger.warning("Auto pipeline skipped: no files from scan completion")
            return

        self._pipeline_state.update(
            {
                "active": True,
                "awaiting_categorization": False,
                "scan_config": scan_config,
                "scan_files": scan_files,
            }
        )

        if scan_config.get("auto_categorize", False):
            categories = (
                scan_config.get("categories")
                or self.settings_manager.get_unified_categories()
            )
            file_types = scan_config.get("file_types", {})
            categorize_overrides = {
                "confidence_threshold": scan_config.get("confidence_threshold", 0.7),
                "process_images": file_types.get("images", True),
                "process_documents": file_types.get("documents", True),
                "show_report": False,
                "export_csv": False,
                "save_results": True,
                "preview_mode": False,
            }

            file_paths = [file_path for file_path, *_ in scan_files]
            self.event_bus.publish(
                EventType.CATEGORIZATION_STARTED,
                {
                    "file_count": len(file_paths),
                    "category_count": len(categories),
                },
                source="MainView",
            )
            try:
                started = self.ui_event_handler.categorization_controller.start_automatic_categorization(
                    file_paths=file_paths,
                    categories=categories,
                    config_overrides=categorize_overrides,
                    parent_widget=self.main_window,
                )
            except Exception as e:
                started = False
                self.logger.error(f"Automatic categorization failed to start: {e}")
                self.event_bus.publish(
                    EventType.CATEGORIZATION_ERROR,
                    {"error_message": str(e)},
                    source="MainView",
                )
            self._pipeline_state["awaiting_categorization"] = started
            if not started and scan_config.get("auto_organize", False):
                self.event_bus.publish(
                    EventType.CATEGORIZATION_ERROR,
                    {"error_message": "Automatic categorization did not start"},
                    source="MainView",
                )
                self._start_automatic_organization(scan_files, scan_config)
            elif not started:
                self._pipeline_state["active"] = False
            return

        if scan_config.get("auto_organize", False):
            self._start_automatic_organization(scan_files, scan_config)

    def _on_categorization_completed_for_pipeline(self, results: dict):
        """Continues the automated pipeline after categorization."""
        if not self._pipeline_state.get("active"):
            return
        if not self._pipeline_state.get("awaiting_categorization"):
            return

        self._pipeline_state["awaiting_categorization"] = False
        self.event_bus.publish(
            EventType.CATEGORIZATION_COMPLETED,
            {
                "total_processed": results.get("total_processed", 0),
                "successful": results.get("successful", 0),
                "failed": results.get("failed", 0),
            },
            source="MainView",
        )

        scan_config = self._pipeline_state.get("scan_config", {})
        if scan_config.get("auto_organize", False):
            scan_files = self._pipeline_state.get("scan_files", [])
            self._start_automatic_organization(scan_files, scan_config)
            return

        self._pipeline_state["active"] = False

    def _start_automatic_organization(
        self, scan_files: List[Tuple[str, str]], scan_config: dict[str, Any]
    ):
        """Starts automatic organization from pipeline configuration."""
        org_config = {
            "target_directory": scan_config.get("target_directory", ""),
            "organization_structure": scan_config.get(
                "organization_structure", "By Category"
            ),
            "organization_action": scan_config.get("organization_action", "copy"),
        }

        if not org_config["target_directory"]:
            self.logger.warning(
                "Auto organization skipped: missing target_directory in scan config"
            )
            self._pipeline_state["active"] = False
            return

        started = self.ui_event_handler.auto_organization_controller.start_organization(
            file_list=scan_files,
            config_dict=org_config,
        )
        if not started:
            self.logger.error("Auto organization failed to start from pipeline")
            self._pipeline_state["active"] = False

    # ✅ NOUVEAUX HANDLERS LOCAUX

    def _handle_refresh_request(self):
        """Handler local pour refresh."""
        self.logger.debug("Refresh request received")
        try:
            if hasattr(self, "file_manager"):
                self.file_manager.refresh_file_list()
        except Exception as e:
            self.logger.error(f"Error during refresh: {e}")

    def _handle_about_request(self):
        """Handler local pour about."""
        try:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.about(
                self.main_window,
                "About Javis",
                "Javis\nVersion 1.0\n\nAutomated file organization using AI",
            )
        except Exception as e:
            self.logger.error(f"Error showing about dialog: {e}")

    def _handle_documentation_request(self):
        """Handler local pour documentation."""
        self.logger.debug("Documentation request received")
        # TODO: Implement documentation opening

    def _handle_logs_request(self):
        """Handler local pour affichage des logs."""
        self.logger.debug("Logs request received")
        try:
            self.main_window.show_log_console(True)
        except Exception as e:
            self.logger.error(f"Error showing log console: {e}")

    def _handle_debug_request(self):
        """Handler local pour affichage des informations de debug."""
        self.logger.debug("Debug request received")
        try:
            from PyQt6.QtWidgets import QMessageBox

            file_count = len(getattr(self.file_manager, "file_list", []) or [])
            connectd = False
            if hasattr(self, "connection_manager"):
                try:
                    connectd, _ = self.connection_manager.get_connection_status()
                except Exception:
                    connectd = bool(
                        getattr(self.connection_manager, "is_connectd", False)
                    )
            theme_name = getattr(self.main_window, "current_theme_name", "unknown")
            msg = (
                "Debug Information\n\n"
                f"Loaded files: {file_count}\n"
                f"LLM connectd: {connectd}\n"
                f"Theme: {theme_name}\n"
                f"Fullscreen: {self.main_window.isFullScreen()}"
            )
            QMessageBox.information(self.main_window, "Debug Information", msg)
        except Exception as e:
            self.logger.error(f"Error showing debug information: {e}")

    def _handle_llm_test_request(self):
        """Handler local pour test LLM."""
        self.logger.debug("LLM test request received")
        try:
            if hasattr(self, "connection_manager"):
                self.connection_manager.test_llm_connections()
        except Exception as e:
            self.logger.error(f"Error testing LLM connection: {e}")

    def _handle_fullscreen_toggle(self):
        """Handler local pour fullscreen."""
        try:
            if self.main_window.isFullScreen():
                self.main_window.showNormal()
            else:
                self.main_window.showFullScreen()
        except Exception as e:
            self.logger.error(f"Error toggling fullscreen: {e}")

    # === SIGNAL HANDLERS (unchanged) ===

    def _on_file_processed(self, file_path: str, metadata_ok: bool, thumbnail_ok: bool):
        """
        Handles individual file processing.

        Args:
            file_path: Path of the processed file
            metadata_ok: True if metadata was extracted
            thumbnail_ok: True if thumbnail was generated
        """
        try:
            # Log for debugging
            filename = os.path.basename(file_path)
            status_msg = f"📁 {filename}"

            if metadata_ok:
                status_msg += " 📊"
            if thumbnail_ok:
                status_msg += " 🖼️"

            # Notify the grid that a thumbnail might be available
            if thumbnail_ok and hasattr(self.main_window, "thumbnail_grid_widget"):
                # Force thumbnail refresh in the grid
                if hasattr(self.main_window.thumbnail_grid_widget, "refresh_thumbnail"):
                    self.main_window.thumbnail_grid_widget.refresh_thumbnail(file_path)
        except Exception as e:
            self.logger.error(f"Error handling file processed signal: {e}")

    def _on_processing_stats(self, stats: dict):
        """
        Handles processing statistics.

        Args:
            stats: Dictionary with statistics
        """
        try:
            # Update status bar with statistics
            stats_msg = (
                f"📊 Files: {stats.get('files_found', 0)} | "
                f"Metadata: {stats.get('metadata_extracted', 0)} | "
                f"Thumbnails: {stats.get('thumbnails_generated', 0)}"
            )

            if stats.get("errors", 0) > 0:
                stats_msg += f" | ❌ Errors: {stats['errors']}"

            self.logger.debug(f"Processing stats: {stats_msg}")
        except Exception as e:
            self.logger.error(f"Error handling processing stats: {e}")

    def _update_categorization_button_state(self, files):
        """Updates the state of the categorization button."""
        try:
            has_files = len(files) > 0
            self.main_window.set_categorization_enabled(has_files)
        except Exception as e:
            self.logger.error(f"Error updating categorization button state: {e}")

    def _setup_initial_state(self):
        """Initial setup with new services."""
        try:
            self.logger.debug("Setting up initial state...")

            # Initial LLM connection test
            self.connection_manager.test_llm_connections()

            # Load and apply LLM settings
            self.llm_controller.update_config()

            # Refresh the file list from the database
            self.file_manager.refresh_file_list()

            # === INITIALIZATION OF NEW SERVICES ===

            # Check if metadata services are functional
            try:
                extractors_count = len(self.metadata_service.extractors)
                self.logger.debug(
                    f"Metadata service ready with {extractors_count} extractors"
                )
            except Exception as e:
                self.logger.warning(f"Metadata service initialization issue: {e}")

            # Check thumbnail service
            try:
                thumbnail_ready = hasattr(self.thumbnail_service, "create_thumbnail")
                self.logger.debug(f"Thumbnail service ready: {thumbnail_ready}")
            except Exception as e:
                self.logger.warning(f"Thumbnail service initialization issue: {e}")

            self.logger.debug("Initial state setup completed")

        except Exception as e:
            self.logger.error(f"Error setting up initial state: {e}")
            raise

    def cleanup(self):
        """Cleanup with new services."""
        try:
            self.logger.info("Starting MainView cleanup...")

            if hasattr(self, "main_window"):
                if hasattr(self.main_window, "cleanup"):
                    self.main_window.cleanup()

            if hasattr(self, "file_manager"):
                if hasattr(self.file_manager, "cancel_current_scan"):
                    self.file_manager.cancel_current_scan()

            # === CLEANUP OF NEW SERVICES ===

            # Thumbnail service cleanup
            if hasattr(self, "thumbnail_service"):
                if hasattr(self.thumbnail_service, "shutdown"):
                    self.thumbnail_service.shutdown()
                elif hasattr(self.thumbnail_service, "cleanup"):
                    self.thumbnail_service.cleanup()

            # Metadata service cleanup
            if hasattr(self, "metadata_service"):
                if hasattr(self.metadata_service, "clear_cache"):
                    self.metadata_service.clear_cache()

            # Signal router cleanup
            if hasattr(self, "signal_router"):
                if hasattr(self.signal_router, "disconnect_all"):
                    self.signal_router.disconnect_all()

            # Core services cleanup
            if hasattr(self, "llm_controller"):
                self.llm_controller.shutdown()

            if hasattr(self, "database_service"):
                if hasattr(self.database_service, "close_all"):
                    self.database_service.close_all()
                elif hasattr(self.database_service, "close"):
                    self.database_service.close()

            self.logger.info("MainView cleanup completed")

        except Exception as e:
            self.logger.error(f"Error during MainView cleanup: {e}")
