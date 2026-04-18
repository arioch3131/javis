"""Auto Organization Service."""

import os

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ai_content_classifier.core.logger import LoggableMixin
from ai_content_classifier.services.auto_organization.operations import (
    CalculateStatisticsOperation,
    GeneratePreviewOperation,
    OrganizeSingleFileOperation,
)
from ai_content_classifier.services.auto_organization.operations.helpers import (
    determine_file_type,
    sanitize_dirname,
)
from ai_content_classifier.services.auto_organization.operations.types import (
    AutoOrganizationStructure,
)
from ai_content_classifier.services.auto_organization.types import (
    AutoOrganizationOperationResult,
    OrganizationConfig,
)
from ai_content_classifier.services.database.types import DatabaseOperationCode


class AutoOrganizationService(LoggableMixin):
    """Pure service for organizing files according to multiple structures."""

    def __init__(self, content_database_service: Any):
        self.__init_logger__()
        self.db_service = content_database_service

        self._organize_single_file_operation = OrganizeSingleFileOperation(
            db_service=self.db_service,
            logger=self.logger,
        )
        self._generate_preview_operation = GeneratePreviewOperation(
            logger=self.logger,
            category_year_resolver=self._resolve_category_year,
        )
        self._calculate_statistics_operation = CalculateStatisticsOperation(
            logger=self.logger,
        )

    @property
    def structure_handlers(self) -> Dict[str, str]:
        """Expose supported structures for controller/UI compatibility."""
        return {member.value: member.value for member in AutoOrganizationStructure}

    def validate_config(self, config: OrganizationConfig) -> Tuple[bool, Optional[str]]:
        """Validate organization configuration."""
        try:
            if not config.target_directory:
                return False, "No target directory specified"

            parent_dir = os.path.dirname(config.target_directory)
            if parent_dir and not os.path.exists(parent_dir):
                return False, f"Parent directory does not exist: {parent_dir}"

            if config.organization_structure not in self.structure_handlers:
                return (
                    False,
                    f"Unsupported organization structure: {config.organization_structure}",
                )

            if config.organization_action not in ["copy", "move"]:
                return (
                    False,
                    f"Invalid organization action: {config.organization_action}",
                )

            return True, None
        except Exception as exc:
            self.logger.error(f"Error validating config: {exc}")
            return False, str(exc)

    def prepare_target_structure(self, config: OrganizationConfig) -> bool:
        """Prepare target folder structure."""
        try:
            os.makedirs(config.target_directory, exist_ok=True)
            self.logger.info(f"Target directory prepared: {config.target_directory}")

            if (
                config.organization_structure
                == AutoOrganizationStructure.BY_CATEGORY.value
            ):
                categories = self._get_available_categories()
                for category in categories:
                    os.makedirs(
                        os.path.join(
                            config.target_directory, sanitize_dirname(category)
                        ),
                        exist_ok=True,
                    )
            elif (
                config.organization_structure == AutoOrganizationStructure.BY_TYPE.value
            ):
                for file_type in ["Documents", "Images", "Videos", "Audio", "Others"]:
                    os.makedirs(
                        os.path.join(config.target_directory, file_type), exist_ok=True
                    )
            elif (
                config.organization_structure == AutoOrganizationStructure.BY_YEAR.value
            ):
                current_year = datetime.now().year
                for year in range(current_year - 10, current_year + 1):
                    os.makedirs(
                        os.path.join(config.target_directory, str(year)), exist_ok=True
                    )

            return True
        except Exception as exc:
            self.logger.error(f"Error preparing target structure: {exc}")
            return False

    def organize_single_file(
        self, file_path: str, config: OrganizationConfig
    ) -> AutoOrganizationOperationResult:
        """Organize a single file based on configuration."""
        return self._organize_single_file_operation.execute(
            file_path=file_path, config=config
        )

    def get_organization_preview(
        self, file_list: List[str], config: OrganizationConfig
    ) -> Dict[str, Any]:
        """Generate an organization preview without performing actions."""
        return self._generate_preview_operation.execute(
            file_list=file_list, config=config
        )

    def calculate_statistics(
        self,
        results: List[AutoOrganizationOperationResult],
        config: OrganizationConfig,
    ) -> Dict[str, Any]:
        """Calculate statistics for an organization operation."""
        return self._calculate_statistics_operation.execute(
            results=results, config=config
        )

    def determine_file_type(self, file_path: str) -> str:
        """Backwards-compatible helper used by tests/UI helpers."""
        return determine_file_type(file_path)

    def _safe_get_content_item(self, file_path: str) -> Optional[Any]:
        try:
            result = self.db_service.get_content_by_path(file_path)
            if not result.success:
                if result.code != DatabaseOperationCode.NOT_FOUND:
                    self.logger.warning(
                        "DB read failed for path '%s': code=%s message=%s",
                        file_path,
                        result.code,
                        result.message,
                    )
                return None
            return (result.data or {}).get("item")
        except Exception as exc:
            self.logger.debug(f"Could not fetch content item for {file_path}: {exc}")
            return None

    def _resolve_category_year(self, file_path: str) -> Tuple[str, int]:
        content_item = self._safe_get_content_item(file_path)

        category = getattr(content_item, "category", None) if content_item else None
        if not isinstance(category, str) or not category.strip():
            category = "Uncategorized"

        try:
            creation_date = (
                getattr(content_item, "creation_date", None) if content_item else None
            )
            if hasattr(creation_date, "year"):
                year = creation_date.year
            elif isinstance(creation_date, str) and creation_date.strip():
                year = datetime.fromisoformat(creation_date).year
            elif isinstance(content_item, dict) and hasattr(
                content_item.get("creation_date"), "year"
            ):
                year = content_item["creation_date"].year
            else:
                year = datetime.fromtimestamp(os.path.getmtime(file_path)).year
        except Exception:
            year = datetime.now().year

        return category, int(year)

    @staticmethod
    def _extract_category(content_item: Optional[Any]) -> str:
        category = getattr(content_item, "category", None) if content_item else None
        if not isinstance(category, str) or not category.strip():
            return "Uncategorized"
        return category

    @staticmethod
    def _extract_year(file_path: str, content_item: Optional[Any]) -> int:
        try:
            creation_date = (
                getattr(content_item, "creation_date", None) if content_item else None
            )
            if hasattr(creation_date, "year"):
                return creation_date.year
            if isinstance(creation_date, str) and creation_date.strip():
                try:
                    return datetime.fromisoformat(creation_date).year
                except ValueError:
                    pass
            if isinstance(content_item, dict):
                metadata_date = content_item.get("creation_date")
                if hasattr(metadata_date, "year"):
                    return metadata_date.year
            return datetime.fromtimestamp(os.path.getmtime(file_path)).year
        except (OSError, TypeError, ValueError):
            return datetime.now().year

    def _perform_file_action(
        self, source_path: str, target_path: str, action: str
    ) -> AutoOrganizationOperationResult:
        return self._organize_single_file_operation._perform_file_action(
            source_path=source_path,
            target_path=target_path,
            action=action,
        )

    def _get_available_categories(self) -> List[str]:
        try:
            categories_result = self.db_service.get_unique_categories()
            if not categories_result.success:
                self.logger.warning(
                    "Unable to load categories from DB: code=%s message=%s",
                    categories_result.code,
                    categories_result.message,
                )
                return ["Work", "Personal", "Archive", "Uncategorized"]
            categories = (categories_result.data or {}).get("categories", [])
            if not categories:
                categories = ["Work", "Personal", "Archive", "Uncategorized"]
            return categories
        except Exception as exc:
            self.logger.error(f"Error getting categories: {exc}")
            return ["Work", "Personal", "Archive", "Uncategorized"]
