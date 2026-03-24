import os
from typing import Optional

from PyQt6.QtCore import QPoint, QRect, QSize
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QLabel, QSizePolicy
from ai_content_classifier.services.theme.theme_service import get_theme_service


class OptimizedThumbnailItem(QLabel):
    """Ultra-optimized thumbnail widget."""

    clicked = pyqtSignal(str)
    activated = pyqtSignal(str)
    hover_started = pyqtSignal(object, object)
    hover_ended = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_path: Optional[str] = None
        self.directory = ""
        self.category = ""
        self.content_type = ""
        self.thumbnail_size_px = 150
        self._is_document_placeholder = False
        self.setup_optimized_ui()

    def _theme_tokens(self):
        return get_theme_service().get_theme_definition()

    def _build_default_style(self) -> str:
        theme = self._theme_tokens()
        palette = theme.palette
        metrics = theme.metrics
        typography = theme.typography
        return f"""
            OptimizedThumbnailItem {{
                border: {metrics.focus_width}px solid {palette.outline_variant};
                border-radius: {metrics.radius_sm - 2}px;
                background-color: {palette.surface};
                color: {palette.on_surface};
                font-family: "{typography.font_family}";
                font-size: {typography.font_size_xs - 1}px;
                padding: {max(1, metrics.spacing_xs - 2)}px;
            }}
            OptimizedThumbnailItem:hover {{
                border-color: {palette.primary};
                background-color: {palette.focused};
            }}
        """

    def _build_document_style(self) -> str:
        theme = self._theme_tokens()
        palette = theme.palette
        metrics = theme.metrics
        typography = theme.typography
        return f"""
            OptimizedThumbnailItem {{
                border: {metrics.focus_width}px solid {palette.primary_light};
                border-radius: {metrics.radius_sm - 2}px;
                background-color: {palette.surface_variant};
                color: {palette.primary_dark};
                font-family: "{typography.font_family}";
                font-size: {typography.font_size_xs}px;
                font-weight: {typography.font_weight_bold};
                padding: {max(1, metrics.spacing_xs - 2)}px;
            }}
            OptimizedThumbnailItem:hover {{
                border-color: {palette.primary};
                background-color: {palette.focused};
            }}
        """

    def setup_optimized_ui(self):
        """Configures the optimized UI."""
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.setWordWrap(False)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(50)
        self.setStyleSheet(self._build_default_style())

    def configure_for_file(
        self, file_path: str, directory: str, content_type: str, category: str = ""
    ):
        """Quickly configures for a file."""
        # FIX: Clear previous state
        self.clear()
        self.setPixmap(QPixmap())  # Clear any existing pixmap

        self.file_path = file_path
        self.directory = directory
        self.category = category
        self.content_type = content_type
        self._is_document_placeholder = False
        self.setText(self._elide_filename(os.path.basename(file_path)))

        # Reset style to default
        self.setStyleSheet(self._build_default_style())

        self.show()

    def set_document_placeholder(self, filename: str):
        """Displays a document placeholder with filename."""
        # Do not clear file_path here, it's set by configure_for_file
        self._is_document_placeholder = True
        self.setText(f"📄 {self._elide_filename(filename)}")
        self.setStyleSheet(self._build_document_style())

    def _elide_filename(self, text: str) -> str:
        """Fits a filename in one line for stable tile heights."""
        metrics = QFontMetrics(self.font())
        available = max(10, self.width() - 12)
        return metrics.elidedText(text, Qt.TextElideMode.ElideMiddle, available)

    def set_thumbnail(self, pixmap: QPixmap):
        """Sets a uniform square thumbnail (center-cropped)."""
        if not pixmap.isNull():
            target_size = QSize(self.thumbnail_size_px, self.thumbnail_size_px)
            scaled = pixmap.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = max(0, (scaled.width() - target_size.width()) // 2)
            y = max(0, (scaled.height() - target_size.height()) // 2)
            cropped = scaled.copy(
                QRect(x, y, target_size.width(), target_size.height())
            )
            self.setPixmap(cropped)
            self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

    def set_thumbnail_size(self, size: int):
        """Quickly adjusts size."""
        self.thumbnail_size_px = max(50, min(300, int(size)))
        metrics = self._theme_tokens().metrics
        tile_w = self.thumbnail_size_px + metrics.spacing_sm + 2
        tile_h = self.thumbnail_size_px + metrics.spacing_xl - 2
        self.setFixedSize(tile_w, tile_h)
        # Refresh text after width changes.
        if self.file_path and not self.pixmap():
            self.setText(self._elide_filename(os.path.basename(self.file_path)))

    def clear_file(self):
        """Quickly clears."""
        self.file_path = None
        self.directory = ""
        self.category = ""
        self.content_type = ""
        self._is_document_placeholder = False
        self.clear()
        self.setText("")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.file_path:
            self.clicked.emit(self.file_path)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.file_path:
            self.activated.emit(self.file_path)
        super().mouseDoubleClickEvent(event)

    def enterEvent(self, event):
        super().enterEvent(event)
        if self.file_path:
            self.hover_started.emit(self._build_preview_payload(), self._hover_anchor())

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.hover_ended.emit()

    def _hover_anchor(self) -> QPoint:
        return self.mapToGlobal(self.rect().topRight())

    def _build_preview_payload(self) -> dict[str, object]:
        return {
            "file_path": self.file_path,
            "directory": self.directory,
            "category": self.category,
            "content_type": self.content_type,
            "thumbnail": self.pixmap(),
        }
