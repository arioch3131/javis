# views/widgets/common/filter_chips.py
"""
FilterChips - Puces de filtres reusables.

Widget to display and manage chip-based filters
with multi-selection support and an intuitive interface.
"""

from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from ai_content_classifier.services.theme.theme_service import (
    ThemePalette,
    get_theme_service,
)
from ai_content_classifier.views.widgets.base.themed_widget import ThemedWidget


class FilterChip(QWidget):  # Changed from QPushButton to QWidget
    """
    Puce de filtre individuelle.

    Represents a single filter with selectable state
    et d'actions contextuelles.
    """

    # Signaux
    chip_clicked = pyqtSignal(str, bool)  # (filter_id, is_selected)
    chip_removed = pyqtSignal(str)  # filter_id
    chip_edited = pyqtSignal(str, str)  # (filter_id, new_value)

    def __init__(
        self,
        filter_id: str,
        label: str,
        is_selected: bool = False,
        is_removable: bool = True,
        chip_type: str = "default",
        parent=None,
    ):
        super().__init__(parent)

        self.filter_id = filter_id
        self.label = label
        self.is_selected = is_selected
        self.is_removable = is_removable
        self.chip_type = chip_type  # default, category, date, size, etc.
        self.setProperty("chip_type", chip_type)

        # Main layout for the chip
        self.chip_layout = QHBoxLayout(self)
        self.chip_layout.setContentsMargins(
            4, 1, 1, 1
        )  # Adjust margins to be more compact
        self.chip_layout.setSpacing(2)  # Reduce spacing

        # Label button (for selection)
        self.label_button = QPushButton(self._format_label())
        self.label_button.setCheckable(True)
        self.label_button.setChecked(is_selected)
        self.label_button.setObjectName(
            f"filterChipLabel_{chip_type}"
        )  # Object name for styling
        self.label_button.clicked.connect(self._on_clicked)
        self.label_button.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.label_button.setMinimumHeight(24)  # Smaller height for label button

        self.chip_layout.addWidget(self.label_button)

        # Close button (for removal)
        if is_removable:
            self.close_button = QToolButton()
            self.close_button.setText("✕")  # Cross symbol
            self.close_button.setObjectName(
                f"filterChipClose_{chip_type}"
            )  # Object name for styling
            self.close_button.setFixedSize(18, 18)  # Smaller fixed size
            self.close_button.clicked.connect(
                lambda: self.chip_removed.emit(self.filter_id)
            )
            self.chip_layout.addWidget(self.close_button)
        else:
            self.close_button = None

        # Overall chip styling (for the QWidget itself)
        self.setObjectName(
            f"filterChip_{chip_type}"
        )  # Object name for styling the whole chip
        self.setMinimumHeight(26)  # Slightly smaller overall height
        self.setMaximumHeight(28)  # Slightly smaller overall height
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )  # Preferred width, fixed height

        # No context menu for removal, as we have a direct button
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

    def _format_label(self) -> str:
        """Formate le label de la puce."""
        # Icons by type
        icons = {
            "category": "📁",
            "extension": "📄",
            "date": "📅",
            "size": "📏",
            "status": "🏷️",
            "default": "🔹",
        }

        icon = icons.get(self.chip_type, "🔹")
        return f"{icon} {self.label}"

    def _on_clicked(self, checked: bool):
        """Called when a chip is clicked (via label_button)."""
        self.is_selected = checked
        self.chip_clicked.emit(self.filter_id, checked)

    def set_selected(self, selected: bool):
        """Set l'state de selection."""
        self.is_selected = selected
        self.label_button.setChecked(selected)

    def set_label(self, label: str):
        """Update le label."""
        self.label = label
        self.label_button.setText(self._format_label())

    def get_filter_data(self) -> Dict[str, Any]:
        """Return filter data."""
        return {
            "id": self.filter_id,
            "label": self.label,
            "type": self.chip_type,
            "selected": self.is_selected,
            "removable": self.is_removable,
        }


