"""Refresh-file-list operation implementation."""

from typing import Any, Dict, List, Tuple

from ai_content_classifier.services.file.operations.types import (
    FileOperationDataKey,
    FileOperationKind,
)
from ai_content_classifier.services.file.types import (
    FileOperationCode,
    FileOperationResult,
)


class RefreshFileListOperation:
    """Refresh in-memory files from the content database."""

    kind = FileOperationKind.REFRESH_FILE_LIST

    def __init__(self, db_service: Any, logger: Any):
        self.db_service = db_service
        self.logger = logger

    def execute(self, current_files: List[Tuple[str, str]]) -> FileOperationResult:
        try:
            # Force database synchronization to ensure all committed data is visible.
            if hasattr(self.db_service, "force_database_sync"):
                self.db_service.force_database_sync()

            # Log database state for debugging purposes.
            if hasattr(self.db_service, "count_all_items"):
                count_result = self.db_service.count_all_items()
                if not count_result.success:
                    self.logger.warning(
                        "Unable to count DB items before refresh: code=%s message=%s",
                        count_result.code,
                        count_result.message,
                    )
                total_count = int((count_result.data or {}).get("count", 0))
                self.logger.info(
                    f"Total items in database before refresh: {total_count}."
                )

            # Retrieve all content items from the database.
            all_content_result = self.db_service.find_items(eager_load=False)
            if not all_content_result.success:
                self.logger.warning(
                    "Unable to refresh file list from DB: code=%s message=%s",
                    all_content_result.code,
                    all_content_result.message,
                )
                return FileOperationResult(
                    success=False,
                    code=FileOperationCode.UNKNOWN_ERROR,
                    message=all_content_result.message
                    or "Unable to retrieve content items from database.",
                    data={
                        FileOperationDataKey.ERROR.value: (
                            all_content_result.data or {}
                        ).get(
                            "error",
                            all_content_result.message,
                        ),
                        FileOperationDataKey.FILE_LIST.value: current_files.copy(),
                        FileOperationDataKey.CONTENT_BY_PATH.value: {},
                    },
                )
            all_content = (all_content_result.data or {}).get("items", [])
            self.logger.info(f"Retrieved {len(all_content)} items from database.")

            # Convert retrieved content items into the expected (file_path, directory) format.
            file_list: List[Tuple[str, str]] = []
            content_by_path: Dict[str, Any] = {}
            for item in all_content:
                if hasattr(item, "path") and hasattr(item, "directory"):
                    file_list.append((item.path, item.directory))
                    content_by_path[item.path] = item
                else:
                    self.logger.warning(
                        f"Skipping item due to missing path or directory attributes: {item}."
                    )

            # Keep the in-memory list when DB is temporarily empty to avoid wiping the UI.
            if not file_list and current_files:
                self.logger.warning(
                    "Database refresh returned 0 items while in-memory list is not empty; preserving current files."
                )
                file_list = current_files.copy()

            return FileOperationResult(
                success=True,
                code=FileOperationCode.OK,
                message="File list refreshed.",
                data={
                    FileOperationDataKey.FILE_LIST.value: file_list,
                    FileOperationDataKey.CONTENT_BY_PATH.value: content_by_path,
                },
            )
        except Exception as exc:
            self.logger.error(
                "Refresh file list operation failed: %s",
                exc,
                exc_info=True,
            )
            return FileOperationResult(
                success=False,
                code=FileOperationCode.UNKNOWN_ERROR,
                message="Unable to refresh file list due to an unexpected error.",
                data={
                    FileOperationDataKey.ERROR.value: str(exc),
                    FileOperationDataKey.FILE_LIST.value: current_files.copy(),
                    FileOperationDataKey.CONTENT_BY_PATH.value: {},
                },
            )
