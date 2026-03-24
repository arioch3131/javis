# controllers/llm_controller.py
"""
Minimal LLM Controller - Qt Interface for the Unified LLM Service.

Replaces the complex LLMServiceController (400+ lines) with a minimal
controller (~100 lines) that solely acts as the Qt-Service interface
and manages necessary signals.

Responsibilities:
- Expose Qt signals for the interface
- Manage asynchronous operations with QTimer
- Delegate all business logic to the unified LLMService
- Maintain compatibility with the existing interface

This controller contains NO business logic - everything is in LLMService.
"""

import threading
from typing import Any, Dict, List, Optional
from PyQt6.QtCore import QCoreApplication, QObject, QTimer, pyqtSignal, pyqtSlot

from ai_content_classifier.core.logger import get_logger
from ai_content_classifier.models.config_models import ConfigKey
from ai_content_classifier.services.settings.config_service import ConfigService
from ai_content_classifier.services.llm.llm_service import (
    ClassificationResult,
    ConnectionTestResult,
    LLMService,
)


class LLMController(QObject):
    """
    Minimal Qt Controller for the Unified LLM Service.

    This controller solely acts as the interface between Qt and the pure service.
    It delegates all business logic to the LLMService and only:
    - Emits appropriate Qt signals
    - Manages asynchronous operations without blocking the UI
    - Maintains compatibility with the existing interface
    """

    # Essential signals for the interface
    connectionStatusChanged = pyqtSignal(bool, str)  # (success, message)
    modelsRetrieved = pyqtSignal(list)  # List of available models
    configurationUpdated = pyqtSignal()  # Configuration updated
    operationError = pyqtSignal(str, str)  # (operation, error_message)

    # Signals for long operations (batch)
    batchProgress = pyqtSignal(int, int)  # (completed, total)
    batchCompleted = pyqtSignal(object)  # BatchResult
    _mainThreadCallbackRequested = pyqtSignal(object)

    def __init__(
        self,
        config_service: ConfigService,
        llm_service: Optional[LLMService] = None,
        parent=None,
    ):
        """
        Initializes the controller with an LLM service.

        Args:
            config_service: The ConfigService instance.
            llm_service: LLM service instance (automatically created if None)
            parent: Qt parent
        """
        super().__init__(parent)
        self.logger = get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        # Pure business service
        self.llm_service = llm_service or LLMService(config_service)

        # Controller state
        self.is_connected = False
        self.is_connectd = False
        self.current_models: List[str] = []
        self.current_api_url = ""
        self._connection_test_lock = threading.Lock()
        self._connection_test_in_progress = False
        self._mainThreadCallbackRequested.connect(self._execute_main_thread_callback)

        self.logger.info("Minimal LLM Controller initialized")

    def update_config(self):
        """Updates the LLM service configuration."""
        try:
            self.logger.debug("Updating LLM configuration")

            # Delegate to the service (business logic)
            url_changed = self.llm_service.update_config()

            # Emit update signal
            self.configurationUpdated.emit()

            # If URL changed, automatically test the new connection
            if url_changed:
                new_url = self.llm_service.config_service.get(ConfigKey.API_URL)
                self.current_api_url = new_url
                self.logger.info(f"API URL changed to: {new_url}")

                # Asynchronous test with delay to avoid blocking the UI
                QTimer.singleShot(100, lambda: self.test_connection(new_url))

        except Exception as e:
            error_msg = f"Error updating configuration: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.operationError.emit("config_update", error_msg)

    def test_connection(self, api_url: str = None):
        """
        Launches an asynchronous connection test.

        Args:
            api_url: URL to test (uses current config if None)
        """
        test_url = api_url or self.llm_service.config_service.get(ConfigKey.API_URL)
        self.logger.info(f"Starting connection test: {test_url}")

        def _perform_test():
            """Internal function to perform the test."""
            with self._connection_test_lock:
                if self._connection_test_in_progress:
                    self.logger.debug(
                        "Connection test skipped: another test is already running"
                    )
                    return
                self._connection_test_in_progress = True

            try:
                # Delegate to the service (business logic)
                result: ConnectionTestResult = self.llm_service.test_connection(
                    test_url
                )

                # Update local state
                self.is_connected = result.success
                self.is_connectd = result.success
                self.current_models = result.models.copy()
                if result.success:
                    self.current_api_url = result.api_url

                # Emit Qt signals
                self._emit_on_main_thread(
                    lambda: self.connectionStatusChanged.emit(
                        result.success, result.message
                    )
                )

                if result.success and result.models:
                    self._emit_on_main_thread(
                        lambda: self.modelsRetrieved.emit(result.models)
                    )
                    self.logger.info(
                        f"Connection successful - {len(result.models)} models found"
                    )
                else:
                    self.logger.warning(f"Connection failed: {result.message}")

            except Exception as e:
                error_msg = f"Connection test error: {str(e)}"
                self.logger.error(error_msg, exc_info=True)

                # Error state
                self.is_connected = False
                self.is_connectd = False
                self.current_models.clear()

                # Signal the error
                self._emit_on_main_thread(
                    lambda: self.connectionStatusChanged.emit(False, error_msg)
                )
                self._emit_on_main_thread(
                    lambda: self.operationError.emit("connection_test", error_msg)
                )
            finally:
                with self._connection_test_lock:
                    self._connection_test_in_progress = False

        # Execute in a real background thread to avoid blocking the UI loop.
        # In unit-test contexts (no Qt app), run synchronously so signals are delivered.
        if QCoreApplication.instance() is None:
            _perform_test()
            return

        worker = threading.Thread(target=_perform_test, daemon=True)
        worker.start()
        # Give very fast mocked operations a chance to complete in test contexts
        # without significantly blocking real UI usage.
        worker.join(timeout=0.05)

    def _emit_on_main_thread(self, callback):
        """Schedule callback on the Qt/main thread when needed."""
        if threading.current_thread() is threading.main_thread():
            callback()
        else:
            self._mainThreadCallbackRequested.emit(callback)

    @pyqtSlot(object)
    def _execute_main_thread_callback(self, callback):
        """Executes a callback in the controller QObject thread (Qt main thread)."""
        try:
            callback()
        except Exception as e:
            self.logger.error(f"Main-thread callback execution failed: {e}")

    def classify_image(
        self, image_path: str, categories: List[str]
    ) -> Optional[ClassificationResult]:
        """
        Synchronous image classification (for simple use).

        Args:
            image_path: Path to the image
            categories: Possible categories

        Returns:
            ClassificationResult or None if error
        """
        try:
            return self.llm_service.classify_image(image_path, categories)
        except Exception as e:
            error_msg = f"Image classification error: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.operationError.emit("classify_image", error_msg)
            return None

    def classify_document(
        self, document_path: str, categories: List[str]
    ) -> Optional[ClassificationResult]:
        """
        Synchronous document classification (for simple use).

        Args:
            document_path: Path to the document
            categories: Possible categories

        Returns:
            ClassificationResult or None if error
        """
        try:
            return self.llm_service.classify_document(document_path, categories)
        except Exception as e:
            error_msg = f"Document classification error: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.operationError.emit("classify_document", error_msg)
            return None

    def get_connection_status(self) -> tuple[bool, str]:
        """
        Returns the current connection status.

        Returns:
            (is_connected, current_api_url)
        """
        return self.is_connected, self.current_api_url

    def get_available_models(self) -> List[str]:
        """
        Returns the list of available models.

        Returns:
            List of model names
        """
        return self.current_models.copy()

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Returns cache statistics.

        Returns:
            Cache statistics
        """
        try:
            return self.llm_service.get_cache_stats()
        except Exception as e:
            self.logger.error(f"Error retrieving cache stats: {e}")
            return {}

    def clear_cache(self):
        """Clears all service caches."""
        try:
            self.llm_service.clear_cache()
            self.logger.info("Caches cleared via controller")
        except Exception as e:
            error_msg = f"Error clearing cache: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.operationError.emit("clear_cache", error_msg)

    def shutdown(self):
        """
        Properly shuts down the controller and service.
        """
        try:
            self.logger.info("Shutting down LLM controller...")
            self.llm_service.shutdown()
            self.logger.info("LLM controller shut down")
        except Exception as e:
            self.logger.error(f"Error shutting down controller: {e}")

    # === COMPATIBILITY METHODS ===
    # (to maintain compatibility with the old LLMServiceController)

    def check_connection(self) -> tuple[bool, str]:
        """Compatibility method - synchronous connection test."""
        try:
            result = self.llm_service.test_connection()
            return result.success, result.message
        except Exception as e:
            return False, str(e)

    def list_models(self) -> List[Dict[str, Any]]:
        """Compatibility method - list of models."""
        try:
            result = self.llm_service.test_connection()
            if result.success:
                return [{"name": model} for model in result.models]
            return []
        except Exception as e:
            self.operationError.emit("list_models", str(e))
            return []
