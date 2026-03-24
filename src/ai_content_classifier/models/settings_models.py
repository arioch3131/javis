# ai_content_classifier/models/settings_models.py
"""
SQLAlchemy ORM Models for Application Configuration Settings.

This module defines the SQLAlchemy Object-Relational Mapper (ORM) models
responsible for managing application-wide configuration settings. It provides
a flexible and extensible structure for storing key-value pairs.
"""

from sqlalchemy import Column, Integer, String, Text

from ai_content_classifier.core.logger import get_logger
from ai_content_classifier.models.base import Base

# Initialize a logger for this module to provide insights into settings operations.
logger = get_logger(__name__)


class AppSettings(Base):
    """A unified model for storing all application settings as key-value pairs."""

    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AppSettings(key='{self.key}', value='{self.value[:50]}...')>"
