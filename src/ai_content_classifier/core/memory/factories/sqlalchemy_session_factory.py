"""
SQLAlchemy Session Factory module.

This module provides an advanced implementation of ObjectFactory for creating
and managing SQLAlchemy session objects with pooling capabilities.
"""

from typing import Any
from sqlalchemy.exc import SQLAlchemyError

from ai_content_classifier.core.memory.factories.factory_interface import ObjectFactory


class SQLAlchemySessionFactory(ObjectFactory):
    """
    An advanced implementation of `ObjectFactory` for creating and managing
    SQLAlchemy session objects. This factory is particularly useful for
    applications that frequently open and close database sessions, as pooling
    them can significantly reduce the overhead associated with session creation
    and connection management.
    """

    def __init__(self, database_service):
        """
        Initializes the SQLAlchemySessionFactory.

        Args:
            database_service: An object that provides a SQLAlchemy Session
                            callable (e.g., `database_service.Session`).
                            This service is responsible for configuring and
                            providing the session factory.
        """
        self.database_service = database_service

    def create(self, *args, **kwargs) -> Any:
        """
        Creates a new SQLAlchemy session instance.

        Args:
            *args: Positional arguments passed to the session constructor.
            **kwargs: Keyword arguments passed to the session constructor.

        Returns:
            Any: A new SQLAlchemy session object.
        """
        return self.database_service.Session(*args, **kwargs)

    def reset(self, obj: Any) -> bool:
        """
        Resets a SQLAlchemy session by rolling back any pending transactions
        and expunging all objects. This prepares the session for reuse in a
        clean state.

        Args:
            obj (Any): The SQLAlchemy session object to reset.

        Returns:
            bool: True if the session was successfully reset, False otherwise.
        """
        try:
            obj.rollback()  # Rollback any pending transactions
            obj.expunge_all()  # Remove all objects from the session
            return True
        except (SQLAlchemyError, AttributeError):
            # Log the exception if necessary
            # Could add logging here: logger.warning("Failed to reset session: %s", e)
            return False

    def validate(self, obj: Any) -> bool:
        """
        Validates a SQLAlchemy session to ensure it is still active and usable.

        Args:
            obj (Any): The SQLAlchemy session object to validate.

        Returns:
            bool: True if the session is active, False otherwise.
        """
        try:
            return obj.is_active
        except AttributeError:
            return False

    def get_key(self, *args, **kwargs) -> str:
        """
        Generates a key for SQLAlchemy sessions. In this example, all sessions
        are considered identical for pooling purposes, so a single default key
        is returned. For more complex scenarios, this could be based on
        connection string or other parameters.

        Args:
            *args: Positional arguments, not used in this simple key generation.
            **kwargs: Keyword arguments, not used in this simple key generation.

        Returns:
            str: A fixed string key "session_default".
        """
        # In this simple example, all sessions are considered identical for pooling.
        # For more complex scenarios, the key might depend on connection parameters.
        return "session_default"
