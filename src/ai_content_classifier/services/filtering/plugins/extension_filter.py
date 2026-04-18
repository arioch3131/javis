"""Extension filter plugin."""

from __future__ import annotations

import os

from typing import Any, Dict, List, Optional, Set, Tuple

from ai_content_classifier.services.filtering.types import (
    FilterCriterion,
    FilterOperator,
)


class ExtensionFilterPlugin:
    """Filter plugin for `extension` criteria."""

    key = "extension"

    def validate(self, criterion: FilterCriterion) -> Optional[str]:
        if criterion.op not in {
            FilterOperator.EQ.value,
            FilterOperator.IN.value,
            FilterOperator.CONTAINS.value,
        }:
            return f"Unsupported operator '{criterion.op}' for 'extension'."

        if criterion.op == FilterOperator.CONTAINS.value:
            if criterion.value is None or not str(criterion.value).strip():
                return "'extension' contains filter requires a non-empty value."
            return None

        values = self._normalize_extensions(criterion.value)
        if not values:
            return "'extension' requires at least one extension."
        return None

    def to_db_clause(self, criterion: FilterCriterion) -> Optional[List[Any]]:
        # No first-class extension column available; use in-memory filtering.
        return None

    def apply_memory(
        self,
        items: List[Tuple[str, str]],
        criterion: FilterCriterion,
        context: Dict[str, Any],
    ) -> List[Tuple[str, str]]:
        if criterion.op == FilterOperator.CONTAINS.value:
            needle = str(criterion.value).strip().lower()
            return [
                (path, directory)
                for path, directory in items
                if needle in os.path.splitext(path)[1].lower()
            ]

        extensions = self._normalize_extensions(criterion.value)
        if not extensions:
            return []

        return [
            (path, directory)
            for path, directory in items
            if os.path.splitext(path)[1].lower() in extensions
        ]

    def _normalize_extensions(self, raw_value: Any) -> Set[str]:
        values = raw_value if isinstance(raw_value, list) else [raw_value]
        normalized: Set[str] = set()
        for value in values:
            if value is None:
                continue
            text = str(value).strip().lower()
            if not text:
                continue
            if not text.startswith("."):
                text = f".{text}"
            normalized.add(text)
        return normalized
