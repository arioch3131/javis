# ai_content_classifier/repositories/config_repository.py
"""
Repository for the unified configuration settings.

This module provides a repository for managing all configuration settings
in a single database table, using a simple key-value approach.
"""

from typing import Any

from ai_content_classifier.core.logger import LoggableMixin
from ai_content_classifier.models.settings_models import AppSettings
from ai_content_classifier.services.database.database_service import DatabaseService


class ConfigRepository(LoggableMixin):
    """Manages CRUD operations for application settings in the database."""

    def __init__(self, database_service: DatabaseService):
        self.__init_logger__()
        self.db_service = database_service

    def get_value(self, key: str, default: Any = None) -> Any:
        """Retrieves a setting value by its key."""
        with self.db_service.get_session() as session:
            setting = session.query(AppSettings).filter_by(key=key).first()
            if setting:
                self.logger.debug(f"Found setting {key} in DB: {setting.value}")
                return setting.value
            self.logger.debug(
                f"Setting {key} not found in DB. Returning default: {default}"
            )
            return default

    def set_value(self, key: str, value: str) -> None:
        """Sets a setting value."""
        with self.db_service.get_session() as session:
            setting = session.query(AppSettings).filter_by(key=key).first()
            if setting is not None:
                self.logger.debug(f"Updating existing setting: {key} = {value}")
                setattr(setting, "value", value)
            else:
                self.logger.debug(f"Adding new setting: {key} = {value}")
                new_setting = AppSettings(key=key, value=value)
                session.add(new_setting)
            self.logger.debug(
                f"Set setting {key} to {value} in session. Committing now."
            )
