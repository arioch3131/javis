from ai_content_classifier.models.config_models import (
    ConfigKey,
    ConfigDefinition,
    CONFIG_DEFINITIONS,
)


class TestConfigModels:
    def test_config_key_enum(self):
        assert ConfigKey.LOG_LEVEL.value == "general.log_level"
        assert ConfigKey.API_URL.value == "api.url"
        assert ConfigKey.IMAGE_MODEL.value == "llm.image_model"
        assert ConfigKey.IMAGE_EXTENSIONS.value == "scan.image_extensions"
        assert ConfigKey.THUMBNAIL_SIZE.value == "thumbnails.size"
        assert ConfigKey.CATEGORIES.value == "categorization.categories"

    def test_config_definition_dataclass(self):
        definition = ConfigDefinition(
            key=ConfigKey.API_URL,
            type=str,
            default="http://localhost:11434",
            category="API",
            label="API URL",
            description="Base URL for the Ollama LLM service.",
        )
        assert definition.key == ConfigKey.API_URL
        assert definition.type == str
        assert definition.default == "http://localhost:11434"
        assert definition.category == "API"
        assert definition.label == "API URL"
        assert definition.description == "Base URL for the Ollama LLM service."
        assert definition.options is None
        assert definition.validation_rules == []

    def test_config_definitions_completeness(self):
        # Check if all ConfigKey enums have a corresponding definition
        for key in ConfigKey:
            assert key in CONFIG_DEFINITIONS, (
                f"Missing definition for ConfigKey: {key.name}"
            )

    def test_config_definitions_content(self):
        # Spot check a few definitions for correctness
        api_url_def = CONFIG_DEFINITIONS[ConfigKey.API_URL]
        assert api_url_def.type == str
        assert api_url_def.default == "http://localhost:11434"
        assert api_url_def.category == "API"

        image_ext_def = CONFIG_DEFINITIONS[ConfigKey.IMAGE_EXTENSIONS]
        assert image_ext_def.type == list
        assert ".jpg" in image_ext_def.default
        assert image_ext_def.category == "Scanning"

        categories_def = CONFIG_DEFINITIONS[ConfigKey.CATEGORIES]
        assert categories_def.type == list
        assert "Work" in categories_def.default
        assert categories_def.category == "Categorization"

    def test_config_definition_with_options_and_validation(self):
        def mock_validation(value):
            return True, ""

        definition = ConfigDefinition(
            key=ConfigKey.LOG_LEVEL,
            type=str,
            default="INFO",
            category="General",
            label="Log Level",
            description="Application logging level.",
            options=["DEBUG", "INFO", "WARNING"],
            validation_rules=[mock_validation],
        )
        assert definition.options == ["DEBUG", "INFO", "WARNING"]
        assert definition.validation_rules == [mock_validation]
