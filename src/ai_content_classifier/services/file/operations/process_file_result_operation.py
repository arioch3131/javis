"""Process-file-result operation implementation."""

from ai_content_classifier.services.file.operations.types import (
    FileOperationDataKey,
    FileOperationKind,
)
from ai_content_classifier.services.file.types import (
    FileOperationCode,
    FileOperationResult,
    FileProcessingResult,
    ScanStatistics,
)


class ProcessFileResultOperation:
    """Apply per-file processing outcome to running scan statistics."""

    kind = FileOperationKind.PROCESS_FILE_RESULT

    def __init__(self, logger):
        self.logger = logger

    def execute(
        self,
        stats: ScanStatistics,
        file_path: str,
        metadata_ok: bool,
        thumbnail_ok: bool,
        error_message: str | None = None,
    ) -> FileOperationResult:
        try:
            if metadata_ok:
                stats.metadata_extracted += 1
            if thumbnail_ok:
                stats.thumbnails_generated += 1
            if error_message:
                stats.errors += 1

            result = FileProcessingResult(
                file_path=file_path,
                metadata_extracted=metadata_ok,
                thumbnail_generated=thumbnail_ok,
                error_message=error_message,
            )
            self.logger.debug(
                f"File processed: {result.file_path} (metadata={result.metadata_extracted}, thumbnail={result.thumbnail_generated})."
            )
            return FileOperationResult(
                success=True,
                code=FileOperationCode.OK,
                message="File processing result recorded.",
                data={FileOperationDataKey.FILE_PROCESSING_RESULT.value: result},
            )
        except Exception as exc:
            self.logger.error(
                "Process file result operation failed: %s",
                exc,
                exc_info=True,
            )
            return FileOperationResult(
                success=False,
                code=FileOperationCode.UNKNOWN_ERROR,
                message="Unable to record file processing result due to an unexpected error.",
                data={FileOperationDataKey.ERROR.value: str(exc)},
            )
