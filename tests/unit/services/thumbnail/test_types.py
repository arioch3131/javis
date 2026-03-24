"""Tests for types.py"""

from unittest.mock import Mock
from PIL import Image

from ai_content_classifier.services.thumbnail.types import ThumbnailResult


class TestThumbnailResult:
    
    def test_thumbnail_result_creation_minimal(self):
        """Test creation of ThumbnailResult with minimal required fields"""
        mock_thumbnail = Mock(spec=Image.Image)
        
        result = ThumbnailResult(
            success=True,
            path="/path/to/image.jpg",
            thumbnail=mock_thumbnail,
            size_str="1.5 MB",
            file_size=1572864
        )
        
        assert result.success is True
        assert result.path == "/path/to/image.jpg"
        assert result.thumbnail == mock_thumbnail
        assert result.size_str == "1.5 MB"
        assert result.file_size == 1572864
        assert result.error_message is None  # Default value
        assert result.format == ""  # Default value
        assert result.quality == 1.0  # Default value
    
    def test_thumbnail_result_creation_full(self):
        """Test creation of ThumbnailResult with all fields"""
        mock_thumbnail = Mock(spec=Image.Image)
        
        result = ThumbnailResult(
            success=False,
            path="/path/to/broken.jpg",
            thumbnail=mock_thumbnail,
            size_str="2.1 MB",
            file_size=2097152,
            error_message="Could not process image",
            format="JPEG",
            quality=0.8
        )
        
        assert result.success is False
        assert result.path == "/path/to/broken.jpg"
        assert result.thumbnail == mock_thumbnail
        assert result.size_str == "2.1 MB"
        assert result.file_size == 2097152
        assert result.error_message == "Could not process image"
        assert result.format == "JPEG"
        assert result.quality == 0.8
    
    def test_thumbnail_result_with_none_thumbnail(self):
        """Test ThumbnailResult with None thumbnail (failed case)"""
        result = ThumbnailResult(
            success=False,
            path="/path/to/invalid.jpg",
            thumbnail=None,
            size_str="Unknown",
            file_size=0,
            error_message="File not found"
        )
        
        assert result.success is False
        assert result.thumbnail is None
        assert result.error_message == "File not found"
    
    def test_thumbnail_result_with_qt_pixmap(self):
        """Test ThumbnailResult with Qt QPixmap thumbnail"""
        # Mock QPixmap (Qt thumbnail type)
        mock_qpixmap = Mock()
        mock_qpixmap.__class__.__name__ = "QPixmap"
        
        result = ThumbnailResult(
            success=True,
            path="/path/to/image.svg",
            thumbnail=mock_qpixmap,
            size_str="512 KB",
            file_size=524288,
            format="SVG"
        )
        
        assert result.success is True
        assert result.thumbnail == mock_qpixmap
        assert result.format == "SVG"
    
    def test_thumbnail_result_zero_file_size(self):
        """Test ThumbnailResult with zero file size"""
        result = ThumbnailResult(
            success=False,
            path="/path/to/empty.jpg",
            thumbnail=None,
            size_str="0 B",
            file_size=0
        )
        
        assert result.file_size == 0
        assert result.size_str == "0 B"
    
    def test_thumbnail_result_large_file_size(self):
        """Test ThumbnailResult with large file size"""
        large_size = 5 * 1024 * 1024 * 1024  # 5 GB
        
        result = ThumbnailResult(
            success=True,
            path="/path/to/huge.tiff",
            thumbnail=Mock(spec=Image.Image),
            size_str="5.0 GB",
            file_size=large_size
        )
        
        assert result.file_size == large_size
        assert result.size_str == "5.0 GB"
    
    def test_thumbnail_result_quality_extremes(self):
        """Test ThumbnailResult with extreme quality values"""
        # Minimum quality
        result_min = ThumbnailResult(
            success=True,
            path="/path/to/low_quality.jpg",
            thumbnail=Mock(spec=Image.Image),
            size_str="1 MB",
            file_size=1048576,
            quality=0.0
        )
        
        assert result_min.quality == 0.0
        
        # Maximum quality
        result_max = ThumbnailResult(
            success=True,
            path="/path/to/high_quality.jpg",
            thumbnail=Mock(spec=Image.Image),
            size_str="1 MB",
            file_size=1048576,
            quality=1.0
        )
        
        assert result_max.quality == 1.0
    
    def test_thumbnail_result_empty_strings(self):
        """Test ThumbnailResult with empty strings"""
        result = ThumbnailResult(
            success=True,
            path="",
            thumbnail=Mock(spec=Image.Image),
            size_str="",
            file_size=0,
            error_message="",
            format=""
        )
        
        assert result.path == ""
        assert result.size_str == ""
        assert result.error_message == ""
        assert result.format == ""
    
    def test_thumbnail_result_special_characters_in_path(self):
        """Test ThumbnailResult with special characters in path"""
        special_path = "/path/to/图片/image with spaces & symbols!@#.jpg"
        
        result = ThumbnailResult(
            success=True,
            path=special_path,
            thumbnail=Mock(spec=Image.Image),
            size_str="1 MB",
            file_size=1048576
        )
        
        assert result.path == special_path
    
    def test_thumbnail_result_dataclass_equality(self):
        """Test equality comparison of ThumbnailResult instances"""
        mock_thumbnail = Mock(spec=Image.Image)
        
        result1 = ThumbnailResult(
            success=True,
            path="/path/to/image.jpg",
            thumbnail=mock_thumbnail,
            size_str="1 MB",
            file_size=1048576
        )
        
        result2 = ThumbnailResult(
            success=True,
            path="/path/to/image.jpg",
            thumbnail=mock_thumbnail,
            size_str="1 MB",
            file_size=1048576
        )
        
        # Note: Dataclass equality compares all fields
        assert result1 == result2
    
    def test_thumbnail_result_dataclass_inequality(self):
        """Test inequality comparison of ThumbnailResult instances"""
        mock_thumbnail1 = Mock(spec=Image.Image)
        mock_thumbnail2 = Mock(spec=Image.Image)
        
        result1 = ThumbnailResult(
            success=True,
            path="/path/to/image1.jpg",
            thumbnail=mock_thumbnail1,
            size_str="1 MB",
            file_size=1048576
        )
        
        result2 = ThumbnailResult(
            success=True,
            path="/path/to/image2.jpg",  # Different path
            thumbnail=mock_thumbnail2,
            size_str="1 MB",
            file_size=1048576
        )
        
        assert result1 != result2