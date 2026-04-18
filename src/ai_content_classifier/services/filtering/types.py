"""Contracts for the content filtering subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Tuple


class FilterOperator(str, Enum):
    """Supported operators for filter criteria."""

    EQ = "eq"
    IN = "in"
    RANGE = "range"
    CONTAINS = "contains"


class FilterOperationCode(str, Enum):
    """Normalized result codes for filtering operations."""

    OK = "ok"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN_FILTER = "unknown_filter"
    DATABASE_ERROR = "database_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass(frozen=True)
class FilterCriterion:
    """A normalized criterion consumed by filtering plugins."""

    key: str
    op: str
    value: Any


@dataclass
class FilterScope:
    """Runtime scope for filter execution."""

    base_items: List[Tuple[str, str]] = field(default_factory=list)
    content_by_path: Dict[str, Any] = field(default_factory=dict)
    batch_size: int = 800


@dataclass
class FilterOperationResult:
    """Unified result contract for filtering operations."""

    success: bool
    code: FilterOperationCode
    message: str
    data: Dict[str, Any] = field(default_factory=dict)


class FilterPlugin(Protocol):
    """Common contract implemented by each filter plugin."""

    key: str

    def validate(self, criterion: FilterCriterion) -> Optional[str]:
        """Return a validation error message or ``None`` when valid."""

    def to_db_clause(self, criterion: FilterCriterion) -> Optional[List[Any]]:
        """Return SQLAlchemy filter clauses when push-down is supported."""

    def apply_memory(
        self,
        items: List[Tuple[str, str]],
        criterion: FilterCriterion,
        context: Dict[str, Any],
    ) -> List[Tuple[str, str]]:
        """Apply in-memory filtering to a list of ``(path, directory)`` tuples."""
