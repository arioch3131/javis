# controllers/categorization_controller.py
"""
Controller for automatic file categorization.
"""

import csv
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from PyQt6.QtCore import QMutex, QThread, QTimer, QWaitCondition, QObject, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from ai_content_classifier.controllers.llm_controller import LLMController
from ai_content_classifier.core.logger import get_logger
from ai_content_classifier.services.database.content_database_service import (
    ContentDatabaseService,
)
from ai_content_classifier.services.llm.llm_service import LLMService
from ai_content_classifier.services.shared.cache_runtime import get_cache_runtime
from ai_content_classifier.views.widgets.common.operation_state import (
    OperationDetail,
    OperationStat,
    OperationViewState,
)

if TYPE_CHECKING:
    from ai_content_classifier.views.managers.file_manager import FileManager
    from ai_content_classifier.views.managers.settings_manager import SettingsManager


class CategorizationWorker(QThread):
    """
    Worker thread for background categorization.
    """

    # Progress signals
    progress_updated = pyqtSignal(int, int, int)  # processed, successful, failed
    current_item_updated = pyqtSignal(str)  # current file path
    result_ready = pyqtSignal(
        str, str, float, float
    )  # file_path, category, confidence, time
    log_message = pyqtSignal(str)
    finished = pyqtSignal(dict)  # Final results

    def __init__(
        self,
        llm_service: LLMService,
        content_database_service: ContentDatabaseService,
        file_paths: List[str],
        categories: List[str],
        config: Dict[str, Any],
    ):
        super().__init__()

        self.llm_service = llm_service
        self.content_database_service = content_database_service
        self.file_paths = file_paths
        self.categories = categories
        self.config = config

        self.should_stop = False
        self._pause_requested = False
        self._pause_mutex = QMutex()
        self._pause_condition = QWaitCondition()
        self.results = []
        self._hash_category_cache = get_cache_runtime().memory_cache(
            "categorization:duplicate_hash_reuse",
            default_ttl=900,
        )

    def run(self):
        """Executes the categorization."""
        processed = 0
        successful = 0
        failed = 0

        self._build_hash_category_cache()
        self.log_message.emit(
            f"Starting categorization of {len(self.file_paths)} files"
        )

        for file_path in self.file_paths:
            self._wait_if_paused()
            if self.should_stop:
                break

            try:
                start_time = time.time()
                self.current_item_updated.emit(file_path)

                # Determine file type
                is_image = self._is_image_file(file_path)

                # Check if this type should be processed
                if is_image and not self.config.get("process_images", True):
                    continue
                if not is_image and not self.config.get("process_documents", True):
                    continue

                reused = self._try_reuse_duplicate_category(file_path)
                if reused is not None:
                    processing_time = time.time() - start_time
                    self.results.append(
                        {
                            "file_path": file_path,
                            "category": reused["category"],
                            "confidence": reused["confidence"],
                            "processing_time": processing_time,
                            "extraction_method": reused["extraction_method"],
                            "extraction_details": reused["extraction_details"],
                            "status": "success",
                        }
                    )
                    successful += 1
                    self.result_ready.emit(
                        file_path,
                        reused["category"],
                        float(reused["confidence"]),
                        processing_time,
                    )
                    processed += 1
                    self.progress_updated.emit(processed, successful, failed)
                    continue

                # Classify the file
                if is_image:
                    result = self.llm_service.classify_image(file_path, self.categories)
                else:
                    result = self.llm_service.classify_document(
                        file_path, self.categories
                    )

                processing_time = time.time() - start_time

                # Check confidence threshold
                confidence_threshold = self.config.get("confidence_threshold", 0.3)
                final_category = result.category
                if result.confidence < confidence_threshold:
                    final_category = "Uncertain"

                # Save the result to the database
                if self.config.get("save_results", True):
                    self.content_database_service.update_content_category(
                        file_path=file_path,
                        category=final_category,
                        confidence=result.confidence,
                        extraction_method=result.extraction_method,
                        extraction_details=result.extraction_details,
                    )

                self.results.append(
                    {
                        "file_path": file_path,
                        "category": final_category,
                        "confidence": result.confidence,
                        "processing_time": processing_time,
                        "extraction_method": result.extraction_method,
                        "status": "success",
                    }
                )

                successful += 1
                self.result_ready.emit(
                    file_path, final_category, result.confidence, processing_time
                )

            except Exception as e:
                self.results.append(
                    {
                        "file_path": file_path,
                        "category": "Error",
                        "confidence": 0.0,
                        "processing_time": 0.0,
                        "error": str(e),
                        "status": "failed",
                    }
                )

                failed += 1
                self.log_message.emit(
                    f"Error processing {os.path.basename(file_path)}: {str(e)}"
                )

            processed += 1
            self.progress_updated.emit(processed, successful, failed)

            # Preview mode: stop after a few files
            if self.config.get("preview_mode", False):
                preview_count = self.config.get("preview_count", 5)
                if processed >= preview_count:
                    break

        # Emit final results
        self.finished.emit(
            {
                "results": self.results,
                "total_processed": processed,
                "successful": successful,
                "failed": failed,
                "cancelled": self.should_stop,
            }
        )

    def stop(self):
        """Stops the worker."""
        self.should_stop = True
        self.resume()

    def pause(self):
        """Pauses worker processing."""
        self._pause_mutex.lock()
        self._pause_requested = True
        self._pause_mutex.unlock()

    def resume(self):
        """Resumes worker processing."""
        self._pause_mutex.lock()
        self._pause_requested = False
        self._pause_condition.wakeAll()
        self._pause_mutex.unlock()

    def _wait_if_paused(self):
        """Blocks processing while pause is requested."""
        self._pause_mutex.lock()
        while self._pause_requested and not self.should_stop:
            self._pause_condition.wait(self._pause_mutex, 250)
        self._pause_mutex.unlock()

    def _is_image_file(self, file_path: str) -> bool:
        """Determines if a file is an image."""
        image_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".tiff",
            ".webp",
            ".svg",
        }
        return Path(file_path).suffix.lower() in image_extensions

    def _build_hash_category_cache(self) -> None:
        """
        Build a hash->category cache from already categorized duplicate groups.
        """
        self._hash_category_cache.clear()
        allowed_categories = {
            category.strip() for category in self.categories if category
        }
        try:
            duplicates_by_hash = self.content_database_service.find_duplicates()
            for file_hash, items in duplicates_by_hash.items():
                if not file_hash or not items:
                    continue

                for item in items:
                    if not item:
                        continue
                    category = getattr(item, "category", None)
                    if (
                        not category
                        or category == "Uncertain"
                        or category not in allowed_categories
                    ):
                        continue

                    content_metadata = getattr(item, "content_metadata", {}) or {}
                    classification = content_metadata.get("classification", {})

                    self._hash_category_cache.set(
                        file_hash,
                        {
                            "category": category,
                            "confidence": float(classification.get("confidence", 1.0)),
                            "extraction_method": classification.get(
                                "extraction_method", "DUPLICATE_HASH_REUSE"
                            ),
                            "extraction_details": classification.get(
                                "extraction_details",
                                f"Reused existing categorization from duplicate hash {file_hash[:12]}...",
                            ),
                        },
                    )
                    break
        except Exception as exc:
            self.log_message.emit(f"Duplicate cache unavailable: {exc}")

    def _try_reuse_duplicate_category(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Reuse an existing categorization for files with the same file hash.
        """
        try:
            content_item = self.content_database_service.get_content_by_path(file_path)
            if not content_item:
                return None

            file_hash = getattr(content_item, "file_hash", None)
            if not file_hash:
                return None

            reused = self._hash_category_cache.get(file_hash, default=None)
            if not reused:
                return None
            if reused.get("category") not in self.categories:
                return None

            if self.config.get("save_results", True):
                self.content_database_service.update_content_category(
                    file_path=file_path,
                    category=reused["category"],
                    confidence=float(reused["confidence"]),
                    extraction_method=reused["extraction_method"],
                    extraction_details=reused["extraction_details"],
                )

            self.log_message.emit(
                f"Duplicate hash reuse: {os.path.basename(file_path)} -> {reused['category']}"
            )
            return reused
        except Exception:
            return None


class CategorizationController(QObject):
    """
    Main controller for automatic categorization.

    Orchestrates:
    - Configuration dialog
    - Retrieving files from the current view
    - Starting the categorization process
    - Displaying results
    """

    # Signal emitted when categorization is complete
    categorization_completed = pyqtSignal(dict)

    def __init__(
        self,
        llm_controller: LLMController,
        settings_manager: "SettingsManager",
        file_manager: "FileManager",
        content_database_service: ContentDatabaseService,
        parent=None,
    ):
        super().__init__(parent)
        self.logger = get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        self.llm_controller = llm_controller
        self.settings_manager = settings_manager
        self.file_manager = file_manager
        self.content_database_service = content_database_service

        # Workers and dialogs
        self.worker = None
        self.progress_dialog = None
        self._categorization_started_at: float | None = None
        self._categorization_operation_snapshot: Dict[str, Any] = {}
        self._operation_refresh_timer = QTimer(self)
        self._operation_refresh_timer.setInterval(1000)
        self._operation_refresh_timer.timeout.connect(
            self._refresh_categorization_operation_state
        )

    def start_categorization_for_current_view(self, parent_widget=None):
        """
        Starts categorization for files in the current view.

        Args:
            parent_widget: Parent widget for dialogs
        """
        # Get currently displayed files
        current_files = self._get_current_view_files()

        if not current_files:
            QMessageBox.information(
                parent_widget,
                "No files",
                "No files to categorize in the current view.\n"
                "Scan a directory first or change the filter.",
            )
            return

        # Analyze file types
        file_types = self._analyze_file_types(current_files)

        # Get categories from settings
        available_categories = self.settings_manager.get_unified_categories()

        # Open configuration dialog
        from ai_content_classifier.views.widgets.dialogs import CategorizationDialog

        dialog = CategorizationDialog(
            file_count=len(current_files),
            file_types=file_types,
            llm_controller=self.llm_controller,
            available_categories=available_categories,
            parent=parent_widget,
        )

        dialog.categorization_requested.connect(
            lambda config: self._execute_categorization(
                self._get_current_view_files(), config, parent_widget
            )
        )

        dialog.exec()

    def start_automatic_categorization(
        self,
        file_paths: List[str],
        categories: List[str],
        config_overrides: Dict[str, Any] | None = None,
        parent_widget=None,
    ) -> bool:
        """
        Starts categorization without opening the configuration dialog.

        This method is intended for pipeline/event-driven execution.
        """
        if not file_paths:
            self.logger.warning("Automatic categorization skipped: no files provided")
            return False

        if not categories:
            self.logger.warning(
                "Automatic categorization skipped: no categories configured"
            )
            return False

        auto_config: Dict[str, Any] = {
            "categories": categories,
            "process_images": True,
            "process_documents": True,
            "confidence_threshold": 0.7,
            "save_results": True,
            "export_csv": False,
            "show_report": False,
            "preview_mode": False,
            "preview_count": 0,
            "only_uncategorized": False,
        }

        if config_overrides:
            auto_config.update(config_overrides)

        self._execute_categorization(file_paths, auto_config, parent_widget)
        return True

    def _get_current_view_files(self) -> List[str]:
        """
        Retrieves the files currently displayed in the view.

        Returns:
            List of file paths
        """
        try:
            files_data = []

            # Prefer the effective view state when filters/search/sort are applied.
            main_window = getattr(self.file_manager, "main_window", None)
            if main_window is not None:
                refresh_view = getattr(main_window, "_refresh_displayed_files", None)
                if callable(refresh_view):
                    refresh_view()
                main_window_files = getattr(main_window, "current_files", None)
                if isinstance(main_window_files, list):
                    files_data = main_window_files

            # Fallback to the file manager dataset when the view has no data yet.
            if not files_data:
                manager_files = getattr(self.file_manager, "current_files", [])
                files_data = manager_files if isinstance(manager_files, list) else []

            file_paths: List[str] = []
            for file_data in files_data:
                if isinstance(file_data, (list, tuple)) and file_data:
                    file_paths.append(str(file_data[0]))
                elif isinstance(file_data, str):
                    file_paths.append(file_data)

            return file_paths

        except Exception as e:
            self.logger.error(f"Error retrieving view files: {e}")
            return []

    def _analyze_file_types(self, file_paths: List[str]) -> Dict[str, int]:
        """
        Analyzes the types of files present.

        Args:
            file_paths: List of file paths

        Returns:
            Dictionary with the count per type
        """
        types_count = {"Images": 0, "Documents": 0, "Others": 0}

        image_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".tiff",
            ".webp",
            ".svg",
        }
        document_extensions = {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md"}

        for file_path in file_paths:
            ext = Path(file_path).suffix.lower()

            if ext in image_extensions:
                types_count["Images"] += 1
            elif ext in document_extensions:
                types_count["Documents"] += 1
            else:
                types_count["Others"] += 1

        return types_count

    def _execute_categorization(
        self, file_paths: List[str], config: Dict[str, Any], parent_widget
    ):
        """
        Executes categorization with the given configuration.

        Args:
            file_paths: Files to categorize
            config: Categorization configuration
            parent_widget: Parent widget for dialogs
        """
        # Filter files according to configuration
        self._operation_refresh_timer.stop()
        self._categorization_operation_snapshot = {}
        self._categorization_started_at = None

        filtered_files = self._filter_files_by_config(file_paths, config)

        if not filtered_files:
            QMessageBox.information(
                parent_widget,
                "No files to process",
                "No file matches the selected criteria.",
            )
            return

        categories = config["categories"]

        using_integrated_operations = self._has_integrated_operations_host()

        # Preview or full mode
        from ai_content_classifier.views.widgets.dialogs import (
            CategorizationProgressDialog,
        )

        if config.get("preview_mode", False):
            preview_count = min(config.get("preview_count", 5), len(filtered_files))
            filtered_files = filtered_files[:preview_count]

        if using_integrated_operations:
            self.progress_dialog = None
            self._configure_categorization_operation_surface(
                total_files=len(filtered_files),
                preview_mode=bool(config.get("preview_mode", False)),
            )
        else:
            if config.get("preview_mode", False):
                self.progress_dialog = CategorizationProgressDialog(
                    total_files=len(filtered_files), parent=parent_widget
                )
                self.progress_dialog.setWindowTitle("🔍 Categorization Preview")
            else:
                self.progress_dialog = CategorizationProgressDialog(
                    total_files=len(filtered_files), parent=parent_widget
                )

        # Connect dialog signals
        if self.progress_dialog:
            self.progress_dialog.cancellation_requested.connect(
                self._cancel_categorization
            )

        # Create and start the worker
        self.worker = CategorizationWorker(
            self.llm_controller.llm_service,
            self.content_database_service,
            filtered_files,
            categories,
            config,
        )

        # Connect worker signals
        if self.progress_dialog:
            self.worker.progress_updated.connect(self.progress_dialog.update_progress)
            self.worker.result_ready.connect(self.progress_dialog.add_result)
            self.worker.log_message.connect(self.progress_dialog.add_log)
            self.progress_dialog.pause_requested.connect(self.worker.pause)
            self.progress_dialog.resume_requested.connect(self.worker.resume)
        self.worker.current_item_updated.connect(self._on_categorization_current_item)
        self.worker.progress_updated.connect(self._on_categorization_progress)
        self.worker.result_ready.connect(self._on_categorization_result)
        self.worker.log_message.connect(self._on_categorization_log)
        self.worker.finished.connect(
            lambda results: self._on_categorization_finished(
                results, config, parent_widget
            )
        )

        # Start
        if self.progress_dialog:
            self.progress_dialog.start_categorization()
        self.worker.start()
        if self.progress_dialog:
            self.progress_dialog.show()

    def _filter_files_by_config(
        self, file_paths: List[str], config: Dict[str, Any]
    ) -> List[str]:
        """Filters files according to the configuration."""
        filtered = []

        image_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".tiff",
            ".webp",
            ".svg",
        }

        only_uncategorized = config.get("only_uncategorized", False)

        for file_path in file_paths:
            ext = Path(file_path).suffix.lower()
            is_image = ext in image_extensions

            # Check if file should be processed based on type
            if (is_image and not config.get("process_images", True)) or (
                not is_image and not config.get("process_documents", True)
            ):
                continue

            # If only uncategorized is selected, check if the file is already categorized
            if only_uncategorized:
                content_item = self.content_database_service.get_content_by_path(
                    file_path
                )
                if (
                    content_item
                    and content_item.category is not None
                    and content_item.category != "Uncertain"
                ):
                    self.logger.debug(
                        f"Skipping already categorized file: {file_path} "
                        f"(Category: {content_item.category})"
                    )
                    continue

            filtered.append(file_path)

        return filtered

    def _cancel_categorization(self):
        """Cancels the ongoing categorization."""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            if self.progress_dialog:
                self.progress_dialog.add_log("Stop requested...")
            self._categorization_operation_snapshot["state"] = "cancelling"
            self._push_categorization_operation_state()

    def _pause_categorization(self):
        """Pauses integrated categorization progress."""
        if self.worker and self.worker.isRunning():
            self.worker.pause()
            self._categorization_operation_snapshot["state"] = "paused"
            self._push_categorization_operation_state()

    def _resume_categorization(self):
        """Resumes integrated categorization progress."""
        if self.worker and self.worker.isRunning():
            self.worker.resume()
            self._categorization_operation_snapshot["state"] = "running"
            self._push_categorization_operation_state()

    def _on_categorization_finished(
        self, results: Dict[str, Any], config: Dict[str, Any], parent_widget
    ):
        """Handles the end of categorization."""
        self.logger.info(
            f"Categorization finished: "
            f"{results['successful']}/{results['total_processed']} successful"
        )

        # Close the progress dialog
        if self.progress_dialog:
            self.progress_dialog.accept()
            self.progress_dialog = None
        self._operation_refresh_timer.stop()
        if self._has_integrated_operations_host():
            self._clear_categorization_operation_surface()

        # Process results according to configuration
        if config.get("save_results", True) and not config.get("preview_mode", False):
            self._save_results_to_database(results["results"])

        if config.get("export_csv", False) and not config.get("preview_mode", False):
            self._export_results_to_csv(results["results"], parent_widget)

        if config.get("show_report", True):
            self._show_results_report(results, config, parent_widget)

        # Emit the completion signal
        self.categorization_completed.emit(results)

        # Refresh the file list in the FileManager to update the UI
        refreshed_files = self.file_manager.refresh_file_list()
        self.file_manager.files_updated.emit(refreshed_files)

        # Cleanup
        self.worker = None
        self._categorization_operation_snapshot = {}
        self._categorization_started_at = None

    def _has_integrated_operations_host(self) -> bool:
        main_window = getattr(self.file_manager, "main_window", None)
        return bool(main_window and hasattr(main_window, "show_operation_state"))

    def _get_integrated_operations_host(self):
        return getattr(self.file_manager, "main_window", None)

    def _configure_categorization_operation_surface(
        self, total_files: int, preview_mode: bool
    ) -> None:
        host = self._get_integrated_operations_host()
        if not host:
            return

        if hasattr(host, "set_operation_action_handlers"):
            host.set_operation_action_handlers(
                {
                    "cancel": self._cancel_categorization,
                    "pause": self._pause_categorization,
                    "resume": self._resume_categorization,
                    "close": self._clear_categorization_operation_surface,
                }
            )

        self._categorization_started_at = time.time()
        self._categorization_operation_snapshot = {
            "total_files": total_files,
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "current_file": "",
            "last_result_file": "",
            "preview_mode": preview_mode,
            "state": "running",
        }
        self._operation_refresh_timer.start()
        self._update_categorization_working_state()
        self._push_categorization_operation_state()

    def _clear_categorization_operation_surface(self) -> None:
        host = self._get_integrated_operations_host()
        if host and hasattr(host, "clear_operation_state"):
            host.clear_operation_state()
        self._reset_categorization_working_state()

    def _refresh_categorization_operation_state(self) -> None:
        if not self.worker or not self.worker.isRunning():
            self._operation_refresh_timer.stop()
            return
        self._push_categorization_operation_state()

    def _format_categorization_elapsed(self) -> str:
        started_at = self._categorization_started_at
        if started_at is None:
            return "00:00"
        elapsed = max(0.0, time.time() - started_at)
        minutes, seconds = divmod(int(elapsed), 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _estimate_categorization_remaining(self) -> str:
        snapshot = self._categorization_operation_snapshot
        total_files = int(snapshot.get("total_files", 0))
        processed = int(snapshot.get("processed", 0))
        started_at = self._categorization_started_at
        if not started_at or processed <= 0 or total_files <= processed:
            return "calculating..."
        elapsed = max(0.001, time.time() - started_at)
        speed = processed / elapsed
        if speed <= 0:
            return "calculating..."
        remaining_seconds = max(0.0, (total_files - processed) / speed)
        minutes, seconds = divmod(int(remaining_seconds), 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _push_categorization_operation_state(self) -> None:
        host = self._get_integrated_operations_host()
        if not host or not hasattr(host, "show_operation_state"):
            return

        snapshot = self._categorization_operation_snapshot
        total_files = max(0, int(snapshot.get("total_files", 0)))
        processed = max(0, int(snapshot.get("processed", 0)))
        successful = max(0, int(snapshot.get("successful", 0)))
        failed = max(0, int(snapshot.get("failed", 0)))
        current_file = snapshot.get("current_file") or "Waiting for first file..."
        state = snapshot.get("state", "running")
        elapsed_text = self._format_categorization_elapsed()
        started_at = self._categorization_started_at
        elapsed_seconds = max(0.001, time.time() - started_at) if started_at else 0.0
        speed = processed / elapsed_seconds if processed > 0 and started_at else 0.0

        if state == "paused":
            title = "Categorization paused"
            secondary_action = "resume"
        elif state == "cancelling":
            title = "Stopping categorization"
            secondary_action = None
        else:
            title = "Categorizing..."
            secondary_action = "pause"

        summary = f"{processed} / {total_files} files"

        payload = OperationViewState(
            operation_id="categorization",
            kind="categorization",
            title=title,
            state=state,  # type: ignore[arg-type]
            summary=summary,
            current_item=current_file,
            progress_current=processed,
            progress_total=total_files,
            is_determinate=total_files > 0,
            stats=[
                OperationStat("Processed", str(processed)),
                OperationStat("Success", str(successful)),
                OperationStat("Failed", str(failed)),
            ],
            details=[
                OperationDetail("Processed", f"{processed}/{total_files}"),
                OperationDetail(
                    "Rate", self._format_rate(speed, "files") if speed > 0 else "--"
                ),
                OperationDetail("Elapsed", elapsed_text),
                OperationDetail("Remaining", self._estimate_categorization_remaining()),
            ],
            primary_action="cancel",
            secondary_action=secondary_action,  # type: ignore[arg-type]
        )
        self._update_categorization_working_state(
            processed=processed,
            total_files=total_files,
            state=state,
        )
        host.show_operation_state(payload)

    @staticmethod
    def _format_rate(rate: float, unit: str) -> str:
        if rate <= 0:
            return f"0.0 {unit}/s"
        if rate < 1:
            return f"{rate * 60:.1f} {unit}/min"
        return f"{rate:.1f} {unit}/s"

    def _on_categorization_current_item(self, file_path: str) -> None:
        if not self._has_integrated_operations_host():
            return
        self._categorization_operation_snapshot["current_file"] = file_path
        self._push_categorization_operation_state()

    def _on_categorization_progress(
        self, processed: int, successful: int, failed: int
    ) -> None:
        if not self._has_integrated_operations_host():
            return
        self._categorization_operation_snapshot.update(
            {
                "processed": processed,
                "successful": successful,
                "failed": failed,
                "state": self._categorization_operation_snapshot.get("state", "running")
                if self._categorization_operation_snapshot.get("state") != "paused"
                else "paused",
            }
        )
        self._push_categorization_operation_state()

    def _on_categorization_result(
        self, file_path: str, category: str, confidence: float, processing_time: float
    ) -> None:
        del category, confidence, processing_time
        if not self._has_integrated_operations_host():
            return
        self._categorization_operation_snapshot["current_file"] = file_path
        self._push_categorization_operation_state()

    def _on_categorization_log(self, message: str) -> None:
        del message
        if not self._has_integrated_operations_host():
            return
        self._push_categorization_operation_state()

    def _update_categorization_working_state(
        self,
        processed: int | None = None,
        total_files: int | None = None,
        state: str | None = None,
    ) -> None:
        host = self._get_integrated_operations_host()
        if not host:
            return

        snapshot = self._categorization_operation_snapshot
        processed = max(
            0, int(processed if processed is not None else snapshot.get("processed", 0))
        )
        total_files = max(
            0,
            int(
                total_files
                if total_files is not None
                else snapshot.get("total_files", 0)
            ),
        )
        state = state or str(snapshot.get("state", "running"))
        percentage = int((processed / total_files) * 100) if total_files > 0 else 0

        if hasattr(host, "set_main_status_chip"):
            host.set_main_status_chip("Working...", is_busy=True)
        if hasattr(host, "set_progress_status_chip"):
            host.set_progress_status_chip(
                f"Categorization: {processed}/{total_files} files ({percentage:.1f}%)",
                is_busy=state in {"running", "paused", "cancelling"},
            )
        if hasattr(host, "update_progress_bar"):
            host.update_progress_bar(percentage)

    def _reset_categorization_working_state(self) -> None:
        host = self._get_integrated_operations_host()
        if not host:
            return
        if hasattr(host, "set_main_status_chip"):
            host.set_main_status_chip("Ready", is_busy=False)
        if hasattr(host, "set_progress_status_chip"):
            host.set_progress_status_chip("Metadata idle", is_busy=False)
        if hasattr(host, "update_progress_bar"):
            host.update_progress_bar(0)

    def _save_results_to_database(self, results: List[Dict[str, Any]]):
        """Saves the results to the database."""
        self.logger.info(f"Saving {len(results)} results to database...")
        for result in results:
            try:
                self.content_database_service.update_content_category(
                    file_path=result["file_path"],
                    category=result["category"],
                    confidence=result["confidence"],
                    extraction_method=result.get(
                        "extraction_method", "LLM_Categorization"
                    ),
                    extraction_details=result.get(
                        "extraction_details", "Automatic categorization"
                    ),
                )
            except Exception as e:
                self.logger.error(
                    f"Error saving category for {result['file_path']}: {e}"
                )
        self.logger.info(f"Finished saving {len(results)} results to database.")

    def _export_results_to_csv(self, results: List[Dict[str, Any]], parent_widget):
        """Exports the results to CSV."""
        file_path, _ = QFileDialog.getSaveFileName(
            parent_widget,
            "Export results",
            f"categorization_results_{int(time.time())}.csv",
            "CSV Files (*.csv)",
        )

        if file_path:
            try:
                with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(
                        [
                            "File",
                            "Category",
                            "Confidence",
                            "Time (s)",
                            "Method",
                            "Status",
                        ]
                    )

                    for result in results:
                        writer.writerow(
                            [
                                result["file_path"],
                                result["category"],
                                f"{result['confidence']:.2%}",
                                f"{result['processing_time']:.2f}",
                                result.get("extraction_method", ""),
                                result["status"],
                            ]
                        )

                QMessageBox.information(
                    parent_widget,
                    "Export successful",
                    f"Results exported to:\n{file_path}",
                )

            except Exception as e:
                QMessageBox.critical(
                    parent_widget, "Export error", f"Could not export:\n{str(e)}"
                )

    def _show_results_report(
        self, results: Dict[str, Any], config: Dict[str, Any], parent_widget
    ):
        """Displays a report of the results."""
        total = results["total_processed"]
        successful = results["successful"]
        failed = results["failed"]

        # Calculate statistics
        if results["results"]:
            avg_confidence = sum(
                r["confidence"] for r in results["results"] if r["status"] == "success"
            ) / max(successful, 1)
            avg_time = sum(r["processing_time"] for r in results["results"]) / total
        else:
            avg_confidence = 0
            avg_time = 0

        # Count by category
        category_counts = {}
        for result in results["results"]:
            if result["status"] == "success":
                cat = result["category"]
                category_counts[cat] = category_counts.get(cat, 0) + 1

        # Build the message
        report = f"""📊 Categorization Report

{"🔍 Preview Mode" if config.get("preview_mode") else "🚀 Full Categorization"}

📈 Global Statistics:
• Total processed: {total} files
• Successful: {successful} ({successful / total * 100:.1f}%)
• Failures: {failed} ({failed / total * 100:.1f}%)
• Average confidence: {avg_confidence:.1%}
• Average time: {avg_time:.1f}s per file

🏷️ Breakdown by category:"""

        for category, count in sorted(category_counts.items()):
            percentage = count / max(successful, 1) * 100
            report += f"\n• {category}: {count} files ({percentage:.1f}%)"

        if config.get("preview_mode"):
            report += (
                f"\n\n💡 This was a preview on {total} files."
                f"\nRun the full categorization to process all files."
            )

        QMessageBox.information(parent_widget, "Categorization Results", report)
