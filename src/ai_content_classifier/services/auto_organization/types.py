"""Typed contracts for auto-organization operations."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class AutoOrganizationOperationCode(str, Enum):
    """Normalized operation codes for auto-organization outcomes."""

    OK = "ok"
    VALIDATION_ERROR = "validation_error"
    FILESYSTEM_ERROR = "filesystem_error"
    DATABASE_ERROR = "database_error"
    CONFLICT_ERROR = "conflict_error"
    CANCELLED = "cancelled"
    UNKNOWN_ERROR = "unknown_error"


class AutoOrganizationDataKey(str, Enum):
    """Canonical keys used in ``AutoOrganizationOperationResult.data``."""

    SOURCE_PATH = "source_path"
    TARGET_PATH = "target_path"
    ACTION = "action"
    ERROR = "error"
    FILE_HASH = "file_hash"
    SIZE_BYTES = "size_bytes"


@dataclass
class AutoOrganizationOperationResult:
    """Unified result contract for auto-organization operations."""

    success: bool
    code: AutoOrganizationOperationCode
    message: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrganizationConfig:
    """Configuration for file organization."""

    target_directory: str
    organization_structure: str
    organization_action: str = "copy"
    custom_rules: Optional[Dict[str, Any]] = None
