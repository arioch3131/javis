# services/auto_organization_service.py
"""
Auto Organization Service - Service for automatically organizing files.

Pure service containing only business organization logic.
Independent from the user interface and Qt signals.
"""

import os
import shutil

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ai_content_classifier.core.logger import LoggableMixin
from ai_content_classifier.services.database.types import DatabaseOperationCode


@dataclass
class OrganizationResult:
    """Result of an organization operation."""

    success: bool
    source_path: str
    target_path: str
    action: str  # 'copy' ou 'move'
    error_message: Optional[str] = None
    size_bytes: int = 0


@dataclass
class OrganizationConfig:
    """Configuration for file organization."""

    target_directory: str
    organization_structure: str
    organization_action: str = "copy"  # 'copy' ou 'move'
    custom_rules: Optional[Dict] = None


class AutoOrganizationService(LoggableMixin):
    """
    Pure service for organizing files according to multiple structures.
    Independent from the user interface.
    """

    def __init__(self, content_database_service):
        self.__init_logger__()
        self.db_service = content_database_service

        # Supported organization structures
        self.structure_handlers = {
            "By Category": self._organize_by_category,
            "By Year": self._organize_by_year,
            "By Type": self._organize_by_type,
            "By Category/Year": self._organize_by_category_year,
            "By Type/Category": self._organize_by_type_category,
            "Custom": self._organize_custom,
        }

    def validate_config(self, config: OrganizationConfig) -> Tuple[bool, Optional[str]]:
        """
        Validate organization configuration.

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        try:
            # Check target folder
            if not config.target_directory:
                return False, "No target directory specified"

            # Check that the target folder parent exists
            parent_dir = os.path.dirname(config.target_directory)
            if parent_dir and not os.path.exists(parent_dir):
                return False, f"Parent directory does not exist: {parent_dir}"

            # Check structure
            if config.organization_structure not in self.structure_handlers:
                return (
                    False,
                    f"Unsupported organization structure: {config.organization_structure}",
                )

            # Check action
            if config.organization_action not in ["copy", "move"]:
                return (
                    False,
                    f"Invalid organization action: {config.organization_action}",
                )

            return True, None

        except Exception as e:
            self.logger.error(f"Error validating config: {e}")
            return False, str(e)

    def prepare_target_structure(self, config: OrganizationConfig) -> bool:
        """Prepare target folder structure."""
        try:
            # Create root target folder
            os.makedirs(config.target_directory, exist_ok=True)
            self.logger.info(f"Target directory prepared: {config.target_directory}")

            # Pre-create structure depending on selected type
            if config.organization_structure == "By Category":
                categories = self._get_available_categories()
                for category in categories:
                    category_dir = os.path.join(
                        config.target_directory, self._sanitize_dirname(category)
                    )
                    os.makedirs(category_dir, exist_ok=True)

            elif config.organization_structure == "By Type":
                file_types = ["Documents", "Images", "Videos", "Audio", "Others"]
                for file_type in file_types:
                    type_dir = os.path.join(config.target_directory, file_type)
                    os.makedirs(type_dir, exist_ok=True)

            elif config.organization_structure == "By Year":
                # Create folders for recent years
                current_year = datetime.now().year
                for year in range(current_year - 10, current_year + 1):
                    year_dir = os.path.join(config.target_directory, str(year))
                    os.makedirs(year_dir, exist_ok=True)

            # Mixed structures will be created dynamically
            return True

        except Exception as e:
            self.logger.error(f"Error preparing target structure: {e}")
            return False

    def organize_single_file(
        self, file_path: str, config: OrganizationConfig
    ) -> OrganizationResult:
        """
        Organize a single file based on configuration.

        Args:
            file_path: Path to the file to organize
            config: Organization configuration

        Returns:
            OrganizationResult: Operation result
        """
        try:
            handler = self.structure_handlers[config.organization_structure]
            return handler(file_path, config)

        except Exception as e:
            self.logger.error(f"Error organizing file {file_path}: {e}")
            return OrganizationResult(
                success=False,
                source_path=file_path,
                target_path="",
                action=config.organization_action,
                error_message=str(e),
            )

    def _safe_get_content_item(self, file_path: str) -> Optional[Any]:
        """Safely fetches content item from database service."""
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
        except Exception as e:
            self.logger.debug(f"Could not fetch content item for {file_path}: {e}")
            return None

    def _extract_category(self, content_item: Optional[Any]) -> str:
        """Extracts a category from a content item with robust fallbacks."""
        category = getattr(content_item, "category", None) if content_item else None
        if not isinstance(category, str) or not category.strip():
            return "Uncategorized"
        return category

    def _extract_year(self, file_path: str, content_item: Optional[Any]) -> int:
        """Extracts year from content item creation date or falls back to file mtime."""
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

    def _organize_by_category(
        self, file_path: str, config: OrganizationConfig
    ) -> OrganizationResult:
        """Organize a file by category."""
        try:
            # Retrieve file category
            content_item = self._safe_get_content_item(file_path)
            category = self._extract_category(content_item)

            # Build target path
            category_dir = os.path.join(
                config.target_directory, self._sanitize_dirname(category)
            )
            os.makedirs(category_dir, exist_ok=True)

            filename = os.path.basename(file_path)
            target_path = os.path.join(category_dir, filename)

            # Handle name conflicts
            target_path = self._resolve_name_conflict(target_path)

            # Perform action
            return self._perform_file_action(
                file_path, target_path, config.organization_action
            )

        except Exception as e:
            self.logger.error(f"Error organizing by category: {e}")
            return OrganizationResult(
                success=False,
                source_path=file_path,
                target_path="",
                action=config.organization_action,
                error_message=str(e),
            )

    def _organize_by_year(
        self, file_path: str, config: OrganizationConfig
    ) -> OrganizationResult:
        """Organize a file by year."""
        try:
            # Retrieve file year
            content_item = self._safe_get_content_item(file_path)
            year = self._extract_year(file_path, content_item)

            # Build target path
            year_dir = os.path.join(config.target_directory, str(year))
            os.makedirs(year_dir, exist_ok=True)

            filename = os.path.basename(file_path)
            target_path = os.path.join(year_dir, filename)

            # Handle name conflicts
            target_path = self._resolve_name_conflict(target_path)

            # Perform action
            return self._perform_file_action(
                file_path, target_path, config.organization_action
            )

        except Exception as e:
            self.logger.error(f"Error organizing by year: {e}")
            return OrganizationResult(
                success=False,
                source_path=file_path,
                target_path="",
                action=config.organization_action,
                error_message=str(e),
            )

    def _organize_by_type(
        self, file_path: str, config: OrganizationConfig
    ) -> OrganizationResult:
        """Organize a file by type."""
        try:
            # Determine file type
            file_type = self.determine_file_type(file_path)

            # Build target path
            type_dir = os.path.join(config.target_directory, file_type)
            os.makedirs(type_dir, exist_ok=True)

            filename = os.path.basename(file_path)
            target_path = os.path.join(type_dir, filename)

            # Handle name conflicts
            target_path = self._resolve_name_conflict(target_path)

            # Perform action
            return self._perform_file_action(
                file_path, target_path, config.organization_action
            )

        except Exception as e:
            self.logger.error(f"Error organizing by type: {e}")
            return OrganizationResult(
                success=False,
                source_path=file_path,
                target_path="",
                action=config.organization_action,
                error_message=str(e),
            )

    def _organize_by_category_year(
        self, file_path: str, config: OrganizationConfig
    ) -> OrganizationResult:
        """Organize a file by category then year."""
        try:
            # Retrieve category and year
            content_item = self._safe_get_content_item(file_path)
            category = self._extract_category(content_item)
            year = self._extract_year(file_path, content_item)

            # Build target path
            category_dir = os.path.join(
                config.target_directory, self._sanitize_dirname(category)
            )
            year_dir = os.path.join(category_dir, str(year))
            os.makedirs(year_dir, exist_ok=True)

            filename = os.path.basename(file_path)
            target_path = os.path.join(year_dir, filename)

            # Handle name conflicts
            target_path = self._resolve_name_conflict(target_path)

            # Perform action
            return self._perform_file_action(
                file_path, target_path, config.organization_action
            )

        except Exception as e:
            self.logger.error(f"Error organizing by category/year: {e}")
            return OrganizationResult(
                success=False,
                source_path=file_path,
                target_path="",
                action=config.organization_action,
                error_message=str(e),
            )

    def _organize_by_type_category(
        self, file_path: str, config: OrganizationConfig
    ) -> OrganizationResult:
        """Organize a file by type then category."""
        try:
            # Determine type and category
            file_type = self.determine_file_type(file_path)
            content_item = self._safe_get_content_item(file_path)
            category = self._extract_category(content_item)

            # Build target path
            type_dir = os.path.join(config.target_directory, file_type)
            category_dir = os.path.join(type_dir, self._sanitize_dirname(category))
            os.makedirs(category_dir, exist_ok=True)

            filename = os.path.basename(file_path)
            target_path = os.path.join(category_dir, filename)

            # Handle name conflicts
            target_path = self._resolve_name_conflict(target_path)

            # Perform action
            return self._perform_file_action(
                file_path, target_path, config.organization_action
            )

        except Exception as e:
            self.logger.error(f"Error organizing by type/category: {e}")
            return OrganizationResult(
                success=False,
                source_path=file_path,
                target_path="",
                action=config.organization_action,
                error_message=str(e),
            )

    def _organize_custom(
        self, file_path: str, config: OrganizationConfig
    ) -> OrganizationResult:
        """Organize a file using a custom structure."""
        try:
            # TODO: Implement custom logic
            # For now, fallback to category
            return self._organize_by_category(file_path, config)

        except Exception as e:
            self.logger.error(f"Error in custom organization: {e}")
            return OrganizationResult(
                success=False,
                source_path=file_path,
                target_path="",
                action=config.organization_action,
                error_message=str(e),
            )

    def _perform_file_action(
        self, source_path: str, target_path: str, action: str
    ) -> OrganizationResult:
        """Perform action on file (copy or move)."""
        try:
            # Check source exists
            if not os.path.exists(source_path):
                return OrganizationResult(
                    success=False,
                    source_path=source_path,
                    target_path=target_path,
                    action=action,
                    error_message="Source file does not exist",
                )

            # Get file size
            file_size = os.path.getsize(source_path)

            # Perform action
            if action == "copy":
                shutil.copy2(source_path, target_path)  # copy2 preserves metadata
                self.logger.debug(f"File copied: {source_path} -> {target_path}")

            elif action == "move":
                shutil.move(source_path, target_path)
                self.logger.debug(f"File moved: {source_path} -> {target_path}")

            return OrganizationResult(
                success=True,
                source_path=source_path,
                target_path=target_path,
                action=action,
                size_bytes=file_size,
            )

        except Exception as e:
            self.logger.error(f"Error performing file action: {e}")
            return OrganizationResult(
                success=False,
                source_path=source_path,
                target_path=target_path,
                action=action,
                error_message=str(e),
            )

    def _resolve_name_conflict(self, target_path: str) -> str:
        """Resolve file name conflicts."""
        if not os.path.exists(target_path):
            return target_path

        # Generate a unique name
        base, ext = os.path.splitext(target_path)
        counter = 1

        while os.path.exists(target_path):
            target_path = f"{base}_{counter}{ext}"
            counter += 1

        return target_path

    def determine_file_type(self, file_path: str) -> str:
        """Determine file type."""
        ext = os.path.splitext(file_path)[1].lower()

        # Document extensions
        if ext in {
            ".pdf",
            ".doc",
            ".docx",
            ".txt",
            ".md",
            ".rtf",
            ".odt",
            ".csv",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
        }:
            return "Documents"

        # Image extensions
        elif ext in {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".tiff",
            ".webp",
            ".ico",
            ".heic",
            ".heif",
            ".svg",
        }:
            return "Images"

        # Extensions for videos
        elif ext in {
            ".mp4",
            ".avi",
            ".mov",
            ".wmv",
            ".flv",
            ".webm",
            ".mkv",
            ".m4v",
            ".3gp",
            ".ogv",
        }:
            return "Videos"

        # Audio extensions
        elif ext in {
            ".mp3",
            ".wav",
            ".flac",
            ".aac",
            ".ogg",
            ".wma",
            ".m4a",
            ".opus",
            ".aiff",
        }:
            return "Audio"

        else:
            return "Others"

    def _get_available_categories(self) -> List[str]:
        """Get available categories from the database."""
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
        except Exception as e:
            self.logger.error(f"Error getting categories: {e}")
            return ["Work", "Personal", "Archive", "Uncategorized"]

    def _sanitize_dirname(self, name: str) -> str:
        """Sanitize a value for safe folder-name usage."""
        # Replace problematic characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, "_")

        # Limit length
        if len(name) > 100:
            name = name[:100]

        # Avoid reserved names
        reserved_names = {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
        }
        if name.upper() in reserved_names:
            name = f"{name}_folder"

        return name.strip()

    def get_organization_preview(
        self, file_list: List[str], config: OrganizationConfig
    ) -> Dict:
        """
        Generate an organization preview without performing actions.

        Args:
            file_list: List of file paths
            config: Organization configuration

        Returns:
            dict: Preview of the structure that would be created
        """
        try:
            preview = {
                "structure": {},
                "file_count": 0,
                "total_size_mb": 0,
                "conflicts": [],
            }

            for file_path in file_list:
                try:
                    # Simulate organization without performing action
                    if config.organization_structure == "By Category":
                        content_item = self._safe_get_content_item(file_path)
                        category = self._extract_category(content_item)
                        folder_path = os.path.join(
                            config.target_directory, self._sanitize_dirname(category)
                        )

                    elif config.organization_structure == "By Type":
                        file_type = self.determine_file_type(file_path)
                        folder_path = os.path.join(config.target_directory, file_type)

                    elif config.organization_structure == "By Year":
                        year = datetime.fromtimestamp(os.path.getmtime(file_path)).year
                        folder_path = os.path.join(config.target_directory, str(year))

                    else:
                        folder_path = config.target_directory

                    # Add to preview structure
                    if folder_path not in preview["structure"]:
                        preview["structure"][folder_path] = []

                    filename = os.path.basename(file_path)
                    preview["structure"][folder_path].append(filename)

                    # Statistics
                    preview["file_count"] += 1
                    try:
                        file_size = os.path.getsize(file_path)
                        preview["total_size_mb"] += file_size / (1024 * 1024)
                    except OSError:
                        pass

                    # Detect potential conflicts
                    target_file_path = os.path.join(folder_path, filename)
                    if os.path.exists(target_file_path):
                        preview["conflicts"].append(
                            {
                                "source": file_path,
                                "target": target_file_path,
                                "type": "name_conflict",
                            }
                        )

                except Exception as e:
                    self.logger.warning(f"Error previewing file {file_path}: {e}")
                    continue

            return preview

        except Exception as e:
            self.logger.error(f"Error generating organization preview: {e}")
            return {"error": str(e)}

    def calculate_statistics(
        self, results: List[OrganizationResult], config: OrganizationConfig
    ) -> Dict:
        """
        Calculate statistics for an organization operation.

        Args:
            results: List of organization results
            config: Configuration used

        Returns:
            dict: Detailed statistics
        """
        try:
            # Calculate statistics
            total_files = len(results)
            successful = sum(1 for r in results if r.success)
            failed = total_files - successful
            total_size = sum(r.size_bytes for r in results if r.success)

            # Statistics by action
            copied = sum(1 for r in results if r.success and r.action == "copy")
            moved = sum(1 for r in results if r.success and r.action == "move")

            # Statistics by file type
            type_stats = {}
            for result in results:
                if result.success:
                    file_type = self.determine_file_type(result.source_path)
                    type_stats[file_type] = type_stats.get(file_type, 0) + 1

            return {
                "total_files": total_files,
                "successful": successful,
                "failed": failed,
                "success_rate": (
                    (successful / total_files * 100) if total_files > 0 else 0
                ),
                "total_size_mb": total_size / (1024 * 1024),
                "copied": copied,
                "moved": moved,
                "by_type": type_stats,
                "target_directory": config.target_directory,
                "structure": config.organization_structure,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Error calculating statistics: {e}")
            return {"error": str(e)}
