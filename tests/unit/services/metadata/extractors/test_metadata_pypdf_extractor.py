from unittest.mock import MagicMock, mock_open, patch

from ai_content_classifier.services.metadata.extractors.pypdf_extractor import (
    PyPDFExtractor,
)


def build_extractor() -> PyPDFExtractor:
    with patch.object(PyPDFExtractor, "_check_dependency", return_value=True):
        extractor = PyPDFExtractor()
    extractor.pypdf_available = True
    return extractor


def test_check_dependency_variants():
    extractor = build_extractor()
    extractor._check_dependency = PyPDFExtractor._check_dependency.__get__(extractor)

    assert extractor._check_dependency("unittest") is True
    assert extractor._check_dependency("module_that_does_not_exist_xyz") is False


def test_init_logs_warning_when_dependency_missing():
    with patch.object(PyPDFExtractor, "_check_dependency", return_value=False):
        extractor = PyPDFExtractor()

    assert extractor.pypdf_available is False


@patch("ai_content_classifier.services.metadata.extractors.pypdf_extractor.os.access")
@patch(
    "ai_content_classifier.services.metadata.extractors.pypdf_extractor.os.path.isfile"
)
def test_can_handle_conditions(mock_isfile, mock_access):
    extractor = build_extractor()

    mock_isfile.return_value = True
    mock_access.return_value = True
    assert extractor.can_handle("/tmp/file.pdf") is True

    assert extractor.can_handle("/tmp/file.txt") is False

    mock_access.return_value = False
    assert extractor.can_handle("/tmp/file.pdf") is False

    extractor.pypdf_available = False
    assert extractor.can_handle("/tmp/file.pdf") is False


def test_get_metadata_when_dependency_missing():
    extractor = build_extractor()
    extractor.pypdf_available = False

    with patch.object(
        extractor, "get_basic_metadata", return_value={"filename": "doc.pdf"}
    ):
        result = extractor.get_metadata("/tmp/doc.pdf")

    assert result["error"] == "pypdf library is not installed"


def test_get_metadata_success_with_document_info_and_preview():
    extractor = build_extractor()
    mock_pdf = MagicMock()
    mock_pdf.pages = [MagicMock()]
    mock_pdf.pages[0].extract_text.return_value = "hello" * 400
    mock_pdf.metadata = {
        "/Title": "My Doc",
        "/Pages": 2,
        "/IgnoredObj": object(),
        "/Empty": "",
    }

    with patch.object(
        extractor, "get_basic_metadata", return_value={"filename": "doc.pdf"}
    ):
        with patch("builtins.open", mock_open(read_data=b"%PDF")):
            with patch(
                "pypdf.PdfReader",
                return_value=mock_pdf,
            ):
                result = extractor.get_metadata("/tmp/doc.pdf")

    assert "pdf_info" in result
    assert result["pdf_info"]["page_count"] == 1
    assert len(result["pdf_info"]["first_page_preview"]) == 1000
    assert result["pdf_info"]["document_info"]["Title"] == "My Doc"
    assert result["pdf_info"]["document_info"]["Pages"] == 2
    assert "IgnoredObj" not in result["pdf_info"]["document_info"]


def test_get_metadata_handles_first_page_text_error():
    extractor = build_extractor()
    mock_pdf = MagicMock()
    mock_pdf.pages = [MagicMock()]
    mock_pdf.pages[0].extract_text.side_effect = RuntimeError("cannot read text")
    mock_pdf.metadata = None

    with patch.object(
        extractor, "get_basic_metadata", return_value={"filename": "doc.pdf"}
    ):
        with patch("builtins.open", mock_open(read_data=b"%PDF")):
            with patch(
                "pypdf.PdfReader",
                return_value=mock_pdf,
            ):
                result = extractor.get_metadata("/tmp/doc.pdf")

    assert result["pdf_info"]["page_count"] == 1
    assert "first_page_preview" not in result["pdf_info"]


def test_get_metadata_returns_error_on_reader_failure():
    extractor = build_extractor()

    with patch.object(
        extractor, "get_basic_metadata", return_value={"filename": "doc.pdf"}
    ):
        with patch("builtins.open", mock_open(read_data=b"%PDF")):
            with patch(
                "pypdf.PdfReader",
                side_effect=RuntimeError("reader failed"),
            ):
                result = extractor.get_metadata("/tmp/doc.pdf")

    assert "error" in result
    assert "reader failed" in result["error"]
