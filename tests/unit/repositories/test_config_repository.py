import pytest

from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from ai_content_classifier.models.settings_models import AppSettings

from ai_content_classifier.repositories.config_repository import ConfigRepository

from ai_content_classifier.services.database.database_service import DatabaseService

@pytest.fixture
def mock_db_service():
    """Fixture for a mock DatabaseService."""
    db_service = MagicMock(spec=DatabaseService)
    mock_session = MagicMock(spec=Session)

    # Create a mock context manager for get_session
    mock_session_context_manager = MagicMock()
    mock_session_context_manager.__enter__.return_value = mock_session

    # Simulate commit on exit for the context manager
    def mock_exit(*args, **kwargs):
        mock_session.commit()
    mock_session_context_manager.__exit__.side_effect = mock_exit

    db_service.get_session.return_value = mock_session_context_manager
    return db_service

@pytest.fixture
def config_repository(mock_db_service):
    """Fixture for ConfigRepository with a mock DatabaseService."""
    return ConfigRepository(mock_db_service)

class TestConfigRepository:
    def test_get_value_found(self, config_repository, mock_db_service):
        """Test retrieving an existing setting value."""
        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_setting = MagicMock(spec=AppSettings)
        mock_setting.value = "test_value"
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_setting

        value = config_repository.get_value("test_key")
        assert value == "test_value"
        mock_session.query.assert_called_once_with(AppSettings)
        mock_session.query.return_value.filter_by.assert_called_once_with(key="test_key")
        mock_session.query.return_value.filter_by.return_value.first.assert_called_once()

    def test_get_value_not_found(self, config_repository, mock_db_service):
        """Test retrieving a non-existent setting value."""
        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        value = config_repository.get_value("non_existent_key", default="default_value")
        assert value == "default_value"
        mock_session.query.assert_called_once_with(AppSettings)
        mock_session.query.return_value.filter_by.assert_called_once_with(key="non_existent_key")
        mock_session.query.return_value.filter_by.return_value.first.assert_called_once()

    def test_set_value_update_existing(self, config_repository, mock_db_service):
        """Test updating an existing setting value."""
        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_setting = MagicMock(spec=AppSettings)
        mock_setting.value = "old_value"
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_setting

        config_repository.set_value("test_key", "new_value")
        assert mock_setting.value == "new_value"
        mock_session.query.assert_called_once_with(AppSettings)
        mock_session.query.return_value.filter_by.assert_called_once_with(key="test_key")
        mock_session.query.return_value.filter_by.return_value.first.assert_called_once()
        mock_session.add.assert_not_called() # Should not add if updating
        mock_session.commit.assert_called_once()

    def test_set_value_add_new(self, config_repository, mock_db_service):
        """Test adding a new setting value."""
        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        with patch('ai_content_classifier.repositories.config_repository.AppSettings') as MockAppSettings:
            config_repository.set_value("new_key", "new_value")
            MockAppSettings.assert_called_once_with(key="new_key", value="new_value")
            mock_session.add.assert_called_once_with(MockAppSettings.return_value)
            mock_session.commit.assert_called_once()
