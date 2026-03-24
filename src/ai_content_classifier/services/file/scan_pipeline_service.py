import os
import threading
import time
from dataclasses import replace
from queue import Empty, Queue
from typing import Callable, List, Optional, Set, Tuple

from ai_content_classifier.core.logger import LoggableMixin
from ai_content_classifier.services.database.content_database_service import (
    ContentDatabaseService,
)
from ai_content_classifier.services.file.scan_models import ScanProgress
from ai_content_classifier.services.file.scanners.base_scanner import BaseScanner
from ai_content_classifier.services.metadata.metadata_service import MetadataService
from ai_content_classifier.services.thumbnail.thumbnail_service import ThumbnailService


class ScanPipelineService(LoggableMixin):
    """
    Dedicated orchestration pipeline for scan + metadata/thumbnail processing.

    The scanner produces file batches, processing workers consume batches and
    push file results through a queue for aggregation and progress updates.
    """

    def __init__(
        self,
        scanner: BaseScanner,
        db_service: ContentDatabaseService,
        metadata_service: MetadataService,
        thumbnail_service: ThumbnailService,
        batch_size: int = 100,
        max_workers: int = 4,
        queue_maxsize: int = 20,
    ):
        self.__init_logger__()
        self.scanner = scanner
        self.db_service = db_service
        self.metadata_service = metadata_service
        self.thumbnail_service = thumbnail_service
        self.batch_size = max(1, batch_size)
        self.max_workers = max(1, max_workers)
        self.queue_maxsize = max(2, queue_maxsize)
        self._is_cancelled = False

    def run_pipeline(
        self,
        directory: str,
        allowed_extensions: Optional[Set[str]] = None,
        progress_callback: Optional[Callable[[ScanProgress], None]] = None,
        file_processed_callback: Optional[Callable[[str, bool, bool], None]] = None,
    ) -> List[Tuple[str, str]]:
        """
        Runs scan/processing pipeline with batch queue orchestration.
        """
        self._is_cancelled = False
        processed_files: List[Tuple[str, str]] = []
        progress = ScanProgress(current_directory=directory)
        progress_lock = threading.Lock()

        batch_queue: Queue = Queue(maxsize=self.queue_maxsize)
        results_queue: Queue = Queue(maxsize=self.queue_maxsize * 2)

        worker_count = self.max_workers
        sentinel = object()
        producer_done = threading.Event()

        def emit_progress():
            if not progress_callback:
                return
            with progress_lock:
                snapshot = replace(progress)
                snapshot.elapsed_time = time.time() - progress.start_time
                # Total is only reliable once file discovery is finished.
                snapshot.estimated_total_files = (
                    snapshot.files_found if producer_done.is_set() else 0
                )
                if (
                    snapshot.estimated_total_files > 0
                    and snapshot.scan_speed > 0
                    and snapshot.files_processed <= snapshot.estimated_total_files
                ):
                    remaining = (
                        snapshot.estimated_total_files - snapshot.files_processed
                    )
                    snapshot.estimated_remaining_time = remaining / snapshot.scan_speed
                else:
                    snapshot.estimated_remaining_time = 0.0
            progress_callback(snapshot)

        def on_scan_progress(scan_progress):
            with progress_lock:
                progress.files_found = scan_progress.files_found
                progress.total_files_scanned = scan_progress.total_files_scanned
                progress.directories_scanned = getattr(
                    scan_progress, "directories_scanned", progress.directories_scanned
                )
                progress.current_directory = scan_progress.current_directory
                progress.current_file = scan_progress.current_file
                progress.scan_speed = scan_progress.scan_speed
            emit_progress()

        def producer():
            batch: List[Tuple[str, str]] = []
            try:
                for file_path, dir_path in self.scanner.scan_directory(
                    directory,
                    allowed_extensions,
                    on_scan_progress,
                ):
                    if self._is_cancelled:
                        break
                    batch.append((file_path, dir_path))
                    if len(batch) >= self.batch_size:
                        batch_queue.put(batch)
                        batch = []

                if batch and not self._is_cancelled:
                    batch_queue.put(batch)
            finally:
                producer_done.set()
                for _ in range(worker_count):
                    batch_queue.put(sentinel)

        def worker():
            while True:
                task = batch_queue.get()
                if task is sentinel:
                    results_queue.put(sentinel)
                    batch_queue.task_done()
                    return

                batch_results = []
                for file_path, dir_path in task:
                    if self._is_cancelled:
                        break
                    batch_results.append(self._process_single_file(file_path, dir_path))
                results_queue.put(batch_results)
                batch_queue.task_done()

        producer_thread = threading.Thread(target=producer, daemon=True)
        worker_threads = [
            threading.Thread(target=worker, daemon=True) for _ in range(worker_count)
        ]

        producer_thread.start()
        for t in worker_threads:
            t.start()

        sentinels_received = 0
        while sentinels_received < worker_count:
            if self._is_cancelled and producer_done.is_set() and results_queue.empty():
                break
            try:
                item = results_queue.get(timeout=0.2)
            except Empty:
                continue

            if item is sentinel:
                sentinels_received += 1
                continue

            for result in item:
                if result["success"]:
                    processed_files.append((result["file_path"], result["directory"]))
                    with progress_lock:
                        progress.files_processed += 1
                        if result["metadata_success"]:
                            progress.metadata_extracted += 1
                        if result["thumbnail_success"]:
                            progress.thumbnails_generated += 1
                else:
                    with progress_lock:
                        progress.errors += 1

                if file_processed_callback:
                    file_processed_callback(
                        result["file_path"],
                        result["metadata_success"],
                        result["thumbnail_success"],
                    )

            emit_progress()

        # Ensure threads stop.
        self._is_cancelled = self._is_cancelled or False
        producer_thread.join(timeout=2)
        for t in worker_threads:
            t.join(timeout=2)

        emit_progress()
        return processed_files

    def cancel(self):
        """Requests cancellation of the current pipeline."""
        self._is_cancelled = True
        self.scanner.cancel_scan()

    def _process_single_file(self, file_path: str, directory: str) -> dict:
        """Processes one file: metadata, thumbnail, then DB save."""
        result = {
            "file_path": file_path,
            "directory": directory,
            "success": False,
            "metadata_success": False,
            "thumbnail_success": False,
            "error": None,
        }

        try:
            existing_item = self.db_service.get_content_by_path(file_path)
            if existing_item:
                result["success"] = True
                return result

            metadata = self.metadata_service.get_all_metadata(file_path)
            if metadata and "error" not in metadata:
                result["metadata_success"] = True

            if self._is_image_file(file_path):
                thumbnail_result = self.thumbnail_service.create_thumbnail(file_path)
                if thumbnail_result and thumbnail_result.success:
                    result["thumbnail_success"] = True

            content_type = self._determine_content_type(file_path)
            self.db_service.create_content_item(
                path=file_path,
                content_type=content_type,
                extract_basic_info=True,
                metadata=metadata,
            )
            result["success"] = True
        except Exception as e:
            self.logger.error(f"Error processing single file {file_path}: {e}")
            result["error"] = str(e)

        return result

    def _is_image_file(self, file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        image_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".tiff",
            ".webp",
            ".ico",
            ".heic",
            ".heif",
            ".svg",
            ".raw",
        }
        return ext in image_extensions

    def _determine_content_type(self, file_path: str) -> str:
        ext = os.path.splitext(file_path)[1].lower()
        image_exts = {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".tiff",
            ".webp",
            ".ico",
            ".heic",
            ".heif",
            ".svg",
            ".raw",
        }
        document_exts = {
            ".pdf",
            ".doc",
            ".docx",
            ".txt",
            ".md",
            ".rtf",
            ".odt",
            ".csv",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
        }
        video_exts = {
            ".mp4",
            ".avi",
            ".mov",
            ".wmv",
            ".flv",
            ".webm",
            ".mkv",
            ".m4v",
            ".3gp",
            ".ogv",
        }
        audio_exts = {
            ".mp3",
            ".wav",
            ".flac",
            ".aac",
            ".ogg",
            ".wma",
            ".m4a",
            ".opus",
            ".aiff",
        }
        if ext in image_exts:
            return "image"
        if ext in document_exts:
            return "document"
        if ext in video_exts:
            return "video"
        if ext in audio_exts:
            return "audio"
        return "content_item"
