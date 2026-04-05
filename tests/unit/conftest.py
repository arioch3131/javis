import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock

# Force Qt to use an offscreen backend during tests.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Import the *actual* Base from the application's models module
from ai_content_classifier.models.base import Base


# Define a mock LoggableMixin for global patching
class MockLoggableMixin:
    def __init_logger__(self):
        self.logger = MagicMock()


@pytest.fixture(scope="function", autouse=True)
def mock_loggable_mixin_global(monkeypatch):
    """
    Globally patches LoggableMixin to use a MagicMock for its logger.
    This ensures all classes inheriting from LoggableMixin in tests
    will have a mock logger.
    """
    monkeypatch.setattr(
        "ai_content_classifier.core.logger.LoggableMixin", MockLoggableMixin
    )


@pytest.fixture(scope="session")
def setup_database():
    """Set up an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:", echo=False
    )  # Set echo=True for SQL debugging

    print(
        f"Tables known to Base.metadata before create_all: {list(Base.metadata.tables.keys())}"
    )
    Base.metadata.create_all(engine)
    print(
        f"Tables known to Base.metadata after create_all: {list(Base.metadata.tables.keys())}"
    )

    # Verify expected tables are created
    expected_tables = {
        "content_items",
        "tags",
        "collections",
        "app_settings",
        "content_tags",
        "collection_contents",
    }
    actual_tables = set(Base.metadata.tables.keys())
    missing_tables = expected_tables - actual_tables
    if missing_tables:
        pytest.fail(f"Missing expected tables: {missing_tables}")

    Session = sessionmaker(bind=engine)
    yield Session

    # Cleanup
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(setup_database):
    """Provide a database session for each test with automatic rollback."""
    session = setup_database()
    try:
        yield session
    finally:
        # Always rollback to ensure test isolation
        session.rollback()
        session.close()
