"""Statistics aggregation operation for organization results."""

from datetime import datetime
from typing import Any, Dict, List

from ai_content_classifier.services.auto_organization.operations.helpers import (
    determine_file_type,
)
from ai_content_classifier.services.auto_organization.types import (
    AutoOrganizationOperationCode,
    AutoOrganizationOperationResult,
    OrganizationConfig,
)


class CalculateStatisticsOperation:
    """Aggregate organization results into UI-friendly statistics."""

    def __init__(self, logger: Any):
        self.logger = logger

    def execute(
        self,
        results: List[AutoOrganizationOperationResult],
        config: OrganizationConfig,
    ) -> Dict[str, Any]:
        try:
            total_files = len(results)
            successful = sum(1 for result in results if result.success)
            failed = total_files - successful

            total_size = sum(
                int((result.data or {}).get("size_bytes", 0) or 0)
                for result in results
                if result.success
            )
            copied = sum(
                1
                for result in results
                if result.success and (result.data or {}).get("action") == "copy"
            )
            moved = sum(
                1
                for result in results
                if result.success and (result.data or {}).get("action") == "move"
            )

            type_stats: Dict[str, int] = {}
            for result in results:
                if not result.success:
                    continue
                source_path = str((result.data or {}).get("source_path", ""))
                file_type = determine_file_type(source_path)
                type_stats[file_type] = type_stats.get(file_type, 0) + 1

            code_stats: Dict[str, int] = {}
            for result in results:
                code_value = (
                    result.code.value
                    if isinstance(result.code, AutoOrganizationOperationCode)
                    else str(result.code)
                )
                code_stats[code_value] = code_stats.get(code_value, 0) + 1

            return {
                "total_files": total_files,
                "successful": successful,
                "failed": failed,
                "success_rate": (successful / total_files * 100)
                if total_files > 0
                else 0,
                "total_size_mb": total_size / (1024 * 1024),
                "copied": copied,
                "moved": moved,
                "by_type": type_stats,
                "by_code": code_stats,
                "target_directory": config.target_directory,
                "structure": config.organization_structure,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as exc:
            self.logger.error(f"Error calculating statistics: {exc}")
            return {"error": str(exc)}
