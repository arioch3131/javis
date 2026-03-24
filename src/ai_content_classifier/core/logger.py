"""
Application Logging Module.

This module provides a robust and centralized logging configuration for the entire application.
It ensures consistent logging format, behavior, and efficient management of loggers across
various components, facilitating effective debugging and monitoring.
"""

import logging
from typing import Dict, Optional
import inspect  # Moved to top


class Logger:  # pylint: disable=too-few-public-methods
    """
    A factory class for creating and managing logger instances.

    This class provides a standardized and centralized mechanism to obtain
    and configure `logging.Logger` instances throughout the application.
    It ensures consistent formatting, prevents duplicate handlers, and
    manages logger levels effectively.
    """

    # Defines the default format string for log messages.
    DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # A dictionary to keep track of already configured logger instances
    # to prevent the addition of duplicate handlers.
    _configured_loggers: Dict[str, logging.Logger] = {}

    @classmethod
    def get_logger(
        cls,
        name: Optional[str] = None,
        level: int = logging.INFO,
        format_str: Optional[str] = None,
    ) -> logging.Logger:
        """
        Retrieves or creates a configured logger instance.

        If a logger with the given `name` already exists and is configured,
        it will be returned. Otherwise, a new logger will be created,
        configured with a `StreamHandler` (outputting to console),
        and added to the internal registry.

        Args:
            name: The name of the logger. If `None`, the name of the
                  calling module will be used. This ensures that log messages
                  are attributed to their source module.
            level: The minimum logging level for messages to be processed
                   by this logger (e.g., `logging.INFO`, `logging.DEBUG`,
                   `logging.WARNING`, `logging.ERROR`, `logging.CRITICAL`).
                   Defaults to `logging.INFO`.
            format_str: An optional custom format string for log messages.
                        If `None`, the `DEFAULT_FORMAT` will be used.

        Returns:
            A fully configured `logging.Logger` instance.
        """
        # Determine the logger name: if not provided, infer from the calling module.
        if name is None:
            # inspect.stack()[1] gets the frame of the caller of get_logger
            frame = inspect.stack()[1]
            module = inspect.getmodule(frame[0])
            # Use module name if available, otherwise fallback to current module's name
            name = module.__name__ if module else __name__

        # Check if the logger has already been configured to prevent adding duplicate handlers.
        if name in cls._configured_loggers:
            logger = cls._configured_loggers[name]
            # Update the logging level in case it has been changed in the call.
            logger.setLevel(level)
            return logger

        # Get a logger instance from the logging module.
        logger = logging.getLogger(name)

        # Configure the logger only if it doesn't have any handlers yet.
        # This prevents re-configuring loggers that might have been set up elsewhere.
        if not logger.handlers:
            # Create a console handler to output log messages to the standard output.
            handler = logging.StreamHandler()

            # Create a formatter using the specified or default format string.
            formatter = logging.Formatter(format_str or cls.DEFAULT_FORMAT)
            handler.setFormatter(formatter)

            # Add the configured handler to the logger.
            logger.addHandler(handler)

            # Prevent messages from being propagated to the root logger,
            # as this logger is self-contained with its own handler.
            logger.propagate = False

        # Set the logging level for the logger.
        logger.setLevel(level)
        # Store the configured logger in the registry.
        cls._configured_loggers[name] = logger

        return logger


class LoggableMixin:  # pylint: disable=too-few-public-methods
    """
    A mixin class designed to easily integrate logging capabilities into any class.

    Classes that inherit from `LoggableMixin` will automatically gain a
    `self.logger` attribute, which is a pre-configured `logging.Logger`
    instance specific to the inheriting class. This promotes consistent
    logging practices across the application's object-oriented structure.
    """

    def __init_logger__(
        self,
        level: int = logging.INFO,
        logger_name: Optional[str] = None,
        propagate: bool = False,
    ):
        """
        Initializes the logger for the instance of the inheriting class.

        This method should be explicitly called from the `__init__` method
        of any subclass that wishes to utilize the `LoggableMixin`. It sets up
        `self.logger` using the `Logger.get_logger` factory method.

        Args:
            level: The desired logging level for this instance's logger.
                   Defaults to `logging.INFO`.
            logger_name: An optional custom name for the logger. If `None`,
                         the logger name will be automatically generated
                         in the format `module_name.ClassName`.
        """
        # Generate a default logger name based on the class's module and name
        # if a custom name is not provided.
        if logger_name is None:
            logger_name = f"{self.__class__.__module__}.{self.__class__.__name__}"

        # Obtain and store the configured logger instance.
        self.logger = Logger.get_logger(logger_name, level)
        self.logger.propagate = propagate

        # Log a debug message indicating the successful initialization of the logger
        # for the current class instance.
        self.logger.debug("Logger initialized for %s", self.__class__.__name__)


# Configure the root logger for general application-wide messages.
# This logger can be used for messages not tied to a specific class or module.
root_logger = Logger.get_logger("root")


# Helper function for direct access to logger instances,
# providing a convenient shortcut for module-level logging.
def get_logger(name: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
    """
    A convenience function to retrieve a configured logger instance.

    This function acts as a direct wrapper around `Logger.get_logger`,
    allowing for simpler access to logger instances without needing
    to directly interact with the `Logger` class.

    Args:
        name: The name of the logger. If `None`, the name of the
              calling module will be used.
        level: The minimum logging level for messages to be processed.
               Defaults to `logging.INFO`.

    Returns:
        A configured `logging.Logger` instance.
    """
    return Logger.get_logger(name, level)
