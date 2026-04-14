"""Operation-specific contracts for file service operations."""

from enum import Enum


class FileOperationKind(str, Enum):
    """Known file operation kinds handled by the file service layer."""

    OPEN_FILE = "open_file"
    REMOVE_FROM_DATABASE = "remove_from_database"
    REFRESH_FILE_LIST = "refresh_file_list"
    APPLY_FILTER = "apply_filter"
    CLEAR_THUMBNAIL_DISK_CACHE = "clear_thumbnail_disk_cache"
    PROCESS_SCAN_RESULTS = "process_scan_results"
    PROCESS_FILE_RESULT = "process_file_result"


class FileOperationDataKey(str, Enum):
    """Canonical keys used in FileOperationResult.data payloads."""

    FILE_LIST = "file_list"
    CONTENT_BY_PATH = "content_by_path"
    FILES_FOUND = "files_found"
    FILTERED_FILES = "filtered_files"
    DELETED_COUNT = "deleted_count"
    NORMALIZED_PATHS = "normalized_paths"
    FILE_PROCESSING_RESULT = "file_processing_result"
    ERROR = "error"
