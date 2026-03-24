# services/theme_service.py
"""Theme service built on top of the shared theme contracts."""

from typing import Callable, Dict, List, Optional
from PyQt6.QtCore import QObject, QSettings, pyqtSignal
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QWidget

from ai_content_classifier.core.logger import get_logger
from ai_content_classifier.themes import (
    AppTheme,
    ThemePalette,
    ThemeRegistry,
    build_default_theme_registry,
)


class ThemeService(QObject):
    """
    Main theme management service.
    """

    # Signaux
    theme_changed = pyqtSignal(str)  # Name of the new theme
    palette_updated = pyqtSignal(object)  # Nouvelle palette

    def __init__(self):
        super().__init__()
        self.logger = get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        # State du service
        self.current_theme = "light"
        self.current_theme_definition: Optional[AppTheme] = None
        self.current_palette: Optional[ThemePalette] = None
        self.registered_widgets: List[QWidget] = []
        self.style_callbacks: Dict[str, Callable] = {}

        # Settings
        self.settings = QSettings("Javis", "Themes")

        # Palettes predefined
        self.theme_registry: ThemeRegistry = ThemeRegistry()
        self.palettes: Dict[str, ThemePalette] = {}
        self._init_predefined_palettes()

        # Load saved theme
        self.load_saved_theme()

    def _init_predefined_palettes(self):
        """Initialise les palettes predefined."""
        self.theme_registry = build_default_theme_registry()
        self.palettes = {
            theme_name: theme.palette
            for theme_name, theme in self.theme_registry.items()
        }

    def get_available_themes(self) -> List[str]:
        """Return the list of available themes."""
        return self.theme_registry.names()

    def get_current_theme(self) -> str:
        """Return the name of the current theme."""
        return self.current_theme

    def get_theme_definition(self, theme_name: Optional[str] = None) -> AppTheme:
        """Return the full configuration of the requested theme."""
        name = theme_name or self.current_theme
        if name not in self.theme_registry:
            name = self.theme_registry.default_theme
        return self.theme_registry.get(name)

    def get_current_palette(self) -> ThemePalette:
        """Return la palette actuelle."""
        return self.current_palette or self.get_theme_definition().palette

    def set_theme(self, theme_name: str) -> bool:
        """
        Change current theme.

        Args:
            theme_name: Theme name to apply

        Returns:
            True if the theme was applied successfully
        """
        try:
            if theme_name not in self.theme_registry:
                self.logger.warning(f"Theme '{theme_name}' not found")
                return False

            old_theme = self.current_theme
            self.current_theme = theme_name
            self.current_theme_definition = self.theme_registry.get(theme_name)
            self.current_palette = self.current_theme_definition.palette

            # Saver le choix
            self.save_theme_preference()

            # Apply theme to application
            self.apply_theme_to_application()

            # Notify registered widgets
            self.refresh_all_widgets()

            # Émettre les signaux
            self.theme_changed.emit(theme_name)
            self.palette_updated.emit(self.current_palette)

            self.logger.info(f"Theme changed from '{old_theme}' to '{theme_name}'")
            return True

        except Exception as e:
            self.logger.error(f"Error setting theme '{theme_name}': {e}")
            return False

    def apply_theme_to_application(self):
        """Apply the theme to the Qt application."""
        try:
            app = QApplication.instance()
            if not app:
                return

            palette = self.current_palette
            qt_palette = QPalette()

            # Configuration de la palette Qt
            qt_palette.setColor(QPalette.ColorRole.Window, QColor(palette.background))
            qt_palette.setColor(
                QPalette.ColorRole.WindowText, QColor(palette.on_background)
            )
            qt_palette.setColor(QPalette.ColorRole.Base, QColor(palette.surface))
            qt_palette.setColor(
                QPalette.ColorRole.AlternateBase, QColor(palette.surface_variant)
            )
            qt_palette.setColor(QPalette.ColorRole.Text, QColor(palette.on_surface))
            qt_palette.setColor(QPalette.ColorRole.Button, QColor(palette.surface))
            qt_palette.setColor(
                QPalette.ColorRole.ButtonText, QColor(palette.on_surface)
            )
            qt_palette.setColor(QPalette.ColorRole.Highlight, QColor(palette.primary))
            qt_palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
            qt_palette.setColor(QPalette.ColorRole.Link, QColor(palette.primary))
            qt_palette.setColor(
                QPalette.ColorRole.LinkVisited, QColor(palette.primary_dark)
            )

            # Appliquer la palette
            app.setPalette(qt_palette)

        except Exception as e:
            self.logger.error(f"Error applying theme to application: {e}")

    def register_widget(
        self, widget: QWidget, style_callback: Optional[Callable] = None
    ):
        """
        Register a widget so it receives theme updates.

        Args:
            widget: Widget to register
            style_callback: Fonction optionalle pour appliquer le style
        """
        try:
            if widget not in self.registered_widgets:
                self.registered_widgets.append(widget)

                if style_callback:
                    widget_id = id(widget)
                    self.style_callbacks[widget_id] = style_callback

                # Apply the theme immediately
                self.apply_theme_to_widget(widget)

                self.logger.debug(
                    f"Widget registered for theme updates: {widget.__class__.__name__}"
                )

        except Exception as e:
            self.logger.error(f"Error registering widget: {e}")

    def apply_theme_to_widget(self, widget: QWidget):
        """Apply the theme to a specific widget."""
        try:
            widget_id = id(widget)

            # Use the custom callback when available
            if widget_id in self.style_callbacks:
                callback = self.style_callbacks[widget_id]
                callback(self.current_palette)

            # Ou usesr la method standard si le widget la supporte
            elif hasattr(widget, "apply_theme"):
                widget.apply_theme(self.current_palette)

            # Ou appliquer un style basic
            else:
                self.apply_basic_theme_to_widget(widget)

        except Exception as e:
            self.logger.error(f"Error applying theme to widget: {e}")

    def apply_basic_theme_to_widget(self, widget: QWidget):
        """Apply a basic theme to a widget."""
        try:
            palette = self.current_palette
            basic_style = f"""
                QWidget {{
                    background-color: {palette.background};
                    color: {palette.on_background};
                }}
                QPushButton {{
                    background-color: {palette.surface};
                    color: {palette.on_surface};
                    border: 1px solid {palette.outline};
                    border-radius: 4px;
                    padding: 6px 12px;
                }}
                QPushButton:hover {{
                    background-color: {palette.hover};
                    border-color: {palette.primary};
                }}
                QPushButton:pressed {{
                    background-color: {palette.pressed};
                }}
                QLineEdit {{
                    background-color: {palette.surface};
                    color: {palette.on_surface};
                    border: 1px solid {palette.outline};
                    border-radius: 4px;
                    padding: 6px;
                }}
                QLineEdit:focus {{
                    border-color: {palette.primary};
                }}
            """
            widget.setStyleSheet(basic_style)

        except Exception as e:
            self.logger.error(f"Error applying basic theme: {e}")

    def refresh_all_widgets(self):
        """Refresh all registered widgets."""
        try:
            # Clean les widgets removed
            self.registered_widgets = [
                w for w in self.registered_widgets if w is not None
            ]

            # Apply the theme to all active widgets
            for widget in self.registered_widgets:
                try:
                    self.apply_theme_to_widget(widget)
                except Exception as e:
                    self.logger.warning(
                        f"Error refreshing widget {widget.__class__.__name__}: {e}"
                    )

            self.logger.debug(f"Refreshed {len(self.registered_widgets)} widgets")

        except Exception as e:
            self.logger.error(f"Error refreshing all widgets: {e}")

    def get_themed_stylesheet(self, base_style: str) -> str:
        """
        Replace theme variables in a stylesheet.

        Args:
            base_style: Style basic avec des variables comme {primary}

        Returns:
            Style avec les variables replaced par les current colors
        """
        try:
            variables = self.get_theme_definition().to_token_map()

            # Replacer les variables
            styled = base_style
            for var_name, var_value in variables.items():
                string_value = str(var_value)
                styled = styled.replace(f"{{{var_name}}}", string_value)
                styled = styled.replace(f"${var_name}", string_value)

            return styled

        except Exception as e:
            self.logger.error(f"Error processing themed stylesheet: {e}")
            return base_style

    def create_custom_palette(
        self, name: str, base_theme: str = "light"
    ) -> ThemePalette:
        """
        Create a custom palette based on an existing theme.

        Args:
            name: Nom de la nouvelle palette
            base_theme: Basic theme to clone

        Returns:
            Nouvelle palette custom
        """
        try:
            if base_theme not in self.theme_registry:
                base_theme = self.theme_registry.default_theme

            base_theme_definition = self.theme_registry.get(base_theme)
            custom_theme = base_theme_definition.clone(name=name)
            custom_palette = custom_theme.palette

            self.theme_registry.register(custom_theme, replace=True)
            self.palettes[name] = custom_palette
            self.logger.info(f"Created custom palette '{name}' based on '{base_theme}'")

            return custom_palette

        except Exception as e:
            self.logger.error(f"Error creating custom palette: {e}")
            return self.palettes["light"]

    def load_saved_theme(self):
        """Load saved theme."""
        try:
            saved_theme = self.settings.value("current_theme", "light")

            if saved_theme in self.theme_registry:
                self.set_theme(saved_theme)
                self.logger.info(f"Loaded saved theme: {saved_theme}")
            else:
                self.set_theme(self.theme_registry.default_theme)
                self.logger.info("Using default light theme")

        except Exception as e:
            self.logger.error(f"Error loading saved theme: {e}")
            self.set_theme(self.theme_registry.default_theme)

    def save_theme_preference(self):
        """Save current theme preference."""
        try:
            self.settings.setValue("current_theme", self.current_theme)
            self.settings.sync()

        except Exception as e:
            self.logger.error(f"Error saving theme preference: {e}")

    def export_theme(self, theme_name: str, file_path: str) -> bool:
        """
        Export a theme to a JSON file.

        Args:
            theme_name: Theme name to export
            file_path: Path of file de destination

        Returns:
            True si l'export a succeeded
        """
        try:
            if theme_name not in self.theme_registry:
                return False

            import json

            theme_definition = self.theme_registry.get(theme_name)
            theme_data = theme_definition.to_dict()

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(theme_data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Theme '{theme_name}' exported to {file_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error exporting theme: {e}")
            return False

    def import_theme(self, file_path: str) -> Optional[str]:
        """
        Import a theme from a JSON file.

        Args:
            file_path: Path of the file to import

        Returns:
            Imported theme name or None if error
        """
        try:
            import json

            with open(file_path, "r", encoding="utf-8") as f:
                theme_data = json.load(f)

            # Backward compatible import with legacy {"colors": {...}} payloads.
            if "palette" not in theme_data and "colors" in theme_data:
                theme_data = {
                    "name": theme_data.get("name", "imported_theme"),
                    "display_name": str(
                        theme_data.get("name", "imported_theme")
                    ).title(),
                    "palette": theme_data.get("colors", {}),
                }

            theme = AppTheme.from_dict(theme_data)
            theme_name = theme.name

            self.theme_registry.register(theme, replace=True)
            self.palettes[theme_name] = theme.palette
            self.logger.info(f"Theme '{theme_name}' imported from {file_path}")

            return theme_name

        except Exception as e:
            self.logger.error(f"Error importing theme: {e}")
            return None

    def register_theme(self, theme: AppTheme, *, replace: bool = False) -> bool:
        """Registers a full theme definition in the registry."""
        try:
            self.theme_registry.register(theme, replace=replace)
            self.palettes[theme.name] = theme.palette
            return True
        except ValueError as e:
            self.logger.warning(str(e))
            return False
        except Exception as e:
            self.logger.error(f"Error registering theme '{theme.name}': {e}")
            return False

    def get_theme_preview(self, theme_name: str) -> Dict[str, str]:
        """
        Return a preview of a theme with the main colors.

        Args:
            theme_name: Theme name

        Returns:
            Dictionnaire avec the main colors pour preview
        """
        try:
            if theme_name not in self.palettes:
                return {}

            palette = self.palettes[theme_name]

            return {
                "primary": palette.primary,
                "accent": palette.accent,
                "background": palette.background,
                "surface": palette.surface,
                "text": palette.on_background,
                "success": palette.success,
                "warning": palette.warning,
                "error": palette.error,
            }

        except Exception as e:
            self.logger.error(f"Error getting theme preview: {e}")
            return {}

    def get_filter_chips_stylesheet(
        self, palette: Optional[ThemePalette] = None
    ) -> str:
        """
        Returns the centralized stylesheet for FilterChipsContainer.
        """
        p = palette or self.get_current_palette()
        checked_text = "#ffffff"
        return f"""
            QFrame#filtersHeader {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {p.surface},
                    stop:1 {p.surface_variant}
                );
                border: 1px solid {p.outline};
                border-radius: 10px 10px 0 0;
            }}

            QScrollArea#filtersScroll {{
                background-color: {p.surface};
                border: 1px solid {p.outline};
                border-top: none;
                border-bottom: none;
            }}

            QWidget#filtersWidget {{
                background-color: {p.surface};
            }}

            QFrame#filtersActions {{
                background-color: {p.surface_variant};
                border: 1px solid {p.outline};
                border-radius: 0 0 10px 10px;
                border-top: none;
            }}

            QFrame[isFilterGroup="true"] {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {p.surface_variant},
                    stop:1 {p.surface}
                );
                border: 1px solid {p.outline};
                border-radius: 8px;
            }}

            QLabel#filterGroupTitle {{
                color: {p.on_surface};
                font-size: 11px;
                letter-spacing: 0.3px;
            }}

            FilterChip {{
                background-color: {p.surface_variant};
                border: 1px solid {p.outline};
                border-radius: 13px;
                margin: 1px;
            }}

            FilterChip[chip_type="default"] {{ background-color: {p.surface_variant}; }}
            FilterChip[chip_type="category"] {{ background-color: {p.surface_variant}; }}
            FilterChip[chip_type="extension"] {{ background-color: {p.surface_variant}; }}
            FilterChip[chip_type="date"] {{ background-color: {p.surface_variant}; }}
            FilterChip[chip_type="size"] {{ background-color: {p.surface_variant}; }}
            FilterChip[chip_type="status"] {{ background-color: {p.surface_variant}; }}

            QPushButton[objectName^="filterChipLabel_"] {{
                background-color: transparent;
                color: {p.on_surface_variant};
                border: none;
                padding: 2px 2px 2px 8px;
                font-weight: 600;
                text-align: left;
            }}

            QPushButton[objectName^="filterChipLabel_"]:checked {{
                color: {checked_text};
                background-color: {p.primary};
                border-radius: 11px;
                padding-right: 8px;
            }}

            QToolButton[objectName^="filterChipClose_"] {{
                background-color: transparent;
                border: none;
                color: {p.on_surface_variant};
                font-weight: 700;
                padding: 0px 3px 0px 0px;
            }}

            QToolButton[objectName^="filterChipClose_"]:hover {{
                color: {p.error};
            }}

            FilterChip:hover {{
                border-color: {p.primary};
            }}

            QPushButton#selectAllButton, QPushButton#clearAllButton {{
                background-color: {p.surface};
                color: {p.on_surface};
                border: 1px solid {p.outline};
                border-radius: 6px;
                padding: 5px 10px;
                font-weight: 600;
            }}

            QPushButton#selectAllButton:hover:enabled, QPushButton#clearAllButton:hover:enabled {{
                background-color: {p.hover};
            }}

            QPushButton#optionsButton {{
                background-color: {p.surface_variant};
                border: 1px solid {p.outline};
                border-radius: 6px;
            }}

            QPushButton#optionsButton:hover {{
                background-color: {p.hover};
            }}

            QLabel#countLabel {{
                color: {p.primary};
                font-weight: 700;
            }}

            QLabel#statusLabel {{
                color: {p.on_surface_variant};
                padding: 12px;
            }}
        """


# Global theme service instance
_theme_service_instance = None


def get_theme_service() -> ThemeService:
    """Return the global theme service instance."""
    global _theme_service_instance
    if _theme_service_instance is None:
        _theme_service_instance = ThemeService()
    return _theme_service_instance


def apply_theme_to_widget(widget: QWidget, style_callback: Optional[Callable] = None):
    """
    Utility function to apply a theme to a widget.

    Args:
        widget: Widget to apply theme to
        style_callback: Optional callback for custom styling
    """
    theme_service = get_theme_service()
    theme_service.register_widget(widget, style_callback)


def get_themed_style(base_style: str) -> str:
    """
    Utility function pour obtenir un style themed.

    Args:
        base_style: Style basic avec variables

    Returns:
        Style avec variables replaced
    """
    theme_service = get_theme_service()
    return theme_service.get_themed_stylesheet(base_style)
