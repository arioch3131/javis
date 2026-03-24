import os
from typing import List

from PyQt6.QtCore import QThread, pyqtSignal


class BatchThumbnailWorker(QThread):
    """Optimized worker for batch generation."""

    thumbnail_ready = pyqtSignal(str, str)

    def __init__(self, file_paths: List[str], generator_func):
        super().__init__()
        self.file_paths = file_paths
        self.generator_func = generator_func
        self.should_stop = False

    def run(self):
        """Generates thumbnails in batch."""
        for file_path in self.file_paths:
            if self.should_stop:
                break

            try:
                thumbnail_path = self.generator_func(file_path)
                if thumbnail_path and os.path.exists(thumbnail_path):
                    self.thumbnail_ready.emit(file_path, thumbnail_path)
            except Exception as e:
                print(f"Batch generation error: {e}")

    def stop(self):
        """Stops the worker."""
        self.should_stop = True
