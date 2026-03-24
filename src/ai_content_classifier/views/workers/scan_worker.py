# workers/scan_worker.py
"""
Scan Worker - Qt Worker to perform directory scanning with metadata and thumbnails.

This worker handles:
- Recursively scanning a directory
- Extracting metadata from each file
- Generating thumbnails for images
- Adding files to the database with all information
- Reporting real-time progress
"""

import os
import time
from typing import Dict, List, Optional, Tuple

from ai_content_classifier.controllers.scan_controller import ScanController
from ai_content_classifier.core.logger import get_logger
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot
from ai_content_classifier.services.config_service import ConfigService
from ai_content_classifier.services.content_database_service import (
    ContentDatabaseService,
)
from ai_content_classifier.services.metadata.metadata_service import MetadataService
from ai_content_classifier.services.file.scanners.base_scanner import ScanProgress


from ai_content_classifier.services.thumbnail.thumbnail_service import ThumbnailService


class ScanWorker(QObject):
    """
    Qt Worker for scanning directories with full processing.

    This worker performs the scan in the background with automatic
    metadata extraction and thumbnail generation.
    """

    # Signals emitted by the worker
    finished = pyqtSignal()
    error = pyqtSignal(tuple)  # (exception,)
    result = pyqtSignal(object)  # List of found files
    progress_updated = pyqtSignal(object)  # ScanProgress
    progress_text = pyqtSignal(str)  # Textual progress message
    file_found = pyqtSignal(str, str)  # (file_path, directory)
    file_processed = pyqtSignal(
        str, bool, bool
    )  # (file_path, metadata_ok, thumbnail_ok)

    def __init__(
        self,
        directory: str,
        db_service: ContentDatabaseService,
        config_service: ConfigService,
        scan_config: Optional[Dict] = None,
        metadata_service: Optional[MetadataService] = None,
        thumbnail_service: Optional[ThumbnailService] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.logger = get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        self.directory = directory
        self.db_service = db_service
        self.config_service = config_service
        self.scan_config = scan_config or {}

        # Services for advanced processing
        self.metadata_service = metadata_service or MetadataService()
        self.thumbnail_service = thumbnail_service or ThumbnailService()

        # The controller does the real work
        self.controller = ScanController(
            directory=directory,
            db_service=db_service,
            config_service=config_service,
            scan_config=self.scan_config,
            metadata_service=self.metadata_service,
            thumbnail_service=self.thumbnail_service,
        )

        # Scan state
        self._is_cancelled = False
        self._start_time = 0
        self._files_found: List[Tuple[str, str]] = []  # (file_path, directory)
        self._current_progress = ScanProgress()

        # Connect controller signals
        self._connect_controller_signals()

        # Timer for regular progress updates
        self._progress_timer = QTimer()
        self._progress_timer.timeout.connect(self._emit_progress_update)
        self._progress_timer.setInterval(500)  # Update every 500ms

        self.logger.info(
            f"ScanWorker initialized with services: metadata={bool(metadata_service)}, thumbnail={bool(thumbnail_service)}"
        )

    def _connect_controller_signals(self):
        """Connects controller signals to worker signals."""
        self.logger.info("🔗 Connecting ScanController → ScanWorker signals...")

        self.controller.finished.connect(self.finished.emit)
        self.controller.error.connect(self.error.emit)
        self.controller.result.connect(self.result.emit)  # 🔍 CRUCIAL CONNECTION
        self.controller.progress_updated.connect(self.progress_updated.emit)
        self.controller.progress_text.connect(self.progress_text.emit)
        self.controller.file_processed.connect(self.file_processed.emit)

        # Also connect for our compatibility
        self.controller.result.connect(self._on_scan_result)
        self.controller.progress_updated.connect(self._on_progress_update)

        self.logger.info("✅ ScanController → ScanWorker signals connectd")

    @pyqtSlot()
    def run(self):
        """
        Main worker method - delegates to the controller.
        """
        try:
            self.logger.info(f"Starting scan of {self.directory}")
            self._start_time = time.time()
            self._is_cancelled = False

            # Start progress timer
            self._progress_timer.start()

            # Initial message
            self.progress_text.emit("🚀 Initializing full scan...")

            # Delegate to the controller
            self.controller.run()

        except Exception as e:
            self.logger.error(f"Error in scan worker: {e}", exc_info=True)
            self.error.emit((e,))
        finally:
            self._progress_timer.stop()

    def _on_scan_result(self, file_list: List[Tuple[str, str]]):
        """Handles scan result."""
        # 🔍 CRUCIAL DEBUG: Check reception in ScanWorker
        self.logger.info(
            f"📥 ScanWorker RECEIVES from controller: {len(file_list)} files"
        )

        if len(file_list) > 0:
            # Show some examples
            for i, (file_path, directory) in enumerate(file_list[:3]):
                self.logger.info(
                    f"📋 ScanWorker file {i + 1}: {os.path.basename(file_path)}"
                )
        else:
            self.logger.warning(
                "❌ ScanWorker: file_list received from controller is empty!"
            )

        self._files_found = file_list
        self.logger.info(
            f"📂 ScanWorker: _files_found updated with {len(file_list)} files"
        )

    def _on_progress_update(self, progress: ScanProgress):
        """Updates local progress."""
        self._current_progress = progress

    @pyqtSlot()
    def _emit_progress_update(self):
        """
        Periodic progress emission.
        (Kept for compatibility, but the controller already emits its progress)
        """
        if self._current_progress:
            # Add elapsed time
            if self._start_time > 0:
                self._current_progress.elapsed_time = time.time() - self._start_time

    def cancel_scan(self):
        """
        Requests scan cancellation.
        """
        self.logger.info("Scan cancellation requested")
        self._is_cancelled = True

        # Delegate to the controller
        if hasattr(self.controller, "cancel_scan"):
            self.controller.cancel_scan()

    @property
    def is_cancelled(self) -> bool:
        """Checks if the scan is cancelled."""
        return self._is_cancelled

    @property
    def files_found(self) -> List[Tuple[str, str]]:
        """Returns the list of found files."""
        return self._files_found
