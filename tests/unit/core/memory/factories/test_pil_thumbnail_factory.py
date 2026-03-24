"""
Tests unitaires complets pour PilThumbnailFactory - Couverture 100%.
"""

from unittest.mock import Mock
from PIL import Image

from ai_content_classifier.core.memory.factories.pil_thumbnail_factory import PilThumbnailFactory


class TestPilThumbnailFactory:
    """Tests complets pour PilThumbnailFactory"""

    def setup_method(self):
        """Setup des mocks pour chaque test"""
        self.format_handlers = {
            '.jpg': Mock(),
            '.png': Mock(),
            '.gif': Mock()
        }
        self.pil_generator = Mock()
        self.placeholder_generator = Mock()
        self.logger = Mock()
        
        self.factory = PilThumbnailFactory(
            format_handlers=self.format_handlers,
            pil_generator=self.pil_generator,
            placeholder_generator=self.placeholder_generator,
            logger=self.logger
        )

    def test_init(self):
        """Test du constructeur"""
        assert self.factory.format_handlers == self.format_handlers
        assert self.factory.pil_generator == self.pil_generator
        assert self.factory.placeholder_generator == self.placeholder_generator
        assert self.factory.logger == self.logger

    def test_get_key_basic(self):
        """Test génération de clé basique"""
        image_path = "/path/to/image.jpg"
        size = (150, 150)
        quality_factor = 0.8
        
        result = self.factory.get_key(image_path, size, quality_factor)
        expected = "/path/to/image.jpg_150x150_0.8"
        
        assert result == expected

    def test_get_key_different_sizes(self):
        """Test génération de clé avec différentes tailles"""
        image_path = "/test/image.png"
        
        key1 = self.factory.get_key(image_path, (100, 100), 0.9)
        key2 = self.factory.get_key(image_path, (200, 150), 0.9)
        key3 = self.factory.get_key(image_path, (100, 100), 0.7)
        
        assert key1 != key2  # Tailles différentes
        assert key1 != key3  # Quality factors différents
        assert key1 == "/test/image.png_100x100_0.9"
        assert key2 == "/test/image.png_200x150_0.9"
        assert key3 == "/test/image.png_100x100_0.7"

    def test_create_success_with_handler(self):
        """Test création réussie avec handler spécifique"""
        image_path = "/path/to/image.jpg"
        size = (150, 150)
        quality_factor = 0.8
        
        # Mock d'une Image PIL
        mock_image = Mock(spec=Image.Image)
        self.format_handlers['.jpg'].return_value = mock_image
        
        result = self.factory.create(image_path, size, quality_factor)
        
        assert result == mock_image
        self.format_handlers['.jpg'].assert_called_once_with(image_path, size, quality_factor)
        self.placeholder_generator.generate.assert_not_called()
        self.logger.warning.assert_not_called()
        self.logger.error.assert_not_called()

    def test_create_success_with_default_pil_generator(self):
        """Test création avec pil_generator par défaut (extension non reconnue)"""
        image_path = "/path/to/image.bmp"  # Extension non dans format_handlers
        size = (150, 150)
        quality_factor = 0.8
        
        mock_image = Mock(spec=Image.Image)
        self.pil_generator.generate.return_value = mock_image
        
        result = self.factory.create(image_path, size, quality_factor)
        
        assert result == mock_image
        self.pil_generator.generate.assert_called_once_with(image_path, size, quality_factor)
        self.placeholder_generator.generate.assert_not_called()

    def test_create_handler_returns_none_fallback_to_placeholder(self):
        """Test fallback vers placeholder quand handler retourne None"""
        image_path = "/path/to/image.png"
        size = (150, 150)
        quality_factor = 0.8
        
        # Handler retourne None
        self.format_handlers['.png'].return_value = None
        
        mock_placeholder = Mock(spec=Image.Image)
        self.placeholder_generator.generate.return_value = mock_placeholder
        
        result = self.factory.create(image_path, size, quality_factor)
        
        assert result == mock_placeholder
        self.format_handlers['.png'].assert_called_once_with(image_path, size, quality_factor)
        self.placeholder_generator.generate.assert_called_once_with(image_path, size)
        self.logger.warning.assert_called_once_with(
            f"PIL Thumbnail generation failed for {image_path}, using placeholder."
        )

    def test_create_exception_fallback_to_placeholder(self):
        """Test fallback vers placeholder quand une exception est levée"""
        image_path = "/path/to/image.gif"
        size = (150, 150)
        quality_factor = 0.8
        
        # Handler lève une exception
        test_exception = IOError("Test exception")
        self.format_handlers['.gif'].side_effect = test_exception
        
        mock_placeholder = Mock(spec=Image.Image)
        self.placeholder_generator.generate.return_value = mock_placeholder
        
        result = self.factory.create(image_path, size, quality_factor)
        
        assert result == mock_placeholder
        self.placeholder_generator.generate.assert_called_once_with(image_path, size)
        self.logger.error.assert_called_once_with(
            f"Exception in PilThumbnailFactory create for {image_path}: {test_exception}"
        )

    def test_create_case_insensitive_extensions(self):
        """Test que les extensions sont traitées en minuscules"""
        image_path = "/path/to/image.JPG"  # Extension en majuscules
        size = (150, 150)
        quality_factor = 0.8
        
        mock_image = Mock(spec=Image.Image)
        self.format_handlers['.jpg'].return_value = mock_image
        
        result = self.factory.create(image_path, size, quality_factor)
        
        assert result == mock_image
        self.format_handlers['.jpg'].assert_called_once_with(image_path, size, quality_factor)

    def test_create_no_extension(self):
        """Test avec fichier sans extension"""
        image_path = "/path/to/imagefile"  # Pas d'extension
        size = (150, 150)
        quality_factor = 0.8
        
        mock_image = Mock(spec=Image.Image)
        self.pil_generator.generate.return_value = mock_image
        
        result = self.factory.create(image_path, size, quality_factor)
        
        assert result == mock_image
        self.pil_generator.generate.assert_called_once_with(image_path, size, quality_factor)

    def test_create_pil_generator_returns_none(self):
        """Test quand pil_generator retourne None"""
        image_path = "/path/to/image.unknown"
        size = (150, 150)
        quality_factor = 0.8
        
        # pil_generator retourne None
        self.pil_generator.generate.return_value = None
        
        mock_placeholder = Mock(spec=Image.Image)
        self.placeholder_generator.generate.return_value = mock_placeholder
        
        result = self.factory.create(image_path, size, quality_factor)
        
        assert result == mock_placeholder
        self.placeholder_generator.generate.assert_called_once_with(image_path, size)
        self.logger.warning.assert_called_once()

    def test_create_pil_generator_exception(self):
        """Test quand pil_generator lève une exception"""
        image_path = "/path/to/image.unknown"
        size = (150, 150)
        quality_factor = 0.8
        
        # pil_generator lève une exception
        test_exception = IOError("PIL generator failed")
        self.pil_generator.generate.side_effect = test_exception
        
        mock_placeholder = Mock(spec=Image.Image)
        self.placeholder_generator.generate.return_value = mock_placeholder
        
        result = self.factory.create(image_path, size, quality_factor)
        
        assert result == mock_placeholder
        self.logger.error.assert_called_once_with(
            f"Exception in PilThumbnailFactory create for {image_path}: {test_exception}"
        )

    def test_validate_valid_image(self):
        """Test validation d'une Image PIL valide"""
        # Créer une vraie image PIL pour le test
        real_image = Image.new('RGB', (100, 100), color='red')
        
        result = self.factory.validate(real_image)
        assert result is True

    def test_validate_mock_image(self):
        """Test validation avec mock d'Image"""
        mock_image = Mock(spec=Image.Image)
        
        result = self.factory.validate(mock_image)
        assert result is True

    def test_validate_invalid_objects(self):
        """Test validation d'objets invalides"""
        assert self.factory.validate(None) is False
        assert self.factory.validate("string") is False
        assert self.factory.validate(123) is False
        assert self.factory.validate([]) is False
        assert self.factory.validate({}) is False
        assert self.factory.validate(Mock()) is False  # Mock générique, pas Image

    def test_reset_always_true(self):
        """Test que reset retourne toujours True"""
        real_image = Image.new('RGB', (100, 100), color='blue')
        mock_image = Mock(spec=Image.Image)
        
        assert self.factory.reset(real_image) is True
        assert self.factory.reset(mock_image) is True
        assert self.factory.reset(None) is True  # Même avec None
        assert self.factory.reset("anything") is True  # Même avec n'importe quoi

    def test_estimate_size_success(self):
        """Test estimation de taille réussie"""
        mock_image = Mock(spec=Image.Image)
        mock_image.width = 200
        mock_image.height = 150
        mock_image.getbands.return_value = ('R', 'G', 'B')  # 3 bandes
        
        result = self.factory.estimate_size(mock_image)
        expected = 200 * 150 * 3  # width * height * nombre de bandes
        
        assert result == expected

    def test_estimate_size_different_bands(self):
        """Test estimation avec différents nombres de bandes"""
        # Image RGBA (4 bandes)
        mock_image_rgba = Mock(spec=Image.Image)
        mock_image_rgba.width = 100
        mock_image_rgba.height = 100
        mock_image_rgba.getbands.return_value = ('R', 'G', 'B', 'A')
        
        result_rgba = self.factory.estimate_size(mock_image_rgba)
        assert result_rgba == 100 * 100 * 4
        
        # Image en niveaux de gris (1 bande)
        mock_image_gray = Mock(spec=Image.Image)
        mock_image_gray.width = 50
        mock_image_gray.height = 50
        mock_image_gray.getbands.return_value = ('L',)
        
        result_gray = self.factory.estimate_size(mock_image_gray)
        assert result_gray == 50 * 50 * 1

    def test_estimate_size_getbands_exception(self):
        """Test fallback quand getbands() lève une exception"""
        mock_image = Mock(spec=Image.Image)
        mock_image.width = 100
        mock_image.height = 100
        mock_image.getbands.side_effect = AttributeError("getbands failed")
        
        result = self.factory.estimate_size(mock_image)
        assert result == 1024  # Fallback size

    def test_estimate_size_real_image(self):
        """Test estimation avec vraie image PIL"""
        real_image = Image.new('RGB', (300, 200), color='green')
        
        result = self.factory.estimate_size(real_image)
        expected = 300 * 200 * 3  # RGB = 3 bandes
        
        assert result == expected

    def test_comprehensive_workflow(self):
        """Test workflow complet avec vraie image"""
        image_path = "/test/complete/workflow.jpg"
        size = (128, 128)
        quality_factor = 0.75
        
        # Mock d'image réussie
        mock_image = Mock(spec=Image.Image)
        mock_image.width = 128
        mock_image.height = 128
        mock_image.getbands.return_value = ('R', 'G', 'B')
        
        self.format_handlers['.jpg'].return_value = mock_image
        
        # Test du workflow complet
        key = self.factory.get_key(image_path, size, quality_factor)
        thumbnail = self.factory.create(image_path, size, quality_factor)
        is_valid = self.factory.validate(thumbnail)
        can_reset = self.factory.reset(thumbnail)
        estimated_size = self.factory.estimate_size(thumbnail)
        
        # Assertions
        assert key == "/test/complete/workflow.jpg_128x128_0.75"
        assert thumbnail == mock_image
        assert is_valid is True
        assert can_reset is True
        assert estimated_size == 128 * 128 * 3
        
        # Vérifications des appels
        self.format_handlers['.jpg'].assert_called_once_with(image_path, size, quality_factor)
        self.logger.warning.assert_not_called()
        self.logger.error.assert_not_called()

    def test_edge_cases(self):
        """Test des cas limites"""
        # Taille 0
        result = self.factory.get_key("/test.jpg", (0, 0), 1.0)
        assert result == "/test.jpg_0x0_1.0"
        
        # Quality factor négatif
        result = self.factory.get_key("/test.jpg", (100, 100), -0.5)
        assert result == "/test.jpg_100x100_-0.5"
        
        # Chemin vide
        result = self.factory.get_key("", (100, 100), 0.8)
        assert result == "_100x100_0.8"

    def test_multiple_extensions(self):
        """Test avec fichiers ayant plusieurs extensions"""
        image_path = "/path/to/image.backup.jpg"
        size = (100, 100)
        quality_factor = 0.8
        
        mock_image = Mock(spec=Image.Image)
        self.format_handlers['.jpg'].return_value = mock_image
        
        result = self.factory.create(image_path, size, quality_factor)
        
        assert result == mock_image
        self.format_handlers['.jpg'].assert_called_once_with(image_path, size, quality_factor)

    def test_format_handlers_modification(self):
        """Test que les format_handlers peuvent être modifiés"""
        # Ajouter un nouveau handler
        new_handler = Mock()
        self.factory.format_handlers['.webp'] = new_handler
        
        image_path = "/test/image.webp"
        size = (150, 150)
        quality_factor = 0.9
        
        mock_image = Mock(spec=Image.Image)
        new_handler.return_value = mock_image
        
        result = self.factory.create(image_path, size, quality_factor)
        
        assert result == mock_image
        new_handler.assert_called_once_with(image_path, size, quality_factor)

    def test_logger_integration(self):
        """Test intégration complète avec le logger"""
        image_path = "/test/problematic.jpg"
        size = (100, 100)
        quality_factor = 0.8
        
        # Premier cas : handler retourne None
        self.format_handlers['.jpg'].return_value = None
        mock_placeholder = Mock(spec=Image.Image)
        self.placeholder_generator.generate.return_value = mock_placeholder
        
        self.factory.create(image_path, size, quality_factor)
        self.logger.warning.assert_called_once()
        
        # Reset du logger
        self.logger.reset_mock()
        
        # Deuxième cas : exception
        self.format_handlers['.jpg'].side_effect = IOError("File corrupted")
        
        self.factory.create(image_path, size, quality_factor)
        self.logger.error.assert_called_once_with(
            f"Exception in PilThumbnailFactory create for {image_path}: {IOError("File corrupted")}"
        )