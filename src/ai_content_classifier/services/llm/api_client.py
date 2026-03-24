import base64
import json
import os
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import requests

from ai_content_classifier.core.logger import LoggableMixin, logging
from ai_content_classifier.models.config_models import ConfigKey
from ai_content_classifier.services.settings.config_service import ConfigService


def retry_on_failure(
    max_retries: Any = 3, backoff_factor: Any = 1.0, retry_exceptions: Tuple = None
):
    """
    A decorator to implement retry logic with exponential backoff for API calls.

    This decorator automatically retries a function call a specified number of times
    if it encounters certain exceptions, waiting longer between each retry.

    Args:
        max_retries (int or ConfigKey): The maximum number of times to retry the function call.
                               Defaults to 3. Can be a ConfigKey enum.
        backoff_factor (float or ConfigKey): The multiplier for the exponential backoff. The wait
                               time before retry `n` is `backoff_factor * (2 ** (n-1))` seconds.
                               Defaults to 1.0. Can be a ConfigKey enum.
        retry_exceptions (Tuple): A tuple of exception types that should trigger a retry.
                                  Defaults to `(requests.exceptions.RequestException, ConnectionError, TimeoutError)`.
    """
    if retry_exceptions is None:
        retry_exceptions = (
            requests.exceptions.RequestException,
            ConnectionError,
            TimeoutError,
        )

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception: Optional[Exception] = None

            # Attempt to get a logger instance and config_service from the first argument (self) if it's a method.
            logger: Optional[logging.Logger] = None
            config_service: Optional[ConfigService] = None
            if args and hasattr(args[0], "logger"):
                logger = args[0].logger
            if args and hasattr(args[0], "config_service"):
                config_service = args[0].config_service

            # Resolve max_retries and backoff_factor from ConfigService if they are ConfigKey enums
            resolved_max_retries = max_retries
            if isinstance(max_retries, ConfigKey) and config_service:
                resolved_max_retries = config_service.get(max_retries)

            resolved_backoff_factor = backoff_factor
            if isinstance(backoff_factor, ConfigKey) and config_service:
                resolved_backoff_factor = config_service.get(backoff_factor)

            for attempt in range(resolved_max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retry_exceptions as e:
                    last_exception = e
                    if attempt == resolved_max_retries:
                        if logger:
                            logger.error(
                                f"Function {func.__name__} failed after {resolved_max_retries} retries: {str(e)}"
                            )
                        break  # Exit loop after last failed attempt.

                    wait_time = resolved_backoff_factor * (2**attempt)
                    if logger:
                        logger.warning(
                            f"Attempt {attempt + 1}/{resolved_max_retries} failed for {func.__name__}, retrying in {wait_time:.1f}s: {str(e)}"
                        )
                    time.sleep(wait_time)
                except Exception as e:
                    # For non-retriable exceptions, log and re-raise immediately.
                    if logger:
                        logger.error(
                            f"Non-retriable error in {func.__name__}: {str(e)}"
                        )
                    raise

            # If the loop completes, it means all retries failed.
            if last_exception:
                raise last_exception
            # This case should ideally not be reached if max_retries > 0 and an exception occurred.
            raise RuntimeError(
                "Unexpected error: Function did not return and no exception was raised."
            )

        return wrapper

    return decorator


class LLMApiClient(LoggableMixin):
    """
    API client for interacting with the LLM service (Ollama).

    This client provides methods to connect to the API, manage models,
    and generate responses from LLM models. It also provides callback
    mechanisms for status updates with built-in retry logic and timeout management.

    Attributes:
        logger (Logger): Logger instance for this class.
        on_connection_status_changed (Optional[Callable]): Callback for connection status changes.
        on_model_status_changed (Optional[Callable]): Callback for model status changes.

    Logging:
        This class uses Python's standard logging with the following levels:
        - DEBUG: Detailed information, typically useful only when diagnosing problems.
        - INFO: Confirmation that things are working as expected.
        - WARNING: Indication that something unexpected happened, or may happen in the near future.
        - ERROR: Due to a more serious problem, the software has not been able to perform a task.
        - CRITICAL: A serious error, indicating that the program itself may be unable to continue running.

        A log level can be specified during initialization.
    """

    def __init__(
        self, api_url: str, config_service: ConfigService, log_level=logging.INFO
    ):
        """
        Initialize the LLM API client.

        Args:
            api_url (str): The base URL for the LLM API service.
            config_service (ConfigService): Configuration service instance.
            log_level (int, optional): Logging level to use for this client.
                Defaults to logging.INFO.
        """
        self.__init_logger__(log_level)
        self.logger.info("Initializing LLM API client.")
        self.api_url = api_url
        self.config_service = config_service

        # Initialize callback handlers
        self.on_connection_status_changed: Optional[Callable[[bool, str], None]] = None
        self.on_model_status_changed: Optional[Callable[[str, str], None]] = None

    @retry_on_failure(
        max_retries=ConfigKey.API_MAX_RETRIES,
        backoff_factor=ConfigKey.API_RETRY_BACKOFF,
        retry_exceptions=(
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
        ),
    )
    def _check_connection_internal(self) -> Tuple[bool, str]:
        """Internal method to check connection, used by check_connection with retry logic."""
        response = requests.get(
            f"{self.api_url}/api/version",
            timeout=self.config_service.get(ConfigKey.API_CONNECTION_TIMEOUT),
        )
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        version_info: Dict[str, Any] = response.json()
        version: str = version_info.get("version", "unknown")
        return True, f"Connected to Ollama v{version}"

    def check_connection(self) -> Tuple[bool, str]:
        """
        Check if the LLM API is accessible and get version information.

        Returns:
            Tuple[bool, str]: (success, message) indicating connection status.
        """
        self.logger.debug(f"Checking connection to API at {self.api_url}")
        start_time = time.time()

        try:
            success, message = self._check_connection_internal()
            request_time = time.time() - start_time
            # Extract version more robustly, handling cases where 'v' might not be present or message format changes
            version_str = message.split("v")[-1] if "v" in message else message
            self.logger.info(
                f"Ollama API accessible. Version: {version_str} (response time: {request_time:.2f}s)"
            )
            if self.on_connection_status_changed:
                self.on_connection_status_changed(success, message)
            return success, message
        except requests.exceptions.Timeout as e:
            timeout_val = self.config_service.get(ConfigKey.API_CONNECTION_TIMEOUT)
            message = f"Connection timeout after {timeout_val}s: {str(e)}"
            self.logger.error(message)
            if self.on_connection_status_changed:
                self.on_connection_status_changed(False, message)
            return False, message
        except requests.exceptions.ConnectionError as e:
            message = f"Connection refused: {str(e)}"
            self.logger.error(message)
            if self.on_connection_status_changed:
                self.on_connection_status_changed(False, message)
            return False, message
        except requests.exceptions.RequestException as e:
            message = f"API request error: {str(e)}"
            self.logger.error(message)
            if self.on_connection_status_changed:
                self.on_connection_status_changed(False, message)
            return False, message
        except Exception as e:
            message = f"An unexpected error occurred: {str(e)}"
            self.logger.error(message, exc_info=True)
            if self.on_connection_status_changed:
                self.on_connection_status_changed(False, message)
            return False, message

    @retry_on_failure(
        max_retries=ConfigKey.API_MAX_RETRIES,
        backoff_factor=ConfigKey.API_RETRY_BACKOFF,
        retry_exceptions=(
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.RequestException,
        ),
    )
    def _list_models_internal(self) -> List[Dict[str, Any]]:
        """Internal method to list models, used by list_models with retry logic."""
        response = requests.get(
            f"{self.api_url}/api/tags",
            timeout=self.config_service.get(ConfigKey.API_CONNECTION_TIMEOUT),
        )
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        models: List[Dict[str, Any]] = response.json().get("models", [])
        return models

    def list_models(self) -> List[Dict[str, Any]]:
        """
        Retrieve a list of available models from the LLM API.

        Returns:
            List[Dict[str, Any]]: List of available models with their information.
        """
        self.logger.debug(f"Requesting list of available models from {self.api_url}")
        start_time = time.time()

        try:
            models = self._list_models_internal()
            request_time = time.time() - start_time
            model_count = len(models)
            self.logger.info(f"Retrieved {model_count} models in {request_time:.2f}s")

            if self.logger.isEnabledFor(logging.DEBUG) and models:
                model_names = [model.get("name", "unnamed") for model in models]
                self.logger.debug(f"Available models: {', '.join(model_names)}")

            return models
        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.RequestException,
        ) as e:
            error_msg = f"Failed to retrieve models after retries: {str(e)}"
            self.logger.error(error_msg)
            return []
        except Exception as e:
            error_msg = f"Failed to retrieve models: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return []

    def pull_model(self, model_name: str) -> bool:
        """
        Download a model from the LLM API.

        Args:
            model_name (str): The name of the model to download.

        Returns:
            bool: True if download was successful, False otherwise.
        """
        self.logger.info(f"Starting download of model: {model_name}")
        start_time = time.time()
        last_log_time = start_time
        log_interval = self.config_service.get(
            ConfigKey.API_CONNECTION_TIMEOUT
        )  # Using a generic timeout for log interval

        try:
            response = requests.post(
                f"{self.api_url}/api/pull",
                json={"name": model_name},
                stream=True,
                timeout=self.config_service.get(
                    ConfigKey.API_GENERATE_TIMEOUT
                ),  # Using generate timeout for pull
            )

            if response.status_code == 200:
                highest_percent = 0

                for line in response.iter_lines():
                    if line:
                        try:
                            data: Dict[str, Any] = json.loads(line)
                            current_time = time.time()

                            if "status" in data:
                                status = data.get("status")

                                if "progress" in data and "total" in data:
                                    try:
                                        progress = int(data.get("progress", 0))
                                        total = int(data.get("total", 1))
                                        percent = (
                                            (progress / total) * 100 if total > 0 else 0
                                        )

                                        if (
                                            percent > highest_percent + 5
                                            or current_time - last_log_time
                                            >= log_interval
                                        ):
                                            self.logger.info(
                                                f"Model download progress: {percent:.1f}% ({progress}/{total} bytes)"
                                            )
                                            highest_percent = max(
                                                highest_percent, percent
                                            )
                                            last_log_time = current_time

                                        message = (
                                            f"Downloading {model_name}: {percent:.1f}%"
                                        )
                                        if self.on_model_status_changed:
                                            self.on_model_status_changed(
                                                "downloading", message
                                            )
                                    except (ValueError, ZeroDivisionError):
                                        pass
                                else:
                                    if current_time - last_log_time >= log_interval:
                                        self.logger.info(
                                            f"Model download status: {status}"
                                        )
                                        last_log_time = current_time

                                    if self.on_model_status_changed:
                                        self.on_model_status_changed(
                                            "downloading", status
                                        )
                        except json.JSONDecodeError as e:
                            self.logger.warning(
                                f"Received invalid JSON in stream: {str(e)}"
                            )

                total_time = time.time() - start_time
                message = f"Model {model_name} downloaded successfully"
                self.logger.info(
                    f"Model {model_name} downloaded successfully in {total_time:.1f}s"
                )

                if self.on_model_status_changed:
                    self.on_model_status_changed("success", message)
                return True
            else:
                error_msg = f"Failed to download model. HTTP {response.status_code}: {response.text[:100]}"
                self.logger.error(error_msg)

                if self.on_model_status_changed:
                    self.on_model_status_changed("error", error_msg)
                return False

        except Exception as e:
            error_msg = f"Failed to download model: {str(e)}"
            self.logger.error(error_msg, exc_info=True)

            if self.on_model_status_changed:
                self.on_model_status_changed("error", error_msg)
            return False

    @retry_on_failure(
        max_retries=ConfigKey.API_MAX_RETRIES,
        backoff_factor=ConfigKey.API_RETRY_BACKOFF,
        retry_exceptions=(
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.RequestException,
        ),
    )
    def _generate_internal(
        self,
        model_name: str,
        prompt: str,
        encoded_images: Optional[List[str]] = None,
        response_format: Optional[Union[Dict[str, Any], str]] = None,
    ) -> str:
        """Internal method to generate response, used by generate with retry logic."""
        payload = {"model": model_name, "prompt": prompt, "stream": False}

        if encoded_images:
            payload["images"] = encoded_images
        if response_format is not None:
            payload["format"] = response_format

        response = requests.post(
            f"{self.api_url}/api/generate",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=self.config_service.get(ConfigKey.API_GENERATE_TIMEOUT),
        )
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        result = response.json()
        return result.get("response", "")

    def generate(
        self,
        model_name: str,
        prompt: str,
        images: Optional[List[str]] = None,
        response_format: Optional[Union[Dict[str, Any], str]] = None,
    ) -> str:
        """
        Generate a response from the specified LLM model.

        Args:
            model_name (str): The name of the model to use.
            prompt (str): The prompt to send to the model.
            images (Optional[List[str]]): A list of image file paths to include.
                                          Images will be base64 encoded.
            response_format (Optional[Union[Dict[str, Any], str]]):
                Optional Ollama `format` value (e.g. "json" or a JSON schema dict)
                to constrain model output.

        Returns:
            str: The generated response from the model, or empty string on error.
        """
        encoded_images = []
        if images:
            for image_path in images:
                if not os.path.exists(image_path):
                    self.logger.warning(f"Image file not found: {image_path}")
                    return ""  # Return empty string immediately if image not found
                try:
                    with open(image_path, "rb") as image_file:
                        encoded_images.append(
                            base64.b64encode(image_file.read()).decode("utf-8")
                        )
                except Exception as e:
                    self.logger.error(f"Failed to encode image {image_path}: {e}")
                    return ""

        try:
            return self._generate_internal(
                model_name, prompt, encoded_images, response_format
            )
        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.RequestException,
        ) as e:
            self.logger.error(f"Generation failed after retries: {str(e)}")
            return ""
        except Exception as e:
            self.logger.error(f"Generation error: {str(e)}", exc_info=True)
            return ""
