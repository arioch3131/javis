import pytest
from unittest.mock import Mock

from ai_content_classifier.services.settings.config_service import ConfigService
from ai_content_classifier.models.config_models import (
    ConfigKey,
    ConfigDefinition,
    CONFIG_DEFINITIONS,
)
from ai_content_classifier.services.shared.cache_runtime import NamespacedMemoryCache


# Mock CONFIG_DEFINITIONS for consistent testing
@pytest.fixture(autouse=True)
def mock_config_definitions():
    original_definitions = CONFIG_DEFINITIONS.copy()
    CONFIG_DEFINITIONS.clear()
    CONFIG_DEFINITIONS.update(
        {
            ConfigKey.API_URL: ConfigDefinition(
                key=ConfigKey.API_URL,
                type=str,
                default="http://localhost:11434",
                category="general",
                label="API URL",
                description="Description for API URL",
            ),
            ConfigKey.IMAGE_MODEL: ConfigDefinition(
                key=ConfigKey.IMAGE_MODEL,
                type=str,
                default="llava",
                category="image",
                label="Image Model",
                description="Description for Image Model",
            ),
            ConfigKey.CATEGORIES: ConfigDefinition(
                key=ConfigKey.CATEGORIES,
                type=list,
                default=["cat1", "cat2"],  # Changed default to list type
                category="general",
                label="Categories",
                description="Description for Categories",
            ),
            ConfigKey.THUMBNAIL_SIZE: ConfigDefinition(
                key=ConfigKey.THUMBNAIL_SIZE,
                type=int,
                default=128,
                category="image",
                label="Thumbnail Size",
                description="Description for Thumbnail Size",
            ),
        }
    )
    yield
    CONFIG_DEFINITIONS.clear()
    CONFIG_DEFINITIONS.update(original_definitions)


class TestConfigService:
    @pytest.fixture
    def mock_config_repository(self):
        return Mock()

    @pytest.fixture
    def config_service(self, mock_config_repository):
        service = ConfigService(mock_config_repository)
        service._cache.clear()
        return service

    @pytest.fixture(autouse=True)
    def clear_shared_cache(self):
        service = ConfigService(Mock())
        service._cache.clear()
        yield
        service._cache.clear()

    def test_initialization(self, config_service, mock_config_repository):
        assert config_service.repo == mock_config_repository
        assert isinstance(config_service._cache, NamespacedMemoryCache)
        assert config_service._cache.size() == 0

    def test_initialize_default_settings(self, config_service, mock_config_repository):
        mock_config_repository.get_value.side_effect = [
            None,
            None,
            None,
            None,
        ]  # Simulate all values as non-existent

        config_service.initialize_default_settings()

        # Check calls for API_URL (None -> set)
        mock_config_repository.get_value.assert_any_call(ConfigKey.API_URL.value)
        mock_config_repository.set_value.assert_any_call(
            ConfigKey.API_URL.value, "http://localhost:11434"
        )

        # Check calls for IMAGE_MODEL (None -> set)
        mock_config_repository.get_value.assert_any_call(ConfigKey.IMAGE_MODEL.value)
        mock_config_repository.set_value.assert_any_call(
            ConfigKey.IMAGE_MODEL.value, "llava"
        )

        # Check calls for CATEGORIES (None -> set)
        mock_config_repository.get_value.assert_any_call(ConfigKey.CATEGORIES.value)
        mock_config_repository.set_value.assert_any_call(
            ConfigKey.CATEGORIES.value, "cat1,cat2"
        )

        # Check calls for THUMBNAIL_SIZE (None -> set)
        mock_config_repository.get_value.assert_any_call(ConfigKey.THUMBNAIL_SIZE.value)
        mock_config_repository.set_value.assert_any_call(
            ConfigKey.THUMBNAIL_SIZE.value, "128"
        )

        # Ensure set_value was called for all non-existing defaults
        assert mock_config_repository.set_value.call_count == len(CONFIG_DEFINITIONS)

    def test_get_from_cache(self, config_service):
        config_service._cache.set(ConfigKey.API_URL.value, "cached_url")
        value = config_service.get(ConfigKey.API_URL)
        assert value == "cached_url"
        config_service.repo.get_value.assert_not_called()

    def test_get_from_repository_and_cache(
        self, config_service, mock_config_repository
    ):
        mock_config_repository.get_value.return_value = "repo_url"
        value = config_service.get(ConfigKey.API_URL)
        assert value == "repo_url"
        assert config_service._cache.get(ConfigKey.API_URL.value) == "repo_url"
        mock_config_repository.get_value.assert_called_once_with(
            ConfigKey.API_URL.value, "http://localhost:11434"
        )

    def test_get_type_conversion_list(self, config_service, mock_config_repository):
        mock_config_repository.get_value.return_value = "item1, item2,item3"
        value = config_service.get(ConfigKey.CATEGORIES)
        assert value == ["item1", "item2", "item3"]
        assert config_service._cache.get(ConfigKey.CATEGORIES.value) == [
            "item1",
            "item2",
            "item3",
        ]

    def test_get_type_conversion_int(self, config_service, mock_config_repository):
        mock_config_repository.get_value.return_value = "256"
        value = config_service.get(ConfigKey.THUMBNAIL_SIZE)
        assert value == 256
        assert config_service._cache.get(ConfigKey.THUMBNAIL_SIZE.value) == 256

    def test_get_invalid_key(self, config_service):
        with pytest.raises(
            ValueError, match="Invalid configuration key"
        ):  # Use a non-existent key
            config_service.get(
                ConfigKey.DOCUMENT_MODEL
            )  # Assuming DOCUMENT_MODEL is not in mock_config_definitions

    def test_set_value(self, config_service, mock_config_repository):
        config_service.set(ConfigKey.API_URL, "new_url")
        mock_config_repository.set_value.assert_called_once_with(
            ConfigKey.API_URL.value, "new_url"
        )
        assert config_service._cache.get(ConfigKey.API_URL.value) == "new_url"

    def test_set_list_value(self, config_service, mock_config_repository):
        config_service.set(ConfigKey.CATEGORIES, ["new_cat1", "new_cat2"])
        mock_config_repository.set_value.assert_called_once_with(
            ConfigKey.CATEGORIES.value, "new_cat1,new_cat2"
        )
        assert config_service._cache.get(ConfigKey.CATEGORIES.value) == [
            "new_cat1",
            "new_cat2",
        ]

    def test_get_all_settings(self, config_service, mock_config_repository):
        # Populate repository with some values
        mock_config_repository.get_value.side_effect = [
            "http://test.com",  # API_URL
            "llama",  # IMAGE_MODEL
            "catA,catB",  # CATEGORIES
            "512",  # THUMBNAIL_SIZE
        ]

        all_settings = config_service.get_all_settings()

        assert "general" in all_settings
        assert "image" in all_settings

        assert all_settings["general"]["API URL"]["value"] == "http://test.com"
        assert all_settings["general"]["Categories"]["value"] == ["catA", "catB"]
        assert all_settings["image"]["Image Model"]["value"] == "llama"
        assert all_settings["image"]["Thumbnail Size"]["value"] == 512

        # Ensure cache is populated
        assert config_service._cache.get(ConfigKey.API_URL.value) == "http://test.com"
        assert config_service._cache.get(ConfigKey.CATEGORIES.value) == ["catA", "catB"]
