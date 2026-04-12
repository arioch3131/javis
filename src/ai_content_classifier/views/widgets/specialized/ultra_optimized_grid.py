# Fully optimized solution to handle hundreds of gigabytes of data
# Based on Qt best practices and performance research
# FIXED VERSION for the filtering issue

from typing import List, Tuple

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget
from ai_content_classifier.services.theme.theme_service import get_theme_service
from ai_content_classifier.views.widgets.grid.grid_core import (
    UltraOptimizedThumbnailGrid,
)


# Main replacement widget
class UltraOptimizedThumbnailGridWidget(QWidget):
    """
    Main ultra-optimized widget to replace ThumbnailGridWidget.
    Designed for hundreds of gigabytes of data.
    Corrected version for filtering behavior.
    """

    file_selected = pyqtSignal(str)
    file_activated = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setup_ui()
        self.thumbnail_generator_func = None

    def setup_ui(self):
        """Configures the interface."""
        metrics = get_theme_service().get_theme_definition().metrics
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(metrics.spacing_sm)

        # Ultra-optimized grid
        self.optimized_grid = UltraOptimizedThumbnailGrid()
        self.optimized_grid.file_selected.connect(self.file_selected.emit)
        self.optimized_grid.file_activated.connect(self.file_activated.emit)

        layout.addWidget(self.optimized_grid)

    def zoom_in(self):
        self.optimized_grid.zoom_in()

    def zoom_out(self):
        self.optimized_grid.zoom_out()

    def zoom_reset(self):
        self.optimized_grid.zoom_reset()

    def set_thumbnail_size(self, size: int):
        self.optimized_grid.set_thumbnail_size(size)

    def set_thumbnail_generator(self, generator_func):
        """Sets the generation function."""
        self.thumbnail_generator_func = generator_func
        self.optimized_grid.thumbnail_generator_func = generator_func

    def set_file_data(self, file_data: List[Tuple[str, str, str, str]]):
        """
        Updates data.
        FIX: Data already arrives filtered from file_manager/file_presenter.
        """
        self.optimized_grid.set_file_data(file_data)

    def set_name_filters(self, name_filters):
        """
        FIX: This method does nothing because data already arrives filtered.
        Filtering is handled upstream by file_manager and file_presenter.
        """
        # Do nothing; data already arrives filtered via set_file_data()
        pass
