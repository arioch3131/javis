"""Orchestrator for composable content filtering."""

from __future__ import annotations

import os

from typing import Any, Dict, Iterable, List, Optional, Tuple

from ai_content_classifier.core.logger import get_logger
from ai_content_classifier.models.content_models import ContentItem
from ai_content_classifier.services.database.content_database_service import (
    ContentDatabaseService,
)
from ai_content_classifier.services.filtering.plugins.category_filter import (
    CategoryFilterPlugin,
)
from ai_content_classifier.services.filtering.plugins.extension_filter import (
    ExtensionFilterPlugin,
)
from ai_content_classifier.services.filtering.plugins.file_type_filter import (
    FileTypeFilterPlugin,
)
from ai_content_classifier.services.filtering.plugins.year_filter import (
    YearFilterPlugin,
)
from ai_content_classifier.services.filtering.registry import FilterRegistry
from ai_content_classifier.services.filtering.types import (
    FilterCriterion,
    FilterOperationCode,
    FilterOperationResult,
    FilterScope,
)


class ContentFilterService:
    """Executes registered content filters through a unified pipeline."""

    def __init__(
        self,
        db_service: ContentDatabaseService,
        registry: Optional[FilterRegistry] = None,
        logger: Any = None,
    ) -> None:
        self.db_service = db_service
        self.logger = logger or get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )
        self.registry = registry or FilterRegistry()
        self._register_default_plugins()

    def _register_default_plugins(self) -> None:
        default_plugins = [
            FileTypeFilterPlugin(),
            CategoryFilterPlugin(),
            YearFilterPlugin(),
            ExtensionFilterPlugin(),
        ]
        for plugin in default_plugins:
            if self.registry.resolve(plugin.key) is None:
                self.registry.register(plugin)

    def apply_filters(
        self,
        criteria: Iterable[FilterCriterion | Dict[str, Any]],
        scope: Optional[FilterScope | Dict[str, Any]] = None,
        allow_db_fallback: bool = True,
    ) -> FilterOperationResult:
        """Apply cumulative filters (logical AND) over a candidate scope."""
        normalized_scope = self._normalize_scope(scope)
        normalized_criteria: List[FilterCriterion] = []
        try:
            normalized_criteria = self._normalize_criteria(criteria)
            if not normalized_criteria:
                return FilterOperationResult(
                    success=True,
                    code=FilterOperationCode.OK,
                    message="No filters applied.",
                    data={
                        "filtered_files": list(normalized_scope.base_items),
                        "applied_filters": [],
                        "error": None,
                    },
                )

            db_clauses: List[Any] = []

            for criterion in normalized_criteria:
                plugin = self.registry.resolve(criterion.key)
                if plugin is None:
                    return FilterOperationResult(
                        success=False,
                        code=FilterOperationCode.UNKNOWN_FILTER,
                        message=f"Unknown filter key '{criterion.key}'.",
                        data={
                            "filtered_files": list(normalized_scope.base_items),
                            "applied_filters": self._serialize_criteria(
                                normalized_criteria
                            ),
                            "error": f"Unknown filter key '{criterion.key}'.",
                        },
                    )

                validation_error = plugin.validate(criterion)
                if validation_error:
                    return FilterOperationResult(
                        success=False,
                        code=FilterOperationCode.VALIDATION_ERROR,
                        message=validation_error,
                        data={
                            "filtered_files": list(normalized_scope.base_items),
                            "applied_filters": self._serialize_criteria(
                                normalized_criteria
                            ),
                            "error": validation_error,
                        },
                    )

                clause = plugin.to_db_clause(criterion)
                if clause:
                    db_clauses.extend(clause)

            working_items, content_by_path, _used_db_pushdown = (
                self._load_initial_dataset(
                    db_clauses=db_clauses,
                    scope=normalized_scope,
                    allow_db_fallback=allow_db_fallback,
                )
            )

            context = {
                "content_by_path": content_by_path,
                "scope": normalized_scope,
                "get_content_map": lambda items: self._get_content_items_by_path(
                    items,
                    cache=content_by_path,
                    batch_size=normalized_scope.batch_size,
                    allow_db_fallback=allow_db_fallback,
                ),
            }

            for criterion in normalized_criteria:
                plugin = self.registry.resolve(criterion.key)
                if plugin is None:
                    continue
                working_items = plugin.apply_memory(working_items, criterion, context)

            return FilterOperationResult(
                success=True,
                code=FilterOperationCode.OK,
                message="Filters applied.",
                data={
                    "filtered_files": working_items,
                    "applied_filters": self._serialize_criteria(normalized_criteria),
                    "error": None,
                },
            )
        except _FilterDatabaseError as exc:
            self.logger.warning(
                "Filtering failed due to a database error: %s", exc, exc_info=True
            )
            error_message = str(exc) or "Unable to apply filters due to a DB error."
            return FilterOperationResult(
                success=False,
                code=FilterOperationCode.DATABASE_ERROR,
                message=error_message,
                data={
                    "filtered_files": list(normalized_scope.base_items),
                    "applied_filters": self._serialize_criteria(normalized_criteria),
                    "error": error_message,
                },
            )
        except Exception as exc:
            self.logger.error("Filtering pipeline failed: %s", exc, exc_info=True)
            return FilterOperationResult(
                success=False,
                code=FilterOperationCode.UNKNOWN_ERROR,
                message="Unable to apply filters due to an unexpected error.",
                data={
                    "filtered_files": list(normalized_scope.base_items),
                    "applied_filters": self._serialize_criteria(normalized_criteria),
                    "error": str(exc),
                },
            )

    def _normalize_scope(
        self, scope: Optional[FilterScope | Dict[str, Any]]
    ) -> FilterScope:
        if scope is None:
            return FilterScope()
        if isinstance(scope, FilterScope):
            return scope

        base_items = list(scope.get("base_items", []) or [])
        content_by_path = dict(scope.get("content_by_path", {}) or {})
        batch_size = int(scope.get("batch_size", 800) or 800)
        return FilterScope(
            base_items=base_items,
            content_by_path=content_by_path,
            batch_size=max(50, batch_size),
        )

    def _normalize_criteria(
        self, criteria: Iterable[FilterCriterion | Dict[str, Any]]
    ) -> List[FilterCriterion]:
        normalized: List[FilterCriterion] = []
        for criterion in list(criteria or []):
            if isinstance(criterion, FilterCriterion):
                normalized.append(criterion)
                continue

            key = str((criterion or {}).get("key", "")).strip()
            op = str((criterion or {}).get("op", "eq")).strip() or "eq"
            value = (criterion or {}).get("value")
            if key:
                normalized.append(FilterCriterion(key=key, op=op, value=value))
        return normalized

    def _load_initial_dataset(
        self,
        db_clauses: List[Any],
        scope: FilterScope,
        allow_db_fallback: bool = True,
    ) -> Tuple[List[Tuple[str, str]], Dict[str, Any], bool]:
        try:
            if db_clauses:
                query_result = self.db_service.find_items(
                    custom_filter=db_clauses,
                    eager_load=False,
                )
            elif scope.base_items:
                return list(scope.base_items), dict(scope.content_by_path), False
            else:
                query_result = self.db_service.find_items(eager_load=False)

            if not query_result.success:
                db_error = (query_result.data or {}).get("error")
                db_message = query_result.message or "Unable to query filtered items."
                if db_error:
                    db_message = f"{db_message} ({db_error})"
                raise _FilterDatabaseError(db_message)

            items = (query_result.data or {}).get("items", [])
            file_list = []
            for item in items:
                if not hasattr(item, "path"):
                    continue
                directory = getattr(item, "directory", None)
                if directory is None:
                    directory = os.path.dirname(str(item.path)) or "."
                file_list.append((item.path, directory))
            content_by_path = {
                item.path: item for item in items if hasattr(item, "path")
            }

            if scope.base_items:
                allowed_paths = {path for path, _ in scope.base_items}
                file_list = [
                    (path, directory)
                    for path, directory in file_list
                    if path in allowed_paths
                ]
                content_by_path = {
                    path: item
                    for path, item in content_by_path.items()
                    if path in allowed_paths
                }
            content_by_path.update(scope.content_by_path)
            return file_list, content_by_path, bool(db_clauses)
        except Exception as exc:
            if allow_db_fallback:
                self.logger.warning(
                    "DB query failed in filter pipeline, using scope fallback: %s", exc
                )
                return list(scope.base_items), dict(scope.content_by_path), False
            if isinstance(exc, _FilterDatabaseError):
                raise
            raise _FilterDatabaseError(
                f"Unable to query filtered items: {exc}"
            ) from exc

    def _get_content_items_by_path(
        self,
        file_list: List[Tuple[str, str]],
        cache: Optional[Dict[str, Any]] = None,
        batch_size: int = 800,
        allow_db_fallback: bool = True,
    ) -> Dict[str, Any]:
        cached = cache if cache is not None else {}
        unique_paths = [path for path, _ in file_list if path]
        if not unique_paths:
            return cached

        unique_paths = list(dict.fromkeys(unique_paths))
        missing_paths: List[str] = []

        for path in unique_paths:
            if path not in cached:
                missing_paths.append(path)

        if not missing_paths:
            return cached

        for index in range(0, len(missing_paths), max(50, batch_size)):
            batch_paths = missing_paths[index : index + max(50, batch_size)]
            batch_result = self.db_service.find_items(
                custom_filter=[ContentItem.path.in_(batch_paths)],
                eager_load=False,
            )
            if not batch_result.success:
                error_message = (
                    "Batch DB read failed in filtering context: "
                    f"code={batch_result.code} message={batch_result.message}"
                )
                if allow_db_fallback:
                    self.logger.warning(error_message)
                    continue
                raise _FilterDatabaseError(error_message)
            for item in (batch_result.data or {}).get("items", []):
                if hasattr(item, "path"):
                    cached[item.path] = item

        return cached

    def _serialize_criteria(
        self, criteria: List[FilterCriterion]
    ) -> List[Dict[str, Any]]:
        return [{"key": c.key, "op": c.op, "value": c.value} for c in criteria]


class _FilterDatabaseError(RuntimeError):
    """Raised when filtering cannot continue due to a DB failure."""
