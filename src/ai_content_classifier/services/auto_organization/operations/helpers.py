"""Shared helpers for auto-organization operations."""

import os

from ai_content_classifier.services.file.file_type_service import (
    FileCategory,
    FileTypeService,
)


def determine_file_type(file_path: str) -> str:
    """Determine canonical organization bucket from ``FileTypeService`` category."""
    category = FileTypeService.get_file_category(file_path)
    mapping = {
        FileCategory.DOCUMENT: "Documents",
        FileCategory.IMAGE: "Images",
        FileCategory.VIDEO: "Videos",
        FileCategory.AUDIO: "Audio",
    }
    return mapping.get(category, "Others")


def sanitize_dirname(name: str) -> str:
    """Sanitize values for folder-name usage."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, "_")

    if len(name) > 100:
        name = name[:100]

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


def resolve_name_conflict(target_path: str) -> str:
    """Resolve destination naming conflicts by appending a counter."""
    if not os.path.exists(target_path):
        return target_path

    base, ext = os.path.splitext(target_path)
    counter = 1
    candidate = target_path

    while os.path.exists(candidate):
        candidate = f"{base}_{counter}{ext}"
        counter += 1

    return candidate
