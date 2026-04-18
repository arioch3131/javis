"""Data structures used by the file service layer."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


@dataclass
class ScanStatistics:
    """Summary statistics for a scan operation."""

    files_found: int = 0
    metadata_extracted: int = 0
    thumbnails_generated: int = 0
    errors: int = 0
    processing_time: float = 0.0
    directory_scanned: str = ""


class FilterType(Enum):
    """Available filter types used by file list filtering."""

    ALL_FILES = "All Files"
    IMAGES = "Images"
    DOCUMENTS = "Documents"
    UNCATEGORIZED = "Uncategorized"
    VIDEOS = "Videos"
    AUDIO = "Audio"
    ARCHIVES = "Archives"
    CODE = "Code"
    OTHER = "Other"

    # Special values for multi-selections
    MULTI_CATEGORY = "multi_category"
    MULTI_YEAR = "multi_year"
    MULTI_EXTENSION = "multi_extension"


class FileOperationCode(str, Enum):
    """Normalized result codes for file open operations."""

    OK = "ok"
    FILE_NOT_FOUND = "file_not_found"
    NO_DEFAULT_APP = "no_default_app"
    ACCESS_DENIED = "access_denied"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN_FILTER = "unknown_filter"
    DATABASE_ERROR = "database_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class FileOperationResult:
    """Structured result for OS-level file operations."""

    success: bool
    code: FileOperationCode
    message: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FileProcessingResult:
    """Outcome of processing a single file in the scan pipeline."""

    file_path: str
    metadata_extracted: bool
    thumbnail_generated: bool
    error_message: Optional[str] = None
