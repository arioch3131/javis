"""Category filter plugin."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ai_content_classifier.models.content_models import ContentItem
from ai_content_classifier.services.filtering.types import (
    FilterCriterion,
    FilterOperator,
)


class CategoryFilterPlugin:
    """Filter plugin for `category` criteria."""

    key = "category"

    def validate(self, criterion: FilterCriterion) -> Optional[str]:
        if criterion.op not in {FilterOperator.EQ.value, FilterOperator.IN.value}:
            return f"Unsupported operator '{criterion.op}' for 'category'."

        categories = self._normalize_categories(criterion.value)
        if not categories:
            return "'category' requires at least one value."
        return None

    def to_db_clause(self, criterion: FilterCriterion) -> Optional[List[Any]]:
        categories = self._normalize_categories(criterion.value)
        if not categories:
            return []
        if len(categories) == 1:
            return [ContentItem.category == categories[0]]
        return [ContentItem.category.in_(categories)]

    def apply_memory(
        self,
        items: List[Tuple[str, str]],
        criterion: FilterCriterion,
        context: Dict[str, Any],
    ) -> List[Tuple[str, str]]:
        categories = set(self._normalize_categories(criterion.value))
        if not categories:
            return []

        get_content_map = context.get("get_content_map")
        if not callable(get_content_map):
            return []

        content_map = get_content_map(items)
        return [
            (path, directory)
            for path, directory in items
            if content_map.get(path)
            and getattr(content_map[path], "category", None) in categories
        ]

    def _normalize_categories(self, raw_value: Any) -> List[str]:
        values = raw_value if isinstance(raw_value, list) else [raw_value]
        normalized: List[str] = []
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                normalized.append(text)
        return normalized
