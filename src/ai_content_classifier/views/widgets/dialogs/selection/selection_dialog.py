# views/widgets/selection_dialog.py
"""
Enhanced Selection Dialog for multi-filter system - With Theme Support.

This dialog supports both single and multiple selection modes and is optimized
for the new filtering system that handles categories, years, extensions, etc.
"""

from typing import List, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from ai_content_classifier.views.widgets.base.action_bar import ActionBar
from ai_content_classifier.views.widgets.base.header_section import HeaderSection
from ai_content_classifier.views.widgets.base.themed_dialog import ThemedDialog


class SelectionDialog(ThemedDialog):
    """
    Enhanced selection dialog with improved UX for multi-filter operations and theme support.
    Inherits from ThemedDialog for consistent styling and common functionalities.
    """

    # Signal emitted when selection changes (for real-time preview if needed)
    selection_changed = pyqtSignal(list)

    def __init__(
        self,
        title: str,
        items: List[str],
        parent=None,
        allow_multiple: bool = True,
        description: Optional[str] = None,
        show_count: bool = True,
    ):

        self.allow_multiple = allow_multiple
        self.show_count = show_count
        self.original_items = sorted(items)  # Keep original sorted list
        self.selected_items: List[str] = []
        self.description = description  # Store description as an instance variable

        super().__init__(
            parent=parent, title=title, description=description, modal=True
        )

        # Set minimum and initial size
        self.setMinimumSize(350, 500)
        self.resize(450, 700)

        # Timer for search debouncing
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_filter)

        self.logger.debug(
            f"Selection dialog created: {title}, {len(items)} items, multiple={allow_multiple}"
        )

        # Populate list after UI is set up by ThemedDialog
        self.populate_list(self.original_items)

        # Connect signals after UI is fully built
        self.setup_connections()

    def create_header(self) -> HeaderSection:
        """Create header with title and optional description."""
        instruction_text = (
            "💡 Hold Ctrl/Cmd to select multiple items, or use the buttons below."
            if self.allow_multiple
            else "💡 Select an item from the list."
        )

        return HeaderSection(
            title=self.windowTitle(),
            description=(
                self.description + "\n\n" + instruction_text
                if self.description
                else instruction_text
            ),
            parent=self,
        )

    def create_content(self) -> QWidget:
        """Create the main content widget."""
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 0, 16, 0)  # Adjusted margins
        content_layout.setSpacing(10)

        # Search section
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to filter items...")
        self.search_input.textChanged.connect(self.on_search_text_changed)
        self.search_input.setObjectName("searchInput")
        self.search_input.setClearButtonEnabled(True)

        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("🔍 Rechercher :"))
        search_layout.addWidget(self.search_input)

        content_layout.addLayout(search_layout)

        # Selection controls (for multi-selection)
        if self.allow_multiple:
            self.select_all_btn = QPushButton("✅ Tout selectionner")
            self.select_all_btn.clicked.connect(self.select_all_visible)
            self.select_all_btn.setObjectName("selectAllButton")

            self.clear_all_btn = QPushButton("❌ Tout effacer")
            self.clear_all_btn.clicked.connect(self.clear_all_selections)
            self.clear_all_btn.setObjectName("clearAllButton")

            self.invert_btn = QPushButton("🔄 Inverser")
            self.invert_btn.clicked.connect(self.invert_selection)
            self.invert_btn.setObjectName("invertButton")

            controls_layout = QHBoxLayout()
            controls_layout.addWidget(self.select_all_btn)
            controls_layout.addWidget(self.clear_all_btn)
            controls_layout.addWidget(self.invert_btn)
            controls_layout.addStretch()
            content_layout.addLayout(controls_layout)

        # Main list widget
        self.list_widget = QListWidget()
        if self.allow_multiple:
            self.list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        else:
            self.list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list_widget.setObjectName("listWidget")
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setUniformItemSizes(True)
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list_widget.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        content_layout.addWidget(self.list_widget)

        # Status section
        if self.show_count:
            self.status_label = QLabel()
            self.status_label.setObjectName("statusLabel")
            content_layout.addWidget(self.status_label)
            self.update_status()  # Initial status update

        return content_widget

    def create_footer(self) -> ActionBar:
        """Create dialog button box with enhanced styling."""
        action_bar = ActionBar(self, alignment="right")

        self.ok_button = QPushButton("✅ OK")
        self.ok_button.setObjectName("okButton")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setDefault(True)

        self.cancel_button = QPushButton("❌ Cancelr")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.clicked.connect(self.reject)

        action_bar.add_action("❌ Cancelr", self.reject, "cancelButton")
        action_bar.add_action("✅ OK", self.accept, "okButton", primary=True)

        # Initially disable OK if no selection in single-selection mode
        if not self.allow_multiple:
            action_bar.get_action_button("okButton").setEnabled(False)

        return action_bar

    def setup_connections(self):
        """Setup signal connections with enhanced handling."""
        try:
            if self.allow_multiple:
                self.list_widget.itemSelectionChanged.connect(self.on_selection_changed)
            else:
                self.list_widget.itemSelectionChanged.connect(
                    self.on_single_selection_changed
                )

            # Double-click to accept in single mode
            if not self.allow_multiple:
                self.list_widget.itemDoubleClicked.connect(self.accept)

        except Exception as e:
            self.logger.error(f"Error setting up connections: {e}")

    def populate_list(self, items: List[str]):
        """Populate the list with items and enhanced styling."""
        try:
            self.list_widget.clear()

            for item_text in items:
                item = QListWidgetItem(item_text)
                item.setToolTip(f"Item: {item_text}")
                self.list_widget.addItem(item)

            self.update_status()
            self.logger.debug(f"Populated list with {len(items)} items")

        except Exception as e:
            self.logger.error(f"Error populating list: {e}")

    def on_search_text_changed(self, text: str):
        """Handle search text changes with debouncing."""
        # Show/hide clear button
        # self.clear_search_btn.setVisible(len(text) > 0)

        # Start/restart timer for debounced search
        self.search_timer.stop()
        self.search_timer.start(300)  # 300ms delay

        # Store current search text
        self.current_search_text = text

    def perform_filter(self):
        """Perform the actual filtering operation."""
        try:
            text = getattr(self, "current_search_text", "")
            self.filter_list(text)
        except Exception as e:
            self.logger.error(f"Error performing filter: {e}")

    def filter_list(self, text: str):
        """Filter list items based on search text with enhanced feedback."""
        try:
            visible_count = 0
            search_text = text.lower().strip()

            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                is_visible = search_text in item.text().lower() if search_text else True
                item.setHidden(not is_visible)
                if is_visible:
                    visible_count += 1

            # Update button states based on visible items
            if self.allow_multiple:
                self.select_all_btn.setEnabled(visible_count > 0)
                self.invert_btn.setEnabled(visible_count > 0)

            # Show search info
            if search_text:
                if visible_count == 0:
                    # self.search_info_label.setText("❌ No item found")
                    # self.search_info_label.setStyleSheet("color: red;")
                    pass  # Handled by status label
                else:
                    # self.search_info_label.setText(f"✅ {visible_count} item(s) found")
                    # self.search_info_label.setStyleSheet("color: green;")
                    pass  # Handled by status label
                # self.search_info_label.show()
            else:
                # self.search_info_label.hide()
                pass

            self.update_status()

        except Exception as e:
            self.logger.error(f"Error filtering list: {e}")

    def clear_search(self):
        """Clear the search input and show all items."""
        try:
            self.search_input.clear()
            # self.search_info_label.hide()
            # self.clear_search_btn.hide()
        except Exception as e:
            self.logger.error(f"Error clearing search: {e}")

    def select_all_visible(self):
        """Select all visible (non-hidden) items."""
        try:
            selected_count = 0
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                if not item.isHidden():
                    item.setSelected(True)
                    selected_count += 1

            self.on_selection_changed()
            self.logger.debug(f"Selected all {selected_count} visible items")

        except Exception as e:
            self.logger.error(f"Error selecting all visible: {e}")

    def clear_all_selections(self):
        """Clear all selections."""
        try:
            self.list_widget.clearSelection()
            self.on_selection_changed()
            self.logger.debug("Cleared all selections")
        except Exception as e:
            self.logger.error(f"Error clearing selections: {e}")

    def invert_selection(self):
        """Invert the current selection for visible items."""
        try:
            inverted_count = 0
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                if not item.isHidden():
                    was_selected = item.isSelected()
                    item.setSelected(not was_selected)
                    if not was_selected:
                        inverted_count += 1

            self.on_selection_changed()
            self.logger.debug(
                f"Inverted selection: {inverted_count} items now selected"
            )

        except Exception as e:
            self.logger.error(f"Error inverting selection: {e}")

    def on_selection_changed(self):
        """Handle selection changes in multi-selection mode."""
        try:
            selected_items = [item.text() for item in self.list_widget.selectedItems()]

            # Update status
            self.update_status()

            # Update selection summary
            if self.allow_multiple and hasattr(self, "selection_summary"):
                if len(selected_items) > 0:
                    if len(selected_items) <= 3:
                        summary = f"Selected: {', '.join(selected_items)}"
                    else:
                        summary = f"Selected: {selected_items[0]}, {selected_items[1]}, ... (+{len(selected_items) - 2} others)"
                    self.selection_summary.setText(summary)
                else:
                    self.selection_summary.setText("Noe selection")

            # Emit signal for real-time updates if needed
            self.selection_changed.emit(selected_items)

            # Update button states
            if self.allow_multiple:
                selected_count = len(selected_items)
                self.clear_all_btn.setEnabled(selected_count > 0)

        except Exception as e:
            self.logger.error(f"Error handling selection change: {e}")

    def on_single_selection_changed(self):
        """Handle selection changes in single-selection mode."""
        try:
            selected_items = self.list_widget.selectedItems()
            has_selection = len(selected_items) > 0

            # Enable/disable OK button
            self.ok_button.setEnabled(has_selection)

            self.update_status()

            if has_selection:
                self.selection_changed.emit([selected_items[0].text()])
            else:
                self.selection_changed.emit([])

        except Exception as e:
            self.logger.error(f"Error handling single selection change: {e}")

    def update_status(self):
        """Update the status label with enhanced information."""
        try:
            if not self.show_count:
                return

            total_items = self.list_widget.count()
            visible_items = sum(
                1 for i in range(total_items) if not self.list_widget.item(i).isHidden()
            )
            selected_items = len(self.list_widget.selectedItems())

            # Build status text with icons
            status_parts = []

            # Visibility info
            if total_items == visible_items:
                status_parts.append(f"📊 {visible_items} items")
            else:
                status_parts.append(f"📊 {visible_items}/{total_items} items")

            # Selection info
            if self.allow_multiple:
                if selected_items > 0:
                    status_parts.append(f"✅ {selected_items} selected")
                else:
                    status_parts.append("⭕ Noe selection")
            else:
                if selected_items > 0:
                    status_parts.append("✅ 1 selected")
                else:
                    status_parts.append("⭕ Noe selection")

            status_text = " • ".join(status_parts)
            self.status_label.setText(status_text)

        except Exception as e:
            self.logger.error(f"Error updating status: {e}")

    def accept(self):
        """Handle dialog acceptance with validation."""
        try:
            self.selected_items = [
                item.text() for item in self.list_widget.selectedItems()
            ]

            self.logger.info(
                f"Dialog accepted with {len(self.selected_items)} selected items"
            )
            super().accept()

        except Exception as e:
            self.logger.error(f"Error accepting dialog: {e}")
            super().accept()

    def reject(self):
        """Handle dialog rejection."""
        try:
            self.selected_items = []
            self.logger.info("Dialog rejected")
            super().reject()

        except Exception as e:
            self.logger.error(f"Error rejecting dialog: {e}")
            super().reject()

    def get_selected_items(self) -> List[str]:
        """
        Get the list of selected items.

        Returns:
            List of selected item texts
        """
        return self.selected_items.copy()

    def set_selected_items(self, items: List[str]):
        """
        Pre-select specific items in the list.

        Args:
            items: List of item texts to select
        """
        try:
            self.list_widget.clearSelection()

            selected_count = 0
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                if item.text() in items:
                    item.setSelected(True)
                    selected_count += 1

            if self.allow_multiple:
                self.on_selection_changed()
            else:
                self.on_single_selection_changed()

            self.logger.debug(f"Pre-selected {selected_count} items")

        except Exception as e:
            self.logger.error(f"Error setting selected items: {e}")

    def get_selection_count(self) -> int:
        """
        Get the number of selected items.

        Returns:
            Number of selected items
        """
        return len(self.list_widget.selectedItems())

    def is_empty_selection(self) -> bool:
        """
        Check if no items are selected.

        Returns:
            True if no items are selected
        """
        return self.get_selection_count() == 0


