# views/managers/connection_manager.py
"""
Adapted Connection Manager - Simplified Qt interface for LLM connection management.

Replaces the old complex connection_manager (200+ lines) with a simplified version (~50 lines)
that directly delegates to the new LLMController.

Removes:
- Complex LLMConnectionService
- ConnectionTestWorker
- Multiple callbacks
- Duplicated state management

Keeps:
- Compatible interface with existing code
- Qt signals for the interface
- Simple delegation to LLMController
"""

import threading
from typing import Callable, List, Optional

from ai_content_classifier.controllers.llm_controller import LLMController
from ai_content_classifier.services.config_service import ConfigKey
from ai_content_classifier.core.logger import get_logger
from PyQt6.QtCore import QObject, QTimer, pyqtSignal


class ConnectionManager(QObject):
    """
    Simplified Qt manager for LLM connections.

    This manager now provides a simple interface to the LLMController
    and no longer contains complex business logic.

    It maintains compatibility with the existing interface while
    delegating everything to the new unified controller.
    """

    # Signals for compatibility with the existing interface
    connection_tested = pyqtSignal(bool, str)  # (success, message)
    models_retrieved = pyqtSignal(list)  # List of model names
    status_updated = pyqtSignal(str, str)  # (status_type, message)
    doc_llm_ready = pyqtSignal(bool, str)  # (is_ready, message)
    img_llm_ready = pyqtSignal(bool, str)  # (is_ready, message)

    def __init__(self, llm_controller: LLMController, parent=None):
        """
        Initializes the manager with the unified LLM controller.

        Args:
            llm_controller: Instance of the unified LLM controller
            parent: Qt parent
        """
        super().__init__(parent)
        self.logger = get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        # Unified controller (replaces service + worker + thread manager)
        self.llm_controller = llm_controller

        # Simple state
        self.current_api_url = ""
        self.is_connectd = False
        self.available_models: List[str] = []

        # Connect controller signals to our own
        self._setup_signal_connections()

        self.logger.info("Simplified ConnectionManager initialized")

    def _setup_signal_connections(self):
        """Configures signal connections with the controller."""
        # Direct redirection of controller signals
        self.llm_controller.connectionStatusChanged.connect(
            self._on_connection_status_changed
        )
        self.llm_controller.modelsRetrieved.connect(self._on_models_retrieved)
        self.llm_controller.operationError.connect(self._on_operation_error)

        self.logger.debug("Controller signals connectd")

    # === SIGNAL HANDLERS ===

    def _on_connection_status_changed(self, success: bool, message: str):
        """Handler for connection status changes."""
        self.is_connectd = success

        # Emit our signal for compatibility
        self.connection_tested.emit(success, message)

        # Update general status
        status_type = "connectd" if success else "error"
        self.status_updated.emit(status_type, message)

        self.logger.debug(f"Connection status: {success} - {message}")

    def _on_models_retrieved(self, models: List[str]):
        """Handler for model retrieval."""
        self.available_models = models.copy()

        # Emit our signal for compatibility
        self.models_retrieved.emit(models)

        self.logger.debug(f"Models retrieved: {len(models)}")

    def _resolve_available_model_name(self, model_name: str) -> Optional[str]:
        """Resolve configured model aliases against the models exposed by the API."""
        requested = (model_name or "").strip()
        if not requested:
            return None

        if requested in self.available_models:
            return requested

        llm_service = self.llm_controller.llm_service
        model_manager = getattr(llm_service, "model_manager", None)
        if model_manager is None:
            return None

        api_url = llm_service.config_service.get(ConfigKey.API_URL)
        model_info = model_manager.get_model_info(api_url, requested)
        if model_info and model_info.name:
            return model_info.name

        return None

    def _on_operation_error(self, operation: str, error_message: str):
        """Handler for operation errors."""
        self.is_connectd = False
        self.available_models.clear()

        # Signal the error
        self.status_updated.emit("error", error_message)

        self.logger.error(f"Operation error {operation}: {error_message}")

    # === PUBLIC INTERFACE ===

    def test_connection(
        self,
        api_url: str,
        on_success: Optional[Callable[[List[str]], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        """
        Launches an asynchronous connection test.

        Args:
            api_url: API URL to test
            on_success: Callback called on success with the list of models
            on_error: Callback called on error with the error message
        """
        self.logger.info(f"Connection test requested: {api_url}")

        # Save the tested URL
        self.current_api_url = api_url

        # Connect temporary callbacks if provided
        if on_success:
            # Temporary connection for this test only
            def temp_success_handler(models: List[str]):
                on_success(models)
                # Disconnect after use
                try:
                    self.models_retrieved.disconnect(temp_success_handler)
                except Exception:
                    pass  # Ignore if already disconnectd

            self.models_retrieved.connect(temp_success_handler)

        if on_error:
            # Temporary connection for this test only
            def temp_error_handler(status_type: str, message: str):
                if status_type == "error":
                    on_error(message)
                    # Disconnect after use
                    try:
                        self.status_updated.disconnect(temp_error_handler)
                    except Exception:
                        pass  # Ignore if already disconnectd

            self.status_updated.connect(temp_error_handler)

        # Delegate to the controller (which does the real work)
        self.llm_controller.test_connection(api_url)

    def get_connection_status(self) -> tuple[bool, str]:
        """
        Returns the current connection status.

        Returns:
            (is_connectd, current_api_url)
        """
        return self.is_connectd, self.current_api_url

    def get_available_models(self) -> List[str]:
        """
        Returns the list of available models.

        Returns:
            List of model names
        """
        return self.available_models.copy()

    # === SPECIALIZED METHODS FOR LLM ===

    def test_llm_connections(self):
        """Tests LLM connections and updates statuses."""
        try:
            api_url = self.llm_controller.llm_service.config_service.get(
                ConfigKey.API_URL
            )
            image_model = self.llm_controller.llm_service.config_service.get(
                ConfigKey.IMAGE_MODEL
            )
            document_model = self.llm_controller.llm_service.config_service.get(
                ConfigKey.DOCUMENT_MODEL
            )

            if api_url:
                self.logger.info("Testing specialized LLM connections")

                def on_connection_tested(success: bool, _message: str):
                    try:
                        self.connection_tested.disconnect(on_connection_tested)
                    except Exception:
                        pass

                    # Do not trigger extra model lookups when Ollama is unreachable.
                    if not success:
                        offline_message = "LLM API unreachable"
                        self.img_llm_ready.emit(False, offline_message)
                        self.doc_llm_ready.emit(False, offline_message)
                        return

                    # Delays to avoid overload once connection is confirmed.
                    QTimer.singleShot(
                        200,
                        lambda: self._check_specific_model_async("image", image_model),
                    )
                    QTimer.singleShot(
                        300,
                        lambda: self._check_specific_model_async(
                            "document", document_model
                        ),
                    )

                self.connection_tested.connect(on_connection_tested)
                self.test_connection(api_url)

        except Exception as e:
            self.logger.error(f"Error testing LLM connections: {e}")

    def _check_specific_model_async(self, model_type: str, model_name: str):
        """Run model availability check in background to keep UI responsive."""
        worker = threading.Thread(
            target=lambda: self._check_specific_model(model_type, model_name),
            daemon=True,
        )
        worker.start()

    def _check_specific_model(self, model_type: str, model_name: str):
        """Checks a specific model."""
        try:
            resolved_model = self._resolve_available_model_name(model_name)
            if resolved_model:
                if resolved_model == model_name:
                    message = f"Model {model_name} available"
                else:
                    message = f"Model {model_name} available as {resolved_model}"
                self.logger.info(f"{model_type}: {message}")

                if model_type == "image":
                    self.img_llm_ready.emit(True, message)
                elif model_type == "document":
                    self.doc_llm_ready.emit(True, message)
            else:
                message = f"Model {model_name} not available"
                self.logger.warning(f"{model_type}: {message}")

                if model_type == "image":
                    self.img_llm_ready.emit(False, message)
                elif model_type == "document":
                    self.doc_llm_ready.emit(False, message)

        except Exception as e:
            error_msg = f"Error checking {model_type} model: {str(e)}"
            self.logger.error(error_msg)

            if model_type == "image":
                self.img_llm_ready.emit(False, error_msg)
            elif model_type == "document":
                self.doc_llm_ready.emit(False, error_msg)
