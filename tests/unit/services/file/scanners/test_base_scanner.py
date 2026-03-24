import pytest
from ai_content_classifier.services.file.scanners.base_scanner import BaseScanner, ScanProgress

class ConcreteScanner(BaseScanner):
    def __init__(self):
        self._cancelled = False

    def scan_directory(self, directory_path, allowed_extensions=None, progress_callback=None):
        yield ("/mock/file1.txt", "/mock")
        yield ("/mock/file2.jpg", "/mock")

    def cancel_scan(self):
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

class TestBaseScanner:
    def test_base_scanner_is_abstract(self):
        with pytest.raises(TypeError):
            BaseScanner()

    def test_concrete_scanner_implements_interface(self):
        scanner = ConcreteScanner()
        assert isinstance(scanner, BaseScanner)
        assert hasattr(scanner, 'scan_directory')
        assert hasattr(scanner, 'cancel_scan')
        assert hasattr(scanner, 'is_cancelled')

    def test_scan_progress_dataclass(self):
        progress = ScanProgress()
        assert progress.files_found == 0
        assert progress.current_directory == ""
        assert progress.start_time is not None

        progress_with_data = ScanProgress(files_found=10, current_file="test.txt")
        assert progress_with_data.files_found == 10
        assert progress_with_data.current_file == "test.txt"
