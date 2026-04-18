"""Organization preview operation."""

import os

from datetime import datetime
from typing import Any, Dict, List

from ai_content_classifier.services.auto_organization.operations.helpers import (
    determine_file_type,
    sanitize_dirname,
)
from ai_content_classifier.services.auto_organization.operations.types import (
    AutoOrganizationStructure,
)
from ai_content_classifier.services.auto_organization.types import OrganizationConfig


class GeneratePreviewOperation:
    """Generate a non-destructive preview of organization outputs."""

    def __init__(self, logger: Any, category_year_resolver: Any):
        self.logger = logger
        self._category_year_resolver = category_year_resolver

    def execute(
        self, file_list: List[str], config: OrganizationConfig
    ) -> Dict[str, Any]:
        try:
            preview: Dict[str, Any] = {
                "structure": {},
                "file_count": 0,
                "total_size_mb": 0,
                "conflicts": [],
            }

            for file_path in file_list:
                try:
                    structure = config.organization_structure
                    if structure == AutoOrganizationStructure.BY_CATEGORY.value:
                        category, _ = self._category_year_resolver(file_path)
                        folder_path = os.path.join(
                            config.target_directory,
                            sanitize_dirname(category),
                        )
                    elif structure == AutoOrganizationStructure.BY_TYPE.value:
                        folder_path = os.path.join(
                            config.target_directory,
                            determine_file_type(file_path),
                        )
                    elif structure == AutoOrganizationStructure.BY_YEAR.value:
                        year = datetime.fromtimestamp(os.path.getmtime(file_path)).year
                        folder_path = os.path.join(config.target_directory, str(year))
                    elif structure == AutoOrganizationStructure.BY_CATEGORY_YEAR.value:
                        category, year = self._category_year_resolver(file_path)
                        folder_path = os.path.join(
                            config.target_directory,
                            sanitize_dirname(category),
                            str(year),
                        )
                    elif structure == AutoOrganizationStructure.BY_TYPE_CATEGORY.value:
                        category, _ = self._category_year_resolver(file_path)
                        folder_path = os.path.join(
                            config.target_directory,
                            determine_file_type(file_path),
                            sanitize_dirname(category),
                        )
                    else:
                        folder_path = config.target_directory

                    if folder_path not in preview["structure"]:
                        preview["structure"][folder_path] = []

                    filename = os.path.basename(file_path)
                    preview["structure"][folder_path].append(filename)
                    preview["file_count"] += 1

                    try:
                        file_size = os.path.getsize(file_path)
                        preview["total_size_mb"] += file_size / (1024 * 1024)
                    except OSError:
                        pass

                    target_file_path = os.path.join(folder_path, filename)
                    if os.path.exists(target_file_path):
                        preview["conflicts"].append(
                            {
                                "source": file_path,
                                "target": target_file_path,
                                "type": "name_conflict",
                            }
                        )
                except Exception as exc:
                    self.logger.warning(f"Error previewing file {file_path}: {exc}")
                    continue

            return preview
        except Exception as exc:
            self.logger.error(f"Error generating organization preview: {exc}")
            return {"error": str(exc)}
