# controllers/scan_controller.py
"""
Scan Controller with integrated metadata extraction and thumbnail generation.
"""

from typing import Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot
from ai_content_classifier.services.metadata.metadata_service import MetadataService
from ai_content_classifier.services.file.scan_pipeline_service import (
    ScanPipelineService,
)
from ai_content_classifier.services.file.scanners.local_filesystem_scanner import (
    LocalFilesystemScanner,
)
from ai_content_classifier.services.file.scan_models import ScanProgress
from ai_content_classifier.services.thumbnail.thumbnail_service import ThumbnailService
from ai_content_classifier.models.config_models import ConfigKey


class ScanController(QObject):
    """
    Scan Controller that:
    - Scans files
    - Extracts metadata
    - Generates thumbnails
    - Saves everything to the database
    """

    # Qt Signals
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress_updated = pyqtSignal(object)  # ScanProgress
    progress_text = pyqtSignal(str)
    file_processed = pyqtSignal(
        str, bool, bool
    )  # (file_path, metadata_ok, thumbnail_ok)

    def __init__(
        self,
        directory: str,
        db_service,
        config_service,  # Add config_service here
        scan_config: Optional[dict] = None,
        metadata_service: Optional[MetadataService] = None,
        thumbnail_service: Optional[ThumbnailService] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.directory = directory
        self.db_service = db_service
        self.config_service = config_service  # Assign config_service
        self.scan_config = scan_config or {}

        # Services for metadata and thumbnails
        self.metadata_service = metadata_service or MetadataService()
        self.thumbnail_service = thumbnail_service or ThumbnailService()

        # Pipeline service
        self.local_scanner = LocalFilesystemScanner()  # Instantiate concrete scanner
        self.scan_pipeline_service = ScanPipelineService(
            scanner=self.local_scanner,
            db_service=self.db_service,  # Pass db_service
            metadata_service=self.metadata_service,  # Pass metadata_service
            thumbnail_service=self.thumbnail_service,  # Pass thumbnail_service
            batch_size=max(1, int(self.scan_config.get("batch_size", 100))),
            max_workers=max(1, int(self.scan_config.get("worker_threads", 4))),
        )
        # Backward-compatible alias used by older tests/callers.
        self.scan_service = self.scan_pipeline_service
        self._legacy_progress_estimation = False

        # State
        self.all_files = []
        self.current_progress = None
        self.processing_stats = {
            "files_found": 0,
            "metadata_extracted": 0,
            "thumbnails_generated": 0,
            "errors": 0,
        }

        # Timer for regular updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._emit_current_progress)

    @pyqtSlot()
    def run(self):
        """Executes the scan with full extraction."""
        try:
            self.progress_text.emit(f"🔍 Starting scan in {self.directory}...")

            # Retrieve allowed extensions based on the scan configuration.
            allowed_extensions = self._build_allowed_extensions()
            if allowed_extensions:
                self.progress_text.emit(
                    f"📄 Extensions searched: {', '.join(allowed_extensions)}"
                )
            else:
                self.progress_text.emit("📄 Extensions searched: all file types")

            # Start the update timer
            self.update_timer.start(1000)

            # Backward compatibility: support old scan_service API in tests/legacy callers.
            if hasattr(self.scan_service, "scan_and_process"):
                self._legacy_progress_estimation = True
                processed_files = self.scan_service.scan_and_process(
                    directory=self.directory,
                    progress_callback=self._on_scan_progress,
                    file_processed_callback=self.file_processed.emit,
                    allowed_extensions=allowed_extensions,
                )
            else:
                self._legacy_progress_estimation = False
                processed_files = self.scan_pipeline_service.run_pipeline(
                    directory=self.directory,
                    allowed_extensions=allowed_extensions,
                    progress_callback=self._on_scan_progress,
                    file_processed_callback=self.file_processed.emit,
                )
            self.all_files = processed_files  # Update all_files with processed files

            self.update_timer.stop()

            # Final report (stats are managed by the pipeline and passed via progress_callback)
            # We need to get the final stats from the last progress update
            final_progress = (
                self.current_progress
            )  # Assuming _on_scan_progress updates this
            if final_progress:
                stats = {
                    "files_found": final_progress.files_found,
                    "metadata_extracted": final_progress.metadata_extracted,
                    "thumbnails_generated": final_progress.thumbnails_generated,
                    "errors": final_progress.errors,
                }
                self.progress_text.emit(
                    f"✅ Scan complete: {stats['files_found']} files | "
                    f"📊 {stats['metadata_extracted']} metadata | "
                    f"🖼️ {stats['thumbnails_generated']} thumbnails | "
                    f"❌ {stats['errors']} errors"
                )
            else:
                self.progress_text.emit(
                    "✅ Scan complete. No detailed stats available."
                )

            # Emit the result
            self.progress_text.emit(
                f"📤 Emitting result signal with {len(self.all_files)} files"
            )
            self.result.emit(self.all_files)

        except Exception as e:
            self.update_timer.stop()
            self.progress_text.emit(f"💥 Fatal error: {str(e)}")
            self.error.emit((e,))
        finally:
            self.finished.emit()

    def _on_scan_progress(self, progress: ScanProgress):
        """Service callback - converts to Qt signals."""
        if (
            (
                self._legacy_progress_estimation
                or self.scan_service is not self.scan_pipeline_service
            )
            and hasattr(progress, "estimated_total_files")
            and getattr(progress, "estimated_total_files", 0) <= 0
            and hasattr(progress, "files_found")
        ):
            progress.estimated_total_files = int(getattr(progress, "files_found", 0))
        self.current_progress = progress
        self.progress_updated.emit(progress)

    def _emit_current_progress(self):
        """Emits current progress (called by Qt timer)."""
        if self.current_progress:
            self.progress_updated.emit(self.current_progress)

    def cancel_scan(self):
        """Cancels the ongoing scan."""
        if hasattr(self.scan_service, "cancel"):
            self.scan_service.cancel()
        elif hasattr(self.scan_service, "cancel_scan"):
            self.scan_service.cancel_scan()
        else:
            self.scan_pipeline_service.cancel()  # Call cancel on the new pipeline service
        self.progress_text.emit("🛑 Scan cancellation requested...")

    def _normalize_extensions(self, extensions) -> list[str]:
        """Normalizes extension values to lowercase '.ext' strings."""
        normalized: list[str] = []
        if not extensions:
            return normalized

        if isinstance(extensions, str):
            raw_values = [v.strip() for v in extensions.split(",") if v.strip()]
        else:
            raw_values = list(extensions)

        for ext in raw_values:
            ext_str = str(ext).strip().lower()
            if not ext_str:
                continue
            if not ext_str.startswith("."):
                ext_str = f".{ext_str}"
            normalized.append(ext_str)

        return normalized

    def _build_allowed_extensions(self) -> list[str]:
        """Builds allowed extensions from scan config and global settings."""
        file_types = self.scan_config.get("file_types", {}) or {}

        selected_groups: list[tuple[bool, ConfigKey]] = [
            (file_types.get("documents", True), ConfigKey.DOCUMENT_EXTENSIONS),
            (file_types.get("images", True), ConfigKey.IMAGE_EXTENSIONS),
            (file_types.get("videos", False), ConfigKey.VIDEO_EXTENSIONS),
            (file_types.get("audio", False), ConfigKey.AUDIO_EXTENSIONS),
        ]

        allowed_extensions: set[str] = set()
        for enabled, config_key in selected_groups:
            if enabled:
                allowed_extensions.update(
                    self._normalize_extensions(self.config_service.get(config_key))
                )

        # "Others" means no extension filtering: scan everything.
        if file_types.get("others", False):
            return []

        # Optional user-provided custom extensions.
        custom_extensions = self.scan_config.get("custom_extensions", []) or []
        allowed_extensions.update(self._normalize_extensions(custom_extensions))

        # Safety fallback if nothing is selected.
        if not allowed_extensions:
            allowed_extensions.update(
                self._normalize_extensions(
                    self.config_service.get(ConfigKey.DOCUMENT_EXTENSIONS)
                )
            )
            allowed_extensions.update(
                self._normalize_extensions(
                    self.config_service.get(ConfigKey.IMAGE_EXTENSIONS)
                )
            )

        return sorted(allowed_extensions)
