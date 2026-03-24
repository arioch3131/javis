"""
Utility functions for the thumbnail service.

This module contains utility functions for safe file operations,
validation, and other common tasks used throughout the thumbnail service.
"""

import os
import mimetypes
from typing import Optional, Tuple, List, Union
import logging

logger = logging.getLogger(__name__)


def safe_get_file_size(path: str) -> int:
    """
    Safely get file size with error handling.

    Args:
        path: File path

    Returns:
        File size in bytes, or 0 if error/not found
    """
    try:
        return os.path.getsize(path) if os.path.exists(path) else 0
    except (OSError, IOError) as e:
        logger.debug(f"Error getting file size for {path}: {e}")
        return 0


def safe_file_exists(path: str) -> bool:
    """
    Safely check if file exists with error handling.

    Args:
        path: File path

    Returns:
        True if file exists and is accessible
    """
    try:
        return os.path.isfile(path)
    except (OSError, IOError) as e:
        logger.debug(f"Error checking file existence for {path}: {e}")
        return False


def safe_is_directory(path: str) -> bool:
    """
    Safely check if path is a directory with error handling.

    Args:
        path: Directory path

    Returns:
        True if path exists and is a directory
    """
    try:
        return os.path.isdir(path)
    except (OSError, IOError) as e:
        logger.debug(f"Error checking directory for {path}: {e}")
        return False


def safe_get_file_extension(path: str) -> str:
    """
    Safely get file extension.

    Args:
        path: File path

    Returns:
        File extension in lowercase, or empty string if none
    """
    try:
        return os.path.splitext(path)[1].lower()
    except (TypeError, AttributeError):
        return ""


def safe_get_mime_type(path: str) -> Optional[str]:
    """
    Safely get MIME type of a file.

    Args:
        path: File path

    Returns:
        MIME type string or None if unable to determine
    """
    try:
        mime_type, _ = mimetypes.guess_type(path)
        return mime_type
    except Exception as e:
        logger.debug(f"Error getting MIME type for {path}: {e}")
        return None


def validate_image_path(path: str) -> Tuple[bool, str]:
    """
    Validate an image path.

    Args:
        path: Path to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(path, str):
        return False, "Path must be a string"

    if not path.strip():
        return False, "Path cannot be empty"

    if not safe_file_exists(path):
        return False, f"File does not exist: {path}"

    # Check if it's likely an image based on extension
    ext = safe_get_file_extension(path)
    if not ext:
        return False, "File has no extension"

    common_image_exts = {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".tiff",
        ".tif",
        ".webp",
        ".svg",
    }
    if ext not in common_image_exts:
        # Still allow it, but warn it might not be an image
        logger.debug(f"Unusual image extension: {ext}")

    return True, ""


def validate_thumbnail_size(
    size: Union[Tuple[int, int], List[int], None],
) -> Tuple[bool, str]:
    """
    Validate thumbnail size parameters.

    Args:
        size: Size tuple/list (width, height) or None

    Returns:
        Tuple of (is_valid, error_message)
    """
    if size is None:
        return True, ""

    if not isinstance(size, (tuple, list)):
        return False, "Size must be a tuple or list"

    if len(size) != 2:
        return False, "Size must have exactly 2 elements (width, height)"

    try:
        width, height = int(size[0]), int(size[1])
    except (ValueError, TypeError):
        return False, "Size elements must be integers"

    if width <= 0 or height <= 0:
        return False, "Size dimensions must be positive"

    if width > 4096 or height > 4096:
        return False, "Size dimensions too large (max 4096)"

    return True, ""


def validate_quality_factor(quality: float) -> Tuple[bool, str]:
    """
    Validate quality factor.

    Args:
        quality: Quality factor (0.0 to 1.0)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(quality, (int, float)):
        return False, "Quality must be a number"

    if quality < 0.0 or quality > 1.0:
        return False, "Quality must be between 0.0 and 1.0"

    return True, ""


