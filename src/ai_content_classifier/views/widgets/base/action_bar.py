# views/widgets/base/action_bar.py
"""
ActionBar - Standardized action bar for dialogs and widgets.

Provides a consistent interface for action buttons with
theme support and state management.
"""

from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QPushButton
from ai_content_classifier.services.theme.theme_service import ThemePalette
from ai_content_classifier.views.widgets.base.themed_widget import ThemedWidget


class ActionBar(ThemedWidget):
    """
    Standardized action bar.

    Manages action buttons with consistent styling and state control.
    """

    # Signal emitted when an action is clicked
    action_triggered = pyqtSignal(str, str)  # (action_name, button_id)

    def __init__(self, parent=None, alignment: str = "right"):
        super().__init__(parent, "actionBar")

        self.alignment = alignment  # "left", "center", "right", "spread"
        self.buttons: Dict[str, QPushButton] = {}
        self.actions: List[Dict[str, Any]] = []

        self.setup_ui()

    def setup_ui(self):
        """Configure l'interface de la barre d'actions."""
        layout = self.get_main_layout()
        layout.setContentsMargins(12, 8, 12, 8)

        # Container principal
        self.action_container = QFrame()
        self.action_container.setObjectName("actionContainer")

        self.action_layout = QHBoxLayout(self.action_container)
        self.action_layout.setSpacing(8)
        self.action_layout.setContentsMargins(8, 8, 8, 8)

        # Ajouter stretch initial selon l'alignement
        if self.alignment in ["center", "right"]:
            self.action_layout.addStretch()

        layout.addWidget(self.action_container)

    def add_action(
        self,
        text: str,
        callback: Callable,
        button_id: str = None,
        primary: bool = False,
        enabled: bool = True,
        tooltip: str = None,
    ) -> QPushButton:
        """
        Add an action to the bar.

        Args:
            text: Texte du bouton
            callback: Function to call on click
            button_id: Identifiant unique du bouton
            primary: True si c'est l'action principale
            enabled: State initial du bouton
            tooltip: Tooltip optionnel

        Returns:
            The created button
        """
        if button_id is None:
            button_id = f"action_{len(self.buttons)}"

        # Creater le bouton
        button = QPushButton(text)
        button.setObjectName(f"{button_id}Button")
        button.setEnabled(enabled)

        if tooltip:
            button.setToolTip(tooltip)

        # Style selon le type
        if primary:
            button.setObjectName(f"{button_id}PrimaryButton")
            button.setDefault(True)

        # Connectr le signal
        button.clicked.connect(lambda: self._on_action_clicked(button_id, callback))

        # Enregistrer
        self.buttons[button_id] = button
        self.actions.append(
            {
                "id": button_id,
                "text": text,
                "callback": callback,
                "primary": primary,
                "button": button,
            }
        )

        # Ajouter au layout
        if self.alignment == "spread" and len(self.buttons) > 1:
            # Ajouter un stretch entre les boutons
            self.action_layout.addStretch()

        self.action_layout.addWidget(button)

        # Ajouter stretch final selon l'alignement
        if self.alignment in ["center", "left"] and len(self.buttons) == 1:
            self.action_layout.addStretch()

        self.logger.debug(f"Action added: {button_id} - {text}")
        return button

    def add_separator(self):
        """Add a separator between actions."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setObjectName("actionSeparator")
        self.action_layout.addWidget(separator)

    def add_stretch(self):
        """Ajoute un stretch dans la barre."""
        self.action_layout.addStretch()

    def remove_action(self, button_id: str):
        """Supprime une action de la barre."""
        if button_id in self.buttons:
            button = self.buttons[button_id]
            self.action_layout.removeWidget(button)
            button.deleteLater()
            del self.buttons[button_id]

            # Supprimer de la liste des actions
            self.actions = [a for a in self.actions if a["id"] != button_id]

            self.logger.debug(f"Action removed: {button_id}")

    def set_action_enabled(self, button_id: str, enabled: bool):
        """Enable/disable an action."""
        if button_id in self.buttons:
            self.buttons[button_id].setEnabled(enabled)

    def set_action_text(self, button_id: str, text: str):
        """Update le texte d'une action."""
        if button_id in self.buttons:
            self.buttons[button_id].setText(text)

    def get_action_button(self, button_id: str) -> Optional[QPushButton]:
        """Return le bouton d'une action."""
        return self.buttons.get(button_id)

    def _on_action_clicked(self, button_id: str, callback: Callable):
        """Handle le clic sur une action."""
        try:
            self.logger.debug(f"Action clicked: {button_id}")

            # Émettre le signal
            self.action_triggered.emit("clicked", button_id)

            # Appeler le callback
            if callback:
                callback()

        except Exception as e:
            self.logger.error(f"Error handling action {button_id}: {e}")

    def apply_default_theme(self, palette: ThemePalette):
        """Apply theme to action bar."""
        try:
            style = f"""
                QFrame#actionContainer {{
                    background-color: {palette.surface_variant};
                    border-top: 1px solid {palette.outline};
                    border-radius: 6px;
                }}

                QPushButton {{
                    background-color: {palette.surface};
                    color: {palette.on_surface};
                    border: 1px solid {palette.outline};
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                    min-width: 80px;
                }}

                QPushButton:hover {{
                    background-color: {palette.hover};
                    border-color: {palette.primary};
                }}

                QPushButton:pressed {{
                    background-color: {palette.pressed};
                }}

                QPushButton:disabled {{
                    background-color: {palette.disabled};
                    color: {palette.disabled_text};
                    border-color: {palette.disabled};
                }}

                QPushButton[objectName$="PrimaryButton"] {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {palette.primary},
                        stop:1 {palette.primary_dark}
                    );
                    color: white;
                    border: 2px solid {palette.primary_dark};
                }}

                QPushButton[objectName$="PrimaryButton"]:hover:enabled {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {palette.primary_light},
                        stop:1 {palette.primary}
                    );
                }}

                QFrame#actionSeparator {{
                    color: {palette.outline};
                    margin: 4px 8px;
                }}
            """
            self.setStyleSheet(style)

        except Exception as e:
            self.logger.error(f"Error applying action bar theme: {e}")

    def clear_actions(self):
        """Supprime toutes les actions."""
        for button_id in list(self.buttons.keys()):
            self.remove_action(button_id)

    def get_action_count(self) -> int:
        """Return le nombre d'actions."""
        return len(self.buttons)
