import unittest

from unittest.mock import patch
from datetime import datetime

from ai_content_classifier.core.logger import LoggableMixin

from ai_content_classifier.services.metadata.extractors.base_extractor import BaseMetadataExtractor

# Create a test class that implements the abstract methods
# but without using a custom __init__ constructor
class TestExtractor(BaseMetadataExtractor):
    # Instead of using __init__, we'll override setup_method
    # which is called by pytest before each test
    __test__ = False  # Tell pytest this is not a test class
    
    def can_handle(self, file_path: str) -> bool:
        return True
        
    def get_metadata(self, file_path: str) -> dict:
        return {"test": "metadata"}


class TestBaseMetadataExtractor(unittest.TestCase):
    """Test cases for the BaseMetadataExtractor class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create an instance of our test class
        self.extractor = TestExtractor()
    
    def test_initialization(self):
        """Test initialization of extractor."""
        self.assertIsInstance(self.extractor, BaseMetadataExtractor)
        self.assertIsInstance(self.extractor, LoggableMixin)
        self.assertTrue(hasattr(self.extractor, 'logger'))
        
    @patch('os.path.exists')
    def test_get_basic_metadata_nonexistent_file(self, mock_exists):
        """Test getting basic metadata from a nonexistent file."""
        mock_exists.return_value = False
        metadata = self.extractor.get_basic_metadata("nonexistent.txt")
        self.assertIn("error", metadata)
        self.assertEqual(metadata["error"], "File does not exist")
        
    @patch('os.path.exists')
    @patch('os.path.getsize')
    @patch('os.path.getmtime')
    @patch('os.path.getctime')
    def test_get_basic_metadata(self, mock_getctime, mock_getmtime, mock_getsize, mock_exists):
        """Test getting basic metadata from a file."""
        # Setup mocks
        mock_exists.return_value = True
        mock_getsize.return_value = 1024
        mock_getmtime.return_value = datetime.now().timestamp()
        mock_getctime.return_value = datetime.now().timestamp()
        
        # Get basic metadata
        metadata = self.extractor.get_basic_metadata("test.txt")
        
        # Check results
        self.assertEqual(metadata["filename"], "test.txt")
        self.assertEqual(metadata["extension"], ".txt")
        self.assertEqual(metadata["file_type"], "document")
        self.assertEqual(metadata["size"], 1024)
        self.assertIn("size_formatted", metadata)
        self.assertIn("created", metadata)
        self.assertIn("last_modified", metadata)
        
    def test_determine_file_type(self):
        """Test determining file type from extension."""
        # Test image extensions
        for ext in ['.jpg', '.jpeg', '.png', '.gif']:
            self.assertEqual(self.extractor._determine_file_type(ext), "image")
            
        # Test document extensions
        for ext in ['.pdf', '.doc', '.docx', '.txt']:
            self.assertEqual(self.extractor._determine_file_type(ext), "document")
            
        # Test other extensions
        self.assertEqual(self.extractor._determine_file_type('.unknown'), "other")
        
    def test_format_size(self):
        """Test formatting file size."""
        # Test various sizes
        self.assertEqual(self.extractor._format_size(500), "500 B")
        self.assertEqual(self.extractor._format_size(1024), "1.00 KB")
        self.assertEqual(self.extractor._format_size(1024 * 1024), "1.00 MB")
        self.assertEqual(self.extractor._format_size(1024 * 1024 * 1024), "1.00 GB")
        
if __name__ == '__main__':
    unittest.main()
