"""Database-only removal operation for file records."""

from typing import Any, List

from ai_content_classifier.services.file.operations.types import (
    FileOperationDataKey,
    FileOperationKind,
)
from ai_content_classifier.services.file.types import (
    FileOperationCode,
    FileOperationResult,
)


class RemoveFilesFromDatabaseOperation:
    """Remove file rows from the content database."""

    kind = FileOperationKind.REMOVE_FROM_DATABASE

    def __init__(self, db_service: Any, logger: Any):
        self.db_service = db_service
        self.logger = logger

    def execute(self, file_paths: List[str]) -> FileOperationResult:
        try:
            normalized_paths = [
                str(path) for path in dict.fromkeys(file_paths or []) if path
            ]
            if not normalized_paths:
                self.logger.info("No file paths provided for database removal.")
                return FileOperationResult(
                    success=True,
                    code=FileOperationCode.OK,
                    message="No file paths provided for database removal.",
                    data={
                        FileOperationDataKey.DELETED_COUNT.value: 0,
                        FileOperationDataKey.NORMALIZED_PATHS.value: [],
                    },
                )

            db_result = self.db_service.delete_content_by_paths(normalized_paths)
            result_data = db_result.data or {}
            deleted_count = int(result_data.get("deleted_count", 0))
            if not db_result.success:
                return FileOperationResult(
                    success=False,
                    code=FileOperationCode.UNKNOWN_ERROR,
                    message=db_result.message
                    or "Database removal failed due to a database operation error.",
                    data={
                        FileOperationDataKey.ERROR.value: result_data.get(
                            "error", db_result.message
                        ),
                        FileOperationDataKey.NORMALIZED_PATHS.value: normalized_paths,
                    },
                )

            return FileOperationResult(
                success=True,
                code=FileOperationCode.OK,
                message=db_result.message or "Database removal completed.",
                data={
                    FileOperationDataKey.DELETED_COUNT.value: (
                        deleted_count if deleted_count > 0 else 0
                    ),
                    FileOperationDataKey.NORMALIZED_PATHS.value: normalized_paths,
                },
            )
        except Exception as exc:
            self.logger.error(
                "Database removal operation failed: %s",
                exc,
                exc_info=True,
            )
            return FileOperationResult(
                success=False,
                code=FileOperationCode.UNKNOWN_ERROR,
                message="Database removal failed due to an unexpected error.",
                data={FileOperationDataKey.ERROR.value: str(exc)},
            )
