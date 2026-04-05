import sys

from PyQt6.QtWidgets import QApplication

from ai_content_classifier.views.widgets.grid.grid_core import (
    UltraOptimizedThumbnailGrid,
)


class TestGridDebugMetrics:
    @classmethod
    def setup_class(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_performance_bar_is_hidden_by_default(self):
        widget = UltraOptimizedThumbnailGrid()

        assert widget.debug_metrics_visible is False
        assert widget.perf_widget.isHidden()

    def test_performance_bar_can_be_toggled(self):
        widget = UltraOptimizedThumbnailGrid()

        widget.set_debug_metrics_visible(True)
        assert not widget.perf_widget.isHidden()

        widget.set_debug_metrics_visible(False)
        assert widget.perf_widget.isHidden()
