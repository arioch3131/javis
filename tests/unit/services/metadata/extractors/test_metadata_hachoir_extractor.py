import unittest

from unittest.mock import patch, MagicMock, mock_open

from ai_content_classifier.services.metadata.extractors.hachoir_extractor import (
    HachoirExtractor,
)


class TestHachoirExtractor(unittest.TestCase):
    """Test cases for the HachoirExtractor class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create the extractor with patched dependency checks
        with patch.object(HachoirExtractor, "_check_dependency", return_value=True):
            self.extractor = HachoirExtractor()

        # Override flag for available libraries
        self.extractor.hachoir_available = True
        self.extractor.pypdf_available = True
        self.extractor.docx_available = True

    def test_initialization(self):
        """Test extractor initialization."""
        # Check extension groups are properly defined
        self.assertTrue(hasattr(self.extractor, "EXTENSION_GROUPS"))
        self.assertTrue(len(self.extractor.EXTENSION_GROUPS) > 0)

        # Check flattened priority extensions list
        self.assertTrue(hasattr(self.extractor, "priority_extensions"))
        self.assertTrue(len(self.extractor.priority_extensions) > 0)

        # Check metadata mappings
        self.assertTrue(hasattr(self.extractor, "IMPORTANT_METADATA"))
        self.assertTrue(len(self.extractor.IMPORTANT_METADATA) > 0)

        # Test initialization with additional extensions
        with patch.object(HachoirExtractor, "_check_dependency", return_value=True):
            extractor = HachoirExtractor(additional_extensions=[".custom", ".xyz"])

        self.assertIn(".custom", extractor.priority_extensions)
        self.assertIn(".xyz", extractor.priority_extensions)

    def test_check_dependency(self):
        """Test dependency checking."""
        # Use real method for this test
        self.extractor._check_dependency = HachoirExtractor._check_dependency.__get__(
            self.extractor
        )

        # Test with available module (unittest is always available)
        self.assertTrue(self.extractor._check_dependency("unittest"))

        # Test with unavailable module
        self.assertFalse(self.extractor._check_dependency("non_existent_module_xyz"))

    @patch("os.path.isfile")
    @patch("os.access")
    def test_can_handle(self, mock_access, mock_isfile):
        """Test can_handle method for supported and unsupported files."""
        # Setup mocks
        mock_isfile.return_value = True
        mock_access.return_value = True

        # Test when Hachoir is available
        self.extractor.hachoir_available = True

        # Test with priority extensions
        for ext in [".pdf", ".doc", ".docx", ".mp3", ".mp4", ".zip"]:
            self.assertTrue(self.extractor.can_handle(f"test{ext}"))

        # Test with non-priority extensions
        for ext in [".xyz", ".unknown"]:
            self.assertFalse(self.extractor.can_handle(f"test{ext}"))

        # Test when Hachoir is not available
        self.extractor.hachoir_available = False
        self.assertFalse(self.extractor.can_handle("test.pdf"))

        # Test with inaccessible file
        self.extractor.hachoir_available = True
        mock_isfile.return_value = False
        self.assertFalse(self.extractor.can_handle("test.pdf"))

        mock_isfile.return_value = True
        mock_access.return_value = False
        self.assertFalse(self.extractor.can_handle("test.pdf"))

    def test_get_metadata_without_hachoir(self):
        """Test metadata extraction when Hachoir is not available."""
        # Set Hachoir as unavailable
        self.extractor.hachoir_available = False

        # Get metadata
        with patch.object(
            self.extractor, "get_basic_metadata", return_value={"filename": "test.pdf"}
        ):
            metadata = self.extractor.get_metadata("test.pdf")

        # Verify error was reported
        self.assertIn("error", metadata)
        self.assertEqual(metadata["error"], "Hachoir library is not installed")

    @patch("hachoir.parser.createParser")
    @patch("hachoir.metadata.extractMetadata")
    def test_extract_hachoir_metadata(self, mock_extract_metadata, mock_create_parser):
        """Test extracting metadata with Hachoir."""
        # Create mock parser and metadata
        mock_parser = MagicMock()
        mock_create_parser.return_value = mock_parser

        # Create mock metadata groups and items
        mock_meta_item1 = MagicMock()
        mock_meta_item1.key = "width"
        mock_meta_item1.values = [MagicMock(value=1024)]

        mock_meta_item2 = MagicMock()
        mock_meta_item2.key = "height"
        mock_meta_item2.values = [MagicMock(value=768)]

        mock_meta_item3 = MagicMock()
        mock_meta_item3.key = "creation_date"
        date_value = MagicMock()
        date_value.year = 2021
        date_value.month = 5
        date_value.day = 15
        mock_meta_item3.values = [MagicMock(value=date_value)]

        mock_meta_group1 = MagicMock()
        mock_meta_group1.header = "Common"
        mock_meta_group1.__iter__.return_value = [
            mock_meta_item1,
            mock_meta_item2,
            mock_meta_item3,
        ]

        mock_meta_group2 = MagicMock()
        mock_meta_group2.header = "Video"
        mock_meta_group2.__iter__.return_value = []

        mock_metadata = MagicMock()
        mock_metadata.__iter__.return_value = [mock_meta_group1, mock_meta_group2]
        mock_extract_metadata.return_value = mock_metadata

        # Extract Hachoir metadata
        result = self.extractor._extract_hachoir_metadata("test.mp4")

        # Verify metadata was extracted and processed
        self.assertIn("hachoir", result)
        self.assertIn("Common", result["hachoir"])
        self.assertEqual(result["hachoir"]["Common"]["width"], 1024)
        self.assertEqual(result["hachoir"]["Common"]["height"], 768)

        # Important metadata should be moved to top level
        self.assertEqual(result["width"], 1024)
        self.assertEqual(result["height"], 768)

        # Date should be extracted
        self.assertIn("creation_date", result)

    @patch("hachoir.parser.createParser")
    def test_extract_hachoir_metadata_failures(self, mock_create_parser):
        """Test handling of Hachoir extraction failures."""
        # Test parser creation failure
        mock_create_parser.return_value = None

        result = self.extractor._extract_hachoir_metadata("test.mp4")
        self.assertEqual(result, {})

        # Test metadata extraction failure
        mock_parser = MagicMock()
        mock_create_parser.return_value = mock_parser

        with patch("hachoir.metadata.extractMetadata", return_value=None):
            result = self.extractor._extract_hachoir_metadata("test.mp4")

        self.assertEqual(result, {})

    @patch("pypdf.PdfReader")
    def test_extract_pdf_metadata(self, mock_pdf_reader):
        """Test extracting PDF-specific metadata."""
        # Create mock PDF reader and file
        mock_pdf = MagicMock()
        mock_pdf_reader.return_value = mock_pdf

        # Setup mock pages and metadata
        mock_pdf.pages = [MagicMock(), MagicMock()]
        mock_pdf.pages[0].extract_text.return_value = "This is the first page text."

        mock_pdf.metadata = {
            "/Title": "Test Document",
            "/Author": "Test Author",
            "/CreationDate": "D:20210515120000",
        }

        # Extract PDF metadata
        with patch("builtins.open", mock_open()):
            result = self.extractor._extract_pdf_metadata("test.pdf")

        # Verify PDF-specific info was extracted
        self.assertEqual(result["pages_count"], 2)
        self.assertIn("first_page_preview", result)
        self.assertIn("document_info", result)
        self.assertEqual(result["document_info"]["Title"], "Test Document")
        self.assertEqual(result["document_info"]["Author"], "Test Author")

    @patch("pypdf.PdfReader")
    def test_extract_pdf_metadata_no_metadata(self, mock_pdf_reader):
        """Test extracting PDF-specific metadata when pdf.metadata is None."""
        mock_pdf = MagicMock()
        mock_pdf_reader.return_value = mock_pdf
        mock_pdf.pages = [MagicMock()]
        mock_pdf.pages[0].extract_text.return_value = "Some text."
        mock_pdf.metadata = None

        with patch("builtins.open", mock_open()):
            result = self.extractor._extract_pdf_metadata("test.pdf")

        # When metadata is None, document_info should not be present
        self.assertNotIn("document_info", result)
        # But pages_count and first_page_preview should still be extracted
        self.assertEqual(result["pages_count"], 1)
        self.assertIn("first_page_preview", result)
        self.assertEqual(result["first_page_preview"], "Some text.")

    @patch("pypdf.PdfReader")
    def test_extract_pdf_metadata_empty_first_page_text(self, mock_pdf_reader):
        """Test extracting PDF-specific metadata when first page text is empty."""
        mock_pdf = MagicMock()
        mock_pdf_reader.return_value = mock_pdf
        mock_pdf.pages = [MagicMock()]
        mock_pdf.pages[0].extract_text.return_value = ""
        mock_pdf.metadata = {"/Title": "Test Document"}

        with patch("builtins.open", mock_open()):
            result = self.extractor._extract_pdf_metadata("test.pdf")

        self.assertNotIn("first_page_preview", result)
        self.assertIn("document_info", result)

    @patch("pypdf.PdfReader")
    def test_extract_pdf_metadata_with_exceptions(self, mock_pdf_reader):
        """Test handling exceptions when extracting PDF metadata."""
        # Create mock PDF that raises an exception when accessing pages
        mock_pdf = MagicMock()
        mock_pdf_reader.return_value = mock_pdf

        # Setup first page to raise exception
        mock_pdf.pages = [MagicMock()]
        mock_pdf.pages[0].extract_text.side_effect = Exception("Text extraction error")

        # Extract PDF metadata
        with patch("builtins.open", mock_open()):
            result = self.extractor._extract_pdf_metadata("test.pdf")

        # Verify basic info was still extracted
        self.assertEqual(result["pages_count"], 1)
        self.assertNotIn("first_page_preview", result)

        # Test with overall exception
        mock_pdf_reader.side_effect = Exception("PDF read error")

        with patch("builtins.open", mock_open()):
            result = self.extractor._extract_pdf_metadata("test.pdf")

        # Should return empty dict on overall exception
        self.assertEqual(result, {})

    @patch("docx.Document")
    def test_extract_docx_metadata(self, mock_document):
        """Test extracting DOCX-specific metadata."""
        # Create mock document
        mock_doc = MagicMock()
        mock_doc.paragraphs = [
            MagicMock(text="First paragraph"),
            MagicMock(text="Second paragraph"),
        ]
        mock_doc.tables = [MagicMock(), MagicMock()]
        mock_doc.sections = [MagicMock()]

        # Mock core properties
        mock_core_props = MagicMock()
        mock_core_props.title = "Test Document"
        mock_core_props.author = "Test Author"
        mock_doc.core_properties = mock_core_props

        mock_document.return_value = mock_doc

        result = self.extractor._extract_docx_metadata("test.docx")

        # Verify document structure
        self.assertIn("document_structure", result)
        self.assertEqual(result["document_structure"]["paragraphs_count"], 2)
        self.assertEqual(result["document_structure"]["tables_count"], 2)
        self.assertEqual(result["document_structure"]["sections_count"], 1)

        # Verify text statistics
        self.assertIn("text_statistics", result)
        self.assertEqual(
            result["text_statistics"]["word_count"], 4
        )  # "First paragraph Second paragraph"

        # Verify text preview
        self.assertIn("text_preview", result)

    @patch("docx.Document")
    def test_extract_docx_metadata_core_properties_exception(self, mock_document):
        """Test _extract_docx_metadata when core_properties extraction raises an exception."""
        mock_doc = MagicMock()
        mock_doc.paragraphs = [MagicMock(text="paragraph 1")]
        mock_doc.tables = []
        mock_doc.sections = []

        # Create a core_properties that raises exception when dir() is called on it
        mock_core_props = MagicMock()
        # Make the core_properties truthy but dir() raises an exception
        mock_core_props.__bool__ = MagicMock(return_value=True)
        mock_doc.core_properties = mock_core_props

        # Make dir() raise an exception when called on core_properties
        with patch("builtins.dir") as mock_dir:

            def dir_side_effect(obj):
                if obj is mock_core_props:
                    raise Exception("Core properties error")
                return []

            mock_dir.side_effect = dir_side_effect

            with patch.object(self.extractor.logger, "debug") as mock_debug:
                mock_document.return_value = mock_doc
                result = self.extractor._extract_docx_metadata("test.docx")

                # Should have basic structure but no core_properties due to exception
                self.assertIn("document_structure", result)
                self.assertNotIn("core_properties", result)
                mock_debug.assert_called_once()

    @patch("docx.Document")
    def test_extract_docx_metadata_empty_paragraphs(self, mock_document):
        """Test _extract_docx_metadata when doc.paragraphs is empty."""
        mock_doc = MagicMock()
        mock_doc.paragraphs = []
        mock_doc.tables = []
        mock_doc.sections = []
        mock_doc.core_properties = MagicMock()
        mock_document.return_value = mock_doc

        result = self.extractor._extract_docx_metadata("test.docx")
        self.assertIn("document_structure", result)
        self.assertNotIn("text_statistics", result)
        self.assertNotIn("text_preview", result)

    @patch("docx.Document")
    def test_extract_docx_metadata_empty_paragraph_text(self, mock_document):
        """Test _extract_docx_metadata when paragraph text is empty."""
        mock_doc = MagicMock()
        mock_doc.paragraphs = [MagicMock(text="")]
        mock_doc.tables = []
        mock_doc.sections = []
        mock_doc.core_properties = MagicMock()
        mock_document.return_value = mock_doc

        result = self.extractor._extract_docx_metadata("test.docx")
        self.assertIn("document_structure", result)
        self.assertEqual(result["text_statistics"]["word_count"], 0)
        self.assertEqual(result["text_statistics"]["character_count"], 0)
        self.assertNotIn("text_preview", result)

    @patch("docx.Document")
    def test_extract_docx_metadata_empty_text_preview(self, mock_document):
        """Test _extract_docx_metadata when text_preview is empty."""
        mock_doc = MagicMock()
        mock_doc.paragraphs = [MagicMock(text="")] * 5  # 5 empty paragraphs
        mock_doc.tables = []
        mock_doc.sections = []
        mock_doc.core_properties = MagicMock()
        mock_document.return_value = mock_doc

        result = self.extractor._extract_docx_metadata("test.docx")
        self.assertIn("document_structure", result)
        self.assertNotIn("text_preview", result)

    def test_process_metadata_item(self):
        """Test processing individual metadata items."""
        # Create test data
        metadata = {"hachoir": {"Common": {}}}
        group_name = "Common"
        extracted_dates = {}

        # Create a regular metadata item
        meta_item = MagicMock()
        meta_item.key = "width"
        meta_item.values = [MagicMock(value=1024)]

        # Process the item
        self.extractor._process_metadata_item(
            meta_item, metadata, group_name, extracted_dates
        )

        # Verify item was processed
        self.assertEqual(metadata["hachoir"]["Common"]["width"], 1024)

        # Test date item processing
        date_item = MagicMock()
        date_item.key = "creation_date"
        date_value = MagicMock()
        date_value.year = 2021
        date_value.month = 5
        date_value.day = 15
        date_item.values = [MagicMock(value=date_value)]

        # Process date item
        self.extractor._process_metadata_item(
            date_item, metadata, "Common", extracted_dates
        )

        # Verify date was extracted
        self.assertIn("creation_date", extracted_dates)
        self.assertEqual(extracted_dates["creation_date"], date_value)

        # Test multi-value item
        multi_item = MagicMock()
        multi_item.key = "tags"
        multi_item.values = [MagicMock(value="tag1"), MagicMock(value="tag2")]

        # Process multi-value item
        self.extractor._process_metadata_item(
            multi_item, metadata, "Common", extracted_dates
        )

        # Verify multi-value was processed as list
        self.assertEqual(metadata["hachoir"]["Common"]["tags"], ["tag1", "tag2"])

    def test_promote_important_metadata(self):
        """Test promoting important metadata to top level."""
        # Create test metadata
        metadata = {
            "hachoir": {
                "Common": {"width": 1024, "height": 768, "comment": "Test comment"},
                "Video": {"frame_rate": 30, "compression": "h264"},
                "Other": {"unimportant": "value"},
            }
        }

        # Promote important metadata
        self.extractor._promote_important_metadata(metadata)

        # Verify important fields are at top level
        self.assertEqual(metadata["width"], 1024)
        self.assertEqual(metadata["height"], 768)
        self.assertEqual(metadata["comment"], "Test comment")
        self.assertEqual(metadata["frame_rate"], 30)
        self.assertEqual(metadata["compression"], "h264")

        # Unimportant field should not be promoted
        self.assertNotIn("unimportant", metadata)

    def test_get_metadata_with_error_in_hachoir_extraction(self):
        """Test get_metadata method when Hachoir extraction raises an exception."""
        # Mock basic metadata
        basic_metadata = {"filename": "test.mp4", "mime_type": "video/mp4"}

        with patch.object(
            self.extractor, "get_basic_metadata", return_value=basic_metadata
        ):
            with patch.object(
                self.extractor,
                "_extract_hachoir_metadata",
                side_effect=Exception("Hachoir error"),
            ):
                with patch.object(self.extractor.logger, "error") as mock_error:
                    metadata = self.extractor.get_metadata("test.mp4")

                    # Verify error was logged and added to metadata
                    self.assertIn("error", metadata)
                    self.assertIn("Error extracting metadata", metadata["error"])
                    mock_error.assert_called_once()

    def test_get_metadata_with_pdf_extraction_error(self):
        """Test get_metadata method when PDF extraction is called but fails."""
        # Mock basic metadata with PDF mime type
        basic_metadata = {"filename": "test.pdf", "mime_type": "application/pdf"}
        hachoir_metadata = {"width": 1024}

        with patch.object(
            self.extractor, "get_basic_metadata", return_value=basic_metadata
        ):
            with patch.object(
                self.extractor,
                "_extract_hachoir_metadata",
                return_value=hachoir_metadata,
            ):
                with patch.object(
                    self.extractor,
                    "_extract_pdf_metadata",
                    side_effect=Exception("PDF error"),
                ):
                    metadata = self.extractor.get_metadata("test.pdf")

                    # Should still have basic and hachoir metadata
                    self.assertEqual(metadata["width"], 1024)
                    # PDF info should not be added due to error
                    self.assertNotIn("pdf_info", metadata)

    def test_get_metadata_with_docx_extraction_error(self):
        """Test get_metadata method when DOCX extraction is called but fails."""
        # Mock basic metadata with DOCX mime type
        basic_metadata = {
            "filename": "test.docx",
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        hachoir_metadata = {"width": 1024}

        with patch.object(
            self.extractor, "get_basic_metadata", return_value=basic_metadata
        ):
            with patch.object(
                self.extractor,
                "_extract_hachoir_metadata",
                return_value=hachoir_metadata,
            ):
                with patch.object(
                    self.extractor,
                    "_extract_docx_metadata",
                    side_effect=Exception("DOCX error"),
                ):
                    metadata = self.extractor.get_metadata("test.docx")

                    # Should still have basic and hachoir metadata
                    self.assertEqual(metadata["width"], 1024)
                    # DOCX info should not be added due to error
                    self.assertNotIn("docx_info", metadata)

    def test_process_metadata_item_date_processing_error(self):
        """Test _process_metadata_item when date processing raises an exception."""
        metadata = {"hachoir": {"Common": {}}}
        group_name = "Common"

        # Create a custom dict that raises an exception on assignment
        class FailingDict(dict):
            def __setitem__(self, key, value):
                if key == "creation_date":
                    raise Exception("Date processing error")
                super().__setitem__(key, value)

        extracted_dates = FailingDict()

        # Create a date item where the date processing will trigger exception handling
        date_item = MagicMock()
        date_item.key = "creation_date"
        date_value = MagicMock()
        date_value.year = 2021
        date_value.month = 5
        date_value.day = 15
        date_item.values = [MagicMock(value=date_value)]

        with patch.object(self.extractor.logger, "debug") as mock_debug:
            self.extractor._process_metadata_item(
                date_item, metadata, group_name, extracted_dates
            )

            # The item should still be stored in hachoir metadata
            self.assertEqual(metadata["hachoir"]["Common"]["creation_date"], date_value)
            # Error should be logged
            mock_debug.assert_called_once()

    def test_check_dependency_import_error(self):
        """Test _check_dependency method with import errors."""
        # Create a fresh extractor to test the real method
        extractor = object.__new__(HachoirExtractor)
        extractor._check_dependency = HachoirExtractor._check_dependency.__get__(
            extractor
        )

        # Test with a module that definitely doesn't exist
        self.assertFalse(
            extractor._check_dependency("definitely_non_existent_module_12345")
        )

        # Test with a module that exists
        self.assertTrue(extractor._check_dependency("os"))

    def test_get_metadata_missing_mime_type(self):
        """Test get_metadata when basic metadata doesn't include mime_type."""
        basic_metadata = {"filename": "test.unknown"}
        hachoir_metadata = {"width": 1024}

        with patch.object(
            self.extractor, "get_basic_metadata", return_value=basic_metadata
        ):
            with patch.object(
                self.extractor,
                "_extract_hachoir_metadata",
                return_value=hachoir_metadata,
            ):
                metadata = self.extractor.get_metadata("test.unknown")

                # Should have basic and hachoir metadata
                self.assertEqual(metadata["width"], 1024)
                # Should not try format-specific extraction without mime_type
                self.assertNotIn("pdf_info", metadata)
                self.assertNotIn("docx_info", metadata)

    def test_extract_hachoir_metadata_no_parser(self):
        """Test _extract_hachoir_metadata when createParser returns None."""
        with patch("hachoir.parser.createParser", return_value=None):
            result = self.extractor._extract_hachoir_metadata("test.mp4")
            self.assertEqual(result, {})

    def test_extract_hachoir_metadata_no_metadata(self):
        """Test _extract_hachoir_metadata when extractMetadata returns None."""
        mock_parser = MagicMock()
        with patch("hachoir.parser.createParser", return_value=mock_parser):
            with patch("hachoir.metadata.extractMetadata", return_value=None):
                result = self.extractor._extract_hachoir_metadata("test.mp4")
                self.assertEqual(result, {})

    def test_process_metadata_item_no_values(self):
        """Test _process_metadata_item when meta_item has no values."""
        metadata = {"hachoir": {"Common": {}}}
        group_name = "Common"
        extracted_dates = {}

        # Create metadata item with no values
        meta_item = MagicMock()
        meta_item.key = "empty_field"
        meta_item.values = []

        self.extractor._process_metadata_item(
            meta_item, metadata, group_name, extracted_dates
        )

        # Nothing should be added to metadata since there are no values
        self.assertNotIn("empty_field", metadata["hachoir"]["Common"])

    def test_promote_important_metadata_missing_groups(self):
        """Test _promote_important_metadata when some metadata groups are missing."""
        metadata = {
            "hachoir": {
                "Common": {"width": 1024, "height": 768}
                # Missing "Video" and "Audio" groups
            }
        }

        # Should not raise any errors
        self.extractor._promote_important_metadata(metadata)

        # Should promote available metadata
        self.assertEqual(metadata["width"], 1024)
        self.assertEqual(metadata["height"], 768)

        # Should not have promoted non-existent fields
        self.assertNotIn("frame_rate", metadata)

    @patch("pypdf.PdfReader")
    def test_extract_pdf_metadata_no_pages(self, mock_pdf_reader):
        """Test PDF metadata extraction when there are no pages."""
        mock_pdf = MagicMock()
        mock_pdf_reader.return_value = mock_pdf
        mock_pdf.pages = []
        mock_pdf.metadata = None

        with patch("builtins.open", mock_open()):
            result = self.extractor._extract_pdf_metadata("test.pdf")

        self.assertEqual(result["pages_count"], 0)
        self.assertNotIn("first_page_preview", result)

    @patch("docx.Document")
    def test_extract_docx_metadata_minimal(self, mock_document):
        """Test DOCX metadata extraction with minimal document structure."""
        mock_doc = MagicMock()
        mock_doc.paragraphs = []
        mock_doc.tables = []
        mock_doc.sections = []

        # Mock core_properties to return None/empty
        mock_doc.core_properties = None
        mock_document.return_value = mock_doc

        result = self.extractor._extract_docx_metadata("test.docx")

        # Should have basic structure
        self.assertIn("document_structure", result)
        self.assertEqual(result["document_structure"]["paragraphs_count"], 0)
        self.assertEqual(result["document_structure"]["tables_count"], 0)
        self.assertEqual(result["document_structure"]["sections_count"], 0)

        # Should not have text statistics or preview
        self.assertNotIn("text_statistics", result)
        self.assertNotIn("text_preview", result)
        self.assertNotIn("core_properties", result)

    def test_can_handle_file_not_exists(self):
        """Test can_handle when file doesn't exist."""
        self.extractor.hachoir_available = True

        # Test with non-existent file
        with patch("os.path.isfile", return_value=False):
            result = self.extractor.can_handle("nonexistent.pdf")
            self.assertFalse(result)

    def test_can_handle_file_not_readable(self):
        """Test can_handle when file is not readable."""
        self.extractor.hachoir_available = True

        # Test with file that exists but is not readable
        with patch("os.path.isfile", return_value=True):
            with patch("os.access", return_value=False):
                result = self.extractor.can_handle("unreadable.pdf")
                self.assertFalse(result)

    def test_get_metadata_pdf_not_available(self):
        """Test get_metadata when PDF library is not available."""
        self.extractor.pypdf_available = False
        basic_metadata = {"filename": "test.pdf", "mime_type": "application/pdf"}
        hachoir_metadata = {"width": 1024}

        with patch.object(
            self.extractor, "get_basic_metadata", return_value=basic_metadata
        ):
            with patch.object(
                self.extractor,
                "_extract_hachoir_metadata",
                return_value=hachoir_metadata,
            ):
                metadata = self.extractor.get_metadata("test.pdf")

                # Should have basic and hachoir metadata
                self.assertEqual(metadata["width"], 1024)
                # Should not try PDF extraction since library is not available
                self.assertNotIn("pdf_info", metadata)

    def test_get_metadata_docx_not_available(self):
        """Test get_metadata when DOCX library is not available."""
        self.extractor.docx_available = False
        basic_metadata = {
            "filename": "test.docx",
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        hachoir_metadata = {"width": 1024}

        with patch.object(
            self.extractor, "get_basic_metadata", return_value=basic_metadata
        ):
            with patch.object(
                self.extractor,
                "_extract_hachoir_metadata",
                return_value=hachoir_metadata,
            ):
                metadata = self.extractor.get_metadata("test.docx")

                # Should have basic and hachoir metadata
                self.assertEqual(metadata["width"], 1024)
                # Should not try DOCX extraction since library is not available
                self.assertNotIn("docx_info", metadata)

    def test_extract_hachoir_metadata_warning_on_no_parser(self):
        """Test that warning is logged when parser creation fails."""
        with patch("hachoir.parser.createParser", return_value=None):
            with patch.object(self.extractor.logger, "warning") as mock_warning:
                result = self.extractor._extract_hachoir_metadata("test.mp4")

                self.assertEqual(result, {})
                mock_warning.assert_called_once()

    def test_extract_hachoir_metadata_warning_on_no_metadata(self):
        """Test that warning is logged when metadata extraction fails."""
        mock_parser = MagicMock()
        with patch("hachoir.parser.createParser", return_value=mock_parser):
            with patch("hachoir.metadata.extractMetadata", return_value=None):
                with patch.object(self.extractor.logger, "warning") as mock_warning:
                    result = self.extractor._extract_hachoir_metadata("test.mp4")

                    self.assertEqual(result, {})
                    mock_warning.assert_called_once()

    @patch("pypdf.PdfReader")
    def test_extract_pdf_metadata_text_extraction_exception(self, mock_pdf_reader):
        """Test PDF metadata extraction when text extraction raises an exception."""
        mock_pdf = MagicMock()
        mock_pdf_reader.return_value = mock_pdf
        mock_pdf.pages = [MagicMock()]
        mock_pdf.pages[0].extract_text.side_effect = Exception("Text extraction failed")
        mock_pdf.metadata = {"/Title": "Test"}

        with patch("builtins.open", mock_open()):
            with patch.object(self.extractor.logger, "debug") as mock_debug:
                result = self.extractor._extract_pdf_metadata("test.pdf")

                # Should still have pages count and document info
                self.assertEqual(result["pages_count"], 1)
                self.assertIn("document_info", result)
                # Should not have text preview due to exception
                self.assertNotIn("first_page_preview", result)
                # Should log the exception
                mock_debug.assert_called_once()

    def test_initialization_without_hachoir(self):
        """Test initialization when Hachoir is not available."""
        with patch.object(HachoirExtractor, "_check_dependency") as mock_check:
            # Make hachoir unavailable but others available
            mock_check.side_effect = lambda module: (
                module != "hachoir.parser" and module != "hachoir.metadata"
            )

            # Patch the LoggableMixin from the base_extractor module since it's inherited
            # We need to mock __init_logger__ but still create a logger attribute
            def mock_init_logger(self):
                self.logger = MagicMock()

            with patch(
                "ai_content_classifier.services.metadata.extractors.base_extractor.LoggableMixin.__init_logger__",
                mock_init_logger,
            ):
                extractor = HachoirExtractor()

                self.assertFalse(extractor.hachoir_available)

    @patch("pypdf.PdfReader")
    def test_extract_pdf_metadata_invalid_metadata_values(self, mock_pdf_reader):
        """Test PDF metadata extraction with invalid metadata values."""
        mock_pdf = MagicMock()
        mock_pdf_reader.return_value = mock_pdf
        mock_pdf.pages = [MagicMock()]
        mock_pdf.pages[0].extract_text.return_value = "Some text"

        # Setup metadata with invalid values (should be filtered out)
        mock_pdf.metadata = {
            "/Title": "Valid Title",
            "/Author": None,  # Should be filtered out
            "/Invalid": {},  # Should be filtered out
            "/CreationDate": "Valid Date",
        }

        with patch("builtins.open", mock_open()):
            result = self.extractor._extract_pdf_metadata("test.pdf")

        # Only valid metadata should be included
        self.assertEqual(result["document_info"]["Title"], "Valid Title")
        self.assertEqual(result["document_info"]["CreationDate"], "Valid Date")
        self.assertNotIn("Author", result["document_info"])
        self.assertNotIn("Invalid", result["document_info"])

    @patch("docx.Document")
    def test_extract_docx_metadata_core_properties_attribute_access(
        self, mock_document
    ):
        """Test DOCX core properties extraction with proper attribute handling."""
        mock_doc = MagicMock()
        mock_doc.paragraphs = [MagicMock(text="test")]
        mock_doc.tables = []
        mock_doc.sections = []

        # Create a real-like core properties object
        mock_core_props = MagicMock()
        mock_core_props.title = "Test Title"
        mock_core_props.author = "Test Author"
        mock_core_props.created = None  # Should be filtered out

        # Mock dir to return these properties
        with patch("builtins.dir") as mock_dir:
            mock_dir.return_value = ["title", "author", "created"]

            # Mock callable to return False for all (they're properties, not methods)
            with patch("builtins.callable") as mock_callable:
                mock_callable.return_value = False

                mock_doc.core_properties = mock_core_props
                mock_document.return_value = mock_doc

                result = self.extractor._extract_docx_metadata("test.docx")

                # Should include only non-None properties
                self.assertIn("core_properties", result)
                self.assertEqual(result["core_properties"]["title"], "Test Title")
                self.assertEqual(result["core_properties"]["author"], "Test Author")
                self.assertNotIn("created", result["core_properties"])

    def test_get_metadata_with_pdf_extraction_when_available(self):
        """Test get_metadata calls PDF extraction when library is available and mime type matches."""
        self.extractor.pypdf_available = True
        basic_metadata = {"filename": "test.pdf", "mime_type": "application/pdf"}
        hachoir_metadata = {"width": 1024}
        pdf_metadata = {"pages_count": 5}

        with patch.object(
            self.extractor, "get_basic_metadata", return_value=basic_metadata
        ):
            with patch.object(
                self.extractor,
                "_extract_hachoir_metadata",
                return_value=hachoir_metadata,
            ):
                with patch.object(
                    self.extractor, "_extract_pdf_metadata", return_value=pdf_metadata
                ) as mock_pdf:
                    metadata = self.extractor.get_metadata("test.pdf")

                    # Should call PDF extraction
                    mock_pdf.assert_called_once_with("test.pdf")
                    # Should wrap result in pdf_info
                    self.assertEqual(metadata["pdf_info"], pdf_metadata)

    def test_get_metadata_with_docx_extraction_when_available(self):
        """Test get_metadata calls DOCX extraction when library is available and mime type matches."""
        self.extractor.docx_available = True
        basic_metadata = {
            "filename": "test.docx",
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        hachoir_metadata = {"width": 1024}
        docx_metadata = {"document_structure": {"paragraphs_count": 10}}

        with patch.object(
            self.extractor, "get_basic_metadata", return_value=basic_metadata
        ):
            with patch.object(
                self.extractor,
                "_extract_hachoir_metadata",
                return_value=hachoir_metadata,
            ):
                with patch.object(
                    self.extractor, "_extract_docx_metadata", return_value=docx_metadata
                ) as mock_docx:
                    metadata = self.extractor.get_metadata("test.docx")

                    # Should call DOCX extraction
                    mock_docx.assert_called_once_with("test.docx")
                    # Should wrap result in docx_info
                    self.assertEqual(metadata["docx_info"], docx_metadata)

    def test_can_handle_with_extension_check_only(self):
        """Test can_handle focuses on extension when hachoir is available."""
        self.extractor.hachoir_available = True

        with patch("os.path.isfile", return_value=True):
            with patch("os.access", return_value=True):
                # Test extension not in priority list
                result = self.extractor.can_handle("test.xyz")
                self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
