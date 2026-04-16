"""Typed result contracts for database mutations."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class DatabaseOperationCode(str, Enum):
    """Normalized outcome codes for UI-facing database mutations."""

    OK = "ok"
    NOT_FOUND = "not_found"
    INVALID_INPUT = "invalid_input"
    PARTIAL_SUCCESS = "partial_success"
    DB_ERROR = "db_error"
    UNKNOWN_ERROR = "unknown_error"


class DatabaseOperationDataKey(str, Enum):
    """Canonical keys used in ``DatabaseOperationResult.data`` payloads."""

    DELETED_COUNT = "deleted_count"
    IGNORED_COUNT = "ignored_count"
    FAILED_IDS = "failed_ids"
    FAILED_PATHS = "failed_paths"
    NORMALIZED_PATHS = "normalized_paths"
    ERROR = "error"


@dataclass
class DatabaseOperationResult:
    """Structured result object for database mutations."""

    success: bool
    code: DatabaseOperationCode
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
