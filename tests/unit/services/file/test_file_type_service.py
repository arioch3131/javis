import pytest
from unittest.mock import patch

from ai_content_classifier.services.file.file_type_service import (
    FileTypeService,
    FileCategory,
)


class TestFileTypeService:
    def test_file_category_enum(self):
        """Test that FileCategory enum has expected values."""
        assert FileCategory.IMAGE.value == "Image"
        assert FileCategory.DOCUMENT.value == "Document"
        assert FileCategory.VIDEO.value == "Video"
        assert FileCategory.AUDIO.value == "Audio"
        assert FileCategory.ARCHIVE.value == "Archive"
        assert FileCategory.CODE.value == "Code"
        assert FileCategory.OTHER.value == "Other"

    @pytest.mark.parametrize(
        "file_path, expected_category_name",
        [
            ("image.jpg", "Image"),
            ("document.pdf", "Document"),
            ("video.mp4", "Video"),
            ("audio.mp3", "Audio"),
            ("archive.zip", "Archive"),
            ("script.py", "Code"),
            ("spreadsheet.csv", "Document"),  # CSV is in DOCUMENT_EXTENSIONS
            ("presentation.ppt", "Document"),  # PPT is in DOCUMENT_EXTENSIONS
            ("text.txt", "Document"),  # TXT is in DOCUMENT_EXTENSIONS
            ("unknown.xyz", "Other"),
            ("file.JPG", "Image"),  # Case-insensitivity
            ("file.TXT", "Document"),  # Case-insensitivity
        ],
    )
    def test_get_file_category_name(self, file_path, expected_category_name):
        assert (
            FileTypeService.get_file_category_name(file_path) == expected_category_name
        )

    @pytest.mark.parametrize(
        "method_name, file_path, expected_result",
        [
            ("is_image_file", "test.jpg", True),
            ("is_image_file", "test.pdf", False),
            ("is_document_file", "test.pdf", True),
            ("is_document_file", "test.jpg", False),
            ("is_video_file", "test.mp4", True),
            ("is_video_file", "test.txt", False),
            ("is_audio_file", "test.mp3", True),
            ("is_audio_file", "test.png", False),
            ("is_archive_file", "test.zip", True),
            ("is_archive_file", "test.txt", False),
            ("is_code_file", "test.py", True),
            ("is_code_file", "test.txt", False),
        ],
    )
    def test_is_file_type_methods(self, method_name, file_path, expected_result):
        method = getattr(FileTypeService, method_name)
        assert method(file_path) == expected_result

    @patch("os.path.exists", return_value=True)
    @patch("os.path.isfile", return_value=True)
    def test_validate_file_path_success(self, mock_isfile, mock_exists):
        assert FileTypeService.validate_file_path("/safe/path/file.txt") is True
        mock_exists.assert_called_once_with("/safe/path/file.txt")
        mock_isfile.assert_called_once_with("/safe/path/file.txt")

    @patch("os.path.exists", return_value=False)
    def test_validate_file_path_non_existent(self, mock_exists):
        assert FileTypeService.validate_file_path("/nonexistent/file.txt") is False
        mock_exists.assert_called_once_with("/nonexistent/file.txt")

    @patch("os.path.exists", side_effect=OSError)
    def test_validate_file_path_os_error(self, mock_exists):
        assert FileTypeService.validate_file_path("/error/path.txt") is False

    def test_format_file_size_zero(self):
        assert FileTypeService.format_file_size(0) == "0 B"

    def test_format_file_size_kb(self):
        assert FileTypeService.format_file_size(1024) == "1.0 KB"

    def test_format_file_size_mb(self):
        # 1234567 bytes = 1.18 MB (not 1.2 MB)
        result = FileTypeService.format_file_size(1234567)
        assert result == "1.18 MB"

    def test_format_file_size_gb(self):
        assert FileTypeService.format_file_size(1073741824) == "1.0 GB"

    @pytest.mark.parametrize(
        "file_path, expected_category_enum",
        [
            ("image.jpg", FileCategory.IMAGE),
            ("document.pdf", FileCategory.DOCUMENT),
            ("video.mp4", FileCategory.VIDEO),
            ("audio.mp3", FileCategory.AUDIO),
            ("archive.zip", FileCategory.ARCHIVE),
            ("script.py", FileCategory.CODE),
            ("spreadsheet.csv", FileCategory.DOCUMENT),  # Falls to Document
            ("presentation.ppt", FileCategory.DOCUMENT),  # Falls to Document
            ("text.txt", FileCategory.DOCUMENT),  # Falls to Document
            ("unknown.xyz", FileCategory.OTHER),
        ],
    )
    def test_get_file_category_enum(self, file_path, expected_category_enum):
        assert FileTypeService.get_file_category(file_path) == expected_category_enum

    def test_extension_sets_not_empty(self):
        """Test that all extension sets contain elements."""
        assert len(FileTypeService.IMAGE_EXTENSIONS) > 0
        assert len(FileTypeService.DOCUMENT_EXTENSIONS) > 0
        assert len(FileTypeService.VIDEO_EXTENSIONS) > 0
        assert len(FileTypeService.AUDIO_EXTENSIONS) > 0
        assert len(FileTypeService.ARCHIVE_EXTENSIONS) > 0
        assert len(FileTypeService.CODE_EXTENSIONS) > 0

    def test_extension_sets_are_lowercase(self):
        """Test that all extensions are lowercase."""
        all_extensions = (
            FileTypeService.IMAGE_EXTENSIONS
            | FileTypeService.DOCUMENT_EXTENSIONS
            | FileTypeService.VIDEO_EXTENSIONS
            | FileTypeService.AUDIO_EXTENSIONS
            | FileTypeService.ARCHIVE_EXTENSIONS
            | FileTypeService.CODE_EXTENSIONS
        )
        for ext in all_extensions:
            assert ext == ext.lower(), f"Extension {ext} is not lowercase"

    def test_convenience_functions(self):
        """Test the convenience functions work correctly."""
        from ai_content_classifier.services.file.file_type_service import (
            is_image_file,
            is_document_file,
            is_video_file,
            is_audio_file,
            get_file_category,
            format_file_size,
        )

        assert is_image_file("test.jpg") is True
        assert is_document_file("test.pdf") is True
        assert is_video_file("test.mp4") is True
        assert is_audio_file("test.mp3") is True
        assert get_file_category("test.jpg") == "Image"
        assert format_file_size(1024) == "1.0 KB"

    def test_case_insensitive_extensions(self):
        """Test that file detection is case-insensitive."""
        assert FileTypeService.is_image_file("TEST.JPG") is True
        assert FileTypeService.is_image_file("test.JPG") is True
        assert FileTypeService.is_image_file("test.Jpg") is True
        assert FileTypeService.get_file_category("TEST.PDF") == FileCategory.DOCUMENT

    def test_file_without_extension(self):
        """Test behavior with files without extensions."""
        assert FileTypeService.get_file_category("README") == FileCategory.OTHER

    def test_file_with_multiple_dots(self):
        """Test behavior with files containing multiple dots."""
        assert (
            FileTypeService.get_file_category("archive.tar.gz") == FileCategory.ARCHIVE
        )
        assert FileTypeService.is_archive_file("backup.tar.gz") is True

    def test_normalize_extension_helpers(self):
        assert FileTypeService.normalize_extension("JPG") == ".jpg"
        assert FileTypeService.normalize_extension(".PDF") == ".pdf"
        assert FileTypeService.normalize_extension("  ") == ""
        assert FileTypeService.normalize_extensions(["JPG", ".png", ""]) == {
            ".jpg",
            ".png",
        }

    def test_get_extension_prefers_longest_match(self):
        assert FileTypeService.get_extension("archive.tar.gz") == ".tar.gz"
        assert FileTypeService.get_extension("README.GITIGNORE") == ".gitignore"
        assert FileTypeService.get_extension("unknownfile") == ""

    def test_get_content_type(self):
        assert FileTypeService.get_content_type("photo.jpg") == "image"
        assert FileTypeService.get_content_type("doc.pdf") == "document"
        assert FileTypeService.get_content_type("movie.mp4") == "video"
        assert FileTypeService.get_content_type("song.mp3") == "audio"
        assert FileTypeService.get_content_type("archive.zip") == "content_item"

    def test_text_like_and_text_format(self):
        assert FileTypeService.is_text_like("README.md") is True
        assert FileTypeService.is_text_like("archive.zip") is False
        assert FileTypeService.get_text_format("notes.md") == "markdown"
        assert FileTypeService.get_text_format("draft.docx") == "docx"
        assert FileTypeService.get_text_format("image.jpg") == "unknown"
