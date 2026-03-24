import sys

from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication

from ai_content_classifier.views.widgets.common.file_hover_preview import (
    FileHoverPreview,
)


class TestFileHoverPreview:
    @classmethod
    def setup_class(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_show_for_file_populates_preview_content(self):
        widget = FileHoverPreview()
        pixmap = QPixmap(24, 24)
        pixmap.fill()

        widget.show_for_file(
            {
                "file_path": "/tmp/example.png",
                "directory": "/tmp",
                "category": "Icons",
                "content_type": "image",
                "thumbnail": pixmap,
            },
            QPoint(120, 120),
        )

        assert widget.isVisible()
        assert widget.name_label.text() == "example.png"
        assert widget.path_label.text() == "/tmp"
        assert "Icons" in widget.meta_label.text()
