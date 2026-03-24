# views/widgets/common/file_selector.py
"""
FileSelector - Reusable file/folder selector.

Standardized widget for selecting files or folders with
built-in validation and a consistent interface.
"""

import os
from typing import Callable, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtWidgets import (
    QCompleter,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)
from ai_content_classifier.services.theme.theme_service import ThemePalette
from ai_content_classifier.views.widgets.base.themed_widget import ThemedWidget


class FileSelector(ThemedWidget):
    """
    Reusable file/folder selector.

    Features:
    - File, directory, or multi-file selection
    - Real-time validation
    - Auto-completion
    - Extension filters
    - Theme-consistent interface
    """

    # Signals
    path_changed = pyqtSignal(str)  # Path changed
    path_validated = pyqtSignal(bool, str)  # (is_valid, error_message)
    browse_clicked = pyqtSignal()  # Browse button clicked

    def __init__(
        self,
        mode: str = "file",
        parent=None,
        label: str = None,
        placeholder: str = None,
    ):
        """
        Initialize the selector.

        Args:
            mode: Selection mode ("file", "directory", "files", "save")
            parent: Widget parent
            label: Label to display
            placeholder: Placeholder text
        """
        super().__init__(parent, "fileSelector")

        # Configuration
        self.mode = mode
        self.label_text = label
        self.placeholder_text = placeholder or self._get_default_placeholder()

        # Validation
        self.file_filters = []  # Liste de filtres (ex: "*.txt")
        self.extension_filters = []  # Allowed extensions
        self.must_exist = True  # File/folder must exist
        self.custom_validator: Optional[Callable[[str], tuple[bool, str]]] = None

        # State
        self.current_path = ""
        self.is_valid = False
        self.last_directory = ""

        self.setup_ui()
        self.setup_validation()

    def _get_default_placeholder(self) -> str:
        """Return the default placeholder for the selected mode."""
        placeholders = {
            "file": "Select a file...",
            "directory": "Select a directory...",
            "files": "Select files...",
            "save": "Enter filename...",
        }
        return placeholders.get(self.mode, "Select...")

    def setup_ui(self):
        """Configure selector UI."""
        layout = self.get_main_layout()
        layout.setSpacing(4)

        # Optional label
        if self.label_text:
            self.label = QLabel(self.label_text)
            self.label.setFont(self.create_bold_font())
            layout.addWidget(self.label)

        # Main container
        self.selector_container = QFrame()
        self.selector_container.setObjectName("selectorContainer")

        selector_layout = QHBoxLayout(self.selector_container)
        selector_layout.setContentsMargins(4, 4, 4, 4)
        selector_layout.setSpacing(8)

        # Input path
        self.path_input = QLineEdit()
        self.path_input.setObjectName("pathInput")
        self.path_input.setPlaceholderText(self.placeholder_text)
        self.path_input.textChanged.connect(self._on_path_changed)

        # Auto-completion pour les folders
        if self.mode in ["directory", "file"]:
            completer = QCompleter()
            file_model = QFileSystemModel(completer)
            file_model.setRootPath("")
            completer.setModel(file_model)
            self.path_input.setCompleter(completer)

        # Browse button
        browse_icon = self._get_browse_icon()
        self.browse_button = QPushButton(f"{browse_icon} Browse")
        self.browse_button.setObjectName("browseButton")
        self.browse_button.clicked.connect(self._on_browse_clicked)

        # Validation indicator
        self.validation_indicator = QLabel("❓")
        self.validation_indicator.setObjectName("validationIndicator")
        self.validation_indicator.setFixedSize(20, 20)
        self.validation_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Assembly
        selector_layout.addWidget(self.path_input, 1)
        selector_layout.addWidget(self.validation_indicator)
        selector_layout.addWidget(self.browse_button)

        layout.addWidget(self.selector_container)

        # Error message
        self.error_label = QLabel()
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

    def _get_browse_icon(self) -> str:
        """Return icon for the current mode."""
        icons = {"file": "📄", "directory": "📁", "files": "📄", "save": "💾"}
        return icons.get(self.mode, "📁")

    def setup_validation(self):
        """Configure real-time validation."""
        # Initial validation
        self._validate_current_path()

    def _on_path_changed(self, path: str):
        """Called when the path changes."""
        self.current_path = path
        self._validate_current_path()
        self.path_changed.emit(path)

    def _on_browse_clicked(self):
        """Called when the browse button is clicked."""
        self.browse_clicked.emit()

        dialog_methods = {
            "file": self._browse_file,
            "directory": self._browse_directory,
            "files": self._browse_files,
            "save": self._browse_save_file,
        }

        method = dialog_methods.get(self.mode, self._browse_file)
        selected_path = method()

        if selected_path:
            self.set_path(selected_path)

    def _browse_file(self) -> Optional[str]:
        """Open file selection dialog."""
        file_filter = self._build_file_filter()
        start_dir = self._get_start_directory()

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select File", start_dir, file_filter
        )

        if file_path:
            self._update_last_directory(file_path)

        return file_path

    def _browse_directory(self) -> Optional[str]:
        """Open folder selection dialog."""
        start_dir = self._get_start_directory()

        directory = QFileDialog.getExistingDirectory(
            self, "Select Directory", start_dir
        )

        if directory:
            self._update_last_directory(directory)

        return directory

    def _browse_files(self) -> Optional[str]:
        """Open multi-selection dialog."""
        file_filter = self._build_file_filter()
        start_dir = self._get_start_directory()

        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Files", start_dir, file_filter
        )

        if file_paths:
            self._update_last_directory(file_paths[0])
            # For multi-selection, join with semicolons
            return ";".join(file_paths)

        return None

    def _browse_save_file(self) -> Optional[str]:
        """Open save dialog."""
        file_filter = self._build_file_filter()
        start_dir = self._get_start_directory()

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save File", start_dir, file_filter
        )

        if file_path:
            self._update_last_directory(file_path)

        return file_path

    def _build_file_filter(self) -> str:
        """Build file filter string for dialogs."""
        if not self.file_filters:
            return "All Files (*)"

        filters = []
        for filter_item in self.file_filters:
            if isinstance(filter_item, tuple):
                name, pattern = filter_item
                filters.append(f"{name} ({pattern})")
            else:
                filters.append(str(filter_item))

        return ";;".join(filters)

    def _get_start_directory(self) -> str:
        """Return start directory for dialogs."""
        # Priority: current path > last directory > home
        if self.current_path and os.path.exists(os.path.dirname(self.current_path)):
            return os.path.dirname(self.current_path)
        elif self.last_directory and os.path.exists(self.last_directory):
            return self.last_directory
        else:
            return os.path.expanduser("~")

    def _update_last_directory(self, file_path: str):
        """Update last used directory."""
        if os.path.isfile(file_path):
            self.last_directory = os.path.dirname(file_path)
        elif os.path.isdir(file_path):
            self.last_directory = file_path

    def _validate_current_path(self):
        """Validate current path."""
        path = self.current_path.strip()

        # Basic validation
        if not path:
            self._set_validation_state(False, "No path specified")
            return

        # Existence validation
        if self.must_exist:
            if self.mode == "directory":
                if not os.path.isdir(path):
                    self._set_validation_state(False, "Directory does not exist")
                    return
            elif self.mode in ["file", "files"]:
                if self.mode == "files":
                    # Multi-selection (separated by ;)
                    paths = [p.strip() for p in path.split(";")]
                    for p in paths:
                        if not os.path.isfile(p):
                            self._set_validation_state(
                                False, f"File does not exist: {os.path.basename(p)}"
                            )
                            return
                else:
                    if not os.path.isfile(path):
                        self._set_validation_state(False, "File does not exist")
                        return

        # Extension validation
        if self.extension_filters and self.mode in ["file", "files", "save"]:
            if self.mode == "files":
                paths = [p.strip() for p in path.split(";")]
                for p in paths:
                    if not self._has_valid_extension(p):
                        self._set_validation_state(
                            False, f"Invalid file type: {os.path.basename(p)}"
                        )
                        return
            else:
                if not self._has_valid_extension(path):
                    valid_ext = ", ".join(self.extension_filters)
                    self._set_validation_state(
                        False, f"Invalid file type. Allowed: {valid_ext}"
                    )
                    return

        # Custom validation
        if self.custom_validator:
            try:
                is_valid, error_msg = self.custom_validator(path)
                if not is_valid:
                    self._set_validation_state(False, error_msg)
                    return
            except Exception as e:
                self._set_validation_state(False, f"Validation error: {str(e)}")
                return

        # All checks passed
        self._set_validation_state(True, "")

    def _has_valid_extension(self, file_path: str) -> bool:
        """Check whether the file has a valid extension."""
        if not self.extension_filters:
            return True

        _, ext = os.path.splitext(file_path.lower())
        return ext in [e.lower() for e in self.extension_filters]

    def _set_validation_state(self, is_valid: bool, error_message: str):
        """Update validation state."""
        self.is_valid = is_valid

        # Update indicator
        if is_valid:
            self.validation_indicator.setText("✅")
            self.validation_indicator.setToolTip("Valid path")
            self.error_label.hide()
        else:
            self.validation_indicator.setText("❌")
            self.validation_indicator.setToolTip(error_message)

            if error_message:
                self.error_label.setText(f"❌ {error_message}")
                self.error_label.show()
            else:
                self.error_label.hide()

        # Emit signal
        self.path_validated.emit(is_valid, error_message)

    def apply_default_theme(self, palette: ThemePalette):
        """Apply theme to selector."""
        try:
            on_secondary = getattr(palette, "on_secondary", "#ffffff")
            error_container = getattr(
                palette,
                "error_container",
                getattr(palette, "surface_variant", "#f1f5f9"),
            )

            style = f"""
                QFrame#selectorContainer {{
                    background-color: {palette.surface};
                    border: 2px solid {palette.outline};
                    border-radius: 8px;
                    padding: 2px;
                }}

                QFrame#selectorContainer:focus-within {{
                    border-color: {palette.primary};
                }}

                QLineEdit#pathInput {{
                    background-color: transparent;
                    border: none;
                    padding: 8px;
                    font-size: 14px;
                    color: {palette.on_surface};
                }}

                QLineEdit#pathInput:focus {{
                    background-color: {palette.surface_variant};
                    border-radius: 4px;
                }}

                QPushButton#browseButton {{
                    background-color: {palette.secondary};
                    color: {on_secondary};
                    border: 1px solid {palette.secondary_dark};
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-weight: bold;
                    min-width: 80px;
                }}

                QPushButton#browseButton:hover {{
                    background-color: {palette.secondary_light};
                }}

                QPushButton#browseButton:pressed {{
                    background-color: {palette.secondary_dark};
                }}

                QLabel#validationIndicator {{
                    background-color: {palette.surface_variant};
                    border-radius: 10px;
                    margin: 2px;
                }}

                QLabel#errorLabel {{
                    color: {palette.error};
                    background-color: {error_container};
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-weight: bold;
                }}
            """
            self.setStyleSheet(style)

        except Exception as e:
            self.logger.error(f"Error applying file selector theme: {e}")

    # === PUBLIC API ===

    def set_path(self, path: str):
        """Set selected path."""
        self.path_input.setText(path)
        self.current_path = path
        self._validate_current_path()

    def get_path(self) -> str:
        """Return current path."""
        return self.current_path

    def get_paths(self) -> List[str]:
        """Return path list (for multi-selection)."""
        if self.mode == "files" and ";" in self.current_path:
            return [p.strip() for p in self.current_path.split(";")]
        else:
            return [self.current_path] if self.current_path else []

    def is_path_valid(self) -> bool:
        """Check whether current path is valid."""
        return self.is_valid

    def set_file_filters(self, filters: List):
        """
        Set file filters.

        Args:
            filters: List of filters, either strings ("*.txt")
                    or tuples ("Text Files", "*.txt")
        """
        self.file_filters = filters
        self._validate_current_path()

    def set_extension_filters(self, extensions: List[str]):
        """
        Set allowed extensions.

        Args:
            extensions: List of extensions ([".txt", ".pdf"])
        """
        self.extension_filters = extensions
        self._validate_current_path()

    def set_must_exist(self, must_exist: bool):
        """Set whether file/folder must exist."""
        self.must_exist = must_exist
        self._validate_current_path()

    def set_custom_validator(self, validator: Callable[[str], tuple[bool, str]]):
        """
        Set a custom validator.

        Args:
            validator: Function taking a path and returning (is_valid, error_message)
        """
        self.custom_validator = validator
        self._validate_current_path()

    def clear(self):
        """Clear selection."""
        self.set_path("")

    def set_placeholder(self, placeholder: str):
        """Update placeholder."""
        self.placeholder_text = placeholder
        if hasattr(self, "path_input"):
            self.path_input.setPlaceholderText(placeholder)

    def set_enabled(self, enabled: bool):
        """Enable/disable selector."""
        super().setEnabled(enabled)
        if hasattr(self, "path_input"):
            self.path_input.setEnabled(enabled)
        if hasattr(self, "browse_button"):
            self.browse_button.setEnabled(enabled)
