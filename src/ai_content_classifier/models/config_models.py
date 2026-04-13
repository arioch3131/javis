# ai_content_classifier/models/config_models.py
"""
Unified Configuration Models for the Application.

This module provides a centralized definition for all application settings,
replacing the fragmented configuration from constants.py and llm_config.py.
It defines the structure, type, default values, and metadata for each
configurable parameter.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


def _validate_positive_int(value: Any) -> Tuple[bool, str]:
    """Validate strictly positive integer values."""
    try:
        return (int(value) > 0, "Value must be greater than 0")
    except (TypeError, ValueError):
        return False, "Value must be an integer"


def _validate_renew_threshold(value: Any) -> Tuple[bool, str]:
    """Validate threshold value in (0, 1]."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False, "Value must be a number"
    return (0.0 < numeric <= 1.0, "Value must be in (0, 1]")


# Enum for configuration parameter keys
class ConfigKey(Enum):
    """Enumeration of all configurable keys in the application."""

    # --- General Settings ---
    LOG_LEVEL = "general.log_level"
    THEME = "general.theme"
    LANGUAGE = "general.language"

    # --- API and LLM Settings ---
    API_URL = "api.url"
    API_CONNECTION_TIMEOUT = "api.connection_timeout"
    API_GENERATE_TIMEOUT = "api.generate_timeout"
    API_MAX_RETRIES = "api.max_retries"
    API_RETRY_BACKOFF = "api.retry_backoff"

    IMAGE_MODEL = "llm.image_model"
    DOCUMENT_MODEL = "llm.document_model"

    IMAGE_PROMPT = "llm.image_prompt"
    DOCUMENT_PROMPT = "llm.document_prompt"

    # --- File and Scan Settings ---
    IMAGE_EXTENSIONS = "scan.image_extensions"
    DOCUMENT_EXTENSIONS = "scan.document_extensions"
    VIDEO_EXTENSIONS = "scan.video_extensions"
    AUDIO_EXTENSIONS = "scan.audio_extensions"

    # --- Preprocessing Settings ---
    PREPROCESS_IMAGE_MAX_SIZE = "preprocess.image.max_size"
    PREPROCESS_IMAGE_QUALITY = "preprocess.image.quality"
    PREPROCESS_TEXT_MAX_LENGTH = "preprocess.text.max_length"

    # --- Thumbnail Settings ---
    THUMBNAIL_SIZE = "thumbnails.size"
    THUMBNAIL_QUALITY = "thumbnails.quality"
    THUMBNAIL_CACHE_ENABLED = "thumbnails.cache.enabled"
    THUMBNAIL_CACHE_TTL_SEC = "thumbnails.cache.ttl_sec"
    THUMBNAIL_CACHE_CLEANUP_INTERVAL_SEC = "thumbnails.cache.cleanup_interval_sec"
    THUMBNAIL_CACHE_MAX_SIZE_MB = "thumbnails.cache.max_size_mb"
    THUMBNAIL_CACHE_RENEW_ON_HIT = "thumbnails.cache.renew_on_hit"
    THUMBNAIL_CACHE_RENEW_THRESHOLD = "thumbnails.cache.renew_threshold"

    # --- Categorization Settings ---
    CATEGORIES = "categorization.categories"
    CONFIDENCE_THRESHOLD = "categorization.confidence_threshold"


# Dataclass for defining a configuration parameter
@dataclass
class ConfigDefinition:
    """Defines the metadata for a single configuration parameter."""

    key: ConfigKey
    type: type
    default: Any
    category: str
    label: str
    description: str
    options: Optional[List[Any]] = None  # For dropdowns/comboboxes
    validation_rules: List[Callable[[Any], Tuple[bool, str]]] = field(
        default_factory=list
    )


