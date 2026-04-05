# views/managers/file_manager.py
"""
File Manager - Qt interface for file operations.

This manager bridges the Qt user interface and the pure business service.
It contains ONLY interface logic and delegates all business logic to the service.

ENHANCED VERSION: Now supports multi-selection filters and improved error handling.
"""

import os
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from ai_content_classifier.core.logger import get_logger
from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
from ai_content_classifier.services.config_service import ConfigService
from ai_content_classifier.services.content_database_service import (
    ContentDatabaseService,
)
from ai_content_classifier.services.file.file_operation_service import (
    FileOperationService,
    FileProcessingResult,
    FilterType,
    ScanStatistics,
)
from ai_content_classifier.services.metadata.metadata_service import MetadataService
from ai_content_classifier.views.widgets.dialogs import ScanProgressDialog
from ai_content_classifier.views.widgets.common.operation_state import (
    OperationDetail,
    OperationStat,
    OperationViewState,
)
from ai_content_classifier.views.workers.scan_worker import ScanWorker
from ai_content_classifier.views.workers.scan_ui_refresh_worker import (
    ScanUiRefreshWorker,
)

from ai_content_classifier.services.thumbnail.thumbnail_service import ThumbnailService


class FileManager(QObject):
    """
    Enhanced Qt manager for file operations.

    This manager interfaces between Qt and the pure business service.
    It only:
    - Manages PyQt signals
    - Orchestrates Qt workers and threads
    - Displays progress dialogs
    - Converts service callbacks to Qt signals

    ENHANCED: Now supports multi-selection filters and robust error handling.
    """

    # Signals emitted by the manager (Qt interface)
    scan_started = pyqtSignal(str)  # Scanned directory
    scan_progress = pyqtSignal(object)  # Scan progress
    scan_completed = pyqtSignal(list)  # List of found files
    scan_error = pyqtSignal(str)  # Scan error
    files_updated = pyqtSignal(list)  # Updated file list
    filter_applied = pyqtSignal(
        object, list
    )  # Filter applied (filter_type, filtered_files)
    file_processed = pyqtSignal(
        str, bool, bool
    )  # (file_path, metadata_ok, thumbnail_ok)
    processing_stats = pyqtSignal(dict)  # Processing statistics

    def __init__(
        self,
        db_service: ContentDatabaseService,
        config_service: ConfigService,
        metadata_service: Optional[MetadataService] = None,
        thumbnail_service: Optional[ThumbnailService] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.logger = get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        # Store services for worker creation
        self.db_service = db_service
        self.config_service = config_service
        self.metadata_service = metadata_service
        self.thumbnail_service = thumbnail_service

        # Pure business service (without Qt)
        self.file_service = FileOperationService(
            db_service=db_service,
            config_service=config_service,
            metadata_service=metadata_service,
            thumbnail_service=thumbnail_service,
        )

        # Initialize state variables
        self.is_scan_active = False
        self.should_cancel_scan = False
        self.scan_worker = None
        self.worker_thread = None
        self.current_scan_config = self._get_default_scan_config()
        self.last_scan_results = {}

        # Centralized filter state
        self._active_filters: Dict[str, List[Any]] = {
            "file_type": [],
            "category": [],
            "year": [],
            "extension": [],
        }
        self._is_applying_filter_internally = False  # New flag to prevent infinite loop

        # Specific Qt state
        self.scan_progress_dialog: Optional[ScanProgressDialog] = None
        self.scan_ui_refresh_worker: Optional[ScanUiRefreshWorker] = None
        self.main_window = None
        self._scan_operation_log: List[str] = []
        self._scan_operation_snapshot: Dict[str, Any] = {}
        self._scan_operation_started_at: float | None = None
        self._scan_operation_refresh_timer = QTimer(self)
        self._scan_operation_refresh_timer.setInterval(1000)
        self._scan_operation_refresh_timer.timeout.connect(
            self._refresh_scan_operation_state
        )

        # Service callback configuration
        self._setup_service_callbacks()

        self.logger.info(
            "Enhanced Qt FileManager initialized with multi-filter support"
        )

    def bind_main_window(self, main_window) -> None:
        """Attaches the main window so Operations can replace progress popups."""
        self.main_window = main_window

    def _normalize_file_type_filter_value(self, value: Any) -> Any:
        """Map UI-friendly file type labels to canonical FilterType values."""
        if not isinstance(value, str):
            return value

        normalized = value.strip().lower()
        aliases = {
            "all": FilterType.ALL_FILES.value,
            "all files": FilterType.ALL_FILES.value,
            "image": FilterType.IMAGES.value,
            "images": FilterType.IMAGES.value,
            "document": FilterType.DOCUMENTS.value,
            "documents": FilterType.DOCUMENTS.value,
            "video": FilterType.VIDEOS.value,
            "videos": FilterType.VIDEOS.value,
            "audio": FilterType.AUDIO.value,
            "archives": FilterType.ARCHIVES.value,
            "archive": FilterType.ARCHIVES.value,
            "code": FilterType.CODE.value,
            "other": FilterType.OTHER.value,
            "others": FilterType.OTHER.value,
            "uncategorized": FilterType.UNCATEGORIZED.value,
        }
        return aliases.get(normalized, value)

    def _setup_service_callbacks(self):
        """Configures callbacks to convert service events to Qt signals."""
        try:
            self.file_service.set_callbacks(
                on_scan_started=self._on_service_scan_started,
                on_scan_progress=self._on_service_scan_progress,
                on_scan_completed=self._on_service_scan_completed,
                on_scan_error=self._on_service_scan_error,
                on_file_processed=self._on_service_file_processed,
                on_files_updated=self._on_service_files_updated,
                on_filter_applied=self._on_service_filter_applied,
                on_stats_updated=self._on_service_stats_updated,
            )
        except Exception as e:
            self.logger.warning(f"Could not set all service callbacks: {e}")

    # === SERVICE CALLBACKS (convert to Qt signals) ===

    def _on_service_scan_started(self, directory: str):
        """Callback called when the service starts a scan."""
        self.scan_started.emit(directory)

    def _on_service_scan_progress(self, progress):
        """Callback called for scan progress."""
        self.scan_progress.emit(progress)

    def _on_service_scan_completed(self, file_list: List[Tuple[str, str, str]]):
        """Callback called when the scan is complete."""
        self.scan_completed.emit(file_list)

    def _on_service_scan_error(self, error_message: str):
        """Callback called on scan error."""
        self.scan_error.emit(error_message)

    def _on_service_file_processed(self, result: FileProcessingResult):
        """Callback called when a file is processed."""
        self.file_processed.emit(
            result.file_path, result.metadata_extracted, result.thumbnail_generated
        )

    def _on_service_files_updated(self, file_list: List[Tuple[str, str, str]]):
        """Callback called when the file list is updated."""
        # When cumulative filtering is running, suppress raw list emission.
        # The filtered result will be emitted at the end of _apply_cumulative_filters.
        if self._is_applying_filter_internally:
            return

        if self._has_active_filters() and not self._is_applying_filter_internally:
            filtered_files = self._apply_filters_to_file_list(file_list)
            self.files_updated.emit(filtered_files)
            self.filter_applied.emit(self._active_filters, filtered_files)
            return
        self.files_updated.emit(file_list)

    def _on_service_filter_applied(
        self, filter_type: FilterType, filtered_files: List[Tuple[str, str]]
    ):
        """Callback called when a filter is applied."""
        # Emit the current active filters and the filtered files
        self.filter_applied.emit(self._active_filters, filtered_files)

    def _on_service_stats_updated(self, stats: ScanStatistics):
        """Callback called when statistics are updated."""
        stats_dict = {
            "files_found": stats.files_found,
            "metadata_extracted": stats.metadata_extracted,
            "thumbnails_generated": stats.thumbnails_generated,
            "errors": stats.errors,
            "processing_time": stats.processing_time,
            "directory_scanned": stats.directory_scanned,
        }
        self.processing_stats.emit(stats_dict)

    # === PUBLIC INTERFACE (delegates to service) ===

    def start_scan(self, directory: str, scan_config: dict = None):
        """
        Starts scanning a directory with optional configuration.

        Args:
            directory: Directory to scan
            scan_config: Optional scan configuration
        """
        if self.is_scan_active:
            self.logger.warning("Scan already in progress, ignoring new request")
            return

        self.logger.info(f"Starting scan: {directory}")

        # Store configuration for use during scan
        self.current_scan_config = scan_config or self._get_default_scan_config()
        self.current_scan_config["directory"] = directory

        self.logger.debug(f"Using scan config: {self.current_scan_config}")

        # Validate configuration
        if not self._validate_scan_config(self.current_scan_config):
            self.logger.error("Invalid scan configuration")
            return

        # Log scan config for debugging
        self._log_scan_config(self.current_scan_config)

        try:
            # Set scan state
            self.is_scan_active = True
            self.should_cancel_scan = False

            # Emit scan started signal
            self.scan_started.emit(directory)

            # Clean up any existing worker and thread
            self._cleanup_worker_and_thread()

            self._create_scan_progress_dialog(directory)
            self._scan_operation_log = []
            self._scan_operation_started_at = time.time()
            self._scan_operation_snapshot = {
                "files_found": 0,
                "files_processed": 0,
                "total_files_scanned": 0,
                "scan_root_directory": directory,
                "current_directory": directory,
                "current_file": "",
                "scan_speed": 0.0,
                "estimated_total": 0,
                "errors": 0,
            }
            self._configure_scan_operation_surface(directory)
            self._scan_operation_refresh_timer.start()

            # Start dedicated background UI refresh worker.
            self._start_scan_ui_refresh_worker()

            self._create_scan_runtime(directory)

            # Connect thread and worker signals
            self._connect_worker_signals()

            # Start the thread
            self.worker_thread.start()

        except Exception as e:
            self.logger.error(f"Error starting scan: {e}")
            self.is_scan_active = False
            self.scan_error.emit(str(e))

    def _create_scan_progress_dialog(self, directory: str) -> None:
        """Creates and shows the scan progress dialog."""
        if self.main_window is not None:
            self.scan_progress_dialog = None
            return

        self.scan_progress_dialog = ScanProgressDialog()
        self.scan_progress_dialog.setModal(False)
        self.scan_progress_dialog.start_scan(directory=directory, estimated_files=0)
        self.scan_progress_dialog.show()

    def _configure_scan_operation_surface(self, directory: str) -> None:
        """Initializes the integrated Operations panel for scans."""
        if not self.main_window:
            return

        if hasattr(self.main_window, "set_operation_action_handlers"):
            self.main_window.set_operation_action_handlers(
                {
                    "cancel": self.cancel_current_scan,
                    "close": self._dismiss_operation_surface,
                }
            )

        self._push_scan_operation_state(
            state="discovering",
            current_directory=directory,
        )

    def _create_scan_runtime(self, directory: str) -> None:
        """Creates the worker/thread pair for a new scan session."""
        self.worker_thread = QThread()
        self.scan_worker = ScanWorker(
            directory=directory,
            db_service=self.db_service,
            config_service=self.config_service,
            scan_config=self.current_scan_config,
            metadata_service=self.metadata_service,
            thumbnail_service=self.thumbnail_service,
        )
        self.scan_worker.moveToThread(self.worker_thread)

    def _cleanup_worker_and_thread(self):
        """Cleans up existing worker and thread."""
        if self.scan_worker:
            self.scan_worker = None

        if self.worker_thread:
            if self.worker_thread.isRunning():
                self.worker_thread.quit()
                if not self.worker_thread.wait(5000):  # Wait 5 seconds
                    self.worker_thread.terminate()
                    self.worker_thread.wait()
            self.worker_thread = None

    def _connect_worker_signals(self):
        """Connects all worker and thread signals."""
        self.logger.info("🔗 Connecting scan worker signals...")

        # Thread management
        self.worker_thread.started.connect(self.scan_worker.run)
        self.scan_worker.finished.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self._on_thread_finished)

        # Worker signals
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.error.connect(self._on_scan_error)
        self.scan_worker.result.connect(self._on_scan_completed)
        self.scan_worker.progress_updated.connect(self._on_scan_progress)
        self.scan_worker.progress_text.connect(self._on_scan_status)
        self.scan_worker.file_processed.connect(self._on_file_processed)

        # If we have a file_found signal, connect it too
        if hasattr(self.scan_worker, "file_found"):
            self.scan_worker.file_found.connect(self._on_file_found)

        # Connect progress dialog if it exists
        self._connect_progress_dialog_signals()

        self.logger.info("✅ Scan worker signals connectd")

    def _get_default_scan_config(self) -> dict:
        """Returns default scan configuration for backward compatibility."""
        return {
            "directory": "",
            "file_types": {
                "documents": True,
                "images": True,
                "videos": False,
                "audio": False,
                "others": False,
            },
            "custom_extensions": [],
            "min_size_kb": 0,
            "max_size_kb": 1_024_000,
            "skip_hidden": True,
            "extract_metadata": True,
            "deep_metadata": False,
            "cache_metadata": True,
            "generate_thumbnails": True,
            "thumbnail_size": "256x256",
            "thumbnail_quality": 85,
            "worker_threads": 4,
            "batch_size": 100,
            "pause_batches": False,
            "auto_categorize": False,
            "categorization_model": "Auto (Recommended)",
            "confidence_threshold": 0.7,
            "categories": [],
            "auto_organize": False,
            "organization_action": "copy",
            "organization_structure": "By Category",
            "target_directory": "",
            "ai_processing": False,
            "preview_mode": False,
        }

    def _validate_scan_config(self, config: dict) -> bool:
        """Validates scan configuration."""
        try:
            # Check required fields
            directory = config.get("directory", "")
            if not directory:
                self.logger.error("No directory specified in scan config")
                return False

            # Check directory exists and is readable
            if not os.path.exists(directory):
                self.logger.error(f"Directory does not exist: {directory}")
                return False

            if not os.access(directory, os.R_OK):
                self.logger.error(f"Cannot read directory: {directory}")
                return False

            # Check file types
            file_types = config.get("file_types", {})
            if not any(file_types.values()):
                self.logger.warning("No file types selected - will scan all files")

            # Validate auto-organization config
            if config.get("auto_organize", False):
                target_dir = config.get("target_directory")
                if not target_dir:
                    self.logger.error(
                        "Auto-organization enabled but no target directory"
                    )
                    return False

                if target_dir == directory:
                    self.logger.error("Target directory cannot be same as source")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating scan config: {e}")
            return False

    def _log_scan_config(self, config: dict):
        """Logs scan configuration for debugging."""
        self.logger.debug("=== ENHANCED SCAN CONFIGURATION ===")
        self.logger.debug(f"📁 Directory: {config.get('directory')}")

        # File types
        file_types = config.get("file_types", {})
        enabled_types = [k for k, v in file_types.items() if v]
        self.logger.debug(
            f"📋 File Types: {', '.join(enabled_types) if enabled_types else 'All'}"
        )

        # Size filters
        # Prefer KB-based settings; keep backward compatibility with MB configs.
        min_size = config.get("min_size_kb")
        max_size = config.get("max_size_kb")
        if min_size is None:
            min_size = int(config.get("min_size_mb", 0) * 1024)
        if max_size is None:
            max_size = int(config.get("max_size_mb", 1000) * 1024)
        self.logger.debug(f"📏 Size Range: {min_size}-{max_size} KB")

        # Processing options
        processing = []
        if config.get("extract_metadata", False):
            processing.append("Metadata")
        if config.get("generate_thumbnails", False):
            processing.append("Thumbnails")
        self.logger.debug(
            f"⚙️ Processing: {', '.join(processing) if processing else 'None'}"
        )

        # AI features
        ai_features = []
        if config.get("auto_categorize", False):
            ai_features.append("Categorization")
        if config.get("auto_organize", False):
            ai_features.append("Organization")
        self.logger.debug(
            f"🤖 AI Features: {', '.join(ai_features) if ai_features else 'None'}"
        )

        # Performance
        threads = config.get("worker_threads", 4)
        batch_size = config.get("batch_size", 100)
        self.logger.debug(f"⚡ Performance: {threads} threads, {batch_size} batch size")

        self.logger.debug("==================================")

    def _connect_progress_dialog_signals(self):
        """Connects the progress dialog's signals."""
        if self.scan_progress_dialog and self.scan_worker:
            self.scan_worker.progress_updated.connect(
                self.scan_progress_dialog.update_progress
            )
            self.scan_worker.progress_text.connect(
                self.scan_progress_dialog.add_log_message
            )
            self.scan_progress_dialog.cancel_requested.connect(self.cancel_current_scan)

    # === WORKER SIGNAL HANDLERS ===

    def _on_scan_progress(self, progress):
        """Handles scan progress."""
        self.scan_progress.emit(progress)
        self._push_scan_operation_state(progress=progress)

    def _on_scan_status(self, status_message: str):
        """Handles scan status messages."""
        self.logger.debug(f"Scan status: {status_message}")
        self._append_scan_operation_log(status_message)

    def _on_file_found(self, file_path: str, directory: str):
        """Handles when a file is found during scanning."""
        self.logger.debug(f"File found: {os.path.basename(file_path)}")

    def _on_scan_completed(self, file_list: List[Tuple[str, str]]):
        """Handles scan completion."""
        try:
            self.logger.info(f"📥 Scan completed: {len(file_list)} files")

            # Store results
            self.last_scan_results = {
                "files": file_list,
                "scan_duration": 0,  # Could be calculated from timestamps
                "processing_duration": 0,
            }

            # Emit the completion signal
            self.scan_completed.emit(file_list)
            self.files_updated.emit(file_list)  # ✅ NEW: Ensure the UI is notified

            if self.scan_progress_dialog:
                self.scan_progress_dialog.on_scan_finished(
                    success=True,
                    final_stats={"files_found": len(file_list)},
                )
            self._push_scan_operation_state(
                state="completed",
                progress={
                    "files_found": len(file_list),
                    "files_processed": len(file_list),
                    "total_files_scanned": len(file_list),
                    "estimated_total": len(file_list),
                },
            )
            self._scan_operation_refresh_timer.stop()
            self._stop_scan_ui_refresh_worker()

            # Delegate to service for processing if it supports it
            if hasattr(self.file_service, "process_scan_results"):
                self.file_service.process_scan_results(file_list)

            # Rebuild the visible dataset from the persisted source of truth after
            # the scan pipeline updated the database/service state.
            refreshed_files = self.refresh_file_list()
            if refreshed_files:
                self.logger.info(
                    f"🔄 UI refreshed after scan with {len(refreshed_files)} files"
                )
                self.files_updated.emit(refreshed_files)

            # Handle post-scan AI processing if enabled
            self._handle_post_scan_ai_processing(file_list, self.current_scan_config)

        except Exception as e:
            error_msg = f"Scan completion error: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.scan_error.emit(error_msg)

    def _on_scan_error(self, error_info):
        """Handles scan errors."""
        try:
            if isinstance(error_info, tuple) and len(error_info) > 0:
                error = error_info[0]
                error_message = f"Scan error: {str(error)}"
            else:
                error_message = f"Scan error: {str(error_info)}"

            self.logger.error(error_message)
            self.scan_error.emit(error_message)

            if self.scan_progress_dialog:
                self.scan_progress_dialog.on_scan_finished(success=False)
            self._push_scan_operation_state(state="failed")
            self._scan_operation_refresh_timer.stop()
            self._stop_scan_ui_refresh_worker()

            # Reset scan state
            self.is_scan_active = False

        except Exception as e:
            self.logger.error(f"Error handling error: {e}")

    def _on_scan_finished(self):
        """Handles scan worker completion."""
        self.logger.debug("Scan worker finished")

        # The thread will handle cleanup through _on_thread_finished

    def _on_thread_finished(self):
        """Handles thread completion."""
        self.logger.debug("Scan thread finished")

        # Reset scan state
        self.is_scan_active = False

        # Close progress dialog if open
        if self.scan_progress_dialog:
            self.scan_progress_dialog.accept()
            self.scan_progress_dialog = None

        self._scan_operation_refresh_timer.stop()
        self._stop_scan_ui_refresh_worker()

        # Clean up worker and thread
        self._cleanup_worker_and_thread()

    def _on_file_processed(self, file_path: str, metadata_ok: bool, thumbnail_ok: bool):
        """Handles individual file processing."""
        # Emit signal and delegate to service if it supports it
        self.file_processed.emit(file_path, metadata_ok, thumbnail_ok)

        if hasattr(self.file_service, "process_file_result"):
            self.file_service.process_file_result(file_path, metadata_ok, thumbnail_ok)

    def _start_scan_ui_refresh_worker(self):
        """Starts the dedicated UI refresh worker for scan snapshots."""
        self._stop_scan_ui_refresh_worker()
        self.scan_ui_refresh_worker = ScanUiRefreshWorker(
            db_service=self.db_service,
            poll_interval_sec=3.0,
            parent=self,
        )
        self.scan_ui_refresh_worker.snapshot_ready.connect(self._on_scan_ui_snapshot)
        self.scan_ui_refresh_worker.refresh_error.connect(
            self._on_scan_ui_refresh_error
        )
        self.scan_ui_refresh_worker.start()

    def _stop_scan_ui_refresh_worker(self):
        """Stops and cleans up the scan UI refresh worker."""
        if not self.scan_ui_refresh_worker:
            return
        try:
            self.scan_ui_refresh_worker.stop()
            self.scan_ui_refresh_worker.wait(1500)
            if self.scan_ui_refresh_worker.isRunning():
                self.scan_ui_refresh_worker.terminate()
                self.scan_ui_refresh_worker.wait(500)
        except Exception as e:
            self.logger.debug(f"Error stopping scan UI refresh worker: {e}")
        finally:
            self.scan_ui_refresh_worker = None

    def _on_scan_ui_snapshot(self, file_list: List[Tuple[str, str]], total_count: int):
        """Applies background snapshots to UI with minimal main-thread work."""
        if not self.is_scan_active:
            return

        if self._has_active_filters():
            filtered_files = self._apply_filters_to_file_list(file_list)
            self.files_updated.emit(filtered_files)
            self.filter_applied.emit(self._active_filters, filtered_files)
            return

        self.files_updated.emit(file_list)
        self.logger.debug(f"Scan UI snapshot applied: {total_count} items")

    def _on_scan_ui_refresh_error(self, error_message: str):
        """Logs non-fatal UI refresh worker errors."""
        self.logger.debug(f"Scan UI refresh worker error: {error_message}")

    def _refresh_scan_operation_state(self) -> None:
        """Refreshes integrated operation details such as elapsed time."""
        if not self.is_scan_active:
            self._scan_operation_refresh_timer.stop()
            return
        self._push_scan_operation_state()

    def _handle_post_scan_ai_processing(self, file_list: list, config: dict):
        """Handles AI processing after scan completion."""
        if not config.get("ai_processing", False):
            self.logger.debug("AI processing disabled, skipping")
            return

        # Event-driven pipeline is now orchestrated from MainView.
        self.logger.debug(
            "Post-scan AI processing delegated to EventBus pipeline in MainView"
        )

    def get_current_scan_config(self) -> dict:
        """Returns the current scan configuration."""
        return self.current_scan_config

    # === ENHANCED FILTERING SYSTEM ===

    def apply_filter(
        self, filter_data: Union[str, Dict[str, Any]]
    ) -> List[Tuple[str, str]]:
        """
        Enhanced filter application that handles both simple and multi-selection filters.

        Args:
            filter_data: Filter data (dict or string for backward compatibility)
                        Examples:
                        - 'Images' (backward compatibility)
                        - {'type': 'file_type', 'value': 'Images'}
                        - {'type': 'category', 'value': ['Sports', 'Travel']}
                        - {'type': 'year', 'value': [2023, 2024]}
                        - {'type': 'extension', 'value': ['.jpg', '.png']}

        Returns:
            List of filtered files
        """
        self.logger.debug(f"🔍 FileManager.apply_filter: {filter_data}")

        try:
            # Normalize input to dict format
            if isinstance(filter_data, str):
                # For backward compatibility, assume it's a file_type filter
                filter_data = {"type": "file_type", "value": filter_data}
            elif not isinstance(filter_data, dict):
                self.logger.warning(
                    f"❓ Unexpected filter_data type: {type(filter_data)}"
                )
                return self.file_service.apply_filter(FilterType.ALL_FILES)

            filter_type = filter_data.get("type")
            filter_value = filter_data.get("value")

            if filter_type == "file_type":
                if isinstance(filter_value, list):
                    filter_value = [
                        self._normalize_file_type_filter_value(value)
                        for value in filter_value
                    ]
                else:
                    filter_value = self._normalize_file_type_filter_value(filter_value)

            # Update internal active filters
            if filter_type in self._active_filters:
                if isinstance(filter_value, list):
                    self._active_filters[filter_type] = filter_value
                else:
                    # For single value filters, replace the list
                    self._active_filters[filter_type] = [filter_value]
            else:
                self.logger.warning(
                    f"Unknown filter type for internal state: {filter_type}"
                )

            # Apply all active filters cumulatively
            return self._apply_cumulative_filters()

        except Exception as e:
            self.logger.error(f"Error applying filter: {e}", exc_info=True)
            return self.file_service.apply_filter(FilterType.ALL_FILES)

    def remove_filter_by_id(self, filter_id: str):
        """
        Removes a specific filter by its ID and re-applies cumulative filters.

        Args:
            filter_id: The ID of the filter to remove (e.g., 'category_Animals').
        """
        self.logger.debug(
            f"FileManager.remove_filter_by_id: Attempting to remove {filter_id}"
        )
        self.logger.debug(
            f"FileManager.remove_filter_by_id: _active_filters BEFORE removal: {self._active_filters}"
        )

        parts = filter_id.split("_", 1)
        if len(parts) != 2:
            self.logger.warning(f"Invalid filter_id format for removal: {filter_id}")
            return

        filter_type, filter_value = parts[0], parts[1]

        if filter_type in self._active_filters:
            if filter_value in self._active_filters[filter_type]:
                self._active_filters[filter_type].remove(filter_value)
                self.logger.debug(f"Removed {filter_value} from {filter_type} filters.")
                self.logger.debug(
                    f"FileManager.remove_filter_by_id: _active_filters AFTER removal: {self._active_filters}"
                )
                self._apply_cumulative_filters()
            else:
                self.logger.debug(
                    f"Filter value {filter_value} not found in {filter_type} filters."
                )
        else:
            self.logger.warning(
                f"Filter type {filter_type} not found in active filters."
            )

    def _apply_cumulative_filters(self) -> List[Tuple[str, str]]:
        """
        Applies all currently active filters cumulatively.
        """
        self.logger.debug(f"Applying cumulative filters: {self._active_filters}")

        self._is_applying_filter_internally = True  # Set flag

        try:
            # Start with all files
            filtered_files = self.file_service.refresh_file_list()

            # Apply file type filter
            file_type_filters = self._active_filters.get("file_type", [])
            if file_type_filters and file_type_filters[0] != "All Files":
                filtered_files = self.file_service.apply_filter_to_list(
                    filtered_files, FilterType(file_type_filters[0])
                )

            # Apply category filter
            category_filters = self._active_filters.get("category", [])
            if category_filters:
                filtered_files = self.file_service.apply_multi_category_filter_to_list(
                    filtered_files, category_filters
                )

            # Apply year filter
            year_filters = self._active_filters.get("year", [])
            if year_filters:
                year_filters = self._normalize_year_filters(year_filters)
                filtered_files = self.file_service.apply_multi_year_filter_to_list(
                    filtered_files, year_filters
                )

            # Apply extension filter
            extension_filters = self._active_filters.get("extension", [])
            if extension_filters:
                filtered_files = self.file_service.apply_multi_extension_filter_to_list(
                    filtered_files, extension_filters
                )

            self.logger.debug(
                f"FileManager: Emitting files_updated with {len(filtered_files)} files"
            )
            self.files_updated.emit(filtered_files)
            self.logger.debug(
                f"FileManager: Emitting filter_applied with {len(filtered_files)} files and active filters: {self._active_filters}"
            )
            self.filter_applied.emit(
                self._active_filters, filtered_files
            )  # Emit the active filters dictionary and filtered files
            self.logger.debug("FileManager: Finished emitting filter_applied")
            return filtered_files
        finally:
            self._is_applying_filter_internally = False  # Reset flag

    def _has_active_filters(self) -> bool:
        """Returns True when any filter group is active."""
        return any(bool(v) for v in self._active_filters.values())

    def _apply_filters_to_file_list(
        self, file_list: List[Tuple[str, str]]
    ) -> List[Tuple[str, str]]:
        """Applies current active filters to a provided file list."""
        filtered_files = list(file_list)

        # Apply file type filter
        file_type_filters = self._active_filters.get("file_type", [])
        if file_type_filters and file_type_filters[0] != "All Files":
            filtered_files = self.file_service.apply_filter_to_list(
                filtered_files, FilterType(file_type_filters[0])
            )

        # Apply category filter
        category_filters = self._active_filters.get("category", [])
        if category_filters:
            filtered_files = self.file_service.apply_multi_category_filter_to_list(
                filtered_files, category_filters
            )

        # Apply year filter
        year_filters = self._active_filters.get("year", [])
        if year_filters:
            year_filters = self._normalize_year_filters(year_filters)
            filtered_files = self.file_service.apply_multi_year_filter_to_list(
                filtered_files, year_filters
            )

        # Apply extension filter
        extension_filters = self._active_filters.get("extension", [])
        if extension_filters:
            filtered_files = self.file_service.apply_multi_extension_filter_to_list(
                filtered_files, extension_filters
            )

        return filtered_files

    def clear_filters(self):
        """
        Clears all active filters and refreshes the file list.
        """
        self.logger.debug("Clearing all filters.")
        self._active_filters = {
            "file_type": [],
            "category": [],
            "year": [],
            "extension": [],
        }
        self._apply_cumulative_filters()

    def get_active_filters(self) -> Dict[str, List[Any]]:
        """
        Returns the currently active filters.
        """
        return self._active_filters.copy()

    def update_filters_from_chips(self, selected_filters: Dict[str, bool]):
        """
        Updates the internal filter state based on selections from FilterChipsContainer.

        Args:
            selected_filters: Dictionary of {filter_id: is_selected}
        """
        if self._is_applying_filter_internally:
            self.logger.debug(
                "Skipping update_filters_from_chips: internal filter application in progress."
            )
            return

        self.logger.debug(f"Updating filters from chips: {selected_filters}")

        # Rebuild a normalized filter state from chip selections.
        rebuilt_filters = {
            "file_type": [],
            "category": [],
            "year": [],
            "extension": [],
        }

        # Rebuild active filters based on chip selections
        for filter_id, is_selected in selected_filters.items():
            if is_selected:
                # Assuming filter_id format is 'type_value' (e.g., 'category_Sports')
                parts = filter_id.split("_", 1)
                if len(parts) == 2:
                    filter_type, filter_value = parts[0], parts[1]
                    if filter_type in rebuilt_filters:
                        # Special handling for file_type, as it's single-select
                        if filter_type == "file_type":
                            rebuilt_filters[filter_type] = [filter_value]
                        elif filter_type == "year":
                            try:
                                rebuilt_filters[filter_type].append(int(filter_value))
                            except (TypeError, ValueError):
                                self.logger.debug(
                                    f"Ignoring non-numeric year filter value: {filter_value}"
                                )
                        elif filter_type == "extension":
                            normalized_ext = (
                                filter_value
                                if str(filter_value).startswith(".")
                                else f".{filter_value}"
                            )
                            rebuilt_filters[filter_type].append(normalized_ext)
                        else:
                            rebuilt_filters[filter_type].append(filter_value)
                    else:
                        self.logger.warning(
                            f"Unknown filter type from chip: {filter_type}"
                        )
                else:
                    self.logger.warning(
                        f"Invalid filter_id format from chip: {filter_id}"
                    )

        # Normalize ordering for stable comparisons and avoid feedback loops.
        rebuilt_filters["category"] = sorted(set(rebuilt_filters["category"]))
        rebuilt_filters["year"] = sorted(
            set(self._normalize_year_filters(rebuilt_filters["year"]))
        )
        rebuilt_filters["extension"] = sorted(
            {ext.lower() for ext in rebuilt_filters["extension"]}
        )

        current_normalized = {
            "file_type": list(self._active_filters.get("file_type", [])),
            "category": sorted(set(self._active_filters.get("category", []))),
            "year": sorted(
                set(self._normalize_year_filters(self._active_filters.get("year", [])))
            ),
            "extension": sorted(
                {str(ext).lower() for ext in self._active_filters.get("extension", [])}
            ),
        }

        if rebuilt_filters == current_normalized:
            self.logger.debug(
                "Skipping update_filters_from_chips: no effective filter-state change."
            )
            return

        self._active_filters = rebuilt_filters

        # Apply the cumulative filters
        self._apply_cumulative_filters()

    def _normalize_year_filters(self, year_filters: List[Any]) -> List[int]:
        """Normalize year values to integer years."""
        normalized: List[int] = []
        for year in year_filters:
            try:
                normalized.append(int(year))
            except (TypeError, ValueError):
                continue
        return normalized

    # === PUBLIC METHODS (delegate to service) ===

    def refresh_file_list(self) -> List[Tuple[str, str]]:
        """
        Refreshes the file list from the database.

        Returns:
            List of files (file_path, directory)
        """
        return self.file_service.refresh_file_list()

    def refresh_and_emit_visible_files(self) -> List[Tuple[str, str]]:
        """
        Refreshes files from the database and emits the visible dataset to the UI.
        Active filters are preserved.
        """
        refreshed_files = self.file_service.refresh_file_list()
        if self._has_active_filters():
            return self._apply_cumulative_filters()
        self.files_updated.emit(refreshed_files)
        return refreshed_files

    def get_thumbnail_path(self, file_path: str) -> Optional[str]:
        """
        Retrieves the thumbnail path for a file.

        Args:
            file_path: File path

        Returns:
            Thumbnail path or None
        """
        return self.file_service.get_thumbnail_path(file_path)

    def get_file_metadata(self, file_path: str) -> dict:
        """
        Retrieves metadata for a file.

        Args:
            file_path: File path

        Returns:
            Dictionary of metadata
        """
        return self.file_service.get_file_metadata(file_path)

    def get_file_count_by_type(self) -> dict:
        """
        Returns the number of files by type.

        Returns:
            Dictionary {type: count}
        """
        return self.file_service.get_file_count_by_type()

    def clear_content_database(self):
        """Clears all content items from the database."""
        self.logger.info("Clearing all content from the database...")
        try:
            self.file_service.db_service.clear_all_content()
            if hasattr(self.file_service, "clear_current_files"):
                self.file_service.clear_current_files()
            self.logger.info("Content database cleared successfully.")
            self.files_updated.emit([])  # Emit signal to update UI
        except Exception as e:
            self.logger.error(f"Error clearing content database: {e}")
            self.scan_error.emit(f"Error clearing content database: {e}")

    def remove_files_from_database(self, file_paths: List[str]) -> int:
        """Removes only the provided files from the content database."""
        self.logger.info(
            f"Removing {len(file_paths or [])} filtered files from the content database"
        )
        try:
            deleted_count = self.file_service.remove_files_from_database(file_paths)
            return deleted_count
        except Exception as e:
            self.logger.error(f"Error removing filtered files from database: {e}")
            self.scan_error.emit(f"Error removing filtered files from database: {e}")
            return 0

    def cancel_current_scan(self):
        """Cancels the ongoing scan (if applicable)."""
        self.logger.info("Scan cancellation requested")

        try:
            if self.is_scan_active and self.scan_worker:
                self.should_cancel_scan = True

                # Request cancellation from the worker
                self.scan_worker.cancel_scan()
                self.logger.info("Scan cancellation requested")
            else:
                self.logger.info("No active scan to cancel")

        except Exception as e:
            self.logger.error(f"Error cancelling scan: {e}")

    def _append_scan_operation_log(self, message: str):
        if not message:
            return
        timestamp = time.strftime("%H:%M:%S")
        self._scan_operation_log.append(f"[{timestamp}] {message}")
        self._scan_operation_log = self._scan_operation_log[-50:]
        self._push_scan_operation_state()

    def _dismiss_operation_surface(self):
        if self.main_window:
            self.main_window.clear_operation_state()
            self.main_window.show_progress_indicator(False)

    def _push_scan_operation_state(
        self,
        progress: Any | None = None,
        state: str | None = None,
        current_directory: str | None = None,
    ) -> None:
        """Builds and pushes scan state to the integrated Operations panel."""
        if not self.main_window or not hasattr(
            self.main_window, "show_operation_state"
        ):
            return

        current_stats = {
            "files_found": 0,
            "files_processed": 0,
            "total_files_scanned": 0,
            "scan_root_directory": current_directory or "",
            "current_directory": current_directory or "",
            "current_file": "",
            "scan_speed": 0.0,
            "estimated_total": 0,
            "errors": 0,
        }
        current_stats.update(self.__dict__.get("_scan_operation_snapshot", {}))
        if current_directory:
            if not current_stats.get("scan_root_directory"):
                current_stats["scan_root_directory"] = current_directory
            current_stats["current_directory"] = current_directory

        if progress is not None:
            if hasattr(progress, "__dict__"):
                current_stats.update(
                    {
                        "files_found": getattr(progress, "files_found", 0),
                        "files_processed": getattr(progress, "files_processed", 0),
                        "total_files_scanned": getattr(
                            progress, "total_files_scanned", 0
                        ),
                        "current_directory": getattr(
                            progress,
                            "current_directory",
                            current_stats["current_directory"],
                        ),
                        "current_file": getattr(progress, "current_file", ""),
                        "scan_speed": getattr(progress, "scan_speed", 0.0),
                        "estimated_total": getattr(
                            progress, "estimated_total_files", 0
                        ),
                        "errors": getattr(progress, "errors", 0),
                    }
                )
            elif isinstance(progress, dict):
                current_stats.update(progress)

        self._scan_operation_snapshot = dict(current_stats)

        operation_state = state or (
            "running" if current_stats["estimated_total"] > 0 else "discovering"
        )
        files_found = max(0, int(current_stats["files_found"]))
        files_processed = max(0, int(current_stats["files_processed"]))
        total_scanned = max(0, int(current_stats["total_files_scanned"]))
        estimated_total = max(0, int(current_stats["estimated_total"]))
        errors = max(0, int(current_stats["errors"]))
        successful = max(0, files_processed - errors)
        speed = float(current_stats["scan_speed"])
        scan_root_directory = str(
            current_stats.get("scan_root_directory")
            or current_stats.get("current_directory")
            or ""
        ).strip()
        current_scanned_directory = str(
            current_stats.get("current_directory") or ""
        ).strip()
        title_directory = scan_root_directory
        if scan_root_directory and current_scanned_directory:
            try:
                relative_path = os.path.relpath(
                    current_scanned_directory, scan_root_directory
                )
                if relative_path not in ("", ".") and not relative_path.startswith(
                    ".."
                ):
                    first_segment = relative_path.split(os.sep)[0]
                    title_directory = os.path.join(scan_root_directory, first_segment)
            except ValueError:
                title_directory = scan_root_directory

        if operation_state == "completed":
            title = "Scan completed"
            summary = f"{files_found} files found"
            primary_action = None
            secondary_action = "close"
        elif operation_state == "failed":
            title = "Scan failed"
            summary = "Scan failed or cancelled"
            primary_action = None
            secondary_action = "close"
        else:
            title = f"Scanning: {title_directory}" if title_directory else "Scanning..."
            summary = f"{total_scanned} files scanned"
            primary_action = "cancel"
            secondary_action = None

        details = [
            OperationDetail("Scanned", current_scanned_directory or "--"),
            OperationDetail("Directory", scan_root_directory or "--"),
            OperationDetail(
                "Rate",
                self._format_rate(speed, "items") if speed > 0 else "0.0 items/s",
            ),
            OperationDetail(
                "Elapsed",
                self._format_elapsed_for_operation(),
            ),
            OperationDetail(
                "Remaining",
                self._estimate_remaining_for_operation(
                    estimated_total, files_processed, speed
                ),
            ),
        ]

        if scan_root_directory:
            current_item_text = f"Root directory: {scan_root_directory}"
        else:
            current_item_text = "Waiting for first directory..."

        state_payload = OperationViewState(
            operation_id="scan",
            kind="scan",
            title=title,
            state=operation_state,  # type: ignore[arg-type]
            summary=summary,
            current_item=current_item_text,
            progress_current=files_processed,
            progress_total=estimated_total,
            is_determinate=estimated_total > 0,
            stats=[
                OperationStat("Found", str(files_found), "files"),
                OperationStat("Success", str(successful), "processed"),
                OperationStat(
                    "Speed",
                    self._format_rate(speed, "files") if speed > 0 else "--",
                    "",
                ),
            ],
            details=details,
            log_entries=list(self._scan_operation_log),
            primary_action=primary_action,  # type: ignore[arg-type]
            secondary_action=secondary_action,  # type: ignore[arg-type]
        )
        self.main_window.show_operation_state(state_payload)

    def _format_elapsed_for_operation(self) -> str:
        started_at = self.__dict__.get("_scan_operation_started_at")
        if started_at is not None:
            elapsed = time.time() - started_at
        elif self.scan_progress_dialog and getattr(
            self.scan_progress_dialog, "start_time", None
        ):
            elapsed = time.time() - self.scan_progress_dialog.start_time
        else:
            elapsed = 0.0
        minutes, seconds = divmod(int(max(0, elapsed)), 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _estimate_remaining_for_operation(
        self, estimated_total: int, files_processed: int, speed: float
    ) -> str:
        if estimated_total <= 0 or speed <= 0:
            return "waiting for file discovery"
        remaining_seconds = max(0.0, (estimated_total - files_processed) / speed)
        minutes, seconds = divmod(int(remaining_seconds), 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _format_rate(rate: float, unit: str) -> str:
        if rate <= 0:
            return f"0.0 {unit}/s"
        if rate < 1:
            return f"{rate * 60:.1f} {unit}/min"
        return f"{rate:.1f} {unit}/s"

    # === PROPERTIES (delegate to service) ===

    @property
    def current_files(self) -> List[Tuple[str, str]]:
        """Returns the current list of files."""
        return self.file_service.current_files

    @property
    def current_filter(self) -> str:
        """Returns the currently applied filter."""
        return self.file_service.current_filter.value

    @property
    def last_scan_stats(self) -> dict:
        """Returns the statistics of the last scan."""
        try:
            stats = self.file_service.last_scan_stats
            return {
                "files_found": stats.files_found,
                "metadata_extracted": stats.metadata_extracted,
                "thumbnails_generated": stats.thumbnails_generated,
                "errors": stats.errors,
                "processing_time": stats.processing_time,
                "directory_scanned": stats.directory_scanned,
            }
        except AttributeError:
            return {
                "files_found": 0,
                "metadata_extracted": 0,
                "thumbnails_generated": 0,
                "errors": 0,
                "processing_time": 0,
                "directory_scanned": "",
            }

    @property
    def file_count(self) -> int:
        """Returns the total number of files."""
        return self.file_service.file_count

    def cleanup(self):
        """Cleans up resources used by the manager."""
        try:
            self.logger.info("Cleaning up Enhanced Qt FileManager")

            # Cancel ongoing scan
            self.cancel_current_scan()
            self._stop_scan_ui_refresh_worker()

            # Close progress dialog
            if self.scan_progress_dialog:
                self.scan_progress_dialog.reject()
                self.scan_progress_dialog = None

            # Clean up worker and thread
            self._cleanup_worker_and_thread()

            # Clean up service
            if hasattr(self.file_service, "cleanup"):
                self.file_service.cleanup()

            self.logger.info("FileManager cleanup complete")

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    # === DEBUGGING HELPERS ===
