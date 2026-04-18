"""File-type filter plugin."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy import or_

from ai_content_classifier.models.content_models import ContentItem
from ai_content_classifier.repositories.content_repository import ContentFilter
from ai_content_classifier.services.file.file_type_service import FileTypeService
from ai_content_classifier.services.filtering.types import (
    FilterCriterion,
    FilterOperator,
)


class FileTypeFilterPlugin:
    """Filter plugin for `file_type` criteria."""

    key = "file_type"

    _ALIASES: Dict[str, str] = {
        "all": "all files",
        "all files": "all files",
        "image": "images",
        "images": "images",
        "document": "documents",
        "documents": "documents",
        "video": "videos",
        "videos": "videos",
        "audio": "audio",
        "archive": "archives",
        "archives": "archives",
        "code": "code",
        "other": "other",
        "others": "other",
        "uncategorized": "uncategorized",
    }

    _DB_TYPE_BY_VALUE: Dict[str, str] = {
        "images": "image",
        "documents": "document",
        "videos": "video",
        "audio": "audio",
        "archives": "archive",
        "code": "code",
        "other": "other",
    }

    _PREDICATES: Dict[str, Callable[[str], bool]] = {
        "images": FileTypeService.is_image_file,
        "documents": FileTypeService.is_document_file,
        "videos": FileTypeService.is_video_file,
        "audio": FileTypeService.is_audio_file,
        "archives": FileTypeService.is_archive_file,
        "code": FileTypeService.is_code_file,
        "other": lambda path: FileTypeService.get_file_category(path).value == "Other",
    }

    def validate(self, criterion: FilterCriterion) -> Optional[str]:
        if criterion.op not in {FilterOperator.EQ.value, FilterOperator.IN.value}:
            return f"Unsupported operator '{criterion.op}' for 'file_type'."

        normalized_values = self._normalize_values(criterion.value)
        if not normalized_values:
            return "'file_type' requires at least one value."

        for value in normalized_values:
            if value not in self._ALIASES and value not in self._ALIASES.values():
                return f"Unknown file_type value '{value}'."
        return None

    def to_db_clause(self, criterion: FilterCriterion) -> Optional[List[Any]]:
        normalized_values = self._normalize_values(criterion.value)
        canonical = [self._ALIASES.get(v, v) for v in normalized_values]

        if not canonical or "all files" in canonical:
            return []

        db_types = [
            self._DB_TYPE_BY_VALUE[v] for v in canonical if v in self._DB_TYPE_BY_VALUE
        ]
        include_uncategorized = "uncategorized" in canonical

        clauses: List[Any] = []
        if db_types and include_uncategorized:
            clauses.append(
                or_(
                    ContentItem.content_type.in_(db_types),
                    ContentItem.category == "Uncategorized",
                )
            )
            return clauses
        if len(db_types) == 1:
            clauses.extend(ContentFilter().by_type(db_types[0]).build())
            return clauses
        if db_types:
            clauses.append(ContentItem.content_type.in_(db_types))
            return clauses
        if include_uncategorized:
            clauses.append(ContentItem.category == "Uncategorized")
            return clauses
        return []

    def apply_memory(
        self,
        items: List[Tuple[str, str]],
        criterion: FilterCriterion,
        context: Dict[str, Any],
    ) -> List[Tuple[str, str]]:
        normalized_values = self._normalize_values(criterion.value)
        canonical = [self._ALIASES.get(v, v) for v in normalized_values]
        if not canonical or "all files" in canonical:
            return list(items)

        content_map = {}
        if "uncategorized" in canonical:
            get_content_map = context.get("get_content_map")
            if callable(get_content_map):
                content_map = get_content_map(items)

        filtered: List[Tuple[str, str]] = []
        for path, directory in items:
            if self._matches(path, canonical, content_map):
                filtered.append((path, directory))
        return filtered

    def _matches(
        self,
        path: str,
        canonical_values: List[str],
        content_map: Dict[str, Any],
    ) -> bool:
        if "uncategorized" in canonical_values:
            content_item = content_map.get(path)
            if (
                content_item is not None
                and getattr(content_item, "category", None) == "Uncategorized"
            ):
                return True

        for value in canonical_values:
            predicate = self._PREDICATES.get(value)
            if predicate and predicate(path):
                return True
        return False

    def _normalize_values(self, raw_value: Any) -> List[str]:
        values = raw_value if isinstance(raw_value, list) else [raw_value]
        normalized: List[str] = []
        for value in values:
            if value is None:
                continue
            text = str(value).strip().lower()
            if not text:
                continue
            normalized.append(text)
        return normalized
