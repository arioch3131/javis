import sys

from PyQt6.QtWidgets import QApplication, QScrollArea

from ai_content_classifier.views.widgets.dialogs.theme.theme_widgets import (
    ThemePreviewWidget,
    ThemeSettingsDialog,
    ThemeSelector,
)


class TestThemeWidgets:
    @classmethod
    def setup_class(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_theme_selector_uses_themed_scroll_area_and_buttons(self):
        widget = ThemeSelector()

        assert (
            widget.findChild(type(widget.import_btn), "themeImportButton") is not None
        )
        assert (
            widget.findChild(type(widget.export_btn), "themeExportButton") is not None
        )
        assert (
            widget.findChild(type(widget.settings_btn), "themeSettingsButton")
            is not None
        )
        assert widget.findChild(QScrollArea, "themeSelectorScrollArea") is not None

    def test_theme_preview_has_expected_size_and_styles(self):
        widget = ThemePreviewWidget("light")

        assert widget.width() > 0
        assert widget.height() > 0
        assert "ThemePreviewWidget" in widget.styleSheet()

    def test_theme_settings_dialog_initializes_without_missing_methods(self):
        dialog = ThemeSettingsDialog()

        assert dialog.get_current_state() == "normal"
