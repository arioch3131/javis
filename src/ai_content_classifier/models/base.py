"""
SQLAlchemy Base Module.

This module establishes the foundational SQLAlchemy declarative base class
(`Base`) that all Object-Relational Mapper (ORM) models within the application
must inherit from. It also integrates with the application's logging system
to provide insights into database-related operations.

Usage:
    To define a new ORM model, import `Base` and inherit from it:

    ```python
    from models.base import Base
    from sqlalchemy import Column, Integer, String

    class User(Base):
        __tablename__ = 'users'
        id = Column(Integer, primary_key=True)
        name = Column(String(50), nullable=False)
    ```
"""

from sqlalchemy.orm import declarative_base

from ai_content_classifier.core.logger import get_logger

# Initialize a logger specifically for database-related operations within this module.
logger = get_logger(__name__)
logger.info("SQLAlchemy base module initialized.")

# Create the declarative base class.
# All SQLAlchemy ORM models will inherit from this `Base` class.
Base = declarative_base()
logger.debug("SQLAlchemy declarative base created.")
