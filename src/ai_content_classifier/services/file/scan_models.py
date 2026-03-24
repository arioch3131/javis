from dataclasses import dataclass, field
import time


@dataclass
class ScanProgress:
    files_found: int = 0
    files_processed: int = 0
    total_files_scanned: int = 0
    current_directory: str = ""
    current_file: str = ""
    scan_speed: float = 0.0
    start_time: float = field(default_factory=time.time)
    metadata_extracted: int = 0
    thumbnails_generated: int = 0
    errors: int = 0
    elapsed_time: float = 0.0
    estimated_total_files: int = 0  # Added for better estimation
    estimated_remaining_time: float = 0.0  # Added for better estimation
    directories_scanned: int = 0  # Added for better estimation
