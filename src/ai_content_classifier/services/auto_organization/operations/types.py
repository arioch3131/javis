"""Operation-specific contracts for auto-organization service operations."""

from enum import Enum


class AutoOrganizationOperationKind(str, Enum):
    """Known operation kinds handled by ``AutoOrganizationService``."""

    ORGANIZE_SINGLE_FILE = "organize_single_file"
    GENERATE_PREVIEW = "generate_preview"
    CALCULATE_STATISTICS = "calculate_statistics"


class AutoOrganizationStructure(str, Enum):
    """Supported organization structures."""

    BY_CATEGORY = "By Category"
    BY_YEAR = "By Year"
    BY_TYPE = "By Type"
    BY_CATEGORY_YEAR = "By Category/Year"
    BY_TYPE_CATEGORY = "By Type/Category"
    CUSTOM = "Custom"
