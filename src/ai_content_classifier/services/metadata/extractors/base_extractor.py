"""
Base metadata extractor module.

This module defines the base class for all metadata extractors.
"""

import os
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from ai_content_classifier.core.logger import LoggableMixin
from ai_content_classifier.services.file.file_type_service import FileTypeService


class BaseMetadataExtractor(ABC, LoggableMixin):
    """Base class for all metadata extractors."""

    # Constants for commonly used date field names
    DATE_FIELDS = ["creation_date", "date", "created", "last_modified"]

    def __init__(self) -> None:
        """Initialize the extractor."""
        self.__init_logger__()
        self.logger.debug(f"Initialized {self.__class__.__name__}")

    @abstractmethod
    def can_handle(self, file_path: str) -> bool:
        """
        Determine if this extractor can process the given file.

        Args:
            file_path: Path to the file

        Returns:
            True if the extractor can process this file, False otherwise
        """
        pass

    @abstractmethod
    def get_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract metadata from the file.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary of metadata
        """
        pass

    def get_basic_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract basic metadata common to all files.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary of basic metadata
        """
        # Validate file path
        if not file_path or not isinstance(file_path, str):
            self.logger.warning(f"Invalid file path: {file_path}")
            return {"error": "Invalid file path"}

        if not os.path.exists(file_path):
            self.logger.warning(f"File does not exist: {file_path}")
            return {"error": "File does not exist"}

        path_obj = Path(file_path)

        # Basic metadata
        metadata: Dict[str, Any] = {
            "filename": path_obj.name,
            "path": file_path,
            "extension": path_obj.suffix.lower(),
            "file_type": self._determine_file_type(path_obj.suffix.lower()),
        }

        # Add file size if available
        try:
            metadata["size"] = os.path.getsize(file_path)
            metadata["size_formatted"] = self._format_size(metadata["size"])
        except Exception as e:
            self.logger.debug(f"Could not get file size: {str(e)}")

        # Add file dates
        try:
            metadata["last_modified"] = datetime.fromtimestamp(
                os.path.getmtime(file_path)
            )
        except Exception as e:
            self.logger.debug(f"Could not get modification time: {str(e)}")

        try:
            metadata["created"] = datetime.fromtimestamp(os.path.getctime(file_path))
        except Exception as e:
            self.logger.debug(f"Could not get creation time: {str(e)}")

        return metadata

    def _determine_file_type(self, extension: str) -> str:
        """
        Determine general file type based on extension.

        Args:
            extension: File extension (with leading dot)

        Returns:
            General file type category
        """
        normalized_ext = FileTypeService.normalize_extension(extension)
        category = FileTypeService.get_file_category(normalized_ext)

        if category.name == "IMAGE":
            return "image"
        if category.name == "DOCUMENT":
            return "document"
        if category.name == "AUDIO":
            return "audio"
        if category.name == "VIDEO":
            return "video"
        if category.name == "ARCHIVE":
            return "archive"
        return "other"

    def _format_size(self, size_bytes: int) -> str:
        """
        Format file size in human-readable format.

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted size string
        """
        # Define size units
        units = ["B", "KB", "MB", "GB", "TB"]

        # Calculate appropriate unit
        unit_index = 0
        size = float(size_bytes)

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        # Format with appropriate precision
        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.2f} {units[unit_index]}"
