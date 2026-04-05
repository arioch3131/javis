import pytest
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ai_content_classifier.models.base import Base
from ai_content_classifier.models.settings_models import (
    AppSettings,
    logger as settings_logger,
)


# Setup in-memory SQLite database for testing
@pytest.fixture(scope="module")
def setup_database():
    engine = create_engine("sqlite:///:memory:")
    # Import all models that inherit from Base to ensure they are registered with Base.metadata
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    yield Session
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(setup_database):
    session = setup_database()
    yield session
    session.rollback()  # Rollback any changes after each test
    session.close()


class TestAppSettingsModel:
    def test_create_app_settings(self, db_session):
        setting = AppSettings(key="test_key", value="test_value")
        db_session.add(setting)
        db_session.commit()
        assert setting.id is not None
        assert setting.key == "test_key"
        assert setting.value == "test_value"

    def test_app_settings_repr(self):
        setting = AppSettings(
            id=1,
            key="repr_key",
            value="a very long value that should be truncated in repr",
        )
        assert (
            repr(setting)
            == "<AppSettings(key='repr_key', value='a very long value that should be truncated in repr...')>"
        )

    def test_app_settings_unique_key(self, db_session):
        setting1 = AppSettings(key="unique_key", value="value1")
        db_session.add(setting1)
        db_session.commit()

        setting2 = AppSettings(key="unique_key", value="value2")
        db_session.add(setting2)
        with pytest.raises(Exception):  # Expecting a unique constraint violation
            db_session.commit()
        db_session.rollback()

    def test_settings_logger_initialized(self):
        assert isinstance(settings_logger, logging.Logger)
        assert settings_logger.name == "ai_content_classifier.models.settings_models"
        # We can't reliably test the info/debug calls on module load with patching
        # as the module is loaded before the test runs. The above assertions are sufficient.
