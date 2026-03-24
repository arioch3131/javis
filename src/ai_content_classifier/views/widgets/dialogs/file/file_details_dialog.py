from __future__ import annotations
# ruff: noqa: E402

import os
import sys
from typing import Any


def _restore_pyqt6_if_mocked() -> None:
    pyqt6_module = sys.modules.get("PyQt6")
    if pyqt6_module is None:
        return
    module_origin = getattr(pyqt6_module.__class__, "__module__", "")
    if module_origin.startswith("unittest.mock"):
        for module_name in (
            "PyQt6",
            "PyQt6.QtCore",
            "PyQt6.QtGui",
            "PyQt6.QtWidgets",
        ):
            sys.modules.pop(module_name, None)


_restore_pyqt6_if_mocked()

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QHBoxLayout, QDialog, QPushButton, QVBoxLayout

from ai_content_classifier.views.widgets.specialized.adaptive_preview_widget import (
    AdaptivePreviewWidget,
)


class FileDetailsDialog(QDialog):
    """Full file details dialog opened from a double-click in result views."""

    previous_requested = pyqtSignal()
    next_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("fileDetailsDialog")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )
        self.setWindowTitle("File details")
        self.resize(980, 720)
        self.current_file_path = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(6)

        self.previous_button = QPushButton("◀", self)
        self.previous_button.setObjectName("detailsNavButton")
        self.previous_button.setFixedWidth(36)
        self.previous_button.clicked.connect(self.previous_requested.emit)
        content_row.addWidget(self.previous_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.preview_widget = AdaptivePreviewWidget(self)
        self.preview_widget.set_display_mode("dialog")
        content_row.addWidget(self.preview_widget, 1)

        self.next_button = QPushButton("▶", self)
        self.next_button.setObjectName("detailsNavButton")
        self.next_button.setFixedWidth(36)
        self.next_button.clicked.connect(self.next_requested.emit)
        content_row.addWidget(self.next_button, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(content_row, 1)

        self.previous_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        self.previous_shortcut.activated.connect(self._trigger_previous)
        self.next_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        self.next_shortcut.activated.connect(self._trigger_next)

    def set_file_details(self, file_details: dict[str, Any]) -> None:
        file_path = file_details.get("file_path") or ""
        self.current_file_path = file_path
        self.setWindowTitle(
            f"File details - {os.path.basename(file_path)}"
            if file_path
            else "File details"
        )
        self.preview_widget.set_file_details(file_details)

    def set_navigation_state(self, has_previous: bool, has_next: bool) -> None:
        self.previous_button.setEnabled(has_previous)
        self.next_button.setEnabled(has_next)

    def _trigger_previous(self) -> None:
        if self.previous_button.isEnabled():
            self.previous_requested.emit()

    def _trigger_next(self) -> None:
        if self.next_button.isEnabled():
            self.next_requested.emit()
