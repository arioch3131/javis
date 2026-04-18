# services/file_operation_service.py
"""
File Operation Service.

This module provides a pure Python service for managing file-related operations
within the application. It encapsulates business logic for file scanning,
processing, open/remove operations, without any direct dependencies on Qt, making it highly
testable and reusable. Communication with higher layers is achieved through callbacks.
"""

import os
import shutil
import sys

from typing import Any, Callable, Dict, List, Optional, Tuple

from ai_content_classifier.core.logger import LoggableMixin

from ai_content_classifier.services.settings.config_service import ConfigService
from ai_content_classifier.services.database.content_database_service import (
    ContentDatabaseService,
)
from ai_content_classifier.services.file.operations import (
    FileOperationDataKey,
    OpenFileOperation,
    ProcessFileResultOperation,
    ProcessScanResultsOperation,
    RefreshFileListOperation,
    RemoveFilesFromDatabaseOperation,
)
from ai_content_classifier.services.file.types import (
    FileOperationCode,
    FilterType,
    FileOperationResult,
    FileProcessingResult,
    ScanStatistics,
)
from ai_content_classifier.services.filtering import (
    ContentFilterService,
    FilterCriterion,
)
from ai_content_classifier.services.metadata.metadata_service import MetadataService
from ai_content_classifier.services.shared.cache_runtime import get_cache_runtime
from ai_content_classifier.services.thumbnail.thumbnail_service import ThumbnailService