# Central registry of all configuration definitions
CONFIG_DEFINITIONS: Dict[ConfigKey, ConfigDefinition] = {
    # --- General Settings ---
    ConfigKey.LOG_LEVEL: ConfigDefinition(
        key=ConfigKey.LOG_LEVEL,
        type=str,
        default="INFO",
        category="General",
        label="Log Level",
        description="The minimum logging level for application messages.",
        options=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    ),
    ConfigKey.THEME: ConfigDefinition(
        key=ConfigKey.THEME,
        type=str,
        default="dark",
        category="General",
        label="Application Theme",
        description="The visual theme of the application (e.g., 'dark', 'light').",
        options=["dark", "light"],
    ),
    ConfigKey.LANGUAGE: ConfigDefinition(
        key=ConfigKey.LANGUAGE,
        type=str,
        default="en",
        category="General",
        label="Application Language",
        description="UI language used by the application.",
        options=["en", "fr"],
    ),
    # --- API and LLM Settings ---
    ConfigKey.API_URL: ConfigDefinition(
        key=ConfigKey.API_URL,
        type=str,
        default="http://localhost:11434",
        category="API",
        label="API URL",
        description="Base URL for the Ollama LLM service.",
    ),
    ConfigKey.API_CONNECTION_TIMEOUT: ConfigDefinition(
        key=ConfigKey.API_CONNECTION_TIMEOUT,
        type=int,
        default=10,
        category="API",
        label="Connection Timeout (s)",
        description="Timeout in seconds for establishing a connection to the API.",
    ),
    ConfigKey.API_GENERATE_TIMEOUT: ConfigDefinition(
        key=ConfigKey.API_GENERATE_TIMEOUT,
        type=int,
        default=300,
        category="API",
        label="Generation Timeout (s)",
        description="Maximum time in seconds to wait for a response from the LLM.",
    ),
    ConfigKey.API_MAX_RETRIES: ConfigDefinition(
        key=ConfigKey.API_MAX_RETRIES,
        type=int,
        default=3,
        category="API",
        label="Max Retries",
        description="Maximum number of times to retry a failed API request.",
    ),
    ConfigKey.API_RETRY_BACKOFF: ConfigDefinition(
        key=ConfigKey.API_RETRY_BACKOFF,
        type=float,
        default=0.5,
        category="API",
        label="Retry Backoff (s)",
        description="Time in seconds to wait between retries (exponential backoff).",
    ),
    ConfigKey.IMAGE_MODEL: ConfigDefinition(
        key=ConfigKey.IMAGE_MODEL,
        type=str,
        default="llava",
        category="LLM",
        label="Image Analysis Model",
        description="The default model to use for image classification (e.g., 'llava').",
    ),
    ConfigKey.DOCUMENT_MODEL: ConfigDefinition(
        key=ConfigKey.DOCUMENT_MODEL,
        type=str,
        default="llama2",
        category="LLM",
        label="Document Analysis Model",
        description="The default model to use for document classification (e.g., 'llama2').",
    ),
    ConfigKey.IMAGE_PROMPT: ConfigDefinition(
        key=ConfigKey.IMAGE_PROMPT,
        type=str,
        default="You are a file classification assistant. Choose exactly one category from this list: {categories}. Analyze the image (file: {image_path}) and reply with only the category name, exactly as written in the list. No explanation, no punctuation, no extra text. If uncertain, pick the closest category from the list.",
        category="LLM",
        label="Image Prompt Template",
        description="The prompt template used for image classification. Use {categories} as a placeholder.",
    ),
    ConfigKey.DOCUMENT_PROMPT: ConfigDefinition(
        key=ConfigKey.DOCUMENT_PROMPT,
        type=str,
        default="You are a file classification assistant. Choose exactly one category from this list: {categories}. Use the document excerpt below and classify the document (file path/name: {document_path}). Reply with only the category name, exactly as written in the list. No explanation, no punctuation, no extra text. If uncertain, pick the closest category from the list.\n\nDocument excerpt:\n{document_excerpt}",
        category="LLM",
        label="Document Prompt Template",
        description="The prompt template used for document classification. Use {categories} as a placeholder.",
    ),
    # --- File and Scan Settings ---
    ConfigKey.IMAGE_EXTENSIONS: ConfigDefinition(
        key=ConfigKey.IMAGE_EXTENSIONS,
        type=list,
        default=[".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"],
        category="Scanning",
        label="Image Extensions",
        description="Comma-separated list of file extensions to be treated as images.",
    ),
    ConfigKey.DOCUMENT_EXTENSIONS: ConfigDefinition(
        key=ConfigKey.DOCUMENT_EXTENSIONS,
        type=list,
        default=[".pdf", ".docx", ".txt", ".md", ".rtf", ".odt"],
        category="Scanning",
        label="Document Extensions",
        description="Comma-separated list of file extensions to be treated as documents.",
    ),
    ConfigKey.VIDEO_EXTENSIONS: ConfigDefinition(
        key=ConfigKey.VIDEO_EXTENSIONS,
        type=list,
        default=[".mp4", ".avi", ".mov", ".mkv"],
        category="Scanning",
        label="Video Extensions",
        description="Comma-separated list of file extensions to be treated as videos.",
    ),
    ConfigKey.AUDIO_EXTENSIONS: ConfigDefinition(
        key=ConfigKey.AUDIO_EXTENSIONS,
        type=list,
        default=[".mp3", ".wav", ".flac", ".aac"],
        category="Scanning",
        label="Audio Extensions",
        description="Comma-separated list of file extensions to be treated as audio.",
    ),
    # --- Preprocessing Settings ---
    ConfigKey.PREPROCESS_IMAGE_MAX_SIZE: ConfigDefinition(
        key=ConfigKey.PREPROCESS_IMAGE_MAX_SIZE,
        type=int,
        default=2048,
        category="Preprocessing",
        label="Max Image Dimension (px)",
        description="Maximum width or height for images sent to the LLM. Larger images will be resized.",
    ),
    ConfigKey.PREPROCESS_IMAGE_QUALITY: ConfigDefinition(
        key=ConfigKey.PREPROCESS_IMAGE_QUALITY,
        type=int,
        default=85,
        category="Preprocessing",
        label="Image Compression Quality",
        description="JPEG/WEBP compression quality (1-100) for preprocessed images.",
    ),
    ConfigKey.PREPROCESS_TEXT_MAX_LENGTH: ConfigDefinition(
        key=ConfigKey.PREPROCESS_TEXT_MAX_LENGTH,
        type=int,
        default=50000,
        category="Preprocessing",
        label="Max Text Length (chars)",
        description="Maximum number of characters to extract from a document for the LLM.",
    ),
    # --- Thumbnail Settings ---
    ConfigKey.THUMBNAIL_SIZE: ConfigDefinition(
        key=ConfigKey.THUMBNAIL_SIZE,
        type=int,
        default=256,
        category="Thumbnails",
        label="Thumbnail Size (px)",
        description="Default size (width and height) for generated thumbnails.",
    ),
    ConfigKey.THUMBNAIL_QUALITY: ConfigDefinition(
        key=ConfigKey.THUMBNAIL_QUALITY,
        type=int,
        default=90,
        category="Thumbnails",
        label="Thumbnail Quality",
        description="JPEG quality (1-100) for generated thumbnails.",
    ),
    ConfigKey.THUMBNAIL_CACHE_ENABLED: ConfigDefinition(
        key=ConfigKey.THUMBNAIL_CACHE_ENABLED,
        type=bool,
        default=True,
        category="Thumbnails",
        label="Enable Thumbnail Disk Cache",
        description="Enable persistent disk cache for generated thumbnails.",
    ),
    ConfigKey.THUMBNAIL_CACHE_TTL_SEC: ConfigDefinition(
        key=ConfigKey.THUMBNAIL_CACHE_TTL_SEC,
        type=int,
        default=3600,
        category="Thumbnails",
        label="Thumbnail Cache TTL (s)",
        description="Default time-to-live (in seconds) for thumbnail cache entries.",
        validation_rules=[_validate_positive_int],
    ),
    ConfigKey.THUMBNAIL_CACHE_CLEANUP_INTERVAL_SEC: ConfigDefinition(
        key=ConfigKey.THUMBNAIL_CACHE_CLEANUP_INTERVAL_SEC,
        type=int,
        default=300,
        category="Thumbnails",
        label="Thumbnail Cache Cleanup Interval (s)",
        description="Background cleanup interval (in seconds) for thumbnail cache.",
        validation_rules=[_validate_positive_int],
    ),
    ConfigKey.THUMBNAIL_CACHE_MAX_SIZE_MB: ConfigDefinition(
        key=ConfigKey.THUMBNAIL_CACHE_MAX_SIZE_MB,
        type=int,
        default=1024,
        category="Thumbnails",
        label="Thumbnail Cache Max Size (MB)",
        description="Maximum disk cache size in MB (enabled automatically on omni-cache >= 2.1.0).",
        validation_rules=[_validate_positive_int],
    ),
    ConfigKey.THUMBNAIL_CACHE_RENEW_ON_HIT: ConfigDefinition(
        key=ConfigKey.THUMBNAIL_CACHE_RENEW_ON_HIT,
        type=bool,
        default=False,
        category="Thumbnails",
        label="Renew TTL On Cache Hit",
        description="Extend cache entry TTL when an entry is read.",
    ),
    ConfigKey.THUMBNAIL_CACHE_RENEW_THRESHOLD: ConfigDefinition(
        key=ConfigKey.THUMBNAIL_CACHE_RENEW_THRESHOLD,
        type=float,
        default=0.5,
        category="Thumbnails",
        label="Renew Threshold",
        description="TTL renew threshold ratio in (0, 1].",
        validation_rules=[_validate_renew_threshold],
    ),
    # --- Categorization Settings ---
    ConfigKey.CATEGORIES: ConfigDefinition(
        key=ConfigKey.CATEGORIES,
        type=list,
        default=["Work", "Personal", "Documents", "Images", "Archive", "Important"],
        category="Categorization",
        label="Default Categories",
        description="Default list of categories for classification. Can be edited in the app.",
    ),
    ConfigKey.CONFIDENCE_THRESHOLD: ConfigDefinition(
        key=ConfigKey.CONFIDENCE_THRESHOLD,
        type=float,
        default=0.3,
        category="Categorization",
        label="Confidence Threshold",
        description="Minimum confidence score (0.0-1.0) for an AI classification to be accepted.",
    ),
}
