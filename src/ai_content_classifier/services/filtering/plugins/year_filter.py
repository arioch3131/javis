"""Year filter plugin."""

from __future__ import annotations

import os
import re

from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from ai_content_classifier.services.filtering.types import (
    FilterCriterion,
    FilterOperator,
)


class YearFilterPlugin:
    """Filter plugin for `year` criteria."""

    key = "year"

    def validate(self, criterion: FilterCriterion) -> Optional[str]:
        if criterion.op not in {
            FilterOperator.EQ.value,
            FilterOperator.IN.value,
            FilterOperator.RANGE.value,
        }:
            return f"Unsupported operator '{criterion.op}' for 'year'."

        years = self._resolve_target_years(criterion)
        if not years:
            return "'year' requires at least one valid year between 1900 and 2100."
        return None

    def to_db_clause(self, criterion: FilterCriterion) -> Optional[List[Any]]:
        # Keep year filtering in memory to preserve metadata/mtime fallback behavior.
        return None

    def apply_memory(
        self,
        items: List[Tuple[str, str]],
        criterion: FilterCriterion,
        context: Dict[str, Any],
    ) -> List[Tuple[str, str]]:
        target_years = self._resolve_target_years(criterion)
        if not target_years:
            return []

        get_content_map = context.get("get_content_map")
        if not callable(get_content_map):
            return []

        content_map = get_content_map(items)
        filtered: List[Tuple[str, str]] = []
        for path, directory in items:
            content_item = content_map.get(path)
            if not content_item:
                continue
            year_value = self._resolve_file_year(content_item, path)
            if year_value is not None and year_value in target_years:
                filtered.append((path, directory))
        return filtered

    def _resolve_target_years(self, criterion: FilterCriterion) -> Set[int]:
        if criterion.op == FilterOperator.RANGE.value:
            start, end = self._parse_range(criterion.value)
            if start is None or end is None:
                return set()
            if start > end:
                start, end = end, start
            return {year for year in range(start, end + 1) if 1900 <= year <= 2100}

        values = (
            criterion.value if isinstance(criterion.value, list) else [criterion.value]
        )
        years: Set[int] = set()
        for raw in values:
            parsed = self._to_int_year(raw)
            if parsed is not None:
                years.add(parsed)
        return years

    def _parse_range(self, raw_value: Any) -> Tuple[Optional[int], Optional[int]]:
        if isinstance(raw_value, dict):
            return self._to_int_year(raw_value.get("start")), self._to_int_year(
                raw_value.get("end")
            )
        if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 2:
            return self._to_int_year(raw_value[0]), self._to_int_year(raw_value[1])
        return None, None

    def _to_int_year(self, raw_value: Any) -> Optional[int]:
        if raw_value is None:
            return None
        try:
            year = int(raw_value)
        except (TypeError, ValueError):
            return None
        return year if 1900 <= year <= 2100 else None

    def _resolve_file_year(self, content_item: Any, file_path: str) -> Optional[int]:
        year_taken = getattr(content_item, "year_taken", None)
        normalized = self._to_int_year(year_taken)
        if normalized is not None:
            return normalized

        for attr_name in ("date_created", "date_modified", "date_indexed"):
            raw_date = getattr(content_item, attr_name, None)
            year_value = getattr(raw_date, "year", None) if raw_date else None
            normalized = self._to_int_year(year_value)
            if normalized is not None:
                return normalized

        metadata = getattr(content_item, "content_metadata", None) or {}
        for date_key in (
            "year",
            "year_taken",
            "creation_date",
            "date_created",
            "date",
            "created",
            "timestamp",
            "DateTimeOriginal",
            "datetime_original",
        ):
            if date_key in metadata and metadata[date_key] is not None:
                metadata_year = self._extract_year_from_value(metadata[date_key])
                if metadata_year is not None:
                    return metadata_year

        try:
            return datetime.fromtimestamp(os.path.getmtime(file_path)).year
        except (OSError, OverflowError, ValueError):
            return None

    def _extract_year_from_value(self, raw_value: Any) -> Optional[int]:
        text = str(raw_value).strip()
        if not text:
            return None

        match = re.search(r"(19\d{2}|20\d{2}|2100)", text)
        if not match:
            return None
        return self._to_int_year(match.group(1))