def format_file_size(size_bytes: int, units: Optional[List[str]] = None) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: File size in bytes
        units: List of units to use (default: ["B", "KB", "MB", "GB", "TB"])

    Returns:
        Formatted file size string
    """
    if units is None:
        units = ["B", "KB", "MB", "GB", "TB"]

    if size_bytes <= 0:
        return f"0 {units[0]}"

    size_value = float(size_bytes)
    unit_index = 0
    conversion_factor = 1024

    while size_value >= conversion_factor and unit_index < len(units) - 1:
        size_value /= conversion_factor
        unit_index += 1

    if unit_index == 0:
        return f"{int(size_value)} {units[unit_index]}"
    else:
        return f"{size_value:.1f} {units[unit_index]}"


def create_directory_safely(directory_path: str) -> bool:
    """
    Safely create a directory if it doesn't exist.

    Args:
        directory_path: Path to directory

    Returns:
        True if directory exists or was created successfully
    """
    try:
        os.makedirs(directory_path, exist_ok=True)
        return True
    except (OSError, IOError) as e:
        logger.error(f"Error creating directory {directory_path}: {e}")
        return False


def get_cache_key(
    image_path: str, size: Tuple[int, int], quality_factor: float = 1.0
) -> str:
    """
    Generate a cache key for thumbnail caching.

    Args:
        image_path: Path to the image
        size: Thumbnail size
        quality_factor: Quality factor

    Returns:
        Cache key string
    """
    import hashlib

    # Include file modification time for cache invalidation
    try:
        mtime = os.path.getmtime(image_path)
    except (OSError, IOError):
        mtime = 0

    key_data = f"{image_path}:{size[0]}x{size[1]}:{quality_factor}:{mtime}"
    return hashlib.md5(key_data.encode()).hexdigest()


def is_image_file(path: str, check_content: bool = False) -> bool:
    """
    Check if a file is likely an image based on extension and optionally content.

    Args:
        path: File path
        check_content: Whether to check file content/MIME type

    Returns:
        True if file appears to be an image
    """
    # Check extension
    ext = safe_get_file_extension(path)
    image_extensions = {
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
        ".psd",
        ".raw",
        ".dng",
    }

    if ext not in image_extensions:
        return False

    if not check_content:
        return True

    # Check MIME type
    mime_type = safe_get_mime_type(path)
    if mime_type and mime_type.startswith("image/"):
        return True

    return False


def get_image_files_in_directory(
    directory: str, recursive: bool = False, max_files: Optional[int] = None
) -> List[str]:
    """
    Get list of image files in a directory.

    Args:
        directory: Directory path
        recursive: Whether to search recursively
        max_files: Maximum number of files to return

    Returns:
        List of image file paths
    """
    if not safe_is_directory(directory):
        return []

    image_files = []

    try:
        if recursive:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if max_files and len(image_files) >= max_files:
                        break

                    file_path = os.path.join(root, file)
                    if is_image_file(file_path):
                        image_files.append(file_path)

                if max_files and len(image_files) >= max_files:
                    break
        else:
            for item in os.listdir(directory):
                if max_files and len(image_files) >= max_files:
                    break

                item_path = os.path.join(directory, item)
                if safe_file_exists(item_path) and is_image_file(item_path):
                    image_files.append(item_path)

    except (OSError, IOError) as e:
        logger.error(f"Error scanning directory {directory}: {e}")

    return sorted(image_files)


def calculate_aspect_ratio_size(
    original_size: Tuple[int, int],
    target_size: Tuple[int, int],
    fit_mode: str = "contain",
) -> Tuple[int, int]:
    """
    Calculate size maintaining aspect ratio.

    Args:
        original_size: Original (width, height)
        target_size: Target (width, height)
        fit_mode: "contain" (fit within) or "cover" (fill completely)

    Returns:
        Calculated (width, height)
    """
    orig_width, orig_height = original_size
    target_width, target_height = target_size

    if orig_width <= 0 or orig_height <= 0:
        return target_size

    # Calculate ratios
    width_ratio = target_width / orig_width
    height_ratio = target_height / orig_height

    if fit_mode == "contain":
        # Use smaller ratio to fit within target
        ratio = min(width_ratio, height_ratio)
    elif fit_mode == "cover":
        # Use larger ratio to cover target completely
        ratio = max(width_ratio, height_ratio)
    else:
        raise ValueError(f"Unknown fit_mode: {fit_mode}")

    new_width = max(1, int(orig_width * ratio))
    new_height = max(1, int(orig_height * ratio))

    return new_width, new_height


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename for safe filesystem usage.

    Args:
        filename: Original filename
        max_length: Maximum length for the filename

    Returns:
        Sanitized filename
    """
    import re

    # Remove or replace problematic characters
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)

    # Remove control characters
    filename = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", filename)

    # Trim whitespace and dots from ends
    filename = filename.strip(" .")

    # Ensure it's not empty
    if not filename:
        filename = "thumbnail"

    # Limit length
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        available_length = max_length - len(ext)
        filename = name[:available_length] + ext

    return filename
