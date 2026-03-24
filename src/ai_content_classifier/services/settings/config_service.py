# ai_content_classifier/services/config_service.py
"""
Centralized Configuration Service.

This service manages all application settings, providing a unified interface
to access and modify configuration values. It uses a database repository to
persist settings and relies on the centralized `ConfigDefinition` for
metadata about each parameter.
"""

from typing import Any, Dict

from ai_content_classifier.core.logger import LoggableMixin
from ai_content_classifier.services.shared.cache_runtime import get_cache_runtime

from ai_content_classifier.models.config_models import (
    CONFIG_DEFINITIONS,
    ConfigKey,
)

from ai_content_classifier.repositories.config_repository import ConfigRepository


class ConfigService(LoggableMixin):
    """Unified service for managing all application settings."""

    def __init__(self, config_repository: ConfigRepository):
        self.__init_logger__()
        self.repo = config_repository
        self._cache = get_cache_runtime().memory_cache(
            "settings:config_service",
            default_ttl=3600,
        )
        self.logger.info("ConfigService initialized.")

    def _normalize_key(self, key: Any) -> ConfigKey:
        """
        Normalize a config key to the canonical ConfigKey enum instance.

        This handles mixed import paths where multiple Enum classes can coexist
        (same values, different identities).
        """
        if isinstance(key, ConfigKey):
            return key

        key_value = getattr(key, "value", None)
        if key_value is None and isinstance(key, str):
            key_value = key

        if not key_value:
            raise ValueError(f"Invalid configuration key: {key}")

        for canonical_key in CONFIG_DEFINITIONS.keys():
            if canonical_key.value == key_value:
                return canonical_key

        raise ValueError(f"Invalid configuration key: {key}")

    def initialize_default_settings(self):
        """Initializes all settings with their default values if they don't exist."""
        self.logger.info("Initializing default settings...")
        for key, definition in CONFIG_DEFINITIONS.items():
            # Check if the setting already exists in the database
            existing_value = self.repo.get_value(key.value)
            if existing_value is None:
                # If not, set it to its default value
                self.set(key, definition.default)
                self.logger.debug(
                    f"Set default for {key.value} to {definition.default}"
                )
        self.logger.info("Default settings initialized.")

    def get(self, key: ConfigKey) -> Any:
        """Retrieves a configuration value by its key."""
        key = self._normalize_key(key)
        cached_value = self._cache.get(key.value, default=None)
        if cached_value is not None:
            return cached_value

        definition = CONFIG_DEFINITIONS.get(key)
        if not definition:
            raise ValueError(f"Invalid configuration key: {key}")

        value = self.repo.get_value(key.value, definition.default)

        # Type conversion
        try:
            if definition.type is list and isinstance(value, str):
                value = [item.strip() for item in value.split(",")]
            else:
                value = definition.type(value)
        except (ValueError, TypeError) as e:
            self.logger.warning(
                f"Could not convert value for {key} to {definition.type}. Using default. Error: {e}"
            )
            value = definition.default

        self._cache.set(key.value, value)
        return value

    def set(self, key: ConfigKey, value: Any) -> None:
        """Sets a configuration value."""
        key = self._normalize_key(key)
        definition = CONFIG_DEFINITIONS.get(key)
        if not definition:
            raise ValueError(f"Invalid configuration key: {key}")

        # Convert list to comma-separated string for storage
        if isinstance(value, list):
            value_to_store = ",".join(map(str, value))
        else:
            value_to_store = str(value)

        self.repo.set_value(key.value, value_to_store)
        self._cache.set(key.value, value)
        self.logger.info(f"Configuration updated: {key.value} = {value}")

    def get_all_settings(self) -> Dict[str, Any]:
        """Retrieves all settings, organized by category."""
        settings_by_category: Dict[str, Dict[str, Any]] = {}
        for key, definition in CONFIG_DEFINITIONS.items():
            if definition.category not in settings_by_category:
                settings_by_category[definition.category] = {}

            settings_by_category[definition.category][definition.label] = {
                "key": key,
                "value": self.get(key),
                "definition": definition,
            }
        return settings_by_category
