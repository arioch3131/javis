from enum import Enum


class EventType(str, Enum):
    """Canonical application events emitted by the views layer."""

    CONNECTION_TESTED = "connection_tested"
    MODELS_RETRIEVED = "models_retrieved"
    CONNECTION_STATUS_UPDATED = "connection_status_updated"

    SETTINGS_UPDATED = "settings_updated"
    SETTINGS_SAVED = "settings_saved"

    SCAN_STARTED = "scan_started"
    SCAN_PROGRESS = "scan_progress"
    SCAN_COMPLETED = "scan_completed"
    SCAN_ERROR = "scan_error"
    FILES_UPDATED = "files_updated"
    FILTER_APPLIED = "filter_applied"
    FILTER_ERROR = "filter_error"
    CATEGORIZATION_STARTED = "categorization_started"
    CATEGORIZATION_COMPLETED = "categorization_completed"
    CATEGORIZATION_ERROR = "categorization_error"

    ORGANIZATION_STARTED = "organization_started"
    ORGANIZATION_PROGRESS = "organization_progress"
    ORGANIZATION_COMPLETED = "organization_completed"
    ORGANIZATION_CANCELLED = "organization_cancelled"
    ORGANIZATION_ERROR = "organization_error"
    ORGANIZATION_PREVIEW_READY = "organization_preview_ready"
