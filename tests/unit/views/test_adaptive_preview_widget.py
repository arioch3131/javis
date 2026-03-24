import sys

from PyQt6.QtWidgets import QApplication

from ai_content_classifier.views.widgets.specialized.adaptive_preview_widget import (
    AdaptivePreviewWidget,
)


class TestAdaptivePreviewWidget:
    @classmethod
    def setup_class(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_preview_summary_is_shown_when_file_details_are_set(self):
        widget = AdaptivePreviewWidget()

        widget.set_file_details(
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

        assert not widget.summary_container.isHidden()
        assert widget.size_summary_label.text() == "149 KB"
        assert "Image" in widget.type_summary_label.text()
        assert widget.meta_summary_label.text() == "914 x 457"

    def test_clear_details_hides_preview_summary(self):
        widget = AdaptivePreviewWidget()
        widget.summary_container.show()

        widget.clear_details()

        assert widget.summary_container.isHidden()
        assert widget.size_summary_label.text() == "No selection"

    def test_classification_section_displays_confidence(self):
        widget = AdaptivePreviewWidget()

        widget.set_file_details(
            {
                "file_path": "/tmp/example.png",
                "content_type": "image",
                "metadata": {"size_formatted": "149 KB"},
                "classification": {"category": "Animals", "confidence": 0.91},
            }
        )

        classification_text = widget.metadata_widget.get_content_label(
            widget.metadata_widget.classification_group
        ).text()
        assert "Category: Animals" in classification_text
        assert "Confidence: 91%" in classification_text
