from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_content_classifier.services.file.scanners.base_scanner import ScanProgress
from ai_content_classifier.services.file.scanners.local_filesystem_scanner import (
    LocalFilesystemScanner,
)


class TestLocalFilesystemScanner:
    @pytest.fixture
    def scanner(self):
        scanner = LocalFilesystemScanner()
        scanner.logger = MagicMock()
        return scanner

    @pytest.fixture
    def mock_os_walk(self):
        # Mock a simple directory structure
        # root, dirs, files
        mock_data = [
            ("/test_dir", ["subdir1", "subdir2"], ["file1.txt", "file2.jpg"]),
            ("/test_dir/subdir1", [], ["file3.pdf"]),
            ("/test_dir/subdir2", [], ["file4.mp3", "file5.png"]),
        ]
        with patch("os.walk", return_value=mock_data) as mock_walk:
            yield mock_walk

    @pytest.fixture
    def mock_os_access(self):
        with patch("os.access", return_value=True) as mock_access:
            yield mock_access

    @pytest.fixture
    def mock_os_path_splitext(self):
        # Mock os.path.splitext to return consistent extensions
        def side_effect(path):
            if path.endswith(".txt"):
                return "file1", ".txt"
            elif path.endswith(".jpg"):
                return "file2", ".jpg"
            elif path.endswith(".pdf"):
                return "file3", ".pdf"
            elif path.endswith(".mp3"):
                return "file4", ".mp3"
            elif path.endswith(".png"):
                return "file5", ".png"
            return "", ""

        with patch("os.path.splitext", side_effect=side_effect) as mock_splitext:
            yield mock_splitext

    def test_scan_directory_basic(
        self, scanner, mock_os_walk, mock_os_access, mock_os_path_splitext
    ):
        files = list(scanner.scan_directory("/test_dir"))
        expected_files = [
            ("/test_dir/file1.txt", "/test_dir"),
            ("/test_dir/file2.jpg", "/test_dir"),
            ("/test_dir/subdir1/file3.pdf", "/test_dir/subdir1"),
            ("/test_dir/subdir2/file4.mp3", "/test_dir/subdir2"),
            ("/test_dir/subdir2/file5.png", "/test_dir/subdir2"),
        ]
        assert sorted(files) == sorted(expected_files)
        mock_os_walk.assert_called_once_with("/test_dir")
        assert mock_os_access.call_count == len(expected_files)

    def test_scan_directory_with_allowed_extensions(
        self, scanner, mock_os_walk, mock_os_access, mock_os_path_splitext
    ):
        allowed_extensions = {".jpg", ".png"}
        files = list(
            scanner.scan_directory("/test_dir", allowed_extensions=allowed_extensions)
        )
        expected_files = [
            ("/test_dir/file2.jpg", "/test_dir"),
            ("/test_dir/subdir2/file5.png", "/test_dir/subdir2"),
        ]
        assert sorted(files) == sorted(expected_files)
        assert mock_os_access.call_count == len(expected_files)

    def test_scan_directory_cancellation(
        self, scanner, mock_os_walk, mock_os_access, mock_os_path_splitext
    ):
        # Simulate cancellation after the first file
        def mock_walk_cancellable(directory):
            yield ("/test_dir", [], ["file1.txt", "file2.jpg"])
            scanner.cancel_scan()  # Cancel during the first iteration
            yield ("/test_dir/subdir1", [], ["file3.pdf"])

        mock_os_walk.side_effect = mock_walk_cancellable

        files = list(scanner.scan_directory("/test_dir"))
        assert (
            len(files) == 2
        )  # The cancellation stops the next iteration of os.walk, not the current one.
        assert files[0] == ("/test_dir/file1.txt", "/test_dir")
        assert scanner.is_cancelled()

    def test_scan_directory_progress_callback(
        self, scanner, mock_os_walk, mock_os_access, mock_os_path_splitext
    ):
        mock_callback = MagicMock()
        files = list(
            scanner.scan_directory(
                "/test_dir", progress_callback=mock_callback, batch_size=2
            )
        )

        # Expect callback to be called at least twice (after 2 files, and final update)
        assert mock_callback.call_count >= 2
        # Check the last call's progress
        last_progress = mock_callback.call_args[0][0]
        assert isinstance(last_progress, ScanProgress)
        assert last_progress.files_found == len(files)
        assert last_progress.files_processed == len(files)

    def test_scan_directory_os_error_handling(
        self, scanner, mock_os_walk, mock_os_access, mock_os_path_splitext
    ):
        mock_os_access.side_effect = PermissionError("Permission denied")
        files = list(scanner.scan_directory("/test_dir"))
        assert len(files) == 0  # No files should be yielded due to error
        # Check that logger.warning was called
        scanner.logger.warning.assert_called()  # Check that a warning was logged

    def test_cancel_scan_and_is_cancelled(self, scanner):
        assert not scanner.is_cancelled()
        scanner.cancel_scan()
        assert scanner.is_cancelled()

    def test_scan_directory_empty(
        self, scanner, mock_os_walk, mock_os_access, mock_os_path_splitext
    ):
        mock_os_walk.return_value = [("/empty_dir", [], [])]
        files = list(scanner.scan_directory("/empty_dir"))
        assert len(files) == 0

    def test_scan_directory_no_matching_extensions(
        self, scanner, mock_os_walk, mock_os_access, mock_os_path_splitext
    ):
        allowed_extensions = {".xyz"}
        files = list(
            scanner.scan_directory("/test_dir", allowed_extensions=allowed_extensions)
        )
        assert len(files) == 0

    def test_scan_directory_exception_handling(
        self, scanner, mock_os_walk, mock_os_access, mock_os_path_splitext
    ):
        mock_os_walk.side_effect = Exception("Unexpected walk error")
        with pytest.raises(Exception, match="Unexpected walk error"):
            list(scanner.scan_directory("/test_dir"))
        scanner.logger.error.assert_called()  # Verify error was logged

    def test_scan_directory_excludes_central_thumbnail_cache(
        self, tmp_path, monkeypatch
    ):
        scan_root = tmp_path / "scan-root"
        scan_root.mkdir()

        keep_file = scan_root / "keep.jpg"
        keep_file.write_text("ok", encoding="utf-8")

        cache_root = scan_root / ".cache"
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache_root))
        excluded_dir = cache_root / "Javis" / "thumbnails"
        excluded_dir.mkdir(parents=True)
        excluded_file = excluded_dir / "skip.jpg"
        excluded_file.write_text("skip", encoding="utf-8")

        scanner = LocalFilesystemScanner()
        scanner.logger = MagicMock()
        results = list(scanner.scan_directory(str(scan_root)))
        scanned_paths = {Path(path) for path, _directory in results}

        assert keep_file in scanned_paths
        assert excluded_file not in scanned_paths
