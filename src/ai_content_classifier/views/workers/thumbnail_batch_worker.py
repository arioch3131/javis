import os
from typing import List

from PyQt6.QtCore import QThread, pyqtSignal


class BatchThumbnailWorker(QThread):
    """Optimized worker for batch generation."""

    thumbnail_ready = pyqtSignal(str, object)

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
                thumbnail_payload = self.generator_func(file_path)
                if not thumbnail_payload:
                    continue

                if isinstance(thumbnail_payload, str):
                    if os.path.exists(thumbnail_payload):
                        self.thumbnail_ready.emit(file_path, thumbnail_payload)
                    continue

                self.thumbnail_ready.emit(file_path, thumbnail_payload)
            except Exception as e:
                print(f"Batch generation error: {e}")

    def stop(self):
        """Stops the worker."""
        self.should_stop = True
