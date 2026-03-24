"""
Tests unitaires complets pour QtThumbnailFactory - Couverture 100%.
"""

import pytest
from unittest.mock import Mock


class TestQtThumbnailFactory:
    """Tests pour QtThumbnailFactory"""

    def setup_method(self):
        """Setup pour chaque test"""
        # Créer une vraie classe QPixmap mockée pour éviter isinstance issues
        class MockQPixmap:
            def __init__(self, is_null=False):
                self._is_null = is_null
                self._width = 100
                self._height = 100
                self._depth = 24
            
            def isNull(self):
                return self._is_null
            
            def width(self):
                return self._width
            
            def height(self):
                return self._height
            
            def depth(self):
                return self._depth
        
        self.MockQPixmap = MockQPixmap
        
        # Importer en assumant que PyQt6 est disponible
        try:
            from ai_content_classifier.core.memory.factories.qt_thumbnail_factory import QtThumbnailFactory
            
            self.format_handlers = {
                '.jpg': Mock(),
                '.png': Mock(),
                '.gif': Mock()
            }
            self.pil_generator = Mock()
            self.placeholder_generator = Mock()
            self.logger = Mock()
            
            self.factory = QtThumbnailFactory(
                format_handlers=self.format_handlers,
                pil_generator=self.pil_generator,
                placeholder_generator=self.placeholder_generator,
                logger=self.logger
            )
            self.qt_available = True
            
        except ImportError:
            self.qt_available = False
            self.factory = None

    def test_init(self):
        """Test du constructeur"""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")
            
        assert self.factory.format_handlers == self.format_handlers
        assert self.factory.pil_generator == self.pil_generator
        assert self.factory.placeholder_generator == self.placeholder_generator
        assert self.factory.logger == self.logger

    def test_get_key_basic(self):
        """Test génération de clé basique"""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")
            
        result = self.factory.get_key("/path/image.jpg", (150, 150), 0.8)
        assert result == "/path/image.jpg_150x150_0.8"

    def test_get_key_different_parameters(self):
        """Test génération de clé avec différents paramètres"""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")
            
        image_path = "/test/image.png"
        
        key1 = self.factory.get_key(image_path, (100, 100), 0.9)
        key2 = self.factory.get_key(image_path, (200, 150), 0.9)
        key3 = self.factory.get_key(image_path, (100, 100), 0.7)
        
        assert key1 != key2
        assert key1 != key3

    def test_create_with_handler(self):
        """Test création avec handler spécifique"""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")
            
        mock_qpixmap = self.MockQPixmap()
        self.format_handlers['.jpg'].return_value = mock_qpixmap
        
        result = self.factory.create("/test/image.jpg", (100, 100), 0.8)
        
        assert result == mock_qpixmap
        self.format_handlers['.jpg'].assert_called_once_with("/test/image.jpg", (100, 100), 0.8)

    def test_create_with_pil_generator(self):
        """Test création avec pil_generator par défaut"""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")
            
        mock_qpixmap = self.MockQPixmap()
        self.pil_generator.generate.return_value = mock_qpixmap
        
        result = self.factory.create("/test/image.bmp", (100, 100), 0.8)
        
        assert result == mock_qpixmap
        self.pil_generator.generate.assert_called_once_with("/test/image.bmp", (100, 100), 0.8)

    def test_create_handler_returns_none(self):
        """Test fallback quand handler retourne None"""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")
            
        self.format_handlers['.jpg'].return_value = None
        mock_placeholder = self.MockQPixmap()
        self.placeholder_generator.generate.return_value = mock_placeholder
        
        result = self.factory.create("/test/image.jpg", (100, 100), 0.8)
        
        assert result == mock_placeholder
        self.logger.warning.assert_called_once()

    def test_create_handler_exception(self):
        """Test fallback sur exception"""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")
            
        self.format_handlers['.jpg'].side_effect = RuntimeError("Handler failed")
        mock_placeholder = self.MockQPixmap()
        self.placeholder_generator.generate.return_value = mock_placeholder
        
        result = self.factory.create("/test/image.jpg", (100, 100), 0.8)
        
        assert result == mock_placeholder
        self.logger.error.assert_called_once()

    def test_create_case_insensitive_extensions(self):
        """Test extensions case-insensitive"""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")
            
        mock_qpixmap = self.MockQPixmap()
        self.format_handlers['.jpg'].return_value = mock_qpixmap
        
        result = self.factory.create("/test/image.JPG", (100, 100), 0.8)
        
        assert result == mock_qpixmap
        self.format_handlers['.jpg'].assert_called_once()

    def test_validate_valid_qpixmap(self):
        """Test validation avec QPixmap valide"""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")
            
        # Utiliser directement un mock avec patch
        from unittest.mock import patch
        mock_qpixmap = Mock()
        mock_qpixmap.isNull.return_value = False
        
        with patch('ai_content_classifier.core.memory.factories.qt_thumbnail_factory.isinstance', return_value=True):
            result = self.factory.validate(mock_qpixmap)
            assert result is True

    def test_validate_null_qpixmap(self):
        """Test validation QPixmap null"""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")
            
        from unittest.mock import patch
        mock_qpixmap = Mock()
        mock_qpixmap.isNull.return_value = True
        
        with patch('ai_content_classifier.core.memory.factories.qt_thumbnail_factory.isinstance', return_value=True):
            result = self.factory.validate(mock_qpixmap)
            assert result is False

    def test_validate_invalid_type(self):
        """Test validation type invalide"""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")
            
        from unittest.mock import patch
        
        with patch('ai_content_classifier.core.memory.factories.qt_thumbnail_factory.isinstance', return_value=False):
            assert self.factory.validate("string") is False
            assert self.factory.validate(None) is False
            assert self.factory.validate(123) is False

    def test_reset_always_true(self):
        """Test reset retourne toujours True"""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")
            
        assert self.factory.reset(self.MockQPixmap()) is True
        assert self.factory.reset(None) is True

    def test_estimate_size_success(self):
        """Test estimation taille réussie"""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")
            
        mock_qpixmap = self.MockQPixmap()
        mock_qpixmap._width = 200
        mock_qpixmap._height = 150
        mock_qpixmap._depth = 24
        
        result = self.factory.estimate_size(mock_qpixmap)
        assert result == 200 * 150 * 3  # 24 // 8 = 3

    def test_estimate_size_different_depths(self):
        """Test estimation avec différentes profondeurs"""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")
            
        # 32 bits
        mock_qpixmap = self.MockQPixmap()
        mock_qpixmap._width = 100
        mock_qpixmap._height = 100
        mock_qpixmap._depth = 32
        
        result = self.factory.estimate_size(mock_qpixmap)
        assert result == 100 * 100 * 4  # 32 // 8 = 4

    def test_estimate_size_exception(self):
        """Test estimation avec exception"""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")
            
        class BadQPixmap:
            def width(self):
                raise AttributeError("Width error")
        
        result = self.factory.estimate_size(BadQPixmap())
        assert result == 1024