class FilterChipsContainer(ThemedWidget):
    """
    Conteneur pour les puces de filtres.

    Manages a collection of chips with advanced features:
    - Selection multiple
    - Groupement par type
    - Filtrage et recherche
    - Actions en lot
    """

    # Signaux
    filters_changed = pyqtSignal(dict)  # {filter_id: is_selected}
    filter_added = pyqtSignal(str, str)  # (filter_id, label)
    filter_removed = pyqtSignal(str)  # filter_id
    selection_cleared = pyqtSignal()  # All selections cleared

    def __init__(
        self,
        parent=None,
        title: str = "Active Filters",
        allow_multiple: bool = True,
        group_by_type: bool = False,
    ):
        super().__init__(parent, "filterChipsContainer")

        # Configuration
        self.title = title
        self.allow_multiple = allow_multiple
        self.group_by_type = group_by_type

        # State
        self.chips: Dict[str, FilterChip] = {}
        self.filter_groups: Dict[str, List[str]] = {}  # type -> [filter_ids]
        self.selection_state: Dict[str, bool] = {}
        self._suppress_signal_emits: bool = False

        # Validation
        self.max_selections = 0  # 0 = unlimited
        self.custom_validator: Optional[Callable[[List[str]], bool]] = None

        self.setup_ui()

    def setup_ui(self):
        """Configure l'interface du conteneur."""
        layout = self.get_main_layout()
        layout.setSpacing(8)

        # Header with title and controls
        self.header_container = self.create_header()
        layout.addWidget(self.header_container)

        # Zone de filtres avec scroll
        self.filters_scroll = QScrollArea()
        self.filters_scroll.setObjectName("filtersScroll")
        self.filters_scroll.setWidgetResizable(True)
        self.filters_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.filters_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.filters_scroll.setMaximumHeight(
            400
        )  # Increased height to reduce forced scrolling

        # Widget interne pour les filtres
        self.filters_widget = QWidget()
        self.filters_widget.setObjectName("filtersWidget")

        # Always use QVBoxLayout for the main filters layout
        self.filters_layout = QVBoxLayout(self.filters_widget)
        self.filters_layout.setContentsMargins(0, 0, 0, 0)  # Ensure no extra margins
        self.filters_layout.setSpacing(4)  # Consistent spacing

        self.filters_scroll.setWidget(self.filters_widget)
        layout.addWidget(self.filters_scroll, 1)

        # Actions rapides
        self.actions_container = self.create_actions()
        layout.addWidget(self.actions_container)

        # Message d'state
        self.status_label = QLabel("No active filters")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(self.create_italic_font())
        layout.addWidget(self.status_label)

    def create_header(self) -> QFrame:
        """Create l'header du conteneur."""
        header = QFrame()
        header.setObjectName("filtersHeader")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Titre
        self.title_label = QLabel(self.title)
        self.title_label.setFont(self.create_bold_font(1))
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Compteur de selections
        self.count_label = QLabel("0 selected")
        self.count_label.setObjectName("countLabel")
        self.count_label.setFont(self.create_bold_font())
        layout.addWidget(self.count_label)

        return header

    def create_actions(self) -> QFrame:
        """Create la barre d'actions."""
        actions = QFrame()
        actions.setObjectName("filtersActions")

        layout = QHBoxLayout(actions)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Bouton tout selectionner
        self.select_all_button = QPushButton("Select All")
        self.select_all_button.setObjectName("selectAllButton")
        self.select_all_button.clicked.connect(self.select_all_filters)
        layout.addWidget(self.select_all_button)

        # Clear-all button
        self.clear_all_button = QPushButton("Clear All")
        self.clear_all_button.setObjectName("clearAllButton")
        self.clear_all_button.clicked.connect(self.clear_all_filters)
        layout.addWidget(self.clear_all_button)

        layout.addStretch()

        # Bouton d'options
        self.options_button = QPushButton("⚙️")
        self.options_button.setObjectName("optionsButton")
        self.options_button.setFixedSize(32, 32)
        self.options_button.clicked.connect(self._show_options_menu)
        layout.addWidget(self.options_button)

        return actions

    def _show_options_menu(self):
        """Affiche le menu d'options."""
        menu = QMenu(self)

        # Option groupement
        group_action = QAction("📂 Group by type", self)
        group_action.setCheckable(True)
        group_action.setChecked(self.group_by_type)
        group_action.triggered.connect(self._toggle_grouping)
        menu.addAction(group_action)

        # Option selection multiple
        multi_action = QAction("☑️ Multiple selection", self)
        multi_action.setCheckable(True)
        multi_action.setChecked(self.allow_multiple)
        multi_action.triggered.connect(self._toggle_multiple_selection)
        menu.addAction(multi_action)

        menu.addSeparator()

        # Actions de nettoyage
        remove_unselected_action = QAction("🗑️ Remove unselected", self)
        remove_unselected_action.triggered.connect(self._remove_unselected_filters)
        menu.addAction(remove_unselected_action)

        menu.exec(
            self.options_button.mapToGlobal(self.options_button.rect().bottomLeft())
        )

    def add_filter(
        self,
        filter_id: str,
        label: str,
        filter_type: str = "default",
        is_selected: bool = False,
        is_removable: bool = True,
    ) -> FilterChip:
        """
        Ajoute un nouveau filtre.

        Args:
            filter_id: Identifiant unique du filtre
            label: Label to display
            filter_type: Type de filtre (category, date, etc.)
            is_selected: State initial de selection
            is_removable: Whether the filter can be removed

        Returns:
            The created chip
        """
        if filter_id in self.chips:
            # Update existing filter
            chip = self.chips[filter_id]
            chip.set_label(label)
            chip.set_selected(is_selected)
            return chip

        # Creater la nouvelle puce
        chip = FilterChip(
            filter_id=filter_id,
            label=label,
            is_selected=is_selected,
            is_removable=is_removable,
            chip_type=filter_type,
            parent=self.filters_widget,
        )

        # Connexions
        chip.chip_clicked.connect(self._on_chip_clicked)
        chip.chip_removed.connect(self._on_chip_removed)

        # Enregistrer
        self.chips[filter_id] = chip
        self.selection_state[filter_id] = is_selected

        # Ajouter au groupe
        if filter_type not in self.filter_groups:
            self.filter_groups[filter_type] = []
        self.filter_groups[filter_type].append(filter_id)

        # Add to interface
        self._add_chip_to_layout(chip, filter_type)

        # Update state
        self._update_interface_state()

        # Signaux
        self.filter_added.emit(filter_id, label)
        self._emit_filters_changed()

        self.logger.debug(f"Filter added: {filter_id} ({filter_type})")
        return chip

    def _add_chip_to_layout(self, chip: FilterChip, filter_type: str):
        """Ajoute une puce au layout selon la configuration."""
        # Trouver ou creater le groupe
        group_layout = self._get_or_create_group_layout(filter_type)
        group_layout.addWidget(chip)

    def _get_or_create_group_layout(self, filter_type: str) -> QLayout:
        """Get or create layout for a filter group."""
        group_id = f"group_{filter_type}"

        # Chercher le groupe existant
        for i in range(self.filters_layout.count()):
            item = self.filters_layout.itemAt(i)
            if item and item.widget() and item.widget().objectName() == group_id:
                # Trouver le layout des puces dans ce groupe
                group_widget = item.widget()
                return group_widget.layout().itemAt(1).layout()  # Layout des puces

        # Creater un nouveau groupe
        group_widget = QFrame()
        group_widget.setObjectName(group_id)
        group_widget.setProperty("isFilterGroup", True)

        group_layout = QVBoxLayout(group_widget)
        group_layout.setContentsMargins(8, 8, 8, 8)
        group_layout.setSpacing(6)

        # Titre du groupe
        type_labels = {
            "file_type": "Type",
            "category": "Category",
            "extension": "Extension",
            "date": "Date",
            "size": "Size",
            "status": "Status",
            "default": "Filters",
        }
        group_title = QLabel(type_labels.get(filter_type, filter_type.title()))
        group_title.setObjectName("filterGroupTitle")
        group_title.setFont(self.create_bold_font())
        group_layout.addWidget(group_title)

        # Layout pour les puces
        chips_layout = QVBoxLayout()
        chips_layout.setSpacing(4)
        chips_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.addLayout(chips_layout)

        # Ajouter le groupe au layout principal
        self.filters_layout.addWidget(group_widget)

        return chips_layout

    def remove_filter(self, filter_id: str):
        """
        Supprime un filtre actif.
        """
        if filter_id in self.chips:
            chip = self.chips.pop(filter_id)
            if filter_id in self.selection_state:
                del self.selection_state[filter_id]

            # Remove from layout
            chip.setParent(None)  # Remove from layout
            chip.deleteLater()

            # Remove from filter_groups
            for group_type, filter_ids in list(self.filter_groups.items()):
                if filter_id in filter_ids:
                    filter_ids.remove(filter_id)
                    if not filter_ids:  # If group becomes empty, remove it
                        del self.filter_groups[group_type]
                    break

            self._update_interface_state()
            self.filter_removed.emit(filter_id)
            self._emit_filters_changed()

    def _on_chip_clicked(self, filter_id: str, is_selected: bool):
        """Called when a chip is clicked."""
        # Gestion de la selection exclusive
        if not self.allow_multiple and is_selected:
            # Deselect all others
            for other_id, other_chip in self.chips.items():
                if other_id != filter_id and other_chip.is_selected:
                    other_chip.set_selected(False)
                    self.selection_state[other_id] = False

        # Validation du nombre maximum
        if (
            self.max_selections > 0
            and is_selected
            and sum(self.selection_state.values()) >= self.max_selections
        ):
            # Prevent selection
            chip = self.chips[filter_id]
            chip.set_selected(False)
            return

        # Update state
        self.selection_state[filter_id] = is_selected

        # Custom validation
        if self.custom_validator:
            selected_filters = [
                fid for fid, selected in self.selection_state.items() if selected
            ]
            if not self.custom_validator(selected_filters):
                # Cancelr la selection
                chip = self.chips[filter_id]
                chip.set_selected(not is_selected)
                self.selection_state[filter_id] = not is_selected
                return

        # Update interface
        self._update_interface_state()

        # Émettre le signal
        self._emit_filters_changed()

    def _on_chip_removed(self, filter_id: str):
        """Called quand une puce demande sa suppression."""
        self.remove_filter(filter_id)

    def select_all_filters(self):
        """Selectionne tous les filtres."""
        if not self.allow_multiple:
            return

        for filter_id, chip in self.chips.items():
            chip.set_selected(True)
            self.selection_state[filter_id] = True

        self._update_interface_state()
        self._emit_filters_changed()

    def clear_all_filters(self):
        """Deselect all filters."""
        for filter_id, chip in self.chips.items():
            chip.set_selected(False)
            self.selection_state[filter_id] = False

        self._update_interface_state()
        self.selection_cleared.emit()
        self._emit_filters_changed()

    def _remove_unselected_filters(self):
        """Remove all unselected filters."""
        to_remove = [
            fid for fid, selected in self.selection_state.items() if not selected
        ]
        for filter_id in to_remove:
            self.remove_filter(filter_id)

    def _toggle_grouping(self, enabled: bool):
        """Enable/disable grouping by type."""
        self.group_by_type = enabled
        self._rebuild_layout()

    def _toggle_multiple_selection(self, enabled: bool):
        """Enable/disable multi-selection."""
        self.allow_multiple = enabled
        if not enabled:
            # Keep only the first selected
            selected_filters = [
                fid for fid, selected in self.selection_state.items() if selected
            ]
            if len(selected_filters) > 1:
                for filter_id in selected_filters[1:]:
                    self.chips[filter_id].set_selected(False)
                    self.selection_state[filter_id] = False

        self._update_interface_state()
        self._emit_filters_changed()

    def _rebuild_layout(self):
        """Reconstruit le layout selon la configuration."""
        # IMPORTANT:
        # Clearing group widgets can destroy child chips at C++ level.
        # Rebuild from immutable data instead of reusing widget instances.
        saved_filters = [chip.get_filter_data() for chip in self.chips.values()]

        self.blockSignals(True)
        try:
            self.clear_all_filters_completely()
            self._clear_layout()

            for filter_data in saved_filters:
                self.add_filter(
                    filter_id=filter_data["id"],
                    label=filter_data["label"],
                    filter_type=filter_data.get("type", "default"),
                    is_selected=filter_data.get("selected", False),
                    is_removable=filter_data.get("removable", True),
                )
        finally:
            self.blockSignals(False)

        self._update_interface_state()
        # Rebuild is a visual/layout operation; do not emit selection changes here
        # to avoid feedback loops with presenters/managers.

    def _clear_layout(self):
        """Vide le layout des filtres."""
        while self.filters_layout.count():
            item = self.filters_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
            elif item.layout():
                self._clear_sub_layout(item.layout())

    def _clear_sub_layout(self, layout):
        """Clear a sub-layout recursively."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
            elif item.layout():
                self._clear_sub_layout(item.layout())

    def _update_interface_state(self):
        """Update l'state de l'interface."""
        selected_count = sum(self.selection_state.values())
        total_count = len(self.chips)

        # Compteur
        self.count_label.setText(f"{selected_count} of {total_count} selected")

        # Boutons
        self.select_all_button.setEnabled(
            total_count > 0 and selected_count < total_count and self.allow_multiple
        )
        self.clear_all_button.setEnabled(selected_count > 0)

        # Message d'state
        if total_count == 0:
            self.status_label.setText("No filters available")
            self.status_label.show()
            self.filters_scroll.hide()
        else:
            self.status_label.hide()
            self.filters_scroll.show()

    def _emit_filters_changed(self):
        """Émet le signal de changement des filtres."""
        if self._suppress_signal_emits:
            return
        self.filters_changed.emit(self.selection_state.copy())

    def apply_default_theme(self, palette: ThemePalette):
        """Apply theme to container."""
        try:
            style = get_theme_service().get_filter_chips_stylesheet(palette)
            self.setStyleSheet(style)

        except Exception as e:
            self.logger.error(f"Error applying filter chips theme: {e}")

    # === API PUBLIQUE ===

    def set_filters(self, filters: List[Dict[str, Any]]):
        """
        Set full filter list.

        Args:
            filters: Liste de dictionnaires avec keys: id, label, type, selected, removable
        """
        self.logger.debug(
            f"📥 FilterChipsContainer.set_filters RECEIVED: {len(filters)} filters"
        )
        # Temporarily block signals to prevent recursive calls.
        self._suppress_signal_emits = True
        self.blockSignals(True)

        try:
            # Vider les filtres existants
            self.clear_all_filters_completely()
            self._clear_layout()

            # Ajouter les nouveaux filtres
            for filter_data in filters:
                self.add_filter(
                    filter_id=filter_data["id"],
                    label=filter_data["label"],
                    filter_type=filter_data.get("type", "default"),
                    is_selected=filter_data.get("selected", False),
                    is_removable=filter_data.get("removable", True),
                )
        finally:
            # Unblock signals
            self.blockSignals(False)
            self._suppress_signal_emits = False

        self._update_interface_state()

    def get_selected_filters(self) -> List[str]:
        """Return selected filters list."""
        return [fid for fid, selected in self.selection_state.items() if selected]

    def get_all_filters(self) -> Dict[str, Dict[str, Any]]:
        """Return all filters with their data."""
        return {fid: chip.get_filter_data() for fid, chip in self.chips.items()}

    def set_filter_selected(self, filter_id: str, selected: bool):
        """Set l'state de selection d'un filtre."""
        if filter_id in self.chips:
            self.chips[filter_id].set_selected(selected)
            self.selection_state[filter_id] = selected
            self._update_interface_state()
            self._emit_filters_changed()

    def clear_all_filters_completely(self):
        """Remove all filters completely."""
        for filter_id in list(self.chips.keys()):
            self.remove_filter(filter_id)

    def set_max_selections(self, max_count: int):
        """Set le nombre maximum de selections."""
        self.max_selections = max_count

    def set_custom_validator(self, validator: Callable[[List[str]], bool]):
        """Set a custom validator for selections."""
        self.custom_validator = validator

    def get_selection_count(self) -> int:
        """Return selected filter count."""
        return sum(self.selection_state.values())

    def has_selections(self) -> bool:
        """Check whether there are active selections."""
        return any(self.selection_state.values())

    def get_filters_by_type(self, filter_type: str) -> List[str]:
        """Return filters of a given type."""
        return self.filter_groups.get(filter_type, [])
