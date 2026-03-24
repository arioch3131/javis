from typing import Any, Dict, List

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QBoxLayout,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ai_content_classifier.services.theme.theme_service import get_theme_service
from ai_content_classifier.views.widgets.common.filter_chips import FilterChipsContainer


class FlowLayout(QLayout):
    """Simple wrapping flow layout for contextual filter chips."""

    def __init__(self, parent=None, margin: int = 0, spacing: int = 6):
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    def __del__(self):
        while self.count():
            self.takeAt(0)

    def addItem(self, item: QLayoutItem):
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(), margins.top() + margins.bottom()
        )
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.spacing()

        for item in self._items:
            item_size = item.sizeHint()
            next_x = x + item_size.width() + spacing

            if line_height > 0 and next_x - spacing > rect.right() and rect.width() > 0:
                x = rect.x()
                y += line_height + spacing
                next_x = x + item_size.width() + spacing
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item_size))

            x = next_x
            line_height = max(line_height, item_size.height())

        return y + line_height - rect.y()


class FilterSidebar(QWidget):
    file_type_selected = pyqtSignal(str)
    category_requested = pyqtSignal()
    date_requested = pyqtSignal()
    extension_requested = pyqtSignal()
    clear_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("filterSidebar")
        self._compact_mode = False
        self._build_ui()

    def _theme_metrics(self):
        return get_theme_service().get_theme_definition().metrics

    def _build_ui(self):
        metrics = self._theme_metrics()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(metrics.spacing_md)

        self._build_file_type_section(layout)

        self.filter_chips_container = FilterChipsContainer(
            parent=self,
            title="Active Filters",
            allow_multiple=True,
            group_by_type=True,
        )
        self.filter_chips_container.hide()
        self.filter_chips_container.setMaximumHeight(0)

        actions_card = QFrame(self)
        actions_card.setObjectName("filterSidebarActions")
        actions_layout = QVBoxLayout(actions_card)
        actions_layout.setContentsMargins(
            metrics.spacing_md,
            metrics.spacing_md,
            metrics.spacing_md,
            metrics.spacing_md,
        )
        actions_layout.setSpacing(metrics.spacing_sm)

        self.actions_title = QLabel("Quick Filters", actions_card)
        self.actions_title.setObjectName("filterSidebarSectionTitle")
        actions_layout.addWidget(self.actions_title)

        self.category_button, self.category_chip_host = (
            self._create_filter_action_block(
                actions_card,
                "Category",
                self.category_requested.emit,
            )
        )
        actions_layout.addWidget(self.category_button)
        actions_layout.addWidget(self.category_chip_host)

        self.date_button, self.date_chip_host = self._create_filter_action_block(
            actions_card,
            "Date",
            self.date_requested.emit,
        )
        actions_layout.addWidget(self.date_button)
        actions_layout.addWidget(self.date_chip_host)

        self.extension_button, self.extension_chip_host = (
            self._create_filter_action_block(
                actions_card,
                "Extension",
                self.extension_requested.emit,
            )
        )
        actions_layout.addWidget(self.extension_button)
        actions_layout.addWidget(self.extension_chip_host)

        self.clear_button = QPushButton("Clear Filters", actions_card)
        self.clear_button.setObjectName("clearFiltersButton")
        self.clear_button.clicked.connect(self.clear_requested.emit)
        self.clear_button.hide()
        actions_layout.addWidget(self.clear_button)

        layout.addWidget(actions_card)
        layout.addStretch(1)
        self.actions_card = actions_card
        self.action_buttons = [
            self.category_button,
            self.date_button,
            self.extension_button,
            self.clear_button,
        ]
        self._default_action_labels = {
            self.category_button: "Category",
            self.date_button: "Date",
            self.extension_button: "Extension",
            self.clear_button: "Clear Filters",
        }
        self._compact_action_labels = {
            self.category_button: "Category",
            self.date_button: "Date",
            self.extension_button: "Ext",
            self.clear_button: "Clear",
        }
        self._section_hosts = {
            "category": self.category_chip_host,
            "date": self.date_chip_host,
            "extension": self.extension_chip_host,
        }

    def _create_filter_action_block(self, parent: QWidget, label: str, callback):
        button = QPushButton(label, parent)
        button.setObjectName("sidebarQuickButton")
        button.clicked.connect(callback)

        chip_host = QFrame(parent)
        chip_host.setObjectName("sidebarFilterChipHost")
        chip_host.hide()

        chip_layout = FlowLayout(
            chip_host,
            margin=0,
            spacing=max(4, self._theme_metrics().spacing_xs),
        )

        chip_host.chip_layout = chip_layout
        return button, chip_host

    def _build_file_type_section(self, parent_layout: QVBoxLayout):
        metrics = self._theme_metrics()
        self.file_type_card = QFrame(self)
        self.file_type_card.setObjectName("fileTypeCard")
        layout = QVBoxLayout(self.file_type_card)
        layout.setContentsMargins(
            metrics.spacing_md,
            metrics.spacing_md,
            metrics.spacing_md,
            metrics.spacing_md,
        )
        layout.setSpacing(metrics.spacing_sm + 2)

        self.file_type_title = QLabel("File Type", self.file_type_card)
        self.file_type_title.setObjectName("filterSidebarSectionTitle")
        layout.addWidget(self.file_type_title)

        self.file_type_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        self.file_type_layout.setSpacing(metrics.spacing_sm)

        self.file_type_group = QButtonGroup(self.file_type_card)
        self.file_type_group.setExclusive(True)

        buttons = [
            ("All", "All Files"),
            ("Images", "Image"),
            ("Documents", "Document"),
        ]
        self.file_type_buttons: Dict[str, QPushButton] = {}
        self._default_button_labels: Dict[str, str] = {}
        self._compact_button_labels: Dict[str, str] = {
            "All Files": "All",
            "Image": "Img",
            "Document": "Doc",
        }

        for index, (label, value) in enumerate(buttons):
            button = QPushButton(label, self.file_type_card)
            button.setObjectName("sidebarFilterButton")
            button.setCheckable(True)
            if index == 0:
                button.setChecked(True)
            button.clicked.connect(
                lambda checked=False, selected=value: self.file_type_selected.emit(
                    selected
                )
            )
            self.file_type_group.addButton(button, index)
            self.file_type_buttons[value] = button
            self._default_button_labels[value] = label
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.file_type_layout.addWidget(button)

        layout.addLayout(self.file_type_layout)
        parent_layout.addWidget(self.file_type_card)

    def set_filters(self, filters: List[Dict[str, Any]]):
        self.filter_chips_container.set_filters(filters)
        has_filters = bool(filters)
        self.clear_button.setVisible(has_filters)
        self._render_contextual_chips(filters)

    def _render_contextual_chips(self, filters: List[Dict[str, Any]]):
        grouped_filters: Dict[str, List[Dict[str, Any]]] = {
            "category": [],
            "date": [],
            "extension": [],
        }

        for filter_data in filters:
            filter_type = filter_data.get("type")
            if filter_type in grouped_filters:
                grouped_filters[filter_type].append(filter_data)

        for filter_type, host in self._section_hosts.items():
            layout = host.chip_layout
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

            items = grouped_filters[filter_type]
            host.setVisible(bool(items))
            for filter_data in items:
                layout.addWidget(self._create_context_chip(filter_data, host))

    def _create_context_chip(
        self, filter_data: Dict[str, Any], parent: QWidget
    ) -> QFrame:
        metrics = self._theme_metrics()
        chip = QFrame(parent)
        chip.setObjectName("sidebarContextChip")
        chip.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(chip)
        layout.setContentsMargins(
            metrics.spacing_sm,
            max(2, metrics.spacing_xs - 1),
            metrics.spacing_xs,
            max(2, metrics.spacing_xs - 1),
        )
        layout.setSpacing(metrics.spacing_xs)

        label = QLabel(str(filter_data.get("label", "")), chip)
        label.setObjectName("sidebarContextChipLabel")
        layout.addWidget(label, 1)

        remove_button = QToolButton(chip)
        remove_button.setObjectName("sidebarContextChipRemove")
        remove_button.setText("x")
        remove_button.clicked.connect(
            lambda checked=False, filter_id=filter_data.get("id", ""): (
                self.filter_chips_container.remove_filter(filter_id)
            )
        )
        layout.addWidget(remove_button)
        return chip

    def set_compact_mode(self, enabled: bool):
        """Adapts the sidebar for intermediate window widths."""
        if self._compact_mode == enabled:
            return

        metrics = self._theme_metrics()
        self._compact_mode = enabled
        self.actions_title.setVisible(True)
        self.filter_chips_container.setMaximumHeight(180 if enabled else 16777215)
        self.file_type_layout.setDirection(QBoxLayout.Direction.TopToBottom)
        self.file_type_layout.setSpacing(
            metrics.spacing_sm - 2 if enabled else metrics.spacing_sm
        )

        if hasattr(self.filter_chips_container, "title_label"):
            self.filter_chips_container.title_label.setVisible(not enabled)
        if hasattr(self.filter_chips_container, "options_button"):
            self.filter_chips_container.options_button.setVisible(not enabled)
        if hasattr(self.filter_chips_container, "select_all_button"):
            self.filter_chips_container.select_all_button.setText(
                "All" if enabled else "Select All"
            )
        if hasattr(self.filter_chips_container, "clear_all_button"):
            self.filter_chips_container.clear_all_button.setText(
                "Clear" if enabled else "Clear All"
            )
        if hasattr(self.filter_chips_container, "status_label"):
            self.filter_chips_container.status_label.setVisible(not enabled)

        for value, button in self.file_type_buttons.items():
            button.setText(
                self._compact_button_labels[value]
                if enabled
                else self._default_button_labels[value]
            )
            button.setMinimumHeight(metrics.control_height - 4 if enabled else 0)

        for button in self.action_buttons:
            button.setText(
                self._compact_action_labels[button]
                if enabled
                else self._default_action_labels[button]
            )
            button.setMinimumHeight(metrics.control_height - 4 if enabled else 0)

        for host in self._section_hosts.values():
            host.setVisible(host.chip_layout.count() > 0)
