# views/managers/settings_manager.py
"""
Adapted Settings Manager - Simplified centralized settings management.

Replaces the old complex settings_manager with a version adapted to the new architecture.

Simplifies:
- Parameter propagation (a single method instead of multiple)
- Connection tests (direct delegation)
- Callback management (less complexity)
- Interface with LLM services

Maintained responsibilities:
- Opening and managing the settings dialog
- Saving and loading configurations
- Coordination with ConnectionManager for LLM tests
- Propagation to LLM services
"""

from ai_content_classifier.controllers.llm_controller import LLMController
from ai_content_classifier.core.logger import get_logger
from PyQt6.QtCore import QObject, pyqtSignal
from ai_content_classifier.services.config_service import ConfigKey, ConfigService
from ai_content_classifier.views.managers.connection_manager import ConnectionManager
from ai_content_classifier.views.widgets.dialogs.settings.settings_view import (
    SettingsView,
)


class SettingsManager(QObject):
    """
    Centralized settings manager adapted to the new architecture.
    """

    settings_updated = pyqtSignal(dict)
    settings_saved = pyqtSignal()
    test_requested = pyqtSignal(str)

    def __init__(
        self,
        config_service: ConfigService,
        llm_controller: LLMController,
        connection_manager: ConnectionManager,
        parent=None,
    ):
        super().__init__(parent)
        self.logger = get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        self.config_service = config_service
        self.llm_controller = llm_controller
        self.connection_manager = connection_manager

        self.logger.info("Adapted SettingsManager initialized")

    def open_settings_dialog(self, parent_window=None):
        """Opens the settings dialog."""
        try:
            self.logger.info("Opening settings dialog")
            clear_thumbnail_cb = None
            if parent_window and hasattr(
                parent_window, "handle_clear_thumbnail_cache_request"
            ):
                clear_thumbnail_cb = parent_window.handle_clear_thumbnail_cache_request
            dialog = SettingsView(
                self.config_service,
                self.llm_controller,
                parent_window,
                on_clear_thumbnail_cache=clear_thumbnail_cb,
            )
            dialog.setModal(True)

            # The new SettingsView handles its own logic, so we just need to show it.
            dialog.exec()

        except Exception as e:
            self.logger.error(f"Error opening settings dialog: {e}", exc_info=True)

    def get_unified_categories(self):
        """Returns configured categories with a safe fallback."""
        try:
            categories = self.config_service.get(ConfigKey.CATEGORIES)
            if isinstance(categories, list) and categories:
                return categories
        except Exception as e:
            self.logger.warning(f"Could not load categories from config service: {e}")

        return ["Work", "Personal", "Documents", "Images", "Archive", "Important"]
