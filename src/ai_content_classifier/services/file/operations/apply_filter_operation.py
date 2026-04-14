"""Apply-filter operation implementation."""

from typing import Any, Callable, List, Tuple

from ai_content_classifier.services.database.content_database_service import (
    ContentFilter,
)
from ai_content_classifier.services.file.operations.types import (
    FileOperationDataKey,
    FileOperationKind,
)
from ai_content_classifier.services.file.types import (
    FileOperationCode,
    FileOperationResult,
    FilterType,
)


class ApplyFilterOperation:
    """Apply a single filter to the current file list."""

    kind = FileOperationKind.APPLY_FILTER

    def __init__(self, db_service: Any, logger: Any):
        self.db_service = db_service
        self.logger = logger

    def execute(
        self,
        filter_type: FilterType,
        current_files: List[Tuple[str, str]],
        filter_uncategorized: Callable[[], List[Tuple[str, str]]],
        filter_files_by_type: Callable[[FilterType], List[Tuple[str, str]]],
    ) -> FileOperationResult:
        try:
            self.logger.debug(f"Applying filter: {filter_type.value}.")

            # For special multi-filter types, delegate to appropriate methods
            if filter_type == FilterType.MULTI_CATEGORY:
                self.logger.warning(
                    "MULTI_CATEGORY filter called directly - use apply_multi_category_filter instead"
                )
                return FileOperationResult(
                    success=True,
                    code=FileOperationCode.OK,
                    message="Filter applied.",
                    data={
                        FileOperationDataKey.FILTERED_FILES.value: current_files.copy()
                    },
                )
            elif filter_type == FilterType.MULTI_YEAR:
                self.logger.warning(
                    "MULTI_YEAR filter called directly - use apply_multi_year_filter instead"
                )
                return FileOperationResult(
                    success=True,
                    code=FileOperationCode.OK,
                    message="Filter applied.",
                    data={
                        FileOperationDataKey.FILTERED_FILES.value: current_files.copy()
                    },
                )
            elif filter_type == FilterType.MULTI_EXTENSION:
                self.logger.warning(
                    "MULTI_EXTENSION filter called directly - use apply_multi_extension_filter instead"
                )
                return FileOperationResult(
                    success=True,
                    code=FileOperationCode.OK,
                    message="Filter applied.",
                    data={
                        FileOperationDataKey.FILTERED_FILES.value: current_files.copy()
                    },
                )

            # For standard filters, use database-based filtering when possible.
            if filter_type == FilterType.ALL_FILES:
                filtered_files = current_files.copy()
            elif filter_type == FilterType.UNCATEGORIZED:
                filtered_files = filter_uncategorized()
            else:
                content_type = self._resolve_content_type(filter_type)
                if content_type is None:
                    filtered_files = filter_files_by_type(filter_type)
                else:
                    content_filter = ContentFilter()
                    content_filter.by_type(content_type)
                    filtered_content = self.db_service.find_items(
                        content_filter=content_filter
                    )
                    filtered_files = [
                        (item.path, item.directory) for item in filtered_content
                    ]

            self.logger.debug(
                f"Filter applied: {len(filtered_files)} files match the criteria."
            )
            return FileOperationResult(
                success=True,
                code=FileOperationCode.OK,
                message="Filter applied.",
                data={FileOperationDataKey.FILTERED_FILES.value: filtered_files},
            )
        except Exception as exc:
            self.logger.error(
                "Apply filter operation failed: %s",
                exc,
                exc_info=True,
            )
            return FileOperationResult(
                success=False,
                code=FileOperationCode.UNKNOWN_ERROR,
                message="Unable to apply filter due to an unexpected error.",
                data={
                    FileOperationDataKey.ERROR.value: str(exc),
                    FileOperationDataKey.FILTERED_FILES.value: current_files.copy(),
                },
            )

    def _resolve_content_type(self, filter_type: FilterType) -> str | None:
        """Map filter type to database content type."""
        if filter_type == FilterType.IMAGES:
            return "image"
        if filter_type == FilterType.DOCUMENTS:
            return "document"
        if filter_type == FilterType.VIDEOS:
            return "video"
        if filter_type == FilterType.AUDIO:
            return "audio"
        if filter_type == FilterType.ARCHIVES:
            return "archive"
        if filter_type == FilterType.CODE:
            return "code"
        if filter_type == FilterType.OTHER:
            return "other"
        return None
