import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from ai_content_classifier.views.widgets.dialogs.file.file_details_dialog import (
    FileDetailsDialog,
)


class TestFileDetailsDialog:
    @classmethod
    def setup_class(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_set_file_details_updates_dialog_title_and_preview(self):
        dialog = FileDetailsDialog()

        dialog.set_file_details(
            {
                "file_path": "/tmp/example.png",
                "content_type": "image",
                "metadata": {
                    "size_formatted": "149 KB",
                    "extension": ".png",
                    "dimensions": "914 x 457",
                },
            }
        )

        assert "example.png" in dialog.windowTitle()
        assert dialog.preview_widget.size_summary_label.text() == "149 KB"

    def test_navigation_state_updates_buttons(self):
        dialog = FileDetailsDialog()

        dialog.set_navigation_state(has_previous=True, has_next=False)

        assert dialog.previous_button.isEnabled()
        assert not dialog.next_button.isEnabled()

    def test_arrow_shortcuts_emit_navigation_requests(self):
        dialog = FileDetailsDialog()
        dialog.set_navigation_state(has_previous=True, has_next=True)
        triggered = {"previous": 0, "next": 0}
        dialog.previous_requested.connect(
            lambda: triggered.__setitem__("previous", triggered["previous"] + 1)
        )
        dialog.next_requested.connect(
            lambda: triggered.__setitem__("next", triggered["next"] + 1)
        )

        dialog.previous_shortcut.activated.emit()
        dialog.next_shortcut.activated.emit()

        assert triggered == {"previous": 1, "next": 1}

    def test_dialog_allows_window_maximize_controls(self):
        dialog = FileDetailsDialog()

        assert dialog.windowFlags() & Qt.WindowType.Window
        assert dialog.windowFlags() & Qt.WindowType.WindowMaximizeButtonHint
