from abc import ABC, abstractmethod
from typing import Generator, Optional, Set, Tuple, Callable
from dataclasses import dataclass, field
import time


@dataclass
class ScanProgress:
    files_found: int = 0
    files_processed: int = 0
    total_files_scanned: int = 0
    directories_scanned: int = 0
    current_directory: str = ""
    current_file: str = ""
    scan_speed: float = 0.0
    start_time: float = field(default_factory=time.time)
    metadata_extracted: int = 0
    thumbnails_generated: int = 0
    errors: int = 0
    elapsed_time: float = 0.0


class BaseScanner(ABC):
    @abstractmethod
    def scan_directory(
        self,
        directory_path: str,
        allowed_extensions: Optional[Set[str]] = None,
        progress_callback: Optional[Callable[[ScanProgress], None]] = None,
    ) -> Generator[Tuple[str, str], None, None]:
        """
        Abstract method to scan a directory and yield file paths.

        Args:
            directory_path: The path to the directory to scan.
            allowed_extensions: An optional set of file extensions to include.
            progress_callback: A callback function to report scan progress.

        Yields:
            A tuple of (file_path, directory_path) for each found file.
        """
        pass

    @abstractmethod
    def cancel_scan(self) -> None:
        """
        Abstract method to request cancellation of the ongoing scan.
        """
        pass

    @abstractmethod
    def is_cancelled(self) -> bool:
        """
        Abstract method to check if the scan has been cancelled.
        """
        pass
