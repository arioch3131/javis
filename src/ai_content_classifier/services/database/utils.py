"""
This module provides utility functions for the content database service,
including metadata serialization, file hashing, and content type detection.
"""

import hashlib
import json
import os
from datetime import date, datetime
from typing import Any, Dict, Optional

from ai_content_classifier.services.file.file_type_service import FileTypeService


def serialize_metadata_for_json(
    metadata: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Serializes a metadata dictionary to ensure all its values are JSON-compatible.

    This method recursively converts `datetime` and `date` objects into ISO 8601
    formatted strings, and attempts to convert any other non-JSON-serializable
    types into strings. This is crucial for storing metadata in JSON columns.

    Args:
        metadata (Optional[Dict[str, Any]]): The metadata dictionary to serialize.
                                              Can be `None`.

    Returns:
        Optional[Dict[str, Any]]: The serialized metadata dictionary, safe for JSON storage.
                                  Returns `None` if the input was `None`.
    """
    if metadata is None:
        return None

    def serialize_value(value: Any) -> Any:
        """
        Recursively serializes individual values to JSON-compatible types.
        """
        if isinstance(value, datetime) or isinstance(value, date):
            return value.isoformat()
        elif isinstance(value, dict):
            return {k: serialize_value(v) for k, v in value.items()}
        elif isinstance(value, (list, tuple)):
            return [serialize_value(item) for item in value]
        elif isinstance(value, (str, int, float, bool)) or value is None:
            return value
        else:
            # Attempt to serialize directly, otherwise convert to string.
            try:
                json.dumps(value)  # Test if already serializable
                return value
            except (TypeError, ValueError):
                return str(value)

    try:
        serialized = {key: serialize_value(value) for key, value in metadata.items()}
        return serialized
    except Exception as e:
        # Return a safe fallback to prevent application crashes.
        return {"error": f"Serialization failed: {str(e)}"}


def compute_file_hash(file_path: str) -> Optional[str]:
    """
    Computes the SHA-256 hash of a given file.

    This method reads the file in chunks to efficiently handle large files
    without loading the entire content into memory.

    Args:
        file_path (str): The absolute path to the file.

    Returns:
        Optional[str]: The hexadecimal digest of the SHA-256 hash if successful,
                       or `None` if the file is not found or an error occurs.
    """
    try:
        if not os.path.exists(file_path):
            return None

        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in 4KB chunks for memory efficiency.
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)

        return hash_sha256.hexdigest()

    except Exception:
        return None


def detect_content_type(file_path: str) -> str:
    """
    Detects the general content type of a file based on its file extension using FileTypeService.

    Args:
        file_path (str): The absolute path to the file.

    Returns:
        str: A string representing the detected content type (e.g., 'image', 'document',
             'video', 'audio', or 'content_item' for unknown/generic types).
    """
    category = FileTypeService.get_file_category_name(file_path)
    # FileTypeService.get_file_category_name returns "Image", "Document", etc.
    # We need "image", "document" (lowercase)
    return category.lower() if category != "Other" else "content_item"
