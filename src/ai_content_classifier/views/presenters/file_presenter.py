# presenters/file_presenter.py - CORRECTED VERSION
"""
File Presenter - Presentation and display of files in the interface.
CORRECTED: Uses the correct ThumbnailService API and centralized file type service.
"""

import os
import sys
from typing import Any, Dict, List, Optional, Tuple

from ai_content_classifier.core.logger import get_logger
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from ai_content_classifier.services.content_database_service import (
    ContentDatabaseService,
)
from ai_content_classifier.services.file.file_type_service import is_image_file
from ai_content_classifier.services.metadata.metadata_service import MetadataService
from ai_content_classifier.services.shared.cache_runtime import get_cache_runtime
from ai_content_classifier.views.main_window import MainWindow
from ai_content_classifier.views.widgets.dialogs.file.file_details_dialog import (
    FileDetailsDialog,
)

from ai_content_classifier.services.thumbnail.thumbnail_service import ThumbnailService

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional import safety
    Image = None


class FilePresenter(QObject):
    """
    Presenter for file display.

    This presenter manages everything related to displaying files
    in the user interface, including thumbnails and filters.
    """

    # Signals emitted by the presenter
    file_selected = pyqtSignal(str)  # File selected
    thumbnail_generated = pyqtSignal(str, str)  # (file_path, thumbnail_path)
    display_updated = pyqtSignal(int)  # Number of displayed files

    _file_data_ready = pyqtSignal(int, list)  # (request_id, file_data)
    _file_data_error = pyqtSignal(int, str)  # (request_id, error_message)

    def __init__(
        self, main_window: MainWindow, db_service: ContentDatabaseService, parent=None
    ):
        super().__init__(parent)
        self.logger = get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        self.main_window = main_window
        self.db_service = db_service
        self.thumbnail_service: Optional[ThumbnailService] = None
        self.metadata_service: Optional[MetadataService] = None

        # Current display state
        self.current_files: List[Tuple[str, str]] = []  # (file_path, directory)
        self.displayed_files: List[Tuple[str, str]] = []

        # Cache of generated thumbnails
        self._cache_runtime = get_cache_runtime()
        self.thumbnail_cache = self._cache_runtime.memory_cache(
            "ui:file_presenter:thumbnails",
            default_ttl=1800,
        )
        self._file_data_worker: Optional["_FileDataWorker"] = None
        self._file_data_request_id = 0
        self._async_threshold = 1000

        self._file_data_ready.connect(self._on_file_data_ready)
        self._file_data_error.connect(self._on_file_data_error)
        self._details_dialog: Optional[FileDetailsDialog] = None
        self._details_dialog_path: Optional[str] = None

        self.logger.debug("File Presenter initialized")

    def set_thumbnail_service(self, thumbnail_service: ThumbnailService):
        """
        Configures the thumbnail generation service.

        Args:
            thumbnail_service: Service for generating thumbnails
        """
        self.thumbnail_service = thumbnail_service
        self.logger.debug("Thumbnail service configured")

    def set_metadata_service(self, metadata_service: MetadataService):
        """
        Configures the metadata service.

        Args:
            metadata_service: Service for metadata extraction
        """
        self.metadata_service = metadata_service
        self.logger.debug("Metadata service configured")

    def update_file_list(self, file_list: List[Tuple[str, str]]):
        """
        Updates the complete list of files.

        Args:
            file_list: List of files (file_path, directory)
        """
        self.logger.info(
            f"📥 FilePresenter.update_file_list RECEIVED: {len(file_list)} files"
        )
        self.logger.debug(
            f"FilePresenter.update_file_list - file_list content (first 3): {[f[0] for f in file_list[:3]]}"
        )

        if len(file_list) > 0:
            # Show some examples
            for i, (file_path, directory) in enumerate(file_list[:3]):
                self.logger.info(
                    f"📋 FilePresenter file {i + 1}: {os.path.basename(file_path)}"
                )
        else:
            self.logger.warning("❌ FilePresenter: received file_list is empty!")

        try:
            # Invalidate any in-flight async build from previous datasets.
            self._invalidate_async_updates()

            # Save the new list
            self.current_files = file_list

            # Apply the current filter
            self.displayed_files = self._apply_current_filter(file_list)
            self.logger.info(
                f"📋 After filtering in FilePresenter.update_file_list: {len(self.displayed_files)} files to display"
            )

            # Update the display in the interface
            self._update_ui_display()

            self.logger.info(
                f"✅ FilePresenter finished update_file_list request: {len(self.displayed_files)} visible files"
            )

        except Exception as e:
            self.logger.error(f"Error updating list: {e}", exc_info=True)

    def _apply_current_filter(
        self, file_list: List[Tuple[str, str]]
    ) -> List[Tuple[str, str]]:
        """
        This method no longer applies filters directly. It simply returns the file_list
        as filtering is now handled cumulatively by FileManager.
        """
        self.logger.debug(
            "FilePresenter._apply_current_filter: Filtering handled by FileManager."
        )
        return file_list

    def refresh_file_list(self):
        """Refreshes the file display from the database."""
        self.logger.debug("Refreshing file list")

        try:
            self._invalidate_async_updates()
            # Re-apply the current filter to the full list of files
            self.displayed_files = self._apply_current_filter(self.current_files)
            self._update_ui_display()

        except Exception as e:
            self.logger.error(f"Error refreshing: {e}", exc_info=True)

    def _update_ui_display(self):
        """Updates the display in the interface widgets."""
        if len(self.displayed_files) >= self._async_threshold:
            self._update_ui_display_async()
            return

        try:
            # Small lists are prepared synchronously for simplicity.
            file_data = self._build_file_data(self.displayed_files)
            self.logger.info(
                f"🖥️ _update_ui_display: Preparing {len(file_data)} files for UI"
            )

            # Update widgets (grid and list)
            if hasattr(self.main_window, "set_file_data"):
                self.logger.info(
                    f"📤 Calling main_window.set_file_data with {len(file_data)} files"
                )
                self.main_window.set_file_data(file_data)
                self.logger.info("✅ main_window.set_file_data called successfully")
            else:
                self.logger.error("❌ main_window does not have set_file_data method!")

            self.display_updated.emit(len(self.displayed_files))
            self._update_details_dialog_navigation()
            self.logger.info(f"✅ Interface updated with {len(file_data)} files")

        except Exception as e:
            self.logger.error(f"💥 Error updating UI: {e}", exc_info=True)

    def _update_ui_display_async(self):
        """Builds file display data in a background thread to keep UI responsive."""
        self._stop_file_data_worker()
        self._file_data_request_id += 1
        request_id = self._file_data_request_id

        self.logger.info(
            f"🧵 Starting background file data build for {len(self.displayed_files)} files (request {request_id})"
        )

        self._file_data_worker = _FileDataWorker(
            request_id=request_id,
            displayed_files=list(self.displayed_files),
            db_service=self.db_service,
        )
        self._file_data_worker.file_data_ready.connect(self._file_data_ready.emit)
        self._file_data_worker.file_data_error.connect(self._file_data_error.emit)
        self._file_data_worker.finished.connect(self._on_file_data_worker_finished)
        self._file_data_worker.start()

    def _build_file_data(
        self, files: List[Tuple[str, str]]
    ) -> List[Tuple[str, str, str, str]]:
        """Builds UI tuples (path, directory, category, content_type)."""
        file_data: List[Tuple[str, str, str, str]] = []
        for file_path, directory in files:
            content_item = self.db_service.get_content_by_path(file_path)
            category = content_item.category if content_item else "Uncategorized"
            content_type = content_item.content_type if content_item else "Unknown"
            file_data.append((file_path, directory, category, content_type))
        return file_data

    def _on_file_data_ready(self, request_id: int, file_data: list):
        """Applies async-built file data if it matches the latest request."""
        if request_id != self._file_data_request_id:
            self.logger.debug(
                f"Ignoring stale file data result for request {request_id}"
            )
            return

        try:
            if hasattr(self.main_window, "set_file_data"):
                self.main_window.set_file_data(file_data)
            self.display_updated.emit(len(self.displayed_files))
            self.logger.info(
                f"✅ Async UI update completed with {len(file_data)} files"
            )
        except Exception as e:
            self.logger.error(f"Error applying async file data: {e}", exc_info=True)

    def _on_file_data_error(self, request_id: int, error_message: str):
        """Logs async worker errors for the current request."""
        if request_id == self._file_data_request_id:
            self.logger.error(f"Async file data build failed: {error_message}")

    def _on_file_data_worker_finished(self):
        """Cleans worker reference after completion."""
        sender_worker = self.sender()
        if sender_worker is self._file_data_worker:
            self._file_data_worker = None

    def _stop_file_data_worker(self):
        """Stops any running background worker."""
        if self._file_data_worker and self._file_data_worker.isRunning():
            self._file_data_worker.requestInterruption()
            self._file_data_worker.wait(1000)
            if self._file_data_worker.isRunning():
                self.logger.warning("Background file data worker did not stop cleanly")
        self._file_data_worker = None

    def _invalidate_async_updates(self):
        """Cancels and invalidates any asynchronous UI build request."""
        self._file_data_request_id += 1
        self._stop_file_data_worker()

    def get_or_create_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Generates or retrieves metadata for a file."""
        if self.metadata_service:
            return self.metadata_service.get_all_metadata(file_path)
        return None

    def get_or_create_thumbnail(self, file_path: str) -> Optional[str]:
        """
        Generates or retrieves a thumbnail for a file.

        ⚠️ CORRECTED VERSION: Uses the correct ThumbnailService API and centralized file type service

        Args:
            file_path: Path to the file

        Returns:
            Path to the thumbnail or None if it cannot be generated or if it's not an image
        """
        try:
            # === 1. FIRST, CHECK IF IT'S AN IMAGE ===
            if not is_image_file(file_path):
                # It's not an image, do not try to create a thumbnail
                return None

            # Skip generated thumbnails to avoid recursive thumbnail chains.
            if self._is_generated_thumbnail_file(file_path):
                return None

            # === 2. CHECK CACHE FIRST ===
            thumbnail_path = self.thumbnail_cache.get(file_path, default=None)
            if thumbnail_path:
                if os.path.exists(thumbnail_path):
                    return thumbnail_path
                else:
                    # Clean cache if file no longer exists
                    self.thumbnail_cache.delete(file_path)

            # === 3. CHECK IF SOURCE FILE EXISTS ===
            if not os.path.exists(file_path):
                self.logger.warning(f"File not found for thumbnail: {file_path}")
                return None

            # === 4. USE THE THUMBNAIL SERVICE WITH THE CORRECT API ===
            if self.thumbnail_service:
                # ✅ USE create_thumbnail() instead of get_or_create_thumbnail()
                thumbnail_result = self.thumbnail_service.create_thumbnail(
                    image_path=file_path,  # Correct parameter
                    size=None,  # Uses default size
                )

                # Check the result
                if (
                    thumbnail_result
                    and hasattr(thumbnail_result, "success")
                    and thumbnail_result.success
                ):
                    # Extract thumbnail path from the result
                    thumbnail_path = None

                    # ThumbnailResult can have different attributes depending on implementation
                    if (
                        hasattr(thumbnail_result, "thumbnail_path")
                        and thumbnail_result.thumbnail_path
                    ):
                        thumbnail_path = thumbnail_result.thumbnail_path
                    elif (
                        hasattr(thumbnail_result, "thumbnail")
                        and thumbnail_result.thumbnail
                    ):
                        # If it's an Image object, it needs to be saved
                        thumbnail_path = self._save_thumbnail_to_disk(
                            thumbnail_result.thumbnail, file_path
                        )

                    if thumbnail_path and os.path.exists(thumbnail_path):
                        # Cache
                        self.thumbnail_cache.set(file_path, thumbnail_path)

                        # Emit signal
                        self.thumbnail_generated.emit(file_path, thumbnail_path)

                        self.logger.debug(f"Thumbnail generated: {thumbnail_path}")
                        return thumbnail_path
                    else:
                        self.logger.warning(
                            f"Thumbnail generated but path not found for: {file_path}"
                        )
                else:
                    self.logger.debug(f"Thumbnail generation failed for: {file_path}")
                    if hasattr(thumbnail_result, "error_message"):
                        self.logger.debug(f"Error: {thumbnail_result.error_message}")

            # === 5. FALLBACK ===
            return self._generate_fallback_thumbnail(file_path)

        except Exception as e:
            self.logger.warning(f"Error generating thumbnail for {file_path}: {e}")
            return None

    def _save_thumbnail_to_disk(
        self, thumbnail_obj, original_file_path: str
    ) -> Optional[str]:
        """
        Saves a thumbnail object to disk.

        Args:
            thumbnail_obj: PIL.Image or QPixmap object
            original_file_path: Path to the original file

        Returns:
            Path to the saved thumbnail file or None
        """
        try:
            if self._is_generated_thumbnail_file(original_file_path):
                return original_file_path

            # Create a file name for the thumbnail
            base_name = os.path.splitext(os.path.basename(original_file_path))[0]
            base_name = self._normalize_thumbnail_basename(base_name)
            path_hash = self._thumbnail_identity_hash(original_file_path)

            thumbnail_dir = self._resolve_thumbnail_cache_dir()

            # Create directory if necessary
            os.makedirs(thumbnail_dir, exist_ok=True)

            thumbnail_path = os.path.join(
                thumbnail_dir, f"{base_name}_{path_hash}_thumb.jpg"
            )

            # Save according to object type
            if Image is not None and isinstance(thumbnail_obj, Image.Image):
                pil_img = thumbnail_obj
                # JPEG does not support alpha channels.
                if pil_img.mode in ("RGBA", "LA", "P"):
                    pil_img = pil_img.convert("RGB")
                pil_img.save(thumbnail_path, "JPEG", quality=85)
            elif hasattr(thumbnail_obj, "save"):
                # QPixmap-like object
                thumbnail_obj.save(thumbnail_path, "JPG", quality=85)
            else:
                self.logger.warning(
                    f"Unsupported thumbnail type: {type(thumbnail_obj)}"
                )
                return None

            return thumbnail_path

        except Exception as e:
            self.logger.error(f"Error saving thumbnail: {e}")
            return None

    @staticmethod
    def _thumbnail_identity_hash(file_path: str) -> str:
        """Return a short, stable hash for thumbnail file naming."""
        import hashlib

        return hashlib.md5(
            file_path.encode("utf-8"), usedforsecurity=False
        ).hexdigest()[:12]

    @staticmethod
    def _resolve_thumbnail_cache_dir() -> str:
        """Return a centralized, user-writable thumbnail cache directory."""
        app_folder = "Javis"
        if sys.platform.startswith("win"):
            base_dir = os.getenv(
                "LOCALAPPDATA",
                os.getenv("APPDATA", str(os.path.expanduser("~\\AppData\\Local"))),
            )
        elif sys.platform == "darwin":
            base_dir = os.path.expanduser("~/Library/Caches")
        else:
            base_dir = os.getenv("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))

        return os.path.join(base_dir, app_folder, "thumbnails")

    @staticmethod
    def _is_generated_thumbnail_file(file_path: str) -> bool:
        """Return True if the path points to an app-generated thumbnail file."""
        normalized = file_path.replace("\\", "/").lower()
        if "/.thumbnails/" in normalized:
            return True
        filename = os.path.basename(file_path).lower()
        name, _ = os.path.splitext(filename)
        return name.endswith("_thumb")

    @staticmethod
    def _normalize_thumbnail_basename(base_name: str) -> str:
        """Remove repeated _thumb suffixes from a base filename."""
        normalized = base_name
        while normalized.lower().endswith("_thumb"):
            normalized = normalized[:-6]
        return normalized or "thumbnail"

    def _generate_fallback_thumbnail(self, file_path: str) -> Optional[str]:
        """
        Generates a simple fallback thumbnail.

        Args:
            file_path: Path to the file

        Returns:
            Path to the thumbnail or None
        """
        try:
            # For now, return None
            # A complete implementation could generate an icon based on the extension
            return None

        except Exception as e:
            self.logger.warning(f"Error generating fallback thumbnail: {e}")
            return None

    def handle_file_selection(self, file_path: str):
        """
        Handles file selection.

        Args:
            file_path: Path to the selected file
        """
        self.logger.debug(f"File selected: {file_path}")

        # Emit selection signal
        self.file_selected.emit(file_path)

    def handle_file_selection_for_preview(self, index: Any, file_path: str):
        """
        Handles file selection for preview, fetching all necessary details.

        Args:
            index: The QModelIndex of the selected item (not directly used here, but passed by signal)
            file_path: The full path to the selected file
        """
        self.logger.info(f"Preparing preview for: {file_path}")

        try:
            file_details = self._build_file_details(file_path)

            # 5. Update the adaptive preview widget
            if (
                hasattr(self.main_window, "adaptive_preview_widget")
                and self.main_window.adaptive_preview_widget
            ):
                self.main_window.adaptive_preview_widget.set_file_details(file_details)
                self.logger.info(f"Preview updated for {file_path}")
            else:
                self.logger.warning(
                    "adaptive_preview_widget not available in MainWindow."
                )

        except Exception as e:
            self.logger.error(
                f"Error preparing file preview for {file_path}: {e}", exc_info=True
            )

    def open_file_details_dialog(self, file_path: str) -> None:
        """Opens the full file details dialog for the activated file."""
        try:
            file_details = self._build_file_details(file_path)
            if self._details_dialog is None:
                self._details_dialog = FileDetailsDialog(self.main_window)
                self._details_dialog.previous_requested.connect(
                    self._show_previous_file_details
                )
                self._details_dialog.next_requested.connect(
                    self._show_next_file_details
                )
                self._details_dialog.clear_category_requested.connect(
                    self._on_clear_category_requested
                )
            self._details_dialog_path = file_path
            self._details_dialog.set_file_details(file_details)
            self._update_details_dialog_navigation()
            self._details_dialog.show()
            self._details_dialog.raise_()
            self._details_dialog.activateWindow()
        except Exception as exc:
            self.logger.error(
                f"Error opening file details dialog for {file_path}: {exc}",
                exc_info=True,
            )

    def _on_clear_category_requested(self, file_path: str) -> None:
        """Clears category for a single file from the details dialog."""
        normalized_path = str(file_path or "").strip()
        if not normalized_path:
            return

        try:
            updated_item = self.db_service.clear_content_category(normalized_path)
            if not updated_item:
                self.logger.warning(
                    f"Unable to clear category: file not found in DB ({normalized_path})"
                )
                return

            if self._details_dialog and self._details_dialog_path == normalized_path:
                self._details_dialog.set_file_details(
                    self._build_file_details(normalized_path)
                )

            file_manager = getattr(self.main_window, "file_manager", None)
            if file_manager and hasattr(file_manager, "refresh_and_emit_visible_files"):
                file_manager.refresh_and_emit_visible_files()
            else:
                # Fallback for tests/legacy hosts without FileManager wiring.
                self.refresh_file_list()

            self.logger.info(f"Category cleared for file: {normalized_path}")
        except Exception as exc:
            self.logger.error(
                f"Error clearing category for file {normalized_path}: {exc}",
                exc_info=True,
            )

    def _build_file_details(self, file_path: str) -> Dict[str, Any]:
        metadata = self.get_or_create_metadata(file_path)

        content_item = self.db_service.get_content_by_path(file_path)
        content_type = content_item.content_type if content_item else "unknown"
        classification_metadata = (
            getattr(content_item, "content_metadata", {}) or {} if content_item else {}
        )
        classification_payload = classification_metadata.get("classification", {})
        confidence = None
        if content_item:
            confidence = getattr(content_item, "classification_confidence", None)
        if confidence is None:
            confidence = classification_payload.get("confidence")
        classification = {
            "category": content_item.category if content_item else "Uncategorized",
            "tags": content_item.tags if content_item and content_item.tags else [],
            "confidence": confidence,
        }

        thumbnail_path = self.get_or_create_thumbnail(file_path)
        return {
            "file_path": file_path,
            "metadata": metadata,
            "content_type": content_type,
            "thumbnail_path": thumbnail_path,
            "classification": classification,
        }

    def _show_previous_file_details(self) -> None:
        self._navigate_details_dialog(-1)

    def _show_next_file_details(self) -> None:
        self._navigate_details_dialog(1)

    def _navigate_details_dialog(self, offset: int) -> None:
        file_paths = self._visible_file_paths()
        if not self._details_dialog_path or not file_paths:
            return
        try:
            current_index = file_paths.index(self._details_dialog_path)
        except ValueError:
            return
        target_index = current_index + offset
        if 0 <= target_index < len(file_paths):
            self.open_file_details_dialog(file_paths[target_index])

    def _update_details_dialog_navigation(self) -> None:
        if self._details_dialog is None:
            return
        file_paths = self._visible_file_paths()
        if not self._details_dialog_path or self._details_dialog_path not in file_paths:
            self._details_dialog.set_navigation_state(False, False)
            return
        current_index = file_paths.index(self._details_dialog_path)
        self._details_dialog.set_navigation_state(
            has_previous=current_index > 0,
            has_next=current_index < len(file_paths) - 1,
        )

    def _visible_file_paths(self) -> List[str]:
        visible_rows = (
            getattr(self.main_window, "current_files", None) or self.displayed_files
        )
        file_paths: List[str] = []
        for item in visible_rows:
            if isinstance(item, tuple) and item:
                file_paths.append(item[0])
        return file_paths

    def clear_cache(self):
        """Clears the thumbnail cache."""
        self.thumbnail_cache.clear()
        self.logger.debug("Thumbnail cache cleared")

    def update_filter_chips(self, active_filters: Dict[str, Any]):
        """
        Updates the FilterChipsContainer with the currently active filters.

        Args:
            active_filters: Dictionary of active filters from FileManager
        """
        self.logger.debug(
            f"📥 FilePresenter.update_filter_chips RECEIVED: {active_filters}"
        )

        filters_to_display = []

        # Add file type filter
        file_type = active_filters.get("file_type")
        if file_type and file_type[0] != "All Files":
            filters_to_display.append(
                {
                    "id": f"file_type_{file_type[0]}",
                    "label": file_type[0],
                    "type": "file_type",
                    "selected": True,
                    "removable": True,
                }
            )

        # Add category filters
        for category in active_filters.get("category", []):
            filters_to_display.append(
                {
                    "id": f"category_{category}",
                    "label": category,
                    "type": "category",
                    "selected": True,
                    "removable": True,
                }
            )

        # Add year filters
        for year in active_filters.get("year", []):
            filters_to_display.append(
                {
                    "id": f"year_{year}",
                    "label": str(year),
                    "type": "date",  # Using 'date' type for years
                    "selected": True,
                    "removable": True,
                }
            )

        # Add extension filters
        for ext in active_filters.get("extension", []):
            filters_to_display.append(
                {
                    "id": f"extension_{ext}",
                    "label": ext,
                    "type": "extension",
                    "selected": True,
                    "removable": True,
                }
            )

        # Update active filters bar if present.
        if (
            hasattr(self.main_window, "active_filters_bar")
            and self.main_window.active_filters_bar
        ):
            if hasattr(self.main_window.active_filters_bar, "set_filters"):
                self.main_window.active_filters_bar.set_filters(filters_to_display)
            else:
                self.main_window.active_filters_bar.clear_all_filters()

        # Always update sidebar if present.
        if (
            hasattr(self.main_window, "filter_sidebar")
            and self.main_window.filter_sidebar
        ):
            self.main_window.filter_sidebar.set_filters(filters_to_display)

        self.logger.debug(
            f"Updated filter chips with {len(filters_to_display)} active filters."
        )


class _FileDataWorker(QThread):
    """Background worker building file data tuples for large lists."""

    file_data_ready = pyqtSignal(int, list)  # (request_id, file_data)
    file_data_error = pyqtSignal(int, str)  # (request_id, error_message)

    def __init__(
        self,
        request_id: int,
        displayed_files: List[Tuple[str, str]],
        db_service: ContentDatabaseService,
    ):
        super().__init__()
        self.request_id = request_id
        self.displayed_files = displayed_files
        self.db_service = db_service

    def run(self):
        try:
            file_data: List[Tuple[str, str, str, str]] = []
            for file_path, directory in self.displayed_files:
                if self.isInterruptionRequested():
                    return
                content_item = self.db_service.get_content_by_path(file_path)
                category = content_item.category if content_item else "Uncategorized"
                content_type = content_item.content_type if content_item else "Unknown"
                file_data.append((file_path, directory, category, content_type))
            self.file_data_ready.emit(self.request_id, file_data)
        except Exception as e:
            self.file_data_error.emit(self.request_id, str(e))
