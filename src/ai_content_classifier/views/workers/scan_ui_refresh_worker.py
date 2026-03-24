"""
Background UI refresh worker for scan operations.

This worker periodically polls database state during scans and emits lightweight
snapshots so the UI can refresh without blocking the main thread.
"""

from typing import List, Tuple

from ai_content_classifier.core.logger import get_logger
from PyQt6.QtCore import QThread, pyqtSignal


class ScanUiRefreshWorker(QThread):
    """
    Polls database content count and emits updated file snapshots while running.
    """

    snapshot_ready = pyqtSignal(list, int)  # (file_list, total_count)
    refresh_error = pyqtSignal(str)

    def __init__(self, db_service, poll_interval_sec: float = 3.0, parent=None):
        super().__init__(parent)
        self.logger = get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )
        self.db_service = db_service
        self.poll_interval_ms = max(500, int(poll_interval_sec * 1000))
        self._running = False
        self._last_count = -1

    def run(self):
        self._running = True
        self.logger.debug("ScanUiRefreshWorker started")

        while self._running:
            try:
                current_count = self.db_service.count_all_items()
                if current_count != self._last_count:
                    items = self.db_service.find_items(eager_load=False)
                    file_list: List[Tuple[str, str]] = []
                    for item in items:
                        if hasattr(item, "path") and hasattr(item, "directory"):
                            file_list.append((item.path, item.directory))
                    self.snapshot_ready.emit(file_list, current_count)
                    self._last_count = current_count
            except Exception as e:
                self.refresh_error.emit(str(e))

            # Sleep in small chunks to allow responsive stop().
            slept = 0
            while self._running and slept < self.poll_interval_ms:
                self.msleep(100)
                slept += 100

        self.logger.debug("ScanUiRefreshWorker stopped")

    def stop(self):
        self._running = False
