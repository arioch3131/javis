import logging
import pytest

from ai_content_classifier.core.logger import Logger, LoggableMixin, get_logger


@pytest.fixture(autouse=True)
def reset_loggers():
    """Fixture to reset loggers before each test to ensure isolation."""
    Logger._configured_loggers = {}
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.root.setLevel(logging.WARNING)  # Reset root logger level


class TestLogger:
    def test_get_logger_default_name_and_level(self):
        # When called without a name, it infers from the calling module, which is this test file.
        logger = Logger.get_logger()
        assert logger.name == "test_logger"  # Inferred from module name
        assert logger.level == logging.INFO
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.StreamHandler)

    def test_get_logger_custom_name_and_level(self):
        logger = Logger.get_logger("CustomLogger", level=logging.DEBUG)
        assert logger.name == "CustomLogger"
        assert logger.level == logging.DEBUG
        assert len(logger.handlers) == 1

    def test_get_logger_returns_existing_logger(self):
        logger1 = Logger.get_logger("ExistingLogger")
        logger2 = Logger.get_logger("ExistingLogger")
        assert logger1 is logger2
        assert len(logger1.handlers) == 1  # Ensure no duplicate handlers

    def test_get_logger_updates_level_of_existing_logger(self):
        logger1 = Logger.get_logger("LevelLogger", level=logging.INFO)
        assert logger1.level == logging.INFO
        logger2 = Logger.get_logger("LevelLogger", level=logging.WARNING)
        assert logger1 is logger2
        assert logger1.level == logging.WARNING

    def test_get_logger_custom_format(self):
        custom_format = "%(levelname)s: %(message)s"
        logger = Logger.get_logger("FormattedLogger", format_str=custom_format)
        formatter = logger.handlers[0].formatter
        assert formatter._fmt == custom_format

    def test_logger_propagate_is_false(self):
        logger = Logger.get_logger("NoPropagateLogger")
        assert logger.propagate is False

    def test_logger_configuration_details(self):
        logger = Logger.get_logger("DetailedLogger")
        assert len(logger.handlers) == 1
        handler = logger.handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        assert isinstance(handler.formatter, logging.Formatter)
        assert handler.formatter._fmt == Logger.DEFAULT_FORMAT
        assert logger.level == logging.INFO


class TestLoggableMixin:
    def test_loggable_mixin_initializes_logger(self):
        class MyClass(LoggableMixin):
            def __init__(self):
                self.__init_logger__()

        instance = MyClass()
        assert hasattr(instance, "logger")
        assert isinstance(instance.logger, logging.Logger)
        # The logger name should be based on the class's module and name, which is 'test_logger.MyClass'
        assert instance.logger.name == "test_logger.MyClass"
        assert instance.logger.level == logging.INFO

    def test_loggable_mixin_custom_logger_name_and_level(self):
        class AnotherClass(LoggableMixin):
            def __init__(self):
                self.__init_logger__(
                    level=logging.WARNING, logger_name="CustomMixinLogger"
                )

        instance = AnotherClass()
        assert instance.logger.name == "CustomMixinLogger"
        assert instance.logger.level == logging.WARNING

    def test_loggable_mixin_logger_is_reused(self):
        class ReusableClass(LoggableMixin):
            def __init__(self):
                self.__init_logger__()

        instance1 = ReusableClass()
        instance2 = ReusableClass()
        # Logger instances are reused by name, so if the name is the same, the object should be the same
        assert instance1.logger is instance2.logger


class TestGetLoggerFunction:
    def test_get_logger_function_wrapper(self):
        logger = get_logger("FunctionLogger", level=logging.ERROR)
        assert logger.name == "FunctionLogger"
        assert logger.level == logging.ERROR
        assert len(logger.handlers) == 1

    def test_get_logger_function_default_name(self):
        # When called without a name, it infers from the module where Logger.get_logger is defined.
        logger = get_logger()
        assert (
            logger.name == "ai_content_classifier.core.logger"
        )  # Inferred from the module where Logger.get_logger is defined
        assert logger.level == logging.INFO
