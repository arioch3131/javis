import os
from typing import Optional, Tuple

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPainter, QPixmap
    from PyQt6.QtSvg import QSvgRenderer

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

from ai_content_classifier.services.thumbnail import constants
from ai_content_classifier.services.thumbnail.generators import (
    BaseThumbnailGenerator,
    PlaceholderGenerator,
)


class SvgGenerator(BaseThumbnailGenerator):
    """Thumbnail generator for SVG images using Qt's QSvgRenderer."""

    def generate(
        self, image_path: str, size: Tuple[int, int], quality_factor: float = 1.0
    ) -> Optional[QPixmap]:
        if not QT_AVAILABLE:
            self.logger.warning("SVG thumbnails require Qt, which is not available")
            return None

        try:
            renderer = QSvgRenderer()
            success = renderer.load(image_path)
            if not success:
                with open(image_path, "rb") as f:
                    svg_data = f.read()
                    renderer.load(svg_data)

            view_box = renderer.viewBoxF()
            if view_box.width() > 0 and view_box.height() > 0:
                aspect_ratio = view_box.width() / view_box.height()
                if aspect_ratio > 1:
                    thumb_width = size[0]
                    thumb_height = int(thumb_width / aspect_ratio)
                else:
                    thumb_height = size[1]
                    thumb_width = int(thumb_height * aspect_ratio)
            else:
                thumb_width, thumb_height = size

            pixmap = QPixmap(thumb_width, thumb_height)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            file_size = os.path.getsize(image_path)
            if file_size > constants.SVG_SIZE_THRESHOLD_HIGH:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            else:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            renderer.render(painter)
            painter.end()
            return pixmap
        except Exception as e:
            self.logger.error(f"Error creating SVG thumbnail for {image_path}: {e}")
            return PlaceholderGenerator().generate(image_path, size, quality_factor)
