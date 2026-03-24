"""Tests for base_generator.py"""

import pytest
import sys

from unittest.mock import Mock, patch
from PIL import Image

# Mock dependencies
sys.modules['core.logger'] = Mock()

# Mock LoggableMixin
class LoggableMixin:
    def __init_logger__(self):
        self.logger = Mock()

with patch('ai_content_classifier.core.logger.LoggableMixin', LoggableMixin):
    from ai_content_classifier.services.thumbnail.generators.base_generator import BaseThumbnailGenerator


class ConcreteThumbnailGenerator(BaseThumbnailGenerator):
    """Concrete implementation for testing the abstract base class"""
    
    def generate(self, image_path: str, size: tuple, quality_factor: float = 1.0):
        return Mock(spec=Image.Image)


class TestBaseThumbnailGenerator:
    
    def test_init_calls_logger_init(self):
        """Test that __init__ calls __init_logger__"""
        with patch.object(BaseThumbnailGenerator, '__init_logger__') as mock_logger_init:
            generator = ConcreteThumbnailGenerator()
            mock_logger_init.assert_called_once()
    
    def test_abstract_class_cannot_be_instantiated(self):
        """Test that the abstract base class cannot be instantiated directly"""
        with pytest.raises(TypeError):
            BaseThumbnailGenerator()
    
    def test_concrete_implementation_works(self):
        """Test that concrete implementation can be instantiated and used"""
        generator = ConcreteThumbnailGenerator()
        result = generator.generate("test.jpg", (100, 100), 1.0)
        assert result is not None
    
    def test_generate_method_signature(self):
        """Test that the generate method has the correct signature"""
        generator = ConcreteThumbnailGenerator()
        # Test with all parameters
        result = generator.generate("test.jpg", (100, 100), 0.5)
        assert result is not None
        
        # Test with default quality_factor
        result = generator.generate("test.jpg", (100, 100))
        assert result is not None