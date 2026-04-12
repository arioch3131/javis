# views/widgets/common/category_editor.py
"""
CategoryEditor - Reusable category editor.

Widget for adding, removing, and editing categories
with validation and an intuitive interface.
"""

from typing import Callable, List, Optional, Set

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
from ai_content_classifier.services.theme.theme_service import ThemePalette
from ai_content_classifier.services.theme.theme_service import get_theme_service
from ai_content_classifier.views.widgets.base.themed_widget import ThemedWidget


class CategoryEditor(ThemedWidget):
    """
    Category editor with an intuitive interface.

    Features:
    - Add/remove categories
    - Inline editing
    - Name validation
    - Predefined categories
    - Context menu
    - Drag-and-drop support for reordering
    """

    # Signals
    categories_changed = pyqtSignal(list)  # Updated category list
    category_added = pyqtSignal(str)  # Added category
    category_removed = pyqtSignal(str)  # Removed category
    category_renamed = pyqtSignal(str, str)  # (old_name, new_name)

    def __init__(self, parent=None, title: str = "Categories"):
        super().__init__(parent, "categoryEditor")

        self.title = title
        self.categories: Set[str] = set()
        self.predefined_categories: Set[str] = {
            "Work",
            "Personal",
            "Archive",
            "Important",
            "Draft",
            "Other",
        }
        self.allow_empty = False
        self.max_categories = 50
        self.custom_validator: Optional[Callable[[str], tuple[bool, str]]] = None

        self.setup_ui()
        self.load_predefined_categories()

    def setup_ui(self):
        """Configure editor UI."""
        layout = self.get_main_layout()

        # Header with title
        self.header_container = QFrame()
        self.header_container.setObjectName("categoryHeader")

        header_layout = QVBoxLayout(self.header_container)
        header_layout.setContentsMargins(8, 8, 8, 8)
        header_layout.setSpacing(4)

        # Title
        self.title_label = QLabel(f"📂 {self.title}")
        self.title_label.setFont(self.create_bold_font(2))
        header_layout.addWidget(self.title_label)

        # Informational subtitle
        self.info_label = QLabel(
            "Add, remove or modify categories for content classification"
        )
        self.info_label.setFont(self.create_italic_font(-1))
        header_layout.addWidget(self.info_label)

        layout.addWidget(self.header_container)

        # Add section
        self.add_container = QFrame()
        self.add_container.setObjectName("addContainer")

        add_layout = QHBoxLayout(self.add_container)
        add_layout.setContentsMargins(8, 8, 8, 8)
        add_layout.setSpacing(8)

        # Input for a new category
        self.new_category_input = QLineEdit()
        self.new_category_input.setObjectName("newCategoryInput")
        self.new_category_input.setPlaceholderText("Enter new category name...")
        self.new_category_input.returnPressed.connect(self._add_category)
        self.new_category_input.textChanged.connect(self._validate_input)

        # Add button
        self.add_button = QPushButton("➕ Add")
        self.add_button.setObjectName("addButton")
        self.add_button.clicked.connect(self._add_category)
        self.add_button.setEnabled(False)

        # Suggestions button
        self.suggestions_button = QPushButton("💡 Suggestions")
        self.suggestions_button.setObjectName("suggestionsButton")
        self.suggestions_button.clicked.connect(self._show_suggestions)

        add_layout.addWidget(self.new_category_input, 1)
        add_layout.addWidget(self.add_button)
        add_layout.addWidget(self.suggestions_button)

        layout.addWidget(self.add_container)

        # Category list
        self.categories_list = QListWidget()
        self.categories_list.setObjectName("categoriesList")
        self.categories_list.setAlternatingRowColors(True)
        self.categories_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.categories_list.customContextMenuRequested.connect(self._show_context_menu)
        self.categories_list.itemDoubleClicked.connect(self._edit_category)

        layout.addWidget(self.categories_list, 1)

        # Action bar
        self.actions_container = QFrame()
        self.actions_container.setObjectName("actionsContainer")

        actions_layout = QHBoxLayout(self.actions_container)
        actions_layout.setContentsMargins(8, 4, 8, 4)
        actions_layout.setSpacing(8)

        # Counter
        self.count_label = QLabel("0 categories")
        self.count_label.setObjectName("countLabel")
        actions_layout.addWidget(self.count_label)

        actions_layout.addStretch()

        # Action buttons
        self.clear_button = QPushButton("🗑️ Clear All")
        self.clear_button.setObjectName("clearButton")
        self.clear_button.clicked.connect(self._clear_all)
        self.clear_button.setEnabled(False)

        self.reset_button = QPushButton("↺ Reset")
        self.reset_button.setObjectName("resetButton")
        self.reset_button.clicked.connect(self._reset_to_defaults)

        actions_layout.addWidget(self.clear_button)
        actions_layout.addWidget(self.reset_button)

        layout.addWidget(self.actions_container)

        # Error message
        self.error_label = QLabel()
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

    def load_predefined_categories(self):
        """Load default predefined categories."""
        for category in ["Work", "Personal", "Other"]:
            self._add_category_internal(category)

    def _validate_input(self, text: str):
        """Validate input text."""
        text = text.strip()

        # Enable/disable button based on validity
        is_valid = self._is_valid_category_name(text)
        self.add_button.setEnabled(is_valid)

        # Update input error state
        if text and not is_valid:
            self._show_input_error("Invalid category name")
        else:
            self._hide_input_error()

    def _is_valid_category_name(self, name: str) -> bool:
        """Check whether a category name is valid."""
        name = name.strip()

        # Basic checks
        if not name:
            return False

        if len(name) < 2:
            return False

        if len(name) > 50:
            return False

        # Forbidden characters
        forbidden_chars = {"/", "\\", ":", "*", "?", '"', "<", ">", "|", ";"}
        if any(char in name for char in forbidden_chars):
            return False

        # Name already exists
        if name.lower() in {cat.lower() for cat in self.categories}:
            return False

        # Custom validation
        if self.custom_validator:
            try:
                is_valid, _ = self.custom_validator(name)
                if not is_valid:
                    return False
            except Exception:
                return False

        return True

    def _add_category(self):
        """Add a new category."""
        text = self.new_category_input.text().strip()

        if self._is_valid_category_name(text):
            self._add_category_internal(text)
            self.new_category_input.clear()
            self.new_category_input.setFocus()

    def _add_category_internal(self, name: str):
        """Add a category without validation (internal use)."""
        if name in self.categories:
            return

        if len(self.categories) >= self.max_categories:
            self._show_error(f"Maximum {self.max_categories} categories allowed")
            return

        # Add to list
        self.categories.add(name)

        # Add to interface
        item = QListWidgetItem(f"📁 {name}")
        item.setData(Qt.ItemDataRole.UserRole, name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.categories_list.addItem(item)

        # Sort list
        self.categories_list.sortItems()

        # Update interface
        self._update_ui_state()

        # Emit signals
        self.category_added.emit(name)
        self.categories_changed.emit(list(self.categories))

        self.logger.debug(f"Category added: {name}")

    def _remove_category(self, name: str):
        """Remove a category."""
        if name not in self.categories:
            return

        # Ask confirmation when category is not default
        if not self.allow_empty and len(self.categories) <= 1:
            self._show_error("At least one category is required")
            return

        # Remove from set
        self.categories.remove(name)

        # Remove from UI
        for i in range(self.categories_list.count()):
            item = self.categories_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == name:
                self.categories_list.takeItem(i)
                break

        # Update interface
        self._update_ui_state()

        # Emit signals
        self.category_removed.emit(name)
        self.categories_changed.emit(list(self.categories))

        self.logger.debug(f"Category removed: {name}")

    def _edit_category(self, item: QListWidgetItem):
        """Edit an existing category."""
        old_name = item.data(Qt.ItemDataRole.UserRole)

        # Edit dialog
        new_name, ok = QInputDialog.getText(
            self, "Edit Category", "Category name:", text=old_name
        )

        if ok and new_name.strip():
            new_name = new_name.strip()

            if new_name != old_name:
                if self._is_valid_category_name(new_name):
                    # Update
                    self.categories.remove(old_name)
                    self.categories.add(new_name)

                    item.setText(f"📁 {new_name}")
                    item.setData(Qt.ItemDataRole.UserRole, new_name)

                    # Sort
                    self.categories_list.sortItems()

                    # Signals
                    self.category_renamed.emit(old_name, new_name)
                    self.categories_changed.emit(list(self.categories))

                    self.logger.debug(f"Category renamed: {old_name} -> {new_name}")
                else:
                    self._show_error("Invalid category name")

    def _show_context_menu(self, position: QPoint):
        """Show context menu."""
        item = self.categories_list.itemAt(position)
        if not item:
            return

        category_name = item.data(Qt.ItemDataRole.UserRole)

        menu = QMenu(self)

        # Actions
        edit_action = QAction("✏️ Edit", self)
        edit_action.triggered.connect(lambda: self._edit_category(item))
        menu.addAction(edit_action)

        duplicate_action = QAction("📋 Duplicate", self)
        duplicate_action.triggered.connect(
            lambda: self._duplicate_category(category_name)
        )
        menu.addAction(duplicate_action)

        menu.addSeparator()

        remove_action = QAction("🗑️ Remove", self)
        remove_action.triggered.connect(lambda: self._remove_category(category_name))
        menu.addAction(remove_action)

        # Show menu
        menu.exec(self.categories_list.mapToGlobal(position))

    def _duplicate_category(self, name: str):
        """Duplicate a category."""
        # Find a unique name
        base_name = name
        counter = 1
        new_name = f"{base_name} Copy"

        while new_name in self.categories:
            counter += 1
            new_name = f"{base_name} Copy {counter}"

        self._add_category_internal(new_name)

    def _show_suggestions(self):
        """Show suggested categories."""
        # Suggestions based on unused predefined categories
        available_suggestions = self.predefined_categories - self.categories

        if not available_suggestions:
            self._show_error("No more suggestions available")
            return

        # Suggestions menu
        menu = QMenu("Category Suggestions", self)

        for suggestion in sorted(available_suggestions):
            action = QAction(f"📁 {suggestion}", self)
            action.triggered.connect(
                lambda checked, s=suggestion: self._add_category_internal(s)
            )
            menu.addAction(action)

        # Show menu
        button_rect = self.suggestions_button.geometry()
        menu.exec(self.suggestions_button.mapToGlobal(button_rect.bottomLeft()))

    def _clear_all(self, confirm: bool = True):
        """Remove all categories."""
        if confirm and not self.allow_empty:
            reply = QMessageBox.question(
                self,
                "Clear All Categories",
                "Are you sure you want to remove all categories?\nThis action cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

        # Save previous categories for signals
        old_categories = list(self.categories)

        # Clear data
        self.categories.clear()
        self.categories_list.clear()

        # Update interface
        self._update_ui_state()

        # Signals for each removed category
        for category in old_categories:
            self.category_removed.emit(category)

        self.categories_changed.emit([])

        self.logger.info("All categories cleared")

    def _reset_to_defaults(self):
        """Reset default categories."""
        self._clear_all()
        self.load_predefined_categories()

    def _update_ui_state(self):
        """Update UI state."""
        count = len(self.categories)
        palette = get_theme_service().get_current_palette()
        typography = get_theme_service().get_theme_definition().typography

        # Counter
        self.count_label.setText(f"{count} categor{'ies' if count != 1 else 'y'}")

        # Buttons
        self.clear_button.setEnabled(count > 0)

        # Counter color based on limits
        if count >= self.max_categories:
            self.count_label.setStyleSheet(
                f"color: {palette.warning}; font-weight: {typography.font_weight_bold};"
            )
        elif count == 0 and not self.allow_empty:
            self.count_label.setStyleSheet(
                f"color: {palette.error}; font-weight: {typography.font_weight_bold};"
            )
        else:
            self.count_label.setStyleSheet("")

    def _show_error(self, message: str):
        """Show an error message."""
        self.error_label.setText(f"❌ {message}")
        self.error_label.show()

        # Auto-hide after 3 seconds
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(3000, self.error_label.hide)

    def _show_input_error(self, message: str):
        """Show an input error."""
        self.new_category_input.setToolTip(message)
        # Style hook can be added here if needed

    def _hide_input_error(self):
        """Hide input error."""
        self.new_category_input.setToolTip("")

    def apply_default_theme(self, palette: ThemePalette):
        """Apply theme to editor."""
        try:
            theme = get_theme_service().get_theme_definition(palette.name)
            metrics = theme.metrics
            typography = theme.typography
            style = f"""
                QFrame#categoryHeader {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {palette.surface},
                        stop:1 {palette.surface_variant}
                    );
                    border: 1px solid {palette.outline};
                    border-radius: {metrics.radius_md - 2}px;
                    margin: {max(1, metrics.spacing_xs - 2)}px;
                }}

                QFrame#addContainer {{
                    background-color: {palette.surface_variant};
                    border: 1px solid {palette.outline};
                    border-radius: {metrics.radius_md - 2}px;
                }}

                QLineEdit#newCategoryInput {{
                    background-color: {palette.surface};
                    border: {metrics.focus_width}px solid {palette.outline};
                    border-radius: {metrics.radius_sm}px;
                    padding: {metrics.spacing_sm}px;
                    font-family: "{typography.font_family}";
                    font-size: {typography.font_size_md + 1}px;
                    color: {palette.on_surface};
                }}

                QLineEdit#newCategoryInput:focus {{
                    border-color: {palette.primary};
                }}

                QPushButton#addButton {{
                    background-color: {palette.primary};
                    color: white;
                    border: none;
                    border-radius: {metrics.radius_sm}px;
                    padding: {metrics.spacing_sm}px {metrics.spacing_lg}px;
                    min-height: {metrics.control_height}px;
                    font-family: "{typography.font_family}";
                    font-weight: {typography.font_weight_bold};
                }}

                QPushButton#addButton:hover:enabled {{
                    background-color: {palette.primary_light};
                }}

                QPushButton#addButton:disabled {{
                    background-color: {palette.disabled};
                    color: {palette.disabled_text};
                }}

                QPushButton#suggestionsButton, QPushButton#clearButton, QPushButton#resetButton {{
                    background-color: {palette.secondary};
                    color: {palette.on_secondary};
                    border: 1px solid {palette.secondary_dark};
                    border-radius: {metrics.radius_sm}px;
                    padding: {metrics.spacing_sm}px {metrics.spacing_md}px;
                    min-height: {metrics.control_height}px;
                    font-family: "{typography.font_family}";
                    font-weight: {typography.font_weight_bold};
                }}

                QPushButton#suggestionsButton:hover, QPushButton#clearButton:hover:enabled, QPushButton#resetButton:hover {{
                    background-color: {palette.secondary_light};
                }}

                QListWidget#categoriesList {{
                    background-color: {palette.surface};
                    border: {metrics.focus_width}px solid {palette.outline};
                    border-radius: {metrics.radius_md - 2}px;
                    padding: {max(2, metrics.spacing_xs)}px;
                    alternate-background-color: {palette.surface_variant};
                    font-family: "{typography.font_family}";
                    font-size: {typography.font_size_md}px;
                }}

                QListWidget#categoriesList::item {{
                    padding: {metrics.spacing_sm}px;
                    border-radius: {metrics.radius_sm - 2}px;
                    margin: 1px;
                }}

                QListWidget#categoriesList::item:selected {{
                    background-color: {palette.primary};
                    color: white;
                }}

                QListWidget#categoriesList::item:hover {{
                    background-color: {palette.hover};
                }}

                QFrame#actionsContainer {{
                    background-color: {palette.surface_variant};
                    border-top: 1px solid {palette.outline};
                    border-radius: 0 0 {metrics.radius_md - 2}px {metrics.radius_md - 2}px;
                }}

                QLabel#countLabel {{
                    color: {palette.on_surface_variant};
                    font-family: "{typography.font_family}";
                    font-weight: {typography.font_weight_bold};
                }}

                QLabel#errorLabel {{
                    color: {palette.error};
                    background-color: {palette.error_container};
                    border-radius: {metrics.radius_sm - 2}px;
                    padding: {metrics.spacing_sm}px;
                    font-family: "{typography.font_family}";
                    font-weight: {typography.font_weight_bold};
                }}
            """
            self.setStyleSheet(style)

        except Exception as e:
            self.logger.error(f"Error applying category editor theme: {e}")

    # === PUBLIC API ===

    def set_categories(self, categories: List[str]):
        """Set the category list."""
        self.clear_all_categories(confirm=False)
        for category in categories:
            if self._is_valid_category_name(category):
                self._add_category_internal(category)

    def get_categories(self) -> List[str]:
        """Return the category list."""
        return sorted(list(self.categories))

    def add_category(self, name: str) -> bool:
        """Add a category programmatically."""
        if self._is_valid_category_name(name):
            self._add_category_internal(name)
            return True
        return False

    def remove_category(self, name: str) -> bool:
        """Remove a category programmatically."""
        if name in self.categories:
            self._remove_category(name)
            return True
        return False

    def has_category(self, name: str) -> bool:
        """Check whether a category exists."""
        return name in self.categories

    def clear_all_categories(self, confirm: bool = True):
        """Remove all categories."""
        self._clear_all(confirm=confirm)

    def set_predefined_categories(self, categories: Set[str]):
        """Set predefined categories."""
        self.predefined_categories = categories

    def set_max_categories(self, max_count: int):
        """Set the maximum number of categories."""
        self.max_categories = max_count
        self._update_ui_state()

    def set_allow_empty(self, allow: bool):
        """Set whether list can be empty."""
        self.allow_empty = allow
        self._update_ui_state()

    def set_custom_validator(self, validator: Callable[[str], tuple[bool, str]]):
        """Set a custom validator."""
        self.custom_validator = validator

    def get_category_count(self) -> int:
        """Return the category count."""
        return len(self.categories)

    def is_empty(self) -> bool:
        """Check whether list is empty."""
        return len(self.categories) == 0