# Convenience factory functions for common filter dialogs


def create_category_selection_dialog(
    categories: List[str], parent=None, selected_categories: Optional[List[str]] = None
) -> SelectionDialog:
    """
    Create a selection dialog specifically for categories.

    Args:
        categories: List of available categories
        parent: Parent widget
        selected_categories: Pre-selected categories

    Returns:
        Configured SelectionDialog
    """
    dialog = SelectionDialog(
        title="🏷️ Selectionner les Categories",
        items=categories,
        parent=parent,
        allow_multiple=True,
        description="Choisissez une ou plusieurs categories pour filtrer les files. Laissez vide pour afficher toutes les categories.",
        show_count=True,
    )

    if selected_categories:
        dialog.set_selected_items(selected_categories)

    return dialog


def create_year_selection_dialog(
    years: List[str], parent=None, selected_years: Optional[List[str]] = None
) -> SelectionDialog:
    """
    Create a selection dialog specifically for years.

    Args:
        years: List of available years (as strings)
        parent: Parent widget
        selected_years: Pre-selected years

    Returns:
        Configured SelectionDialog
    """
    dialog = SelectionDialog(
        title="📅 Select Years",
        items=years,
        parent=parent,
        allow_multiple=True,
        description="Choose one or more years to filter files by creation date. Leave empty to show all years.",
        show_count=True,
    )

    if selected_years:
        dialog.set_selected_items(selected_years)

    return dialog


def create_extension_selection_dialog(
    extensions: List[str], parent=None, selected_extensions: Optional[List[str]] = None
) -> SelectionDialog:
    """
    Create a selection dialog specifically for file extensions.

    Args:
        extensions: List of available extensions
        parent: Parent widget
        selected_extensions: Pre-selected extensions

    Returns:
        Configured SelectionDialog
    """
    dialog = SelectionDialog(
        title="📎 Selectionner les Extensions de Fichier",
        items=extensions,
        parent=parent,
        allow_multiple=True,
        description="Choisissez une ou plusieurs extensions de file pour filtrer. Laissez vide pour afficher toutes les extensions.",
        show_count=True,
    )

    if selected_extensions:
        dialog.set_selected_items(selected_extensions)

    return dialog
