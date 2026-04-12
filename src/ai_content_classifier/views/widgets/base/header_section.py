# views/widgets/base/header_section.py
"""
HeaderSection - Section d'header reusable avec titre et description.

Used in dialogs and widgets to keep a consistent presentation.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout
from ai_content_classifier.services.theme.theme_service import ThemePalette
from ai_content_classifier.views.widgets.base.themed_widget import ThemedWidget


class HeaderSection(ThemedWidget):
    """
    Standardized header section.

    Displays a title and optional description with consistent styling.
    """

    def __init__(
        self, title: str, description: str = None, icon: str = None, parent=None
    ):
        super().__init__(parent, "headerSection")

        self.title_text = title
        self.description_text = description
        self.icon_text = icon

        self.setup_ui()

    def setup_ui(self):
        """Configure l'interface de l'header."""
        layout = self.get_main_layout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Container principal
        self.header_container = QFrame()
        self.header_container.setObjectName("headerContainer")

        header_layout = QVBoxLayout(self.header_container)
        header_layout.setContentsMargins(12, 12, 12, 12)
        header_layout.setSpacing(8)

        # Title with optional icon
        title_text = (
            f"{self.icon_text} {self.title_text}" if self.icon_text else self.title_text
        )
        self.title_label = QLabel(title_text)
        self.title_label.setObjectName("titleLabel")
        self.title_label.setFont(self.create_bold_font(4))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.title_label)

        # Description optionnelle
        if self.description_text:
            self.description_label = QLabel(self.description_text)
            self.description_label.setObjectName("descriptionLabel")
            self.description_label.setFont(self.create_italic_font())
            self.description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.description_label.setWordWrap(True)
            header_layout.addWidget(self.description_label)

        # Decorative separator
        separator = QFrame()
        separator.setObjectName("headerSeparator")
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        header_layout.addWidget(separator)

        layout.addWidget(self.header_container)

    def apply_default_theme(self, palette: ThemePalette):
        """Apply theme to header."""
        try:
            style = f"""
                QFrame#headerContainer {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 {palette.surface},
                        stop:1 {palette.surface_variant}
                    );
                    border: 2px solid {palette.outline};
                    border-radius: 12px;
                    margin: 4px;
                }}

                QLabel#titleLabel {{
                    color: {palette.primary};
                    background-color: transparent;
                    padding: 4px;
                }}

                QLabel#descriptionLabel {{
                    color: {palette.on_surface_variant};
                    background-color: transparent;
                    padding: 2px;
                }}

                QFrame#headerSeparator {{
                    color: {palette.outline};
                    margin: 8px 0;
                }}
            """
            self.setStyleSheet(style)

        except Exception as e:
            self.logger.error(f"Error applying header theme: {e}")

    def set_title(self, title: str):
        """Update the title."""
        self.title_text = title
        title_text = f"{self.icon_text} {title}" if self.icon_text else title
        if hasattr(self, "title_label"):
            self.title_label.setText(title_text)

    def set_description(self, description: str):
        """Update the description."""
        self.description_text = description
        if hasattr(self, "description_label"):
            self.description_label.setText(description)
        elif description:
            # Creater la description si elle n'existait pas
            self.setup_ui()

    def set_icon(self, icon: str):
        """Update icon."""
        self.icon_text = icon
        self.set_title(self.title_text)  # Refresh title with icon
