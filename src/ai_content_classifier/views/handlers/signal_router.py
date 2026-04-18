# handlers/signal_router.py
"""
Signal Router - Centralized routing of signals between components.

Responsibilities:
- Connect signals between different managers and components
- Avoid direct coupling between modules
- Centralize inter-component communication logic
- Integration with AutoOrganizationController
"""

from __future__ import annotations

from typing import Any, Optional

from ai_content_classifier.controllers.auto_organization_controller import (
    AutoOrganizationController,
)
from ai_content_classifier.core.logger import get_logger
from PyQt6.QtCore import QObject, Qt
from ai_content_classifier.services.i18n.i18n_service import tr
from ai_content_classifier.views.main_window.main import MainWindow
from ai_content_classifier.views.managers.connection_manager import ConnectionManager
from ai_content_classifier.views.managers.file_manager import FileManager
from ai_content_classifier.views.managers.settings_manager import SettingsManager
from ai_content_classifier.services.file.types import FileOperationCode
from ai_content_classifier.views.events.event_bus import EventBus
from ai_content_classifier.views.events.event_types import EventType
from ai_content_classifier.views.presenters.file_presenter import FilePresenter
from ai_content_classifier.views.presenters.status_presenter import StatusPresenter


class SignalRouter(QObject):
    """
    Centralized signal router between components avec support pour AutoOrganizationController.

    This router prevents components from knowing each other directly
    by centralizing signal connections.
    """

    def __init__(
        self,
        main_window: MainWindow,
        event_bus: Optional[EventBus] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.logger = get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        self.main_window = main_window  # Store reference to main_window
        self.event_bus = event_bus

        # References to components (will be defined during connect_managers)
        self.connection_manager: Optional[ConnectionManager] = None
        self.settings_manager: Optional[SettingsManager] = None
        self.file_manager: Optional[FileManager] = None
        self.status_presenter: Optional[StatusPresenter] = None
        self.file_presenter: Optional[FilePresenter] = None

        # ✅ NOUVEAU: Controller d'organisation automatique
        self.auto_organization_controller: Optional[AutoOrganizationController] = None
        # Dedup guard for noisy repeated file-list emissions.
        self._last_scan_signature: Optional[tuple] = None

    def connect_managers(
        self,
        connection_manager: ConnectionManager,
        settings_manager: SettingsManager,
        file_manager: FileManager,
        status_presenter: StatusPresenter,
        file_presenter: FilePresenter,
        auto_organization_controller: Optional[AutoOrganizationController] = None,
    ):
        """
        Connects all managers and establishes signal routes.

        Args:
            connection_manager: LLM connection manager
            settings_manager: Settings manager
            file_manager: File manager
            status_presenter: Status presenter
            file_presenter: File presenter
            auto_organization_controller: Auto organization controller (optional)
        """
        self.logger.info("Configuring signal routing with AutoOrganizationController")

        # Save references
        self.connection_manager = connection_manager
        self.settings_manager = settings_manager
        self.file_manager = file_manager
        self.status_presenter = status_presenter
        self.file_presenter = file_presenter
        self.auto_organization_controller = auto_organization_controller

        # Establish connections
        self._connect_connection_manager_signals()
        self._connect_settings_manager_signals()
        self._connect_file_manager_signals()

        # ✅ NOUVEAU: Connectr les signaux du controller d'organisation
        if self.auto_organization_controller:
            self._connect_auto_organization_controller_signals()

        self.logger.info("Signal routing configured with AutoOrganizationController")

    def _connect_connection_manager_signals(self):
        """Connects the connection manager's signals."""
        if not self.connection_manager:
            return

        self.logger.debug("Connecting ConnectionManager signals")

        # Connection tested → Status Presenter
        self.connection_manager.connection_tested.connect(
            self._on_connection_tested, Qt.ConnectionType.QueuedConnection
        )

        # Models retrieved → Status Presenter
        self.connection_manager.models_retrieved.connect(
            self._on_models_retrieved, Qt.ConnectionType.QueuedConnection
        )

        # Status updated → Status Presenter
        self.connection_manager.status_updated.connect(
            self._on_connection_status_updated, Qt.ConnectionType.QueuedConnection
        )

        # ADDITION: Connections for specific LLM statuses
        self.connection_manager.doc_llm_ready.connect(
            lambda ready, msg: self.status_presenter.update_llm_status(
                "document", ready, msg
            ),
            Qt.ConnectionType.QueuedConnection,
        )

        self.connection_manager.img_llm_ready.connect(
            lambda ready, msg: self.status_presenter.update_llm_status(
                "image", ready, msg
            ),
            Qt.ConnectionType.QueuedConnection,
        )

    def _connect_settings_manager_signals(self):
        """Connects the settings manager's signals."""
        if not self.settings_manager:
            return

        self.logger.debug("Connecting SettingsManager signals")

        # Settings updated → File Manager (to refresh filters)
        self.settings_manager.settings_updated.connect(
            self._on_settings_updated, Qt.ConnectionType.QueuedConnection
        )

        # Settings saved → Status Presenter
        self.settings_manager.settings_saved.connect(
            self._on_settings_saved, Qt.ConnectionType.QueuedConnection
        )

        # Connection test requested → Status Presenter
        self.settings_manager.test_requested.connect(
            self._on_connection_test_requested, Qt.ConnectionType.QueuedConnection
        )

    def _connect_file_manager_signals(self):
        """Connects the file manager's signals."""
        if not self.file_manager:
            return

        self.logger.debug("Connecting FileManager signals")

        # Scan started → Status Presenter
        self.file_manager.scan_started.connect(
            self._on_scan_started, Qt.ConnectionType.QueuedConnection
        )

        # Scan progress → Status Presenter
        self.file_manager.scan_progress.connect(
            self._on_scan_progress, Qt.ConnectionType.QueuedConnection
        )

        # Scan completed → File Presenter + Status Presenter
        self.file_manager.scan_completed.connect(
            self._on_scan_completed, Qt.ConnectionType.QueuedConnection
        )

        # Scan error → Status Presenter
        self.file_manager.scan_error.connect(
            self._on_scan_error, Qt.ConnectionType.QueuedConnection
        )

        # Files updated → File Presenter
        self.file_manager.files_updated.connect(
            self._on_files_updated, Qt.ConnectionType.QueuedConnection
        )

        # Filter applied → File Presenter + Status Presenter
        self.file_manager.filter_applied.connect(
            self._on_filter_applied, Qt.ConnectionType.QueuedConnection
        )
        self.file_manager.filter_failed.connect(
            self._on_filter_failed, Qt.ConnectionType.QueuedConnection
        )

        # Filter removed from chips → File Manager (to update filters)
        self.logger.debug(
            f"SIGNAL ROUTER: Checking active_filters_bar for connection. Has active_filters_bar: {hasattr(self.main_window, 'active_filters_bar')}"
        )
        if hasattr(self.main_window, "active_filters_bar"):
            self.logger.debug(
                f"SIGNAL ROUTER: active_filters_bar objectName: {self.main_window.active_filters_bar.objectName()}"
            )
            self.logger.debug(
                "SIGNAL ROUTER: Attempting to connect active_filters_bar.filter_removed to _on_filter_removed_from_chips"
            )
            self.main_window.active_filters_bar.filter_removed.connect(
                self._on_filter_removed_from_chips, Qt.ConnectionType.QueuedConnection
            )

    def _connect_auto_organization_controller_signals(self):
        """✅ NOUVEAU: Connect les signaux du controller d'organisation automatique."""
        if not self.auto_organization_controller:
            return

        self.logger.debug("Connecting AutoOrganizationController signals")

        # Organization started → Status Presenter
        self.auto_organization_controller.organization_started.connect(
            self._on_organization_started, Qt.ConnectionType.QueuedConnection
        )

        # Organization progress → Status Presenter
        self.auto_organization_controller.progress_updated.connect(
            self._on_organization_progress, Qt.ConnectionType.QueuedConnection
        )

        # File organized → Status Presenter (for logging)
        self.auto_organization_controller.file_organized.connect(
            self._on_file_organized, Qt.ConnectionType.QueuedConnection
        )

        # Organization completed → Status Presenter + File Manager (refresh)
        self.auto_organization_controller.organization_completed.connect(
            self._on_organization_completed, Qt.ConnectionType.QueuedConnection
        )

        # Organization cancelled → Status Presenter
        self.auto_organization_controller.organization_cancelled.connect(
            self._on_organization_cancelled, Qt.ConnectionType.QueuedConnection
        )

        # Organization error → Status Presenter
        self.auto_organization_controller.organization_error.connect(
            self._on_organization_error, Qt.ConnectionType.QueuedConnection
        )

        # Preview ready → Status Presenter (for logging)
        self.auto_organization_controller.preview_ready.connect(
            self._on_organization_preview_ready, Qt.ConnectionType.QueuedConnection
        )

    # =========================================================================
    # SLOTS - Handlers for received signals
    # =========================================================================

    def _on_connection_tested(self, success: bool, message: str):
        """Handler: Connection tested."""
        self._publish_event(
            EventType.CONNECTION_TESTED,
            {"success": success, "message": message},
        )
        if self.status_presenter:
            if success:
                self.status_presenter.log_message(
                    f"✅ Connection successful: {message}", "INFO"
                )
            else:
                self.status_presenter.log_message(
                    f"❌ Connection failed: {message}", "ERROR"
                )

    def _on_models_retrieved(self, models: list):
        """Handler: Models retrieved."""
        self._publish_event(
            EventType.MODELS_RETRIEVED,
            {"model_count": len(models), "models": models},
        )
        if self.status_presenter:
            self.status_presenter.log_message(
                f"📋 {len(models)} models available", "INFO"
            )
            self.status_presenter.update_model_count(len(models))

    def _on_connection_status_updated(self, status_type: str, message: str):
        """Handler: Connection status updated."""
        self._publish_event(
            EventType.CONNECTION_STATUS_UPDATED,
            {"status_type": status_type, "message": message},
        )
        if self.status_presenter:
            is_connected = status_type in {"connected", "connectd"}
            self.status_presenter.update_connection_status(
                message, is_connected=is_connected
            )
            # Route according to status type
            if status_type == "error":
                self.status_presenter.log_message(f"❌ {message}", "ERROR")
            elif status_type == "connection":
                self.status_presenter.log_message(f"🔗 {message}", "INFO")
            else:
                self.status_presenter.log_message(message, "DEBUG")

    def _on_settings_updated(self, settings: dict):
        """Handler: Settings updated."""
        self._publish_event(EventType.SETTINGS_UPDATED, {"settings": settings})
        if self.status_presenter:
            self.status_presenter.log_message("⚙️ Settings updated", "INFO")

        # Notify the file manager to update filters
        if self.file_manager:
            # The file manager may need to reload allowed extensions
            self.file_manager.refresh_file_list()

    def _on_settings_saved(self):
        """Handler: Settings saved."""
        self._publish_event(EventType.SETTINGS_SAVED, {})
        if self.status_presenter:
            self.status_presenter.log_message("💾 Settings saved", "INFO")

        # ADDITION: Trigger an automatic connection test
        if self.connection_manager:
            self.connection_manager.test_llm_connections()

    def _on_connection_test_requested(self, api_url: str):
        """Handler: Connection test requested."""
        if self.status_presenter:
            self.status_presenter.log_message(f"🔍 Connection test: {api_url}", "INFO")

    def _on_scan_started(self, directory: str):
        """Handler: Scan started."""
        self._publish_event(EventType.SCAN_STARTED, {"directory": directory})
        if self.status_presenter:
            self.status_presenter.log_message(f"🔍 Scan started: {directory}", "INFO")
            self.status_presenter.show_scan_progress(True)

    def _on_scan_progress(self, progress_info):
        """Handler: Scan progress."""
        self._publish_event(EventType.SCAN_PROGRESS, {"progress_info": progress_info})
        if self.status_presenter:
            # Extract progress information based on object type
            if hasattr(progress_info, "files_processed"):
                processed = int(getattr(progress_info, "files_processed", 0))
                total = int(
                    getattr(progress_info, "estimated_total_files", 0)
                    or getattr(progress_info, "files_found", 0)
                    or getattr(progress_info, "total_files_scanned", 0)
                )
                percentage = (processed / total * 100.0) if total > 0 else 0.0

                self.status_presenter.update_scan_progress(processed, total, percentage)
            else:
                # Fallback if the object does not have the expected structure
                self.status_presenter.log_message("📊 Scan in progress...", "DEBUG")

    def _on_scan_completed(self, file_list: list):
        """Handler: Scan completed."""
        signature = self._build_file_list_signature(file_list)
        if signature == self._last_scan_signature:
            self.logger.debug(
                "Ignoring duplicate scan_completed event with identical file list"
            )
            return
        self._last_scan_signature = signature

        self._publish_event(
            EventType.SCAN_COMPLETED,
            {"file_count": len(file_list), "file_list": file_list},
        )
        if self.status_presenter:
            self.status_presenter.log_message(
                f"✅ Scan completed: {len(file_list)} files found", "INFO"
            )
            self.status_presenter.show_scan_progress(False)
            self.status_presenter.update_file_count(len(file_list))

        # Notify the file presenter to update the display
        if self.file_presenter:
            self.file_presenter.update_file_list(file_list)

    def _on_scan_error(self, error_message: str):
        """Handler: Scan error."""
        self._publish_event(EventType.SCAN_ERROR, {"error_message": error_message})
        if self.status_presenter:
            self.status_presenter.log_message(
                f"❌ Scan error: {error_message}", "ERROR"
            )
            self.status_presenter.show_scan_progress(False)

    def _on_files_updated(self, file_list: list):
        """Handler: File list updated."""
        self._publish_event(
            EventType.FILES_UPDATED,
            {"file_count": len(file_list), "file_list": file_list},
        )
        if self.file_presenter:
            self.file_presenter.update_file_list(file_list)

        if self.status_presenter:
            self.status_presenter.update_file_count(len(file_list))

    @staticmethod
    def _build_file_list_signature(file_list: list) -> tuple:
        """
        Build a compact signature for deduplicating repeated file-list events.
        """
        if not file_list:
            return (0, "", "")
        first = (
            file_list[0][0]
            if isinstance(file_list[0], (tuple, list)) and file_list[0]
            else str(file_list[0])
        )
        last = (
            file_list[-1][0]
            if isinstance(file_list[-1], (tuple, list)) and file_list[-1]
            else str(file_list[-1])
        )
        return (len(file_list), first, last)

    def _on_filter_applied(self, active_filters: dict[str, Any], filtered_files: list):
        """
        Handler: Filter applied.

        CORRECTED: For multi-selection filters, update file list directly instead of re-filtering.
        """
        self.logger.debug(
            f"🔍 SIGNAL ROUTER: Received filter_applied - active_filters: {active_filters}, files: {len(filtered_files)}"
        )
        self._publish_event(
            EventType.FILTER_APPLIED,
            {
                "active_filters": active_filters,
                "filtered_count": len(filtered_files),
                "filtered_files": filtered_files,
            },
        )

        try:
            if self.file_presenter:
                # Always update the file list with the pre-filtered results from FileManager
                self.file_presenter.update_file_list(filtered_files)

                # Prepare filter data for display in the UI (e.g., filter chips)
                # The file_presenter.update_filter_chips method expects a dictionary of active filters
                self.logger.debug(
                    f"🔍 SIGNAL ROUTER: Calling update_filter_chips with: {active_filters}"
                )
                self.file_presenter.update_filter_chips(active_filters)

            if self.status_presenter:
                # Extract display name for status
                display_name = "Custom Filter"
                if "file_type" in active_filters and active_filters["file_type"]:
                    display_name = active_filters["file_type"][0]
                elif "category" in active_filters and active_filters["category"]:
                    display_name = (
                        f"Categories: {', '.join(active_filters['category'])}"
                    )
                elif "year" in active_filters and active_filters["year"]:
                    display_name = (
                        f"Years: {', '.join(map(str, active_filters['year']))}"
                    )
                elif "extension" in active_filters and active_filters["extension"]:
                    display_name = (
                        f"Extensions: {', '.join(active_filters['extension'])}"
                    )

                self.status_presenter.log_message(
                    f"🔍 Filter '{display_name}': {len(filtered_files)} files displayed",
                    "DEBUG",
                )
                self.status_presenter.update_filtered_count(len(filtered_files))

        except Exception as e:
            self.logger.error(f"❌ Error in _on_filter_applied: {e}", exc_info=True)
            if self.status_presenter:
                self.status_presenter.log_message(f"❌ Filter error: {e}", "ERROR")

    def _on_filter_failed(
        self,
        code: str,
        error_message: str,
        active_filters: dict[str, Any],
    ):
        """Handler: filter application failed."""
        normalized_code = str(code or FileOperationCode.UNKNOWN_ERROR.value).lower()
        self._publish_event(
            EventType.FILTER_ERROR,
            {
                "code": normalized_code,
                "error_message": error_message,
                "active_filters": active_filters,
            },
        )

        if not self.status_presenter:
            return

        level, status_message, log_message = self._build_filter_failure_notification(
            normalized_code=normalized_code,
            error_message=error_message,
        )
        self.status_presenter.update_status(status_message, is_busy=False)
        self.status_presenter.log_message(log_message, level)

    def _build_filter_failure_notification(
        self,
        normalized_code: str,
        error_message: str,
    ) -> tuple[str, str, str]:
        """Build a user-facing, category-aware filter failure notification."""
        reason = str(error_message or "").strip() or "No details provided."

        if normalized_code == FileOperationCode.VALIDATION_ERROR.value:
            return (
                "WARNING",
                tr(
                    "filter.error.validation.status",
                    "Filter not applied: invalid filter value",
                ),
                tr(
                    "filter.error.validation.log",
                    "⚠️ Filter validation error: {reason}",
                    reason=reason,
                ),
            )
        if normalized_code == FileOperationCode.UNKNOWN_FILTER.value:
            return (
                "WARNING",
                tr(
                    "filter.error.unknown_filter.status",
                    "Filter not applied: unsupported filter",
                ),
                tr(
                    "filter.error.unknown_filter.log",
                    "⚠️ Unknown filter type: {reason}",
                    reason=reason,
                ),
            )
        if normalized_code == FileOperationCode.DATABASE_ERROR.value:
            return (
                "ERROR",
                tr(
                    "filter.error.database.status",
                    "Filter not applied: database unavailable",
                ),
                tr(
                    "filter.error.database.log",
                    "❌ Database error while applying filters: {reason}",
                    reason=reason,
                ),
            )
        return (
            "ERROR",
            tr(
                "filter.error.unknown.status",
                "Filter not applied: unexpected error",
            ),
            tr(
                "filter.error.unknown.log",
                "❌ Unexpected filter error: {reason}",
                reason=reason,
            ),
        )

    # =========================================================================
    # ✅ NOUVEAUX SLOTS POUR AUTO-ORGANIZATION CONTROLLER
    # =========================================================================

    def _on_organization_started(self):
        """Handler: Organization started."""
        self._publish_event(EventType.ORGANIZATION_STARTED, {})
        if self.status_presenter:
            self.status_presenter.log_message("📁 Auto-organization started", "INFO")
            self.status_presenter.show_organization_progress(True)

    def _on_organization_progress(self, processed: int, total: int):
        """Handler: Organization progress updated."""
        self._publish_event(
            EventType.ORGANIZATION_PROGRESS,
            {"processed": processed, "total": total},
        )
        if self.status_presenter:
            percentage = int((processed / total) * 100) if total > 0 else 0
            self.status_presenter.update_organization_progress(
                processed, total, percentage
            )
            self.status_presenter.log_message(
                f"📊 Organization progress: {processed}/{total} files ({percentage}%)",
                "DEBUG",
            )

    def _on_file_organized(self, source: str, target: str, action: str):
        """Handler: File organized."""
        if self.status_presenter:
            import os

            filename = os.path.basename(source)
            self.status_presenter.log_message(
                f"📁 {action.title()}: {filename} → {os.path.basename(target)}", "DEBUG"
            )

    def _on_organization_completed(self, stats: dict):
        """Handler: Organization completed."""
        self._publish_event(EventType.ORGANIZATION_COMPLETED, {"stats": stats})
        if self.status_presenter:
            successful = stats.get("successful", 0)
            total = stats.get("total_files", 0)
            success_rate = stats.get("success_rate", 0)
            target_dir = stats.get("target_directory", "")

            self.status_presenter.log_message(
                f"✅ Organization completed: {successful}/{total} files ({success_rate:.1f}% success)",
                "INFO",
            )
            self.status_presenter.show_organization_progress(False)

            if target_dir:
                self.status_presenter.log_message(
                    f"📁 Files organized in: {target_dir}", "INFO"
                )

        # Optional: Refresh file list if needed
        if self.file_manager and stats.get("refresh_needed", False):
            self.file_manager.refresh_file_list()

    def _on_organization_cancelled(self):
        """Handler: Organization cancelled."""
        self._publish_event(EventType.ORGANIZATION_CANCELLED, {})
        if self.status_presenter:
            self.status_presenter.log_message(
                "❌ Organization cancelled by user", "INFO"
            )
            self.status_presenter.show_organization_progress(False)

    def _on_organization_error(self, error_message: str):
        """Handler: Organization error."""
        self._publish_event(
            EventType.ORGANIZATION_ERROR, {"error_message": error_message}
        )
        if self.status_presenter:
            self.status_presenter.log_message(
                f"❌ Organization error: {error_message}", "ERROR"
            )
            self.status_presenter.show_organization_progress(False)

    def _on_organization_preview_ready(self, preview: dict):
        """Handler: Organization preview ready."""
        self._publish_event(EventType.ORGANIZATION_PREVIEW_READY, {"preview": preview})
        if self.status_presenter:
            if "error" in preview:
                self.status_presenter.log_message(
                    f"❌ Preview error: {preview['error']}", "ERROR"
                )
            else:
                file_count = preview.get("file_count", 0)
                folder_count = len(preview.get("structure", {}))
                conflicts = len(preview.get("conflicts", []))

                self.status_presenter.log_message(
                    f"👁️ Preview ready: {file_count} files, {folder_count} folders, {conflicts} conflicts",
                    "DEBUG",
                )

    def _on_filter_removed_from_chips(self, filter_type: str, filter_value: Any):
        """
        Handler for when a filter chip is removed directly from the UI.
        Notifies the FileManager to update its filter state.
        """
        self.logger.debug(
            f"SIGNAL ROUTER: _on_filter_removed_from_chips received: {filter_type}, {filter_value}"
        )
        if self.file_manager:
            # Reconstruct filter_id for FileManager
            filter_id = f"{filter_type}_{filter_value}"
            self.file_manager.remove_filter_by_id(filter_id)

    def _publish_event(self, event_type: EventType, payload: dict[str, Any]):
        """Publishes a normalized event to the optional event bus."""
        if self.event_bus:
            self.event_bus.publish(
                event_type=event_type,
                payload=payload,
                source="SignalRouter",
            )

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def disconnect_all(self):
        """Disconnects all signals."""
        self.logger.info("Disconnecting all signals")

        try:
            if self.connection_manager:
                self.connection_manager.connection_tested.disconnect()
                self.connection_manager.models_retrieved.disconnect()
                self.connection_manager.status_updated.disconnect()

            if self.settings_manager:
                self.settings_manager.settings_updated.disconnect()
                self.settings_manager.settings_saved.disconnect()
                self.settings_manager.test_requested.disconnect()

            if self.file_manager:
                self.file_manager.scan_started.disconnect()
                self.file_manager.scan_progress.disconnect()
                self.file_manager.scan_completed.disconnect()
                self.file_manager.scan_error.disconnect()
                self.file_manager.files_updated.disconnect()
                self.file_manager.filter_applied.disconnect()
                self.file_manager.filter_failed.disconnect()
                if hasattr(self.main_window, "active_filters_bar"):
                    self.main_window.active_filters_bar.filter_removed.disconnect()

            # ✅ NEW: Disconnect organization controller signals
            if self.auto_organization_controller:
                self.auto_organization_controller.organization_started.disconnect()
                self.auto_organization_controller.progress_updated.disconnect()
                self.auto_organization_controller.file_organized.disconnect()
                self.auto_organization_controller.organization_completed.disconnect()
                self.auto_organization_controller.organization_cancelled.disconnect()
                self.auto_organization_controller.organization_error.disconnect()
                self.auto_organization_controller.preview_ready.disconnect()

        except Exception as e:
            self.logger.warning(f"Error during disconnection: {e}")
