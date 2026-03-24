"""
Compatibility shim for legacy imports.
"""

from ai_content_classifier.services.settings.config_service import (
    ConfigKey,
    ConfigService,
)

__all__ = ["ConfigKey", "ConfigService"]
