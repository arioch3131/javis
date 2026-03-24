# views/widgets/base/theme_mixin.py
"""
ThemeMixin - Mixin for applying themes to widgets.
"""

from PyQt6.QtCore import pyqtSignal
from ai_content_classifier.services.theme.theme_service import (
    ThemePalette,
    get_theme_service,
)


class ThemeMixin:
    """
    Mixin to manage theme application on PyQt widgets.

    Cette mixin fournit une method pour configure l'application
    automatic theme application to a widget via ThemeService connection.
    """

    theme_changed = pyqtSignal(ThemePalette)

    def __init__(self):
        super().__init__()
        self._theme_apply_func = None

    def setup_theme(self, apply_func):
        """
        Configure theme support for the widget.

        Args:
            apply_func (callable): Function called to apply the theme.
                                   Elle doit accepter un argument ThemePalette.
        """
        self._theme_apply_func = apply_func
        theme_service = get_theme_service()
        theme_service.palette_updated.connect(self._apply_theme_internal)

        # Apply initial theme
        self._apply_theme_internal(theme_service.get_current_palette())

    def _apply_theme_internal(self, palette: ThemePalette):
        """Apply theme using the provided function."""
        if self._theme_apply_func:
            self._theme_apply_func(palette)
        self.theme_changed.emit(palette)
