# views/widgets/theme_widgets.py
"""
Theme Widgets - components for theme management and selection.

Inclut :
- ThemeSelector : Theme selection widget
- ThemePreviewWidget : Theme previews
- ThemeSettingsDialog : Theme configuration dialog
"""

from typing import Dict

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from ai_content_classifier.services.theme.theme_service import (
    ThemePalette,
    get_theme_service,
)
from ai_content_classifier.views.widgets.base.themed_dialog import ThemedDialog
from ai_content_classifier.views.widgets.base.themed_widget import ThemedWidget


class ThemePreviewWidget(ThemedWidget):
    """Theme preview widget with primary colors."""

    def __init__(self, theme_name: str, parent=None):
        super().__init__(parent, object_name="themePreviewWidget")
        self.theme_name = theme_name
        metrics = get_theme_service().get_theme_definition().metrics
        self.setFixedSize(
            metrics.sidebar_width_medium - 20,
            metrics.preview_height_medium - 130,
        )
        self.setup_ui()

    def setup_ui(self):
        """Configure preview UI."""
        theme = get_theme_service().get_theme_definition()
        metrics = theme.metrics
        typography = theme.typography
        layout = self.get_main_layout()
        layout.setContentsMargins(
            metrics.spacing_sm,
            metrics.spacing_sm,
            metrics.spacing_sm,
            metrics.spacing_sm,
        )
        layout.setSpacing(metrics.spacing_xs)

        # Theme name
        self.name_label = QLabel(self.theme_name.title())
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet(
            f'font-family: "{typography.font_family}"; '
            f"font-size: {typography.font_size_md}px; "
            f"font-weight: {typography.font_weight_bold};"
        )
        layout.addWidget(self.name_label)

        # Conteneur des couleurs
        colors_container = QWidget()
        colors_layout = QGridLayout(colors_container)
        colors_layout.setSpacing(metrics.spacing_xs - 2)

        # Get theme preview
        theme_service = get_theme_service()
        preview_colors = theme_service.get_theme_preview(self.theme_name)

        # Create color swatches
        color_order = ["primary", "accent", "success", "warning"]
        for i, color_name in enumerate(color_order):
            if color_name in preview_colors:
                color_square = self.create_color_square(preview_colors[color_name])
                row, col = i // 2, i % 2
                colors_layout.addWidget(color_square, row, col)

        layout.addWidget(colors_container)

        # Surface preview
        self.surface_preview = QFrame()
        self.surface_preview.setFrameStyle(QFrame.Shape.Box)
        self.surface_preview.setMinimumHeight(metrics.control_height - 6)
        layout.addWidget(self.surface_preview)

        self.apply_preview_style(preview_colors)

    def create_color_square(self, color: str) -> QWidget:
        """Create a color swatch."""
        metrics = get_theme_service().get_theme_definition().metrics
        square = QFrame()
        square.setFixedSize(metrics.spacing_lg + 4, metrics.spacing_lg + 4)
        square.setStyleSheet(
            f"""
            QFrame {{
                background-color: {color};
                border: 1px solid #ccc;
                border-radius: {max(3, metrics.radius_sm - 3)}px;
            }}
        """
        )
        return square

    def apply_preview_style(self, colors: Dict[str, str]):
        """Apply preview style."""
        theme = get_theme_service().get_theme_definition()
        metrics = theme.metrics
        typography = theme.typography
        background = colors.get("background", "#ffffff")
        surface = colors.get("surface", "#f8fafc")
        text = colors.get("text", "#000000")
        primary = colors.get("primary", "#3b82f6")

        style = f"""
            ThemePreviewWidget {{
                background-color: {background};
                border: {metrics.focus_width}px solid {primary};
                border-radius: {metrics.radius_md - 2}px;
            }}
            ThemePreviewWidget:hover {{
                border-color: {primary};
            }}
            QLabel {{
                color: {text};
                font-family: "{typography.font_family}";
            }}
            QFrame {{
                background-color: {surface};
                border: 1px solid {primary};
                border-radius: {metrics.radius_sm - 2}px;
            }}
        """
        self.setStyleSheet(style)


