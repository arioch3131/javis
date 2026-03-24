"""
File Type Detection Service

Centralized service for detecting file types, validating files, and providing
file-related utilities. This service can be used across the entire application
to ensure consistent file type detection logic.

Used by:
- file_operation_service.py
- file_presenter.py
- preprocessing services
- metadata extractors
- thumbnail services
- grid widgets
"""

import os

from enum import Enum
from typing import Set


class FileCategory(Enum):
    """Enumeration of file categories."""

    IMAGE = "Image"
    DOCUMENT = "Document"
    VIDEO = "Video"
    AUDIO = "Audio"
    ARCHIVE = "Archive"
    CODE = "Code"
    OTHER = "Other"


class FileTypeService:
    """
    Service for file type detection and file utilities.

    This service provides centralized logic for:
    - Detecting file types by extension
    - Categorizing files
    - Validating file paths
    - Formatting file information
    """

    # File extension mappings
    IMAGE_EXTENSIONS: Set[str] = {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".tiff",
        ".tif",
        ".webp",
        ".svg",
        ".ico",
        ".heic",
        ".heif",
        ".jp2",
        ".j2k",
        ".jpx",
        ".j2c",
        ".avif",
        ".jxl",
        ".tga",
        ".dds",
        ".exr",
        ".hdr",
        ".pbm",
        ".pgm",
        ".ppm",
        ".pnm",
        ".raw",
        ".cr2",
        ".nef",
        ".orf",
        ".sr2",
        ".arw",
        ".dng",
        ".rw2",
        ".pef",
        ".raf",
        ".3fr",
        ".fff",
        ".iiq",
        ".x3f",
    }

    DOCUMENT_EXTENSIONS: Set[str] = {
        ".pdf",
        ".doc",
        ".docx",
        ".docm",
        ".dot",
        ".dotx",
        ".dotm",
        ".txt",
        ".md",
        ".markdown",
        ".rst",
        ".tex",
        ".rtf",
        ".odt",
        ".ott",
        ".ods",
        ".ots",
        ".odp",
        ".otp",
        ".odg",
        ".otg",
        ".csv",
        ".tsv",
        ".xls",
        ".xlsx",
        ".xlsm",
        ".xlt",
        ".xltx",
        ".xltm",
        ".ppt",
        ".pptx",
        ".pptm",
        ".pot",
        ".potx",
        ".potm",
        ".pps",
        ".ppsx",
        ".pages",
        ".numbers",
        ".key",
        ".epub",
        ".mobi",
        ".azw",
        ".azw3",
        ".fb2",
        ".lit",
        ".prc",
        ".djvu",
        ".xps",
        ".oxps",
        ".ps",
        ".eps",
    }

    VIDEO_EXTENSIONS: Set[str] = {
        ".mp4",
        ".avi",
        ".mkv",
        ".mov",
        ".wmv",
        ".flv",
        ".webm",
        ".m4v",
        ".3gp",
        ".3g2",
        ".ogv",
        ".ogg",
        ".ts",
        ".m2ts",
        ".mts",
        ".vob",
        ".mpg",
        ".mpeg",
        ".m1v",
        ".m2v",
        ".mpe",
        ".mpv",
        ".mp2",
        ".m4p",
        ".m4b",
        ".f4v",
        ".f4p",
        ".f4a",
        ".f4b",
        ".asf",
        ".rm",
        ".rmvb",
        ".qt",
        ".divx",
        ".xvid",
        ".dv",
        ".amv",
        ".mxf",
        ".roq",
        ".nsv",
    }

    AUDIO_EXTENSIONS: Set[str] = {
        ".mp3",
        ".wav",
        ".flac",
        ".aac",
        ".ogg",
        ".oga",
        ".wma",
        ".m4a",
        ".m4b",
        ".m4p",
        ".mp2",
        ".mp1",
        ".opus",
        ".spx",
        ".ape",
        ".wv",
        ".tta",
        ".ac3",
        ".dts",
        ".ra",
        ".rm",
        ".aiff",
        ".aif",
        ".aifc",
        ".au",
        ".snd",
        ".voc",
        ".iff",
        ".svx",
        ".sf",
        ".vox",
        ".gsm",
        ".amr",
        ".awb",
        ".caf",
        ".xm",
        ".it",
        ".s3m",
        ".mod",
    }

    ARCHIVE_EXTENSIONS: Set[str] = {
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".lzma",
        ".tgz",
        ".tbz2",
        ".txz",
        ".tlz",
        ".tar.gz",
        ".tar.bz2",
        ".tar.xz",
        ".tar.lzma",
        ".cab",
        ".msi",
        ".deb",
        ".rpm",
        ".dmg",
        ".iso",
        ".img",
        ".bin",
        ".cue",
        ".nrg",
        ".mdf",
        ".udf",
        ".vcd",
        ".ace",
        ".arj",
        ".lzh",
        ".zoo",
        ".arc",
    }

    CODE_EXTENSIONS: Set[str] = {
        ".py",
        ".js",
        ".ts",
        ".html",
        ".htm",
        ".css",
        ".scss",
        ".sass",
        ".less",
        ".php",
        ".java",
        ".cpp",
        ".c",
        ".h",
        ".hpp",
        ".cs",
        ".rb",
        ".go",
        ".rs",
        ".swift",
        ".kt",
        ".scala",
        ".clj",
        ".hs",
        ".pl",
        ".sh",
        ".bash",
        ".ps1",
        ".bat",
        ".cmd",
        ".vbs",
        ".lua",
        ".r",
        ".m",
        ".sql",
        ".xml",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".properties",
        ".gradle",
        ".maven",
        ".makefile",
        ".dockerfile",
        ".gitignore",
        ".editorconfig",
    }

    @classmethod
    def is_image_file(cls, file_path: str) -> bool:
        """
        Check if file is an image by extension.

        Args:
            file_path: Path to the file

        Returns:
            True if it's an image file, False otherwise
        """
        ext = os.path.splitext(file_path)[1].lower()
        return ext in cls.IMAGE_EXTENSIONS

    @classmethod
    def is_document_file(cls, file_path: str) -> bool:
        """
        Check if file is a document by extension.

        Args:
            file_path: Path to the file

        Returns:
            True if it's a document file, False otherwise
        """
        ext = os.path.splitext(file_path)[1].lower()
        return ext in cls.DOCUMENT_EXTENSIONS

    @classmethod
    def is_video_file(cls, file_path: str) -> bool:
        """
        Check if file is a video by extension.

        Args:
            file_path: Path to the file

        Returns:
            True if it's a video file, False otherwise
        """
        ext = os.path.splitext(file_path)[1].lower()
        return ext in cls.VIDEO_EXTENSIONS

    @classmethod
    def is_audio_file(cls, file_path: str) -> bool:
        """
        Check if file is an audio by extension.

        Args:
            file_path: Path to the file

        Returns:
            True if it's an audio file, False otherwise
        """
        ext = os.path.splitext(file_path)[1].lower()
        return ext in cls.AUDIO_EXTENSIONS

    @classmethod
    def is_archive_file(cls, file_path: str) -> bool:
        """
        Check if file is an archive by extension.

        Args:
            file_path: Path to the file

        Returns:
            True if it's an archive file, False otherwise
        """
        ext = os.path.splitext(file_path)[1].lower()
        return ext in cls.ARCHIVE_EXTENSIONS

    @classmethod
    def is_code_file(cls, file_path: str) -> bool:
        """
        Check if file is a code file by extension.

        Args:
            file_path: Path to the file

        Returns:
            True if it's a code file, False otherwise
        """
        ext = os.path.splitext(file_path)[1].lower()
        return ext in cls.CODE_EXTENSIONS

    @classmethod
    def get_file_category(cls, file_path: str) -> FileCategory:
        """
        Determines the category of a file based on its extension.

        Args:
            file_path: Path to the file

        Returns:
            FileCategory enum value
        """
        if cls.is_image_file(file_path):
            return FileCategory.IMAGE
        elif cls.is_document_file(file_path):
            return FileCategory.DOCUMENT
        elif cls.is_video_file(file_path):
            return FileCategory.VIDEO
        elif cls.is_audio_file(file_path):
            return FileCategory.AUDIO
        elif cls.is_archive_file(file_path):
            return FileCategory.ARCHIVE
        elif cls.is_code_file(file_path):
            return FileCategory.CODE
        else:
            return FileCategory.OTHER

    @classmethod
    def get_file_category_name(cls, file_path: str) -> str:
        """
        Gets the category name as a string.

        Args:
            file_path: Path to the file

        Returns:
            Category name as string
        """
        return cls.get_file_category(file_path).value

    @classmethod
    def validate_file_path(cls, file_path: str) -> bool:
        """
        Validates if a file path exists and is accessible.

        Args:
            file_path: Path to validate

        Returns:
            True if valid and accessible, False otherwise
        """
        try:
            return os.path.exists(file_path) and os.path.isfile(file_path)
        except (OSError, PermissionError, ValueError):
            return False

    @classmethod
    def format_file_size(cls, size_bytes: int) -> str:
        """
        Formats file size in human-readable format.

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted size string (e.g., "1.5 MB")
        """
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB", "PB"]
        import math

        i = int(math.floor(math.log(size_bytes, 1024)))
        i = min(i, len(size_names) - 1)  # Prevent index out of range
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"


# Convenience functions for backward compatibility and ease of use
def is_image_file(file_path: str) -> bool:
    """Convenience function - checks if file is an image."""
    return FileTypeService.is_image_file(file_path)


def is_document_file(file_path: str) -> bool:
    """Convenience function - checks if file is a document."""
    return FileTypeService.is_document_file(file_path)


def is_video_file(file_path: str) -> bool:
    """Convenience function - checks if file is a video."""
    return FileTypeService.is_video_file(file_path)


def is_audio_file(file_path: str) -> bool:
    """Convenience function - checks if file is an audio."""
    return FileTypeService.is_audio_file(file_path)


def get_file_category(file_path: str) -> str:
    """Convenience function - gets file category as string."""
    return FileTypeService.get_file_category_name(file_path)


def format_file_size(size_bytes: int) -> str:
    """Convenience function - formats file size."""
    return FileTypeService.format_file_size(size_bytes)


def validate_file_path(file_path: str) -> bool:
    """Convenience function - validates file path."""
    return FileTypeService.validate_file_path(file_path)
