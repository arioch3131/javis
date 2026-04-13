from unittest.mock import MagicMock

from ai_content_classifier.controllers.categorization_controller import (
    CategorizationWorker,
)
from ai_content_classifier.services.file.file_type_service import FileTypeService
from ai_content_classifier.services.file.scan_pipeline_service import (
    ScanPipelineService,
)
from ai_content_classifier.services.llm.llm_service import LLMService
from ai_content_classifier.services.metadata.extractors.base_extractor import (
    BaseMetadataExtractor,
)
from ai_content_classifier.services.metadata.extractors.text_metadata_extractor import (
    TextMetadataExtractor,
)
from ai_content_classifier.services.preprocessing.text_extraction_service import (
    TextExtractionService,
)
from ai_content_classifier.services.thumbnail.utils import (
    is_image_file as thumbnail_utils_is_image_file,
)


class _DummyMetadataExtractor(BaseMetadataExtractor):
    def can_handle(self, file_path: str) -> bool:  # pragma: no cover - test helper
        return True

    def get_metadata(self, file_path: str) -> dict:  # pragma: no cover - test helper
        return {}


def _build_scan_pipeline() -> ScanPipelineService:
    return ScanPipelineService(
        scanner=MagicMock(),
        db_service=MagicMock(),
        metadata_service=MagicMock(),
        thumbnail_service=MagicMock(),
    )


def test_image_detection_consistency_across_modules():
    worker = CategorizationWorker(
        llm_service=MagicMock(),
        content_database_service=MagicMock(),
        file_paths=[],
        categories=[],
        config={},
    )

    for path in ("/tmp/a.jpg", "/tmp/b.png", "/tmp/c.pdf", "/tmp/d.bin"):
        expected = FileTypeService.is_image_file(path)
        assert worker._is_image_file(path) == expected
        assert LLMService._is_image_file(None, path) == expected
        assert thumbnail_utils_is_image_file(path, check_content=False) == expected


def test_content_type_consistency_for_scan_pipeline():
    service = _build_scan_pipeline()

    for path in (
        "/tmp/a.jpg",
        "/tmp/a.pdf",
        "/tmp/a.mp4",
        "/tmp/a.mp3",
        "/tmp/a.bin",
    ):
        assert service._determine_content_type(
            path
        ) == FileTypeService.get_content_type(path)


def test_text_format_consistency_for_preprocessing():
    service = TextExtractionService()

    for path in (
        "/tmp/a.txt",
        "/tmp/a.md",
        "/tmp/a.csv",
        "/tmp/a.pdf",
        "/tmp/a.docx",
        "/tmp/a.rtf",
        "/tmp/a.odt",
        "/tmp/a.bin",
    ):
        assert service._detect_file_format(path) == FileTypeService.get_text_format(
            path
        )


def test_metadata_type_resolution_consistency():
    extractor = _DummyMetadataExtractor()

    expected_type_by_category = {
        "IMAGE": "image",
        "DOCUMENT": "document",
        "AUDIO": "audio",
        "VIDEO": "video",
        "ARCHIVE": "archive",
    }

    for path in (
        "/tmp/a.jpg",
        "/tmp/a.pdf",
        "/tmp/a.mp3",
        "/tmp/a.mp4",
        "/tmp/a.zip",
        "/tmp/a.py",
        "/tmp/a.bin",
    ):
        ext = FileTypeService.get_extension(path)
        category = FileTypeService.get_file_category(path)
        expected = expected_type_by_category.get(category.name, "other")
        assert extractor._determine_file_type(ext) == expected


def test_metadata_text_extractor_consistency_with_text_like(tmp_path):
    extractor = TextMetadataExtractor()
    text_file = tmp_path / "notes.md"
    binary_file = tmp_path / "image.png"
    text_file.write_text("# Notes\ncontent")
    binary_file.write_bytes(b"\x89PNG\r\n")

    assert extractor.can_handle(str(text_file)) == FileTypeService.is_text_like(
        str(text_file)
    )
    assert extractor.can_handle(str(binary_file)) == FileTypeService.is_text_like(
        str(binary_file)
    )