class ThemeSelector(ThemedWidget):
    """
    Theme selection widget with visual previews.
    """

    theme_selected = pyqtSignal(str)  # Selected theme name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.populate_themes()

    def setup_ui(self):
        """Configure l'interface utilisateur."""
        theme = get_theme_service().get_theme_definition()
        metrics = theme.metrics
        typography = theme.typography
        layout = self.get_main_layout()
        layout.setSpacing(metrics.spacing_md)

        # Titre
        title_label = QLabel("🎨 Choose Theme")
        title_label.setObjectName("themeSelectorTitle")
        title_label.setStyleSheet(
            f'font-family: "{typography.font_family}"; '
            f"font-size: {typography.font_size_lg}px; "
            f"font-weight: {typography.font_weight_bold};"
        )
        layout.addWidget(title_label)

        # Scrollable area for themes
        scroll_area = QScrollArea()
        scroll_area.setObjectName("themeSelectorScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Container for theme previews
        self.themes_container = QWidget()
        self.themes_layout = QGridLayout(self.themes_container)
        self.themes_layout.setSpacing(metrics.spacing_md)
        self.themes_layout.setContentsMargins(
            metrics.spacing_sm,
            metrics.spacing_sm,
            metrics.spacing_sm,
            metrics.spacing_sm,
        )

        scroll_area.setWidget(self.themes_container)
        layout.addWidget(scroll_area)

        # Boutons d'action
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(metrics.spacing_sm)

        self.import_btn = QPushButton("📂 Import Theme")
        self.import_btn.setObjectName("themeImportButton")
        self.import_btn.clicked.connect(self.import_theme)

        self.export_btn = QPushButton("💾 Export Current")
        self.export_btn.setObjectName("themeExportButton")
        self.export_btn.clicked.connect(self.export_current_theme)

        self.settings_btn = QPushButton("⚙️ Advanced Settings")
        self.settings_btn.setObjectName("themeSettingsButton")
        self.settings_btn.clicked.connect(self.show_theme_settings)

        actions_layout.addWidget(self.import_btn)
        actions_layout.addWidget(self.export_btn)
        actions_layout.addStretch()
        actions_layout.addWidget(self.settings_btn)

        layout.addLayout(actions_layout)

    def populate_themes(self):
        """Fill grid with theme previews."""
        # Vider le layout existant
        for i in reversed(range(self.themes_layout.count())):
            self.themes_layout.itemAt(i).widget().setParent(None)

        theme_service = get_theme_service()
        available_themes = theme_service.get_available_themes()
        current_theme = theme_service.get_current_theme()

        # Create previews
        for i, theme_name in enumerate(available_themes):
            preview = ThemePreviewWidget(theme_name)

            # Creater un bouton clickable
            theme_btn = QPushButton()
            theme_btn.setObjectName("themeCardButton")
            theme_btn.setFlat(True)
            theme_btn.setFixedSize(preview.size())

            # Layout wrapper for preview
            btn_layout = QVBoxLayout(theme_btn)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.addWidget(preview)

            # Mark current theme
            if theme_name == current_theme:
                metrics = theme_service.get_theme_definition().metrics
                palette = theme_service.get_current_palette()
                theme_btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        border: {metrics.focus_width + 1}px solid {palette.success};
                        border-radius: {metrics.radius_md - 2}px;
                    }}
                """
                )

            # Connectr le clic
            theme_btn.clicked.connect(
                lambda checked, name=theme_name: self.select_theme(name)
            )

            # Add to grid (2 columns)
            row, col = i // 2, i % 2
            self.themes_layout.addWidget(theme_btn, row, col)

    def select_theme(self, theme_name: str):
        """Select a theme."""
        theme_service = get_theme_service()
        success = theme_service.set_theme(theme_name)

        if success:
            self.theme_selected.emit(theme_name)
            self.populate_themes()  # Refresh to reflect selection
        else:
            QMessageBox.warning(
                self, "Theme Error", f"Could not apply theme '{theme_name}'"
            )

    def import_theme(self):
        """Import a theme from file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Theme", "", "JSON files (*.json);;All files (*.*)"
        )

        if file_path:
            theme_service = get_theme_service()
            theme_name = theme_service.import_theme(file_path)

            if theme_name:
                QMessageBox.information(
                    self,
                    "Import Successful",
                    f"Theme '{theme_name}' imported successfully!",
                )
                self.populate_themes()
            else:
                QMessageBox.warning(
                    self,
                    "Import Failed",
                    "Could not import theme. Please check the file format.",
                )

    def export_current_theme(self):
        """Export current theme."""
        theme_service = get_theme_service()
        current_theme = theme_service.get_current_theme()

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Theme",
            f"{current_theme}_theme.json",
            "JSON files (*.json);;All files (*.*)",
        )

        if file_path:
            success = theme_service.export_theme(current_theme, file_path)

            if success:
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Theme '{current_theme}' exported to:\n{file_path}",
                )
            else:
                QMessageBox.warning(self, "Export Failed", "Could not export theme.")

    def show_theme_settings(self):
        """Show advanced theme settings."""
        dialog = ThemeSettingsDialog(self)
        dialog.exec()

        # Refresh after changes
        self.populate_themes()

    def apply_theme(self, palette: ThemePalette):
        """Apply theme to selector."""
        theme = get_theme_service().get_theme_definition(palette.name)
        metrics = theme.metrics
        typography = theme.typography
        style = f"""
            ThemeSelector {{
                background-color: {palette.background};
                color: {palette.on_background};
            }}
            QPushButton {{
                background-color: {palette.surface};
                color: {palette.on_surface};
                border: 1px solid {palette.outline};
                border-radius: {metrics.radius_sm}px;
                padding: {metrics.spacing_sm}px {metrics.spacing_lg}px;
                min-height: {metrics.control_height}px;
                font-family: "{typography.font_family}";
                font-size: {typography.font_size_sm}px;
                font-weight: {typography.font_weight_semibold};
            }}
            QPushButton:hover {{
                background-color: {palette.hover};
                border-color: {palette.primary};
            }}
            QPushButton:pressed {{
                background-color: {palette.pressed};
            }}
            QScrollArea {{
                border: 1px solid {palette.outline};
                border-radius: {metrics.radius_sm - 2}px;
                background-color: {palette.surface};
            }}
            QLabel#themeSelectorTitle {{
                color: {palette.on_surface};
            }}
        """
        self.setStyleSheet(style)


class ThemeSettingsDialog(ThemedDialog):
    """Dialog for advanced theme settings."""

    def __init__(self, parent=None):
        super().__init__(
            parent=parent,
            title="Theme Settings",
            description="Advanced settings for managing and customizing application themes.",
            modal=True,
        )
        self.resize(600, 500)
        self.load_current_settings()

    def create_header(self) -> QFrame | None:
        """Keep the placeholder dialog compact and avoid the generic header path."""
        return None

    def create_content(self) -> QFrame:
        """Create a minimal, non-crashing placeholder for theme settings."""
        content = QFrame()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        info_label = QLabel(
            "Advanced theme settings are not exposed yet.\n"
            "You can still switch, import, and export themes from the main selector."
        )
        info_label.setWordWrap(True)
        info_label.setObjectName("themeSettingsInfo")
        layout.addWidget(info_label)
        layout.addStretch()
        return content

    def create_footer(self) -> QFrame:
        footer = QFrame(self)
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(20, 0, 20, 20)
        layout.addStretch()

        close_button = QPushButton("Close", footer)
        close_button.setObjectName("okButton")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
        return footer

    def load_current_settings(self):
        """Load current settings placeholder for compatibility."""
        self._config_data = {}
