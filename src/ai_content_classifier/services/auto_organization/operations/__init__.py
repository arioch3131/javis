"""Auto-organization operations package."""

from ai_content_classifier.services.auto_organization.operations.calculate_statistics_operation import (
    CalculateStatisticsOperation,
)
from ai_content_classifier.services.auto_organization.operations.generate_preview_operation import (
    GeneratePreviewOperation,
)
from ai_content_classifier.services.auto_organization.operations.organize_single_file_operation import (
    OrganizeSingleFileOperation,
)
from ai_content_classifier.services.auto_organization.operations.types import (
    AutoOrganizationOperationKind,
    AutoOrganizationStructure,
)

__all__ = [
    "AutoOrganizationOperationKind",
    "AutoOrganizationStructure",
    "CalculateStatisticsOperation",
    "GeneratePreviewOperation",
    "OrganizeSingleFileOperation",
]
