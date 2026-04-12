# views/widgets/base/themed_widget.py
"""
ThemedWidget - Base widget with integrated theme support.

All custom widgets inherit from this class to get
automatic theme support and shared features.
"""

from typing import Optional

from ai_content_classifier.core.logger import get_logger
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from ai_content_classifier.services.theme.theme_service import ThemePalette
from ai_content_classifier.views.widgets.base.theme_mixin import ThemeMixin


class ThemedWidget(QWidget, ThemeMixin):
    """
    Base widget with automatic theme support.

    Features:
    - Automatic theme application
    - Shared state management (enabled, visible, etc.)
    - Layout utility methods
    - Integrated logging
    - Base signals
    """

    # Shared signals
    value_changed = pyqtSignal()
    state_changed = pyqtSignal(str)  # Widget state

    def __init__(self, parent=None, object_name: str = None):
        super().__init__(parent)
        self.logger = get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        # Basic configuration
        if object_name:
            self.setObjectName(object_name)

        # Widget state
        self._state = "normal"  # normal, loading, error, disabled
        self._auto_theme = True

        # Theme setup
        self.setup_theme(self.apply_default_theme)

        # Main layout (can be overridden)
        self._main_layout = None

        self.logger.debug(f"ThemedWidget initialized: {self.__class__.__name__}")

    def apply_default_theme(self, palette: ThemePalette):
        """Apply default theme to widget."""
        try:
            if not self._auto_theme:
                return

            style = f"""
                QWidget {{
                    background-color: {palette.surface};
                    color: {palette.on_surface};
                    border-radius: 6px;
                }}
                QWidget:disabled {{
                    background-color: {palette.disabled};
                    color: {palette.disabled_text};
                }}
            """
            self.setStyleSheet(style)

        except Exception as e:
            self.logger.error(f"Error applying theme: {e}")

    def set_auto_theme(self, enabled: bool):
        """Enable/disable automatic theme application."""
        self._auto_theme = enabled

    def get_main_layout(self) -> Optional[QVBoxLayout]:
        """Return or create the main layout."""
        if self._main_layout is None:
            self._main_layout = QVBoxLayout(self)
            self._main_layout.setContentsMargins(8, 8, 8, 8)
            self._main_layout.setSpacing(8)
        return self._main_layout

    def create_horizontal_layout(
        self, spacing: int = 8, margins: tuple = (0, 0, 0, 0)
    ) -> QHBoxLayout:
        """Create a horizontal layout with standard settings."""
        layout = QHBoxLayout()
        layout.setSpacing(spacing)
        layout.setContentsMargins(*margins)
        return layout

    def create_vertical_layout(
        self, spacing: int = 8, margins: tuple = (0, 0, 0, 0)
    ) -> QVBoxLayout:
        """Create a vertical layout with standard settings."""
        layout = QVBoxLayout()
        layout.setSpacing(spacing)
        layout.setContentsMargins(*margins)
        return layout

    def set_state(self, state: str):
        """
        Set the widget state.

        Args:
            state: State ('normal', 'loading', 'error', 'disabled', 'success')
        """
        if self._state != state:
            old_state = self._state
            self._state = state
            self.on_state_changed(old_state, state)
            self.state_changed.emit(state)

    def get_state(self) -> str:
        """Return current widget state."""
        return self._state

    def on_state_changed(self, old_state: str, new_state: str):
        """
        Method called on state change.
        Override in subclasses.
        """
        self.logger.debug(f"State changed: {old_state} -> {new_state}")

    def set_loading(self, loading: bool):
        """Mark widget as loading."""
        self.set_state("loading" if loading else "normal")
        self.setEnabled(not loading)

    def set_error(self, error: bool, message: str = ""):
        """Mark widget as error."""
        self.set_state("error" if error else "normal")
        if error and message:
            self.setToolTip(f"Error: {message}")
        elif not error:
            self.setToolTip("")

    def set_success(self, success: bool):
        """Mark widget as success."""
        self.set_state("success" if success else "normal")

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

    def add_to_layout(self, widget_or_layout, stretch: int = 0):
        """Add a widget or layout to the main layout."""
        main_layout = self.get_main_layout()
        if hasattr(widget_or_layout, "widget"):  # It's a layout
            main_layout.addLayout(widget_or_layout, stretch)
        else:  # It's a widget
            main_layout.addWidget(widget_or_layout, stretch)

    def add_stretch(self, factor: int = 1):
        """Add stretch to the main layout."""
        self.get_main_layout().addStretch(factor)

    def clear_layout(self):
        """Clear the main layout."""
        if self._main_layout:
            while self._main_layout.count():
                child = self._main_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
