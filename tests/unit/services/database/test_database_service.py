import pytest
import os
from unittest.mock import MagicMock, Mock, call, patch
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool

# Mock dependencies
# Removed: sys.modules['core.logger'] = Mock()


# Mock LoggableMixin
class LoggableMixin:
    def __init_logger__(self):
        self.logger = MagicMock()


with patch("ai_content_classifier.core.logger.LoggableMixin", LoggableMixin):
    from ai_content_classifier.services.database.database_service import DatabaseService

# Path to a temporary database for testing
TEST_DB_PATH = "test_db.sqlite"


class TestDatabaseService:
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
        yield
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

    @pytest.fixture(autouse=True)
    def patch_logger_init(self):
        """
        Ensure DatabaseService always uses a mock logger in tests.
        This allows assert_called* checks on logger methods.
        """
        with patch.object(
            DatabaseService,
            "__init_logger__",
            lambda self: setattr(self, "logger", MagicMock()),
        ):
            yield

    @pytest.fixture
    def mock_create_engine(self):
        with patch(
            "ai_content_classifier.services.database.database_service.create_engine"
        ) as mock_engine:
            yield mock_engine

    @pytest.fixture
    def mock_event_listens_for(self):
        with patch(
            "ai_content_classifier.services.database.database_service.event.listens_for"
        ) as mock_listens_for:
            yield mock_listens_for

    @pytest.fixture
    def mock_run_migrations(self):
        with patch(
            "ai_content_classifier.services.database.database_service.run_migrations"
        ) as mock_migrations:
            yield mock_migrations

    @pytest.fixture
    def mock_scoped_session(self):
        with patch(
            "ai_content_classifier.services.database.database_service.scoped_session"
        ) as mock_scoped:
            yield mock_scoped

    @pytest.fixture
    def mock_sessionmaker(self):
        with patch(
            "ai_content_classifier.services.database.database_service.sessionmaker"
        ) as mock_sm:
            yield mock_sm

    def test_creates_distinct_instances(
        self,
        mock_create_engine,
        mock_event_listens_for,
        mock_run_migrations,
        mock_scoped_session,
        mock_sessionmaker,
    ):
        db_service1 = DatabaseService(TEST_DB_PATH)
        db_service2 = DatabaseService(TEST_DB_PATH)
        assert db_service1 is not db_service2
        assert mock_create_engine.call_count == 2

    # Test _initialize_engine method
    def test_initialize_engine_success(
        self,
        mock_create_engine,
        mock_event_listens_for,
        mock_run_migrations,
        mock_scoped_session,
        mock_sessionmaker,
    ):
        mock_engine_instance = mock_create_engine.return_value
        mock_session_factory = mock_sessionmaker.return_value
        mock_scoped_session.return_value = mock_session_factory

        db_service = DatabaseService(TEST_DB_PATH)

        mock_create_engine.assert_called_once_with(
            f"sqlite:///{TEST_DB_PATH}",
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False},
        )
        assert db_service.engine == mock_engine_instance
        assert db_service.Session == mock_session_factory
        mock_event_listens_for.assert_called_once_with(mock_engine_instance, "connect")
        mock_run_migrations.assert_called_once_with(
            engine=mock_engine_instance,
            db_path=TEST_DB_PATH,
        )
        mock_sessionmaker.assert_called_once_with(bind=mock_engine_instance)
        mock_scoped_session.assert_called_once_with(mock_session_factory)
        db_service.logger.info.assert_called_with(
            f"Database successfully initialized at {TEST_DB_PATH}."
        )

    def test_initialize_engine_sqlalchemy_error(self, mock_create_engine):
        mock_create_engine.side_effect = SQLAlchemyError("Test DB Error")
        with pytest.raises(SQLAlchemyError, match="Test DB Error"):
            DatabaseService(TEST_DB_PATH)

    def test_set_sqlite_pragma_success(
        self, mock_create_engine, mock_event_listens_for
    ):
        mock_listens_for_return_value = MagicMock()
        mock_event_listens_for.return_value = mock_listens_for_return_value

        db_service = DatabaseService(TEST_DB_PATH)

        # Verify listens_for was called with the engine and "connect"
        mock_event_listens_for.assert_called_once_with(db_service.engine, "connect")

        # Now, the mock_listens_for_return_value should have been called with the set_sqlite_pragma function
        # We can get this function from its call_args
        set_sqlite_pragma_func = mock_listens_for_return_value.call_args[0][0]

        mock_dbapi_connection = MagicMock()
        mock_cursor = mock_dbapi_connection.cursor.return_value

        set_sqlite_pragma_func(
            mock_dbapi_connection, None
        )  # Call the decorated function

        expected_calls = [
            call("PRAGMA journal_mode=WAL"),
            call("PRAGMA synchronous=NORMAL"),
            call("PRAGMA cache_size=10000"),
            call("PRAGMA temp_store=MEMORY"),
        ]
        mock_cursor.execute.assert_has_calls(expected_calls)
        mock_cursor.close.assert_called_once()
        db_service.logger.warning.assert_not_called()  # Use db_service.logger as it's the instance logger

    def test_set_sqlite_pragma_failure(
        self, mock_create_engine, mock_event_listens_for
    ):
        mock_listens_for_return_value = MagicMock()
        mock_event_listens_for.return_value = mock_listens_for_return_value

        db_service = DatabaseService(TEST_DB_PATH)

        set_sqlite_pragma_func = mock_listens_for_return_value.call_args[0][0]

        mock_dbapi_connection = MagicMock()
        mock_cursor = mock_dbapi_connection.cursor.return_value
        mock_cursor.execute.side_effect = Exception("Pragma error")

        set_sqlite_pragma_func(mock_dbapi_connection, None)

        db_service.logger.warning.assert_called_once_with(
            "Failed to set SQLite pragmas: Pragma error"
        )
        mock_cursor.close.assert_called_once()

    # Test get_session context manager
    def test_get_session_success(
        self,
        mock_create_engine,
        mock_event_listens_for,
        mock_run_migrations,
        mock_scoped_session,
        mock_sessionmaker,
    ):
        db_service = DatabaseService(TEST_DB_PATH)
        mock_session_instance = MagicMock(spec=Session)
        mock_scoped_session.return_value.return_value = (
            mock_session_instance  # This is the session factory
        )

        with db_service.get_session() as session:
            assert session is mock_session_instance
            # Simulate some operation
            session.add(Mock())

        mock_session_instance.commit.assert_called_once()
        mock_session_instance.close.assert_called_once()
        mock_session_instance.rollback.assert_not_called()
        db_service.logger.error.assert_not_called()

    def test_get_session_rollback_on_exception(
        self,
        mock_create_engine,
        mock_event_listens_for,
        mock_run_migrations,
        mock_scoped_session,
        mock_sessionmaker,
    ):
        db_service = DatabaseService(TEST_DB_PATH)
        mock_session_instance = MagicMock(spec=Session)
        mock_scoped_session.return_value.return_value = mock_session_instance

        with pytest.raises(ValueError, match="Test exception"):
            with db_service.get_session() as session:
                assert session is mock_session_instance
                raise ValueError("Test exception")

        mock_session_instance.rollback.assert_called_once()
        mock_session_instance.close.assert_called_once()
        mock_session_instance.commit.assert_not_called()
        db_service.logger.error.assert_called_once()  # Check that error was logged

    # Test close_all method
    def test_close_all_success(
        self,
        mock_create_engine,
        mock_event_listens_for,
        mock_run_migrations,
        mock_scoped_session,
        mock_sessionmaker,
    ):
        db_service = DatabaseService(TEST_DB_PATH)

        db_service.close_all()

        mock_scoped_session.return_value.remove.assert_called_once()
        mock_create_engine.return_value.dispose.assert_called_once()
        db_service.logger.info.assert_called_with(
            "All database connections successfully closed."
        )
        db_service.logger.error.assert_not_called()

    def test_close_all_error(
        self,
        mock_create_engine,
        mock_event_listens_for,
        mock_run_migrations,
        mock_scoped_session,
        mock_sessionmaker,
    ):
        db_service = DatabaseService(TEST_DB_PATH)
        mock_scoped_session.return_value.remove.side_effect = Exception("Close error")

        db_service.close_all()

        db_service.logger.error.assert_called_once_with(
            "Error during database connection closure: Close error"
        )
        mock_create_engine.return_value.dispose.assert_called_once()  # Dispose should still be called if remove fails
