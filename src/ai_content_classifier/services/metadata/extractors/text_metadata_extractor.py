"""
Lightweight text metadata extractor.

Handles plain-text and common source/documentation formats to avoid noisy
"no suitable extractor" warnings for files like README.md / CHANGELOG.md.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from ai_content_classifier.services.metadata.extractors.base_extractor import (
    BaseMetadataExtractor,
)


class TextMetadataExtractor(BaseMetadataExtractor):
    """Fast metadata extractor for text-like files."""

    SUPPORTED_EXTENSIONS = {
        ".txt",
        ".md",
        ".rst",
        ".log",
        ".csv",
        ".json",
        ".yaml",
        ".yml",
        ".xml",
        ".ini",
        ".cfg",
        ".conf",
        ".toml",
        ".py",
        ".js",
        ".ts",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".go",
        ".rs",
        ".sh",
        ".bash",
        ".zsh",
        ".sql",
        ".css",
        ".html",
        ".htm",
    }
    _MAX_SAMPLE_BYTES = 64 * 1024

    def can_handle(self, file_path: str) -> bool:
        ext = Path(file_path).suffix.lower()
        return (
            ext in self.SUPPORTED_EXTENSIONS
            and os.path.isfile(file_path)
            and os.access(file_path, os.R_OK)
        )

    def get_metadata(self, file_path: str) -> Dict[str, Any]:
        metadata = self.get_basic_metadata(file_path)

        ext = Path(file_path).suffix.lower()
        metadata["content_type"] = "text"
        metadata["text_format"] = ext.lstrip(".") or "plain"

        try:
            with open(file_path, "rb") as file_obj:
                sample = file_obj.read(self._MAX_SAMPLE_BYTES)

            # Decode conservatively to avoid extractor failures.
            text_sample = sample.decode("utf-8", errors="replace")
            metadata["sample_bytes"] = len(sample)
            metadata["sample_line_count"] = text_sample.count("\n") + (
                1 if text_sample else 0
            )
            metadata["sample_char_count"] = len(text_sample)
            metadata["sample_word_count"] = len(text_sample.split())
        except Exception as exc:
            metadata["error"] = f"Error extracting text metadata: {exc}"

        return metadata
