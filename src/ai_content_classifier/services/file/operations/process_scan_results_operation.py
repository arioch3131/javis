"""Process-scan-results operation implementation."""

from typing import List, Tuple

from ai_content_classifier.services.file.operations.types import (
    FileOperationDataKey,
    FileOperationKind,
)
from ai_content_classifier.services.file.types import (
    FileOperationCode,
    FileOperationResult,
)


class ProcessScanResultsOperation:
    """Prepare in-memory state updates from a scan file list."""

    kind = FileOperationKind.PROCESS_SCAN_RESULTS

    def __init__(self, logger):
        self.logger = logger

    def execute(self, file_list: List[Tuple[str, str]]) -> FileOperationResult:
        try:
            normalized_file_list = list(file_list or [])
            self.logger.info(
                f"Processing scan results: {len(normalized_file_list)} files found."
            )
            return FileOperationResult(
                success=True,
                code=FileOperationCode.OK,
                message="Scan results processed.",
                data={
                    FileOperationDataKey.FILE_LIST.value: normalized_file_list,
                    FileOperationDataKey.CONTENT_BY_PATH.value: {},
                    FileOperationDataKey.FILES_FOUND.value: len(normalized_file_list),
                },
            )
        except Exception as exc:
            self.logger.error(
                "Process scan results operation failed: %s",
                exc,
                exc_info=True,
            )
            return FileOperationResult(
                success=False,
                code=FileOperationCode.UNKNOWN_ERROR,
                message="Unable to process scan results due to an unexpected error.",
                data={
                    FileOperationDataKey.ERROR.value: str(exc),
                    FileOperationDataKey.FILE_LIST.value: [],
                },
            )
