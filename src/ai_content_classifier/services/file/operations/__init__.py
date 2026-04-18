"""File operations package.

This package contains operation handlers used by FileOperationService.
"""

from ai_content_classifier.services.file.operations.open_file_operation import (
    OpenFileOperation,
)
from ai_content_classifier.services.file.operations.refresh_file_list_operation import (
    RefreshFileListOperation,
)
from ai_content_classifier.services.file.operations.remove_files_from_database_operation import (
    RemoveFilesFromDatabaseOperation,
)
from ai_content_classifier.services.file.operations.process_file_result_operation import (
    ProcessFileResultOperation,
)
from ai_content_classifier.services.file.operations.process_scan_results_operation import (
    ProcessScanResultsOperation,
)
from ai_content_classifier.services.file.operations.types import (
    FileOperationDataKey,
    FileOperationKind,
)

__all__ = [
    "FileOperationKind",
    "FileOperationDataKey",
    "OpenFileOperation",
    "ProcessFileResultOperation",
    "ProcessScanResultsOperation",
    "RefreshFileListOperation",
    "RemoveFilesFromDatabaseOperation",
]
