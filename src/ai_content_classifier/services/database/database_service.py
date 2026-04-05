"""
Database Service for Application Data Management.

This module provides a robust, thread-safe database service utilizing SQLAlchemy ORM
for efficient management of database connections and sessions, particularly
optimized for SQLite databases.

Key Features:
- **Optimized SQLite Connections**: Configures SQLite for enhanced performance and concurrency.
- **Connection Pooling**: Manages a pool of database connections to reduce overhead.
- **Versioned Schema Management**: Applies Alembic migrations to keep schema up to date.
- **Contextual Session Management**: Provides a context manager for safe and efficient
  database session handling, including automatic commit/rollback.
"""

from contextlib import contextmanager
from typing import Generator

from ai_content_classifier.core.logger import LoggableMixin
from ai_content_classifier.services.database.migrations import run_migrations
from sqlalchemy import create_engine, event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as SASession, scoped_session, sessionmaker
from sqlalchemy.pool import QueuePool


class DatabaseService(LoggableMixin):
    """
    This class provides a centralized and thread-safe mechanism for interacting
    with the application's database. It ensures efficient resource management
    through connection pooling and optimizes performance for SQLite databases.

    Attributes:
        db_path (str): The absolute path to the SQLite database file.
        engine (Engine): The SQLAlchemy engine instance, representing the core
                         interface to the database.
        Session (scoped_session): A factory for creating thread-local SQLAlchemy
                                  session objects, ensuring proper session management
                                  in multi-threaded environments.
    """

    def __init__(self, db_path: str):
        """
        Initializes a database service bound to a specific database path.

        Args:
            db_path: Absolute or relative path to the SQLite database file.
        """
        self.db_path = db_path
        self.__init_logger__()
        self._initialize_engine()

    def _initialize_engine(self) -> None:
        """
        Initializes the SQLAlchemy engine and configures database-specific settings.

        This method sets up the connection to the SQLite database, configures
        connection pooling, applies performance-enhancing pragmas for SQLite,
        and applies Alembic migrations to reach the latest schema version.

        Raises:
            SQLAlchemyError: If there is an issue during database engine creation or initialization.
        """
        sqlite_url = f"sqlite:///{self.db_path}"

        try:
            self.engine = create_engine(
                sqlite_url,
                poolclass=QueuePool,  # Use QueuePool for connection pooling.
                pool_size=5,  # Maintain a minimum of 5 open connections in the pool.
                max_overflow=10,  # Allow up to 10 additional connections beyond pool_size if needed.
                pool_pre_ping=True,  # Test connections for liveness before use.
                connect_args={
                    "check_same_thread": False  # Allow multithreaded access to the same connection (for SQLite).
                },
            )

            # Event listener to apply SQLite-specific performance pragmas upon connection.
            @event.listens_for(self.engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                """
                Configures SQLite performance and durability settings for optimal operation.

                These pragmas enhance database write performance, reduce I/O bottlenecks,
                and improve concurrency for SQLite databases.
                """
                cursor = dbapi_connection.cursor()
                try:
                    cursor.execute(
                        "PRAGMA journal_mode=WAL"
                    )  # Enable Write-Ahead Logging for better concurrency.
                    cursor.execute(
                        "PRAGMA synchronous=NORMAL"
                    )  # Balance durability and performance.
                    cursor.execute(
                        "PRAGMA cache_size=10000"
                    )  # Increase cache size for better read performance.
                    cursor.execute(
                        "PRAGMA temp_store=MEMORY"
                    )  # Store temporary tables in memory for speed.
                except Exception as e:
                    self.logger.warning(f"Failed to set SQLite pragmas: {e}")
                finally:
                    cursor.close()

            # Apply versioned schema changes through Alembic.
            run_migrations(engine=self.engine, db_path=self.db_path)

            # Create a thread-local session factory.
            self.Session = scoped_session(sessionmaker(bind=self.engine))

            self.logger.info(f"Database successfully initialized at {self.db_path}.")
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to initialize database engine: {e}")
            raise

    @contextmanager
    def get_session(self) -> Generator[SASession, None, None]:
        """
        Provides a context-managed SQLAlchemy database session.

        This context manager ensures that database sessions are properly acquired,
        used, and released. It automatically commits transactions upon successful
        completion and rolls back in case of any exceptions, guaranteeing data integrity.

        Yields:
            scoped_session: An active SQLAlchemy database session, scoped to the current thread.

        Raises:
            Exception: Re-raises any database-related exceptions after performing a rollback.
        """
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Database transaction failed: {e}", exc_info=True)
            raise
        finally:
            session.close()

    def close_all(self) -> None:
        """
        Gracefully closes all database connections and removes active sessions.

        This method should be invoked during application shutdown to ensure that
        all database resources are properly released, preventing resource leaks
        and potential issues.
        """
        try:
            if hasattr(self, "Session"):
                self.Session.remove()  # Remove all sessions from the current scope.
        except Exception as e:
            self.logger.error(f"Error during database connection closure: {e}")
        finally:
            if hasattr(self, "engine"):
                self.engine.dispose()  # Dispose of the engine, closing all connections in the pool.
            self.logger.info("All database connections successfully closed.")

    def close(self) -> None:
        """Compatibility alias for callers expecting a generic close method."""
        self.close_all()
