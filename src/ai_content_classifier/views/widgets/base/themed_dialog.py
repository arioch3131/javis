# views/widgets/base/themed_dialog.py
"""
ThemedDialog - Base dialog with theme support and common features.

All dialogs inherit from this class to keep a consistent look
and standardized behavior.
"""

from typing import Any, Dict, Optional

from ai_content_classifier.core.logger import get_logger
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QShowEvent
from PyQt6.QtWidgets import QApplication, QDialog, QFrame, QScrollArea, QVBoxLayout
from ai_content_classifier.services.theme.theme_service import ThemePalette
from ai_content_classifier.views.widgets.base.theme_mixin import ThemeMixin


class ThemedDialog(QDialog, ThemeMixin):
    """
    Base dialog with shared theme and behavior.

    Features:
    - Standardized header with title and description
    - Configurable action bar
    - Automatic theme support
    - State management (loading, error, etc.)
    - Built-in validation
    - Extended signals
    """

    # Extended signals
    validation_failed = pyqtSignal(str)  # Error message
    state_changed = pyqtSignal(str)  # Dialog state
    _SCREEN_WIDTH_RATIO = 0.9
    _SCREEN_HEIGHT_RATIO = 0.88

    def __init__(
        self,
        parent=None,
        title: str = "Dialog",
        description: str = None,
        modal: bool = True,
    ):
        super().__init__(parent)
        self.logger = get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        # Base configuration
        self.setWindowTitle(title)
        self.setModal(modal)
        self.resize(600, 400)  # Default size

        # Dialog state
        self._state = "normal"
        self._validation_enabled = True
        self._screen_fit_applied = False

        # Dialog data
        self._title = title
        self._description = description
        self._config_data = {}

        # Theme setup
        self.setup_theme(self.apply_dialog_theme)

        # UI construction
        self.setup_ui()
        self._fit_to_screen()

        self.logger.debug(f"ThemedDialog initialized: {title}")

    def _fit_to_screen(self):
        """Ensure dialog geometry fits laptop-sized screens."""
        try:
            screen = self.screen() or QApplication.primaryScreen()
            if screen is None:
                return
            geometry = screen.availableGeometry()
            max_width = int(geometry.width() * self._SCREEN_WIDTH_RATIO)
            max_height = int(geometry.height() * self._SCREEN_HEIGHT_RATIO)
            if self.width() > max_width or self.height() > max_height:
                self.resize(
                    min(self.width(), max_width), min(self.height(), max_height)
                )
        except Exception as e:
            self.logger.debug(f"Could not fit dialog to screen: {e}")

    def showEvent(self, event: QShowEvent) -> None:
        """Apply screen-fit again when the dialog is actually shown."""
        super().showEvent(event)
        if not self._screen_fit_applied:
            self._fit_to_screen()
            self._screen_fit_applied = True

    def setup_ui(self):
        """Configure the dialog UI."""
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Header
        if self._title or self._description:
            self.header_widget = self.create_header()
            self.main_layout.addWidget(self.header_widget)

        # Main content (implemented in subclasses)
        self.content_widget = self.create_content()
        if self.content_widget:
            # Keep footer actions visible on small laptop screens by allowing
            # the central content area to scroll when needed.
            scroll_area = QScrollArea(self)
            scroll_area.setObjectName("dialogContentScrollArea")
            scroll_area.setWidgetResizable(True)
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            scroll_area.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )
            scroll_area.setWidget(self.content_widget)
            self.main_layout.addWidget(scroll_area, 1)

        # Footer with actions
        self.footer_widget = self.create_footer()
        if self.footer_widget:
            self.main_layout.addWidget(self.footer_widget)

    def create_header(self) -> QFrame:
        """Create the standardized header."""
        from views.widgets.base.header_section import HeaderSection

        return HeaderSection(
            title=self._title, description=self._description, parent=self
        )

    def create_content(self) -> Optional[QFrame]:
        """
        Create the main dialog content.
        Implement in subclasses.
        """
        return None

    def create_footer(self) -> QFrame:
        """Create the footer with action buttons."""
        from views.widgets.base.action_bar import ActionBar

        action_bar = ActionBar(self)

        # Default action buttons
        action_bar.add_action("❌ Cancel", self.reject, "cancelButton")
        action_bar.add_action(
            "✅ OK", self.accept_with_validation, "okButton", primary=True
        )

        return action_bar

    def apply_dialog_theme(self, palette: ThemePalette):
        """Apply the theme to the dialog."""
        try:
            style = f"""
                ThemedDialog {{
                    background-color: {palette.background};
                    color: {palette.on_background};
                }}

                QFrame {{
                    background-color: {palette.surface};
                    border-radius: 8px;
                }}
            """
            self.setStyleSheet(style)

        except Exception as e:
            self.logger.error(f"Error applying dialog theme: {e}")

    def set_state(self, state: str):
        """
        Set the dialog state.

        Args:
            state: State ('normal', 'loading', 'error', 'validating')
        """
        if self._state != state:
            old_state = self._state
            self._state = state
            self.on_state_changed(old_state, state)
            self.state_changed.emit(state)

    def on_state_changed(self, old_state: str, new_state: str):
        """Called when state changes."""
        # Update UI based on state
        if new_state == "loading":
            self.setEnabled(False)
        elif new_state == "normal":
            self.setEnabled(True)

        self.logger.debug(f"Dialog state: {old_state} -> {new_state}")

    def set_loading(self, loading: bool, message: str = "Processing..."):
        """Mark the dialog as processing."""
        self.set_state("loading" if loading else "normal")

        # Update title with processing indicator
        if loading:
            if not self.windowTitle().startswith("🔄"):
                self.setWindowTitle(f"🔄 {self.windowTitle()}")
        else:
            title = self.windowTitle().replace("🔄 ", "")
            self.setWindowTitle(title)

    def validate_configuration(self) -> tuple[bool, str]:
        """
        Validate dialog configuration.
        Implement in subclasses.

        Returns:
            Tuple (is_valid, error_message)
        """
        return True, ""

    def get_configuration(self) -> Dict[str, Any]:
        """
        Return dialog configuration.
        Implement in subclasses.
        """
        return self._config_data.copy()

    def set_configuration(self, config: Dict[str, Any]):
        """
        Set dialog configuration.
        Implement in subclasses.
        """
        self._config_data.update(config)

    def accept_with_validation(self):
        """Accept the dialog after validation."""
        if not self._validation_enabled:
            self.accept()
            return

        self.set_state("validating")

        try:
            is_valid, error_message = self.validate_configuration()

            if is_valid:
                self.logger.info(f"Dialog validation successful: {self._title}")
                self.set_state("normal")
                self.accept()
            else:
                self.logger.warning(f"Dialog validation failed: {error_message}")
                self.set_state("error")
                self.validation_failed.emit(error_message)
                self.show_validation_error(error_message)

        except Exception as e:
            error_msg = f"Validation error: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.set_state("error")
            self.validation_failed.emit(error_msg)
            self.show_validation_error(error_msg)

    def show_validation_error(self, message: str):
        """Show a validation error."""
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.warning(self, "❌ Validation Error", message)

    def set_validation_enabled(self, enabled: bool):
        """Enable/disable validation."""
        self._validation_enabled = enabled

    def add_custom_button(
        self, text: str, callback, object_name: str = None, primary: bool = False
    ):
        """Add a custom button to the footer."""
        if hasattr(self, "footer_widget") and hasattr(self.footer_widget, "add_action"):
            self.footer_widget.add_action(text, callback, object_name, primary)

    def get_current_state(self) -> str:
        """Return the current dialog state."""
        return self._state

    def is_valid_state(self) -> bool:
        """Check whether the dialog is in a valid state."""
        return self._state not in ["error", "loading"]

    def create_bold_font(self, size_offset: int = 0) -> QFont:
        """Create a bold font with optional size offset."""
        font = self.font()
        font.setBold(True)
        if size_offset != 0:
            font.setPointSize(font.pointSize() + size_offset)
        return font

    def create_italic_font(self, size_offset: int = 0) -> QFont:
        """Create an italic font with optional size offset."""
        font = self.font()
        font.setItalic(True)
        if size_offset != 0:
            font.setPointSize(font.pointSize() + size_offset)
        return font
