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

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ai_content_classifier.services.theme.theme_service import get_theme_service


class FileHoverPreview(QFrame):
    """Compact floating preview shown when hovering a thumbnail."""

    def __init__(self, parent=None):
        super().__init__(
            parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint
        )
        self.setObjectName("fileHoverPreview")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.thumbnail_label = QLabel(self)
        self.thumbnail_label.setObjectName("hoverPreviewThumb")
        self.thumbnail_label.setFixedSize(68, 68)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.name_label = QLabel(self)
        self.name_label.setObjectName("hoverPreviewName")
        self.name_label.setWordWrap(False)

        self.path_label = QLabel(self)
        self.path_label.setObjectName("hoverPreviewPath")
        self.path_label.setWordWrap(False)

        self.meta_label = QLabel(self)
        self.meta_label.setObjectName("hoverPreviewMeta")
        self.meta_label.setWordWrap(True)

        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)
        info_layout.addWidget(self.name_label)
        info_layout.addWidget(self.path_label)
        info_layout.addWidget(self.meta_label)

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)
        root_layout.addWidget(self.thumbnail_label)
        root_layout.addLayout(info_layout, 1)

        self._apply_theme()

    def _apply_theme(self) -> None:
        theme = get_theme_service().get_theme_definition()
        palette = theme.palette
        metrics = theme.metrics
        typography = theme.typography
        self.setStyleSheet(
            f"""
            QFrame#fileHoverPreview {{
                background-color: {palette.surface};
                border: 1px solid {palette.outline};
                border-radius: {metrics.radius_md}px;
            }}
            QLabel#hoverPreviewThumb {{
                background-color: {palette.surface_variant};
                border: 1px solid {palette.outline_variant};
                border-radius: {metrics.radius_sm}px;
                color: {palette.on_surface_variant};
            }}
            QLabel#hoverPreviewName {{
                color: {palette.on_surface};
                font-family: "{typography.font_family}";
                font-size: {typography.font_size_sm}px;
                font-weight: {typography.font_weight_bold};
            }}
            QLabel#hoverPreviewPath,
            QLabel#hoverPreviewMeta {{
                color: {palette.on_surface_variant};
                font-family: "{typography.font_family}";
                font-size: {typography.font_size_xs}px;
            }}
            """
        )

    def show_for_file(self, preview_data: dict[str, Any], global_pos: QPoint) -> None:
        file_path = preview_data.get("file_path") or ""
        directory = preview_data.get("directory") or os.path.dirname(file_path)
        category = preview_data.get("category") or "Uncategorized"
        content_type = preview_data.get("content_type") or "File"

        self.name_label.setText(os.path.basename(file_path) or "Unknown file")
        self.path_label.setText(self._elide_path(directory or file_path))
        self.meta_label.setText(f"{content_type} • {category}")

        pixmap = preview_data.get("thumbnail")
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            self.thumbnail_label.setPixmap(
                pixmap.scaled(
                    self.thumbnail_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self.thumbnail_label.setText("")
        else:
            self.thumbnail_label.setPixmap(QPixmap())
            self.thumbnail_label.setText(content_type[:1].upper())

        self.adjustSize()
        self._move_inside_screen(global_pos)
        self.show()
        self.raise_()

    def _elide_path(self, file_path: str) -> str:
        if len(file_path) <= 44:
            return file_path
        return f"...{file_path[-41:]}"

    def _move_inside_screen(self, global_pos: QPoint) -> None:
        screen = QApplication.screenAt(global_pos) or QApplication.primaryScreen()
        geometry = screen.availableGeometry() if screen else None
        x = global_pos.x() + 14
        y = global_pos.y() + 14
        if geometry is not None:
            if x + self.width() > geometry.right():
                x = max(geometry.left(), global_pos.x() - self.width() - 14)
            if y + self.height() > geometry.bottom():
                y = max(geometry.top(), global_pos.y() - self.height() - 14)
        self.move(x, y)
