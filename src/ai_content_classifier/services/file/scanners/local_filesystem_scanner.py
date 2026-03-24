import os
import sys
import time
from typing import Callable, Generator, Optional, Set, Tuple

from ai_content_classifier.core.logger import LoggableMixin
from ai_content_classifier.services.file.scanners.base_scanner import (
    BaseScanner,
    ScanProgress,
)


class LocalFilesystemScanner(BaseScanner, LoggableMixin):
    """
    A concrete scanner implementation for local filesystem traversal.
    """

    def __init__(self):
        self.__init_logger__()
        self._is_cancelled_flag = False
        self._thumbnail_cache_dir = self._resolve_thumbnail_cache_dir()

    @staticmethod
    def _resolve_thumbnail_cache_dir() -> str:
        """Return the centralized thumbnail cache directory for this OS."""
        app_folder = "Javis"
        if sys.platform.startswith("win"):
            base_dir = os.getenv(
                "LOCALAPPDATA",
                os.getenv("APPDATA", str(os.path.expanduser("~\\AppData\\Local"))),
            )
        elif sys.platform == "darwin":
            base_dir = os.path.expanduser("~/Library/Caches")
        else:
            base_dir = os.getenv("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))

        return os.path.normpath(
            os.path.abspath(os.path.join(base_dir, app_folder, "thumbnails"))
        )

    @staticmethod
    def _is_same_or_child_path(path: str, parent_path: str) -> bool:
        """Return True when `path` equals or is inside `parent_path`."""
        try:
            normalized_path = os.path.normpath(os.path.abspath(path))
            normalized_parent = os.path.normpath(os.path.abspath(parent_path))
            return (
                os.path.commonpath([normalized_path, normalized_parent])
                == normalized_parent
            )
        except ValueError:
            # Different drives on Windows, invalid path mix, etc.
            return False

    def scan_directory(
        self,
        directory_path: str,
        allowed_extensions: Optional[Set[str]] = None,
        progress_callback: Optional[Callable[[ScanProgress], None]] = None,
        batch_size: int = 100,
    ) -> Generator[Tuple[str, str], None, None]:
        """
        Scans a local directory progressively, yielding file paths as they are found.

        Args:
            directory_path (str): The root directory to start scanning from.
            allowed_extensions (Optional[Set[str]]): A set of file extensions (e.g., {".jpg", ".png"})
                                                    to include in the scan. Case-insensitive.
            progress_callback (Optional[Callable[[ScanProgress], None]]): A callback function
                                                                        to report scan progress.
            batch_size (int): The number of files to process before invoking the progress callback.

        Yields:
            Tuple[str, str]: A tuple containing the absolute file path and its directory.
        """
        self._is_cancelled_flag = False
        start_time = time.time()

        progress = ScanProgress()
        progress.current_directory = directory_path

        self.logger.debug(
            f"Starting local filesystem scan for: {directory_path} with allowed extensions: {allowed_extensions}"
        )

        normalized_extensions = set()
        if allowed_extensions:
            for ext in allowed_extensions:
                if ext.startswith("."):
                    normalized_extensions.add(ext.lower())
                else:
                    normalized_extensions.add(f".{ext.lower()}")

        try:
            for root, dirs, files in os.walk(directory_path):
                if self._is_cancelled_flag:
                    break

                if self._is_same_or_child_path(root, self._thumbnail_cache_dir):
                    continue

                # Never recurse into generated thumbnail folders.
                pruned_dirs = []
                for directory_name in dirs:
                    child_path = os.path.join(root, directory_name)
                    if directory_name == ".thumbnails":
                        continue
                    if self._is_same_or_child_path(
                        child_path, self._thumbnail_cache_dir
                    ):
                        continue
                    pruned_dirs.append(directory_name)
                dirs[:] = pruned_dirs

                progress.directories_scanned += 1
                progress.current_directory = root
                progress.elapsed_time = time.time() - start_time

                for file in files:
                    if self._is_cancelled_flag:
                        break
                    if self._is_cancelled_flag:
                        break

                    progress.total_files_scanned += 1
                    file_path = os.path.join(root, file)

                    _, ext = os.path.splitext(file.lower())

                    if normalized_extensions and ext not in normalized_extensions:
                        continue

                    try:
                        # Basic accessibility check
                        if not os.access(file_path, os.R_OK):
                            continue

                        progress.files_found += 1
                        progress.current_file = file_path

                        if progress.elapsed_time > 0:
                            progress.scan_speed = (
                                progress.files_found / progress.elapsed_time
                            )

                        if progress_callback and progress.files_found % batch_size == 0:
                            progress_callback(progress)

                        yield (file_path, root)
                        progress.files_processed += 1

                    except (OSError, PermissionError) as e:
                        self.logger.warning(
                            f"Skipping file {file_path} due to error: {e}"
                        )
                        progress.errors += 1
                        continue

                if progress_callback:
                    progress_callback(progress)

        except Exception as e:
            self.logger.error(
                f"Unexpected error during local filesystem scan: {e}", exc_info=True
            )
            raise

        finally:
            progress.elapsed_time = time.time() - start_time
            if progress_callback:
                progress_callback(progress)  # Final update

    def cancel_scan(self) -> None:
        """Requests cancellation of the ongoing scan."""
        self.logger.info("LocalFilesystemScanner: Scan cancellation requested.")
        self._is_cancelled_flag = True

    def is_cancelled(self) -> bool:
        """Checks if the scan has been cancelled."""
        return self._is_cancelled_flag