class FileOperationService(LoggableMixin):
    """
    A pure Python service dedicated to managing file system operations.

    This service encapsulates all core business logic related to file handling,
    including scanning directories, processing individual files (metadata extraction,
    thumbnail generation), and filtering file lists. It is designed to be independent
    of any UI framework (e.g., Qt) and communicates with other components via callbacks.

    Attributes:
        db_service (ContentDatabaseService): Service for interacting with the content database.
        settings_service (SettingsService): Service for managing application settings.
        metadata_service (MetadataService): Service for extracting file metadata.
        thumbnail_service (ThumbnailService): Service for generating file thumbnails.

    Callbacks:
        The service defines several optional callbacks (`_on_scan_started`, `_on_scan_progress`,
        etc.) that can be set by external components to receive notifications about
        the progress and results of file operations.
    """

    def __init__(
        self,
        db_service: ContentDatabaseService,
        config_service: ConfigService,
        metadata_service: Optional[MetadataService] = None,
        thumbnail_service: Optional[ThumbnailService] = None,
    ):
        """
        Initializes the `FileOperationService`.

        Args:
            db_service (ContentDatabaseService): The database service instance.
            settings_service (SettingsService): The settings service instance.
            metadata_service (Optional[MetadataService]): An optional metadata service instance.
                                                          If `None`, a default `MetadataService` will be created.
            thumbnail_service (Optional[ThumbnailService]): An optional thumbnail service instance.
                                                            If `None`, a default `ThumbnailService` will be created.
        """
        self.__init_logger__()

        self.db_service = db_service
        self.config_service = config_service
        self.metadata_service = metadata_service or MetadataService()
        self.thumbnail_service = thumbnail_service or ThumbnailService()

        # Internal state variables to keep track of current files, filters, and scan statistics.
        self._current_files: List[
            Tuple[str, str]
        ] = []  # Stores (file_path, directory) tuples.
        self._current_content_by_path: Dict[str, Any] = {}
        self._last_scan_stats = ScanStatistics()
        self._open_file_operation = OpenFileOperation(logger=self.logger)
        self._remove_from_db_operation = RemoveFilesFromDatabaseOperation(
            db_service=self.db_service,
            logger=self.logger,
        )
        self._refresh_file_list_operation = RefreshFileListOperation(
            db_service=self.db_service,
            logger=self.logger,
        )
        self._content_filter_service = ContentFilterService(
            db_service=self.db_service,
            logger=self.logger,
        )
        self._process_scan_results_operation = ProcessScanResultsOperation(
            logger=self.logger
        )
        self._process_file_result_operation = ProcessFileResultOperation(
            logger=self.logger
        )

        # Callbacks for notifying external components about events. These are not Qt signals.
        self._on_scan_started: Optional[Callable[[str], None]] = None
        self._on_scan_progress: Optional[Callable[[Any], None]] = None
        self._on_scan_completed: Optional[Callable[[List[Tuple[str, str]]], None]] = (
            None
        )
        self._on_scan_error: Optional[Callable[[str], None]] = None
        self._on_file_processed: Optional[Callable[[FileProcessingResult], None]] = None
        self._on_files_updated: Optional[Callable[[List[Tuple[str, str]]], None]] = None
        self._on_stats_updated: Optional[Callable[[ScanStatistics], None]] = None

        self.logger.info("FileOperationService initialized.")

    # === CALLBACK CONFIGURATION ===

    def set_callbacks(
        self,
        on_scan_started: Optional[Callable[[str], None]] = None,
        on_scan_progress: Optional[Callable[[Any], None]] = None,
        on_scan_completed: Optional[Callable[[List[Tuple[str, str]]], None]] = None,
        on_scan_error: Optional[Callable[[str], None]] = None,
        on_file_processed: Optional[Callable[[FileProcessingResult], None]] = None,
        on_files_updated: Optional[Callable[[List[Tuple[str, str]]], None]] = None,
        on_stats_updated: Optional[Callable[[ScanStatistics], None]] = None,
    ) -> None:
        """
        Configures the callback functions for various events within the service.

        These callbacks allow external components (e.g., UI elements) to react to
        changes and progress updates without direct coupling to the service's internal logic.
        """
        self._on_scan_started = on_scan_started
        self._on_scan_progress = on_scan_progress
        self._on_scan_completed = on_scan_completed
        self._on_scan_error = on_scan_error
        self._on_file_processed = on_file_processed
        self._on_files_updated = on_files_updated
        self._on_stats_updated = on_stats_updated

    # === SCAN OPERATIONS ===

    def process_scan_results(
        self, file_list: List[Tuple[str, str]]
    ) -> FileOperationResult:
        """
        Processes the results obtained from a directory scan.

        This method updates the service's internal state with the list of found files,
        updates scan statistics, and triggers relevant completion and update callbacks.

        Args:
            file_list (List[Tuple[str, str]]): A list of tuples, where each tuple contains
                                                the absolute file path and its directory.
        """
        try:
            operation_result = self._process_scan_results_operation.execute(file_list)
            if not operation_result.success:
                error_msg = (
                    operation_result.message or "Failed to process scan results."
                )
                self.logger.error(error_msg)
                if self._on_scan_error:
                    self._on_scan_error(error_msg)
                return operation_result
            result_data = operation_result.data or {}
            normalized_file_list = result_data.get(
                FileOperationDataKey.FILE_LIST.value,
                list(file_list or []),
            )

            # Update internal state with the new list of files.
            self._current_files = normalized_file_list
            self._current_content_by_path = result_data.get(
                FileOperationDataKey.CONTENT_BY_PATH.value, {}
            )
            self._last_scan_stats.files_found = int(
                result_data.get(
                    FileOperationDataKey.FILES_FOUND.value, len(normalized_file_list)
                )
            )

            # Notify registered callbacks about the completion and updates.
            if self._on_scan_completed:
                self._on_scan_completed(normalized_file_list)

            if self._on_files_updated:
                self._on_files_updated(normalized_file_list)

            if self._on_stats_updated:
                self._on_stats_updated(self._last_scan_stats)

            self.logger.info(
                f"Scan results processed: {len(normalized_file_list)} files."
            )
            return operation_result

        except Exception as e:
            error_msg = f"An error occurred while processing scan results: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            if self._on_scan_error:
                self._on_scan_error(error_msg)
            return FileOperationResult(
                success=False,
                code=FileOperationCode.UNKNOWN_ERROR,
                message=error_msg,
                data={},
            )

    def remove_files_from_database(self, file_paths: List[str]) -> FileOperationResult:
        """Removes the provided files from the content database only."""
        operation_result = self._remove_from_db_operation.execute(file_paths)
        if not operation_result.success:
            self.logger.error(
                operation_result.message or "Failed to remove files from database."
            )
            return operation_result
        result_data = operation_result.data or {}
        deleted_count = int(
            result_data.get(FileOperationDataKey.DELETED_COUNT.value, 0)
        )
        if deleted_count <= 0:
            return operation_result

        removed_paths = set(
            result_data.get(FileOperationDataKey.NORMALIZED_PATHS.value, [])
        )
        self._current_files = [
            (file_path, directory)
            for file_path, directory in self._current_files
            if file_path not in removed_paths
        ]
        self._last_scan_stats.files_found = len(self._current_files)

        if self._on_files_updated:
            self._on_files_updated(self._current_files)

        if self._on_stats_updated:
            self._on_stats_updated(self._last_scan_stats)

        self.logger.info(
            f"Removed {deleted_count} files from the database; {len(self._current_files)} remain in the current dataset."
        )
        return operation_result

    def open_file(self, file_path: str) -> FileOperationResult:
        """Open a file via the system default application."""
        return self._open_file_operation.execute(file_path)

    def process_file_result(
        self,
        file_path: str,
        metadata_ok: bool,
        thumbnail_ok: bool,
        error_message: Optional[str] = None,
    ) -> FileOperationResult:
        """
        Processes the outcome of an individual file processing operation.

        This method updates the scan statistics based on the success of metadata
        extraction and thumbnail generation for a single file, and then notifies
        via the `on_file_processed` callback.
        """
        try:
            operation_result = self._process_file_result_operation.execute(
                stats=self._last_scan_stats,
                file_path=file_path,
                metadata_ok=metadata_ok,
                thumbnail_ok=thumbnail_ok,
                error_message=error_message,
            )
            if not operation_result.success:
                raise RuntimeError(
                    operation_result.message or "Failed to process file result."
                )
            result = operation_result.data.get(
                FileOperationDataKey.FILE_PROCESSING_RESULT.value
            )
            if not isinstance(result, FileProcessingResult):
                raise RuntimeError("Invalid file processing payload returned.")

            # Notify the callback about the processed file.
            if self._on_file_processed:
                self._on_file_processed(result)
            return operation_result

        except Exception as e:
            error_msg = (
                f"An error occurred while processing individual file result: {e}"
            )
            self.logger.error(
                error_msg,
                exc_info=True,
            )
            return FileOperationResult(
                success=False,
                code=FileOperationCode.UNKNOWN_ERROR,
                message=error_msg,
                data={},
            )

    # === FILE MANAGEMENT ===

    def refresh_file_list(self) -> FileOperationResult:
        """
        Refreshes the internal list of files by querying the database.

        This method ensures that the service's file list is up-to-date with the
        current state of the database. It forces a database synchronization to
        ensure all committed data is visible before retrieval.

        Returns:
            List[Tuple[str, str]]: An updated list of files, where each item is a
                                   tuple containing the file's absolute path and its directory.
        """
        try:
            self.logger.debug("Refreshing file list from database.")
            operation_result = self._refresh_file_list_operation.execute(
                self._current_files
            )
            if not operation_result.success:
                error_msg = (
                    operation_result.message
                    or "An error occurred while refreshing the file list."
                )
                self.logger.error(error_msg)
                if self._on_scan_error:
                    self._on_scan_error(error_msg)
                return operation_result
            result_data = operation_result.data or {}
            file_list = result_data.get(FileOperationDataKey.FILE_LIST.value, [])
            content_by_path = result_data.get(
                FileOperationDataKey.CONTENT_BY_PATH.value, {}
            )

            # Update the service's internal list of files.
            self._current_files = file_list
            self._current_content_by_path = content_by_path

            # Notify the callback that the file list has been updated.
            if self._on_files_updated:
                self._on_files_updated(file_list)

            self.logger.info(f"File list updated: {len(file_list)} files.")
            return operation_result

        except Exception as e:
            error_msg = f"An error occurred while refreshing the file list: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            if self._on_scan_error:
                self._on_scan_error(error_msg)
            return FileOperationResult(
                success=False,
                code=FileOperationCode.UNKNOWN_ERROR,
                message=error_msg,
                data={
                    FileOperationDataKey.FILE_LIST.value: [],
                    FileOperationDataKey.CONTENT_BY_PATH.value: {},
                },
            )

    def clear_current_files(self) -> None:
        """
        Clears the in-memory file list managed by the service.
        """
        self._current_files = []
        self._current_content_by_path = {}
        self._last_scan_stats = ScanStatistics()

    @staticmethod
    def _resolve_thumbnail_cache_dir() -> str:
        """Return the centralized, user-writable thumbnail cache directory."""
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

        return os.path.normpath(
            os.path.abspath(os.path.join(base_dir, app_folder, "thumbnails"))
        )

    def clear_thumbnail_disk_cache(self) -> None:
        """Clear thumbnail cache through omni-cache DISK adapter when available."""
        runtime = get_cache_runtime()
        try:
            if runtime.clear(adapter="thumbnail_disk"):
                self.logger.info("Thumbnail DISK adapter cache cleared successfully.")
                return
        except Exception as e:
            self.logger.debug(f"thumbnail_disk clear via runtime failed: {e}")

        # Fallback path for environments without registered adapter.
        thumbnail_cache_dir = self._resolve_thumbnail_cache_dir()
        if not os.path.isdir(thumbnail_cache_dir):
            self.logger.debug(
                f"Thumbnail disk cache directory does not exist: {thumbnail_cache_dir}"
            )
            return

        try:
            shutil.rmtree(thumbnail_cache_dir)
            os.makedirs(thumbnail_cache_dir, exist_ok=True)
            self.logger.info(
                f"Thumbnail disk cache cleared via filesystem fallback: {thumbnail_cache_dir}"
            )
        except Exception as e:
            self.logger.warning(f"Unable to clear thumbnail disk cache: {e}")

    # === FILTERING DELEGATION (for aggregate counters only) ===

    def _run_filter_criteria(
        self,
        criteria: List[FilterCriterion],
        base_items: List[Tuple[str, str]],
        allow_db_fallback: bool = True,
    ) -> FileOperationResult:
        """Compatibility shim delegating filtering to ContentFilterService."""
        try:
            filtering_result = self._content_filter_service.apply_filters(
                criteria=criteria,
                scope={
                    "base_items": list(base_items),
                    "content_by_path": dict(self._current_content_by_path),
                },
                allow_db_fallback=allow_db_fallback,
            )
            if not filtering_result.success:
                return FileOperationResult(
                    success=False,
                    code=self._map_filter_code_to_file_code(filtering_result.code),
                    message=filtering_result.message,
                    data={
                        FileOperationDataKey.ERROR.value: (
                            filtering_result.data or {}
                        ).get("error", filtering_result.message),
                        FileOperationDataKey.FILTERED_FILES.value: list(base_items),
                    },
                )

            filtered_files = list(
                (filtering_result.data or {}).get("filtered_files", list(base_items))
            )
            return FileOperationResult(
                success=True,
                code=FileOperationCode.OK,
                message=filtering_result.message,
                data={FileOperationDataKey.FILTERED_FILES.value: filtered_files},
            )
        except Exception as exc:
            self.logger.error("Delegated filtering failed: %s", exc, exc_info=True)
            return FileOperationResult(
                success=False,
                code=FileOperationCode.UNKNOWN_ERROR,
                message="Unable to apply filter due to an unexpected error.",
                data={
                    FileOperationDataKey.ERROR.value: str(exc),
                    FileOperationDataKey.FILTERED_FILES.value: list(base_items),
                },
            )

    def _map_filter_code_to_file_code(self, filter_code: Any) -> FileOperationCode:
        """Map filtering-specific error codes to file operation error codes."""
        normalized = str(getattr(filter_code, "value", filter_code)).lower()
        mapping = {
            "validation_error": FileOperationCode.VALIDATION_ERROR,
            "unknown_filter": FileOperationCode.UNKNOWN_FILTER,
            "database_error": FileOperationCode.DATABASE_ERROR,
            "unknown_error": FileOperationCode.UNKNOWN_ERROR,
        }
        return mapping.get(normalized, FileOperationCode.UNKNOWN_ERROR)

    # === UTILITIES AND METADATA ===

    def get_thumbnail_path(self, file_path: str) -> Optional[str]:
        """
        Retrieves the path to the thumbnail for a given file.

        Args:
            file_path (str): The absolute path to the file.

        Returns:
            Optional[str]: The path to the thumbnail image, or `None` if no thumbnail
                           can be found or generated.
        """
        try:
            # Delegates to the `thumbnail_service` to get the thumbnail path.
            return self.thumbnail_service.get_thumbnail_path(file_path)
        except Exception as e:
            self.logger.error(f"Error retrieving thumbnail path for {file_path}: {e}")
            return None

    def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Retrieves all available metadata for a given file.

        Args:
            file_path (str): The absolute path to the file.

        Returns:
            Dict[str, Any]: A dictionary containing all extracted metadata for the file.
                            Returns an empty dictionary if an error occurs during extraction.
        """
        try:
            # Delegates to the `metadata_service` to extract all metadata.
            return self.metadata_service.get_all_metadata(file_path)
        except Exception as e:
            self.logger.error(f"Error retrieving metadata for {file_path}: {e}")
            return {}

    def get_file_count_by_type(self) -> Dict[str, int]:
        """
        Calculates and returns the number of files categorized by `FilterType`.

        This method provides a summary of the current file list, broken down
        by the predefined filter categories.

        Returns:
            Dict[str, int]: A dictionary where keys are `FilterType` enum values (as strings)
                            and values are the corresponding file counts.
        """
        try:
            counts = {}
            for filter_type in FilterType:
                if filter_type == FilterType.ALL_FILES:
                    counts[filter_type.value] = len(self._current_files)
                elif filter_type in [
                    FilterType.MULTI_CATEGORY,
                    FilterType.MULTI_YEAR,
                    FilterType.MULTI_EXTENSION,
                ]:
                    # Skip multi-filter types in count calculations
                    continue
                else:
                    # Delegate all filtering to the dedicated content filter service.
                    criterion = FilterCriterion(
                        key="file_type",
                        op="eq",
                        value=filter_type.value,
                    )
                    result = self._run_filter_criteria([criterion], self._current_files)
                    filtered = (result.data or {}).get(
                        FileOperationDataKey.FILTERED_FILES.value,
                        [],
                    )
                    counts[filter_type.value] = len(filtered)

            return counts

        except Exception as e:
            self.logger.error(f"Error calculating file counts by type: {e}")
            return {}

    # === PROPERTIES ===

    @property
    def current_files(self) -> List[Tuple[str, str]]:
        """
        Returns a copy of the current list of files managed by the service.

        Returns:
            List[Tuple[str, str]]: A list of (file_path, directory) tuples.
        """
        return self._current_files.copy()

    @property
    def last_scan_stats(self) -> ScanStatistics:
        """
        Returns the statistics object from the most recently completed scan operation.

        Returns:
            ScanStatistics: An object containing detailed statistics of the last scan.
        """
        return self._last_scan_stats

    @property
    def file_count(self) -> int:
        """
        Returns the total number of files currently managed by the service (before filtering).

        Returns:
            int: The total count of files.
        """
        return len(self._current_files)

    def cleanup(self) -> None:
        """
        Performs cleanup operations to release resources used by the service.

        This method should be called when the `FileOperationService` is no longer needed
        to ensure proper shutdown of its dependencies (thumbnail and metadata services)
        and to clear internal state.
        """
        try:
            self.logger.info("Initiating cleanup for FileOperationService.")

            # Call cleanup methods on dependent services if they exist.
            if hasattr(self.thumbnail_service, "cleanup"):
                self.thumbnail_service.cleanup()

            if hasattr(self.metadata_service, "clear_cache"):
                self.metadata_service.clear_cache()

            # Reset internal state variables.
            self._current_files.clear()
            self._last_scan_stats = ScanStatistics()

            self.logger.info("FileOperationService cleanup complete.")

        except Exception as e:
            self.logger.error(
                f"An error occurred during FileOperationService cleanup: {e}"
            )


# === BACKWARD COMPATIBILITY METHODS ===
# These methods are kept for compatibility with existing code that might call them directly

# Note: The old _is_image_file and _is_document_file methods have been removed
# in favor of using the centralized FileTypeService. If any code still references
# these methods, they should be updated to use:
# - FileTypeService.is_image_file(file_path) instead of service._is_image_file(file_path)
# - FileTypeService.is_document_file(file_path) instead of service._is_document_file(file_path)
