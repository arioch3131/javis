from pathlib import Path
from unittest.mock import mock_open, patch

from ai_content_classifier.services.metadata.extractors.text_metadata_extractor import (
    TextMetadataExtractor,
)


def test_can_handle_supported_extension_and_readable_file():
    extractor = TextMetadataExtractor()

    with patch(
        "ai_content_classifier.services.metadata.extractors.text_metadata_extractor.os.path.isfile",
        return_value=True,
    ):
        with patch(
            "ai_content_classifier.services.metadata.extractors.text_metadata_extractor.os.access",
            return_value=True,
        ):
            assert extractor.can_handle("/tmp/readme.md") is True


def test_can_handle_rejects_unsupported_or_unreadable_file():
    extractor = TextMetadataExtractor()

    with patch(
        "ai_content_classifier.services.metadata.extractors.text_metadata_extractor.os.path.isfile",
        return_value=True,
    ):
        with patch(
            "ai_content_classifier.services.metadata.extractors.text_metadata_extractor.os.access",
            return_value=True,
        ):
            assert extractor.can_handle("/tmp/file.bin") is False

    with patch(
        "ai_content_classifier.services.metadata.extractors.text_metadata_extractor.os.path.isfile",
        return_value=False,
    ):
        assert extractor.can_handle("/tmp/readme.md") is False


def test_get_metadata_success_counts_and_format():
    extractor = TextMetadataExtractor()
    sample_text = "hello world\nline2"

    with patch.object(
        extractor, "get_basic_metadata", return_value={"filename": "README.md"}
    ):
        with patch("builtins.open", mock_open(read_data=sample_text.encode("utf-8"))):
            metadata = extractor.get_metadata("/tmp/README.md")

    assert metadata["content_type"] == "text"
    assert metadata["text_format"] == "md"
    assert metadata["sample_bytes"] == len(sample_text.encode("utf-8"))
    assert metadata["sample_line_count"] == 2
    assert metadata["sample_char_count"] == len(sample_text)
    assert metadata["sample_word_count"] == 3


def test_get_metadata_plain_when_no_extension():
    extractor = TextMetadataExtractor()

    with patch.object(extractor, "get_basic_metadata", return_value={}):
        with patch("builtins.open", mock_open(read_data=b"abc")):
            metadata = extractor.get_metadata("/tmp/README")

    assert metadata["text_format"] == "plain"


def test_get_metadata_handles_read_error():
    extractor = TextMetadataExtractor()

    with patch.object(extractor, "get_basic_metadata", return_value={}):
        with patch("builtins.open", side_effect=OSError("cannot read")):
            metadata = extractor.get_metadata(str(Path("/tmp/readme.md")))

    assert "error" in metadata
    assert "cannot read" in metadata["error"]
