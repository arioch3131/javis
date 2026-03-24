import unittest

from datetime import datetime
from unittest.mock import patch, MagicMock

from ai_content_classifier.services.metadata.extractors.pillow_extractor import PillowImageExtractor


class TestPillowImageExtractor(unittest.TestCase):
    """Test cases for the PillowImageExtractor class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create the extractor
        with patch('importlib.import_module') as mock_import:
            mock_import.return_value = MagicMock()
            self.extractor = PillowImageExtractor()
            
            

    def test_initialization(self):
        """Test extractor initialization."""
        # Check supported extensions
        self.assertTrue(len(self.extractor.supported_extensions) > 0)
        self.assertIn('.jpg', self.extractor.supported_extensions)
        self.assertIn('.png', self.extractor.supported_extensions)
        
        # Check EXIF date tags
        self.assertTrue(len(self.extractor.EXIF_DATE_TAGS) > 0)
        
        # Check EXIF tag mappings
        self.assertTrue(len(self.extractor.IMPORTANT_EXIF_TAGS) > 0)
        
        # Check GPS tag mappings
        self.assertTrue(len(self.extractor.GPS_TAG_MAPPING) > 0)

    @patch('PIL.Image.open')
    def test_get_metadata_general_exception(self, mock_image_open):
        mock_image_open.side_effect = Exception("Simulated image open error")
        metadata = self.extractor.get_metadata('test.jpg')
        self.assertIn('error', metadata)
        self.assertEqual(metadata['error'], 'Simulated image open error')

    def test_can_handle(self):
        """Test can_handle method for supported and unsupported files."""
        # Test with Pillow available
        self.extractor.pillow_available = True
        
        # Test supported types
        for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            self.assertTrue(self.extractor.can_handle(f'test{ext}'))
        
        # Test unsupported types
        for ext in ['.mp3', '.mp4', '.pdf', '.xyz']:
            self.assertFalse(self.extractor.can_handle(f'test{ext}'))
        
        # Test when Pillow is not available
        self.extractor.pillow_available = False
        self.assertFalse(self.extractor.can_handle('test.jpg'))

    @patch('PIL.Image.open')
    def test_get_metadata_basic_image_info(self, mock_image_open):
        """Test extracting basic image metadata."""
        # Create mock image
        mock_img = MagicMock()
        mock_img.width = 800
        mock_img.height = 600
        mock_img.format = 'JPEG'
        mock_img.mode = 'RGB'
        mock_img.info = {}
        
        # Set up mock to return our test image
        mock_image_open.return_value.__enter__.return_value = mock_img
        
        # Get metadata
        with patch.object(self.extractor, 'get_basic_metadata', return_value={'filename': 'test.jpg'}):
            metadata = self.extractor.get_metadata('test.jpg')
        
        # Verify basic image info was extracted
        self.assertEqual(metadata['width'], 800)
        self.assertEqual(metadata['height'], 600)
        self.assertEqual(metadata['format'], 'JPEG')
        self.assertEqual(metadata['mode'], 'RGB')
        self.assertEqual(metadata['aspect_ratio'], 1.33)  # 800/600 = 1.33

    @patch('PIL.Image.open')
    def test_get_metadata_without_pillow(self, mock_image_open):
        """Test metadata extraction when Pillow is not available."""
        # Set Pillow as unavailable
        self.extractor.pillow_available = False
        
        # Get metadata
        with patch.object(self.extractor, 'get_basic_metadata', return_value={'filename': 'test.jpg'}):
            metadata = self.extractor.get_metadata('test.jpg')
        
        # Verify error was reported
        self.assertTrue('error' in metadata)
        self.assertEqual(metadata['error'], 'Pillow library is not installed')
        
        # Verify Image.open was not called
        mock_image_open.assert_not_called()

    @patch('PIL.Image.open')
    def test_get_metadata_with_exif_data(self, mock_image_open):
        """Test extracting EXIF metadata."""
        # Create mock image
        mock_img = MagicMock()
        mock_img.width = 800
        mock_img.height = 600
        mock_img.format = 'JPEG'
        mock_img.mode = 'RGB'
        mock_img.info = {}
        
        # Mock EXIF data
        mock_exif = {
            0x010F: 'Camera Maker',  # Make
            0x0110: 'Camera Model',  # Model
            0x8769: {  # ExifIFD
                0x829A: (1, 125),  # ExposureTime
                0x8827: 100,  # ISO
            },
            0x8825: {  # GPSInfo
                1: 'N',  # GPSLatitudeRef
                2: ((35, 1), (40, 1), (0, 1)),  # GPSLatitude
                3: 'W',  # GPSLongitudeRef
                4: ((120, 1), (30, 1), (0, 1)),  # GPSLongitude
            }
        }
        
        # Set up mock EXIF data
        mock_img._getexif = MagicMock(return_value=mock_exif)
        
        # Mock EXIF tags
        exif_tags = {
            0x010F: 'Make',
            0x0110: 'Model',
            0x8769: 'ExifIFD',
            0x829A: 'ExposureTime',
            0x8827: 'ISOSpeedRatings',
            0x8825: 'GPSInfo'
        }
        
        # Mock GPS tags
        gps_tags = {
            1: 'GPSLatitudeRef',
            2: 'GPSLatitude',
            3: 'GPSLongitudeRef',
            4: 'GPSLongitude'
        }
        
        # Set up mock to return our test image
        mock_image_open.return_value.__enter__.return_value = mock_img
        
        # Get metadata
        with patch.object(self.extractor, 'get_basic_metadata', return_value={'filename': 'test.jpg'}):
            with patch('PIL.ExifTags.TAGS', exif_tags), patch('PIL.ExifTags.GPSTAGS', gps_tags):
                metadata = self.extractor.get_metadata('test.jpg')
        
        # Verify EXIF data was extracted
        self.assertEqual(metadata['camera_make'], 'Camera Maker')
        self.assertEqual(metadata['camera_model'], 'Camera Model')
        self.assertEqual(metadata['exif']['Make'], 'Camera Maker')
        self.assertEqual(metadata['exif']['Model'], 'Camera Model')
        
        # Verify GPS info
        self.assertIn('gps', metadata)
        self.assertIn('latitude', metadata['gps'])

    @patch('PIL.Image.open')
    def test_extract_date_from_exif(self, mock_image_open):
        """Test extracting creation date from EXIF."""
        # Create mock image with date
        mock_img = MagicMock()
        mock_img.width = 800
        mock_img.height = 600
        mock_img.format = 'JPEG'
        mock_img.info = {}
        
        # Mock EXIF data with date
        date_str = '2021:05:15 12:30:45'
        mock_exif = {
            0x9003: date_str  # DateTimeOriginal
        }
        
        # Set up mock EXIF data
        mock_img._getexif = MagicMock(return_value=mock_exif)
        
        # Set up mock to return our test image
        mock_image_open.return_value.__enter__.return_value = mock_img
        
        # Create metadata with EXIF data
        metadata = {
            'exif': {
                'DateTimeOriginal': date_str
            }
        }
        
        # Extract date
        self.extractor._extract_date_from_exif(metadata)
        
        # Verify date was extracted correctly
        self.assertIn('creation_date', metadata)
        self.assertEqual(metadata['creation_date'], datetime(2021, 5, 15, 12, 30, 45))

    def test_process_gps_coordinates(self):
        """Test processing GPS coordinates."""
        # Create metadata with GPS data
        metadata = {
            'gps': {
                'latitude': ((35, 1), (10, 1), (30, 1)),
                'longitude': ((118, 1), (25, 1), (15, 1)),
                'GPSLatitudeRef': 'N',
                'GPSLongitudeRef': 'W'
            }
        }
        
        # Process GPS coordinates
        self.extractor._process_gps_coordinates(metadata)
        
        # Verify coordinates were processed
        self.assertIn('decimal_latitude', metadata['gps'])
        self.assertIn('decimal_longitude', metadata['gps'])
        self.assertIn('maps_url', metadata['gps'])
        
        # Verify correct conversion
        # 35° 10' 30" N = 35.175°
        # 118° 25' 15" W = -118.420833°
        self.assertAlmostEqual(metadata['gps']['decimal_latitude'], 35.175, places=3)
        self.assertAlmostEqual(metadata['gps']['decimal_longitude'], -118.420833, places=3)

    def test_convert_to_decimal_degrees(self):
        """Test converting DMS coordinates to decimal degrees."""
        # Test regular format
        dms = (35, 10, 30)  # 35° 10' 30"
        decimal = self.extractor._convert_to_decimal_degrees(dms)
        self.assertAlmostEqual(decimal, 35.175, places=3)
        
        # Test with fractions
        dms = ((35, 1), (10, 1), (30, 1))  # 35° 10' 30"
        decimal = self.extractor._convert_to_decimal_degrees(dms)
        self.assertAlmostEqual(decimal, 35.175, places=3)
        
        # Test with unexpected format (should return as is)
        unexpected = "35.175"
        result = self.extractor._convert_to_decimal_degrees(unexpected)
        self.assertEqual(result, unexpected)

    def test_generate_caption(self):
        """Test generating an image caption from metadata."""
        # Create sample metadata
        metadata = {
            'filename': 'test.jpg',
            'width': 3000,
            'height': 2000,
            'format': 'JPEG',
            'camera_make': 'Canon',
            'camera_model': 'EOS 5D',
            'creation_date': datetime(2021, 5, 15)
        }
        
        # Generate caption
        caption = self.extractor._generate_caption(metadata)
        
        # Verify caption contains expected information
        self.assertIn('3000x2000', caption)
        self.assertIn('JPEG', caption)
        self.assertIn('Canon', caption)
        self.assertIn('EOS 5D', caption)
        self.assertIn('May 15, 2021', caption)
        
        # Test with minimal metadata
        minimal_metadata = {
            'filename': 'test.jpg'
        }
        
        minimal_caption = self.extractor._generate_caption(minimal_metadata)
        self.assertIn('test.jpg', minimal_caption)

    @patch('PIL.Image.open')
    def test_format_specific_handlers(self, mock_image_open):
        """Test format-specific metadata handlers."""
        # Test JPEG handler
        jpeg_handler = self.extractor._get_format_handler('JPEG')
        self.assertEqual(jpeg_handler, self.extractor._process_jpeg_specific)
        
        # Test PNG handler
        png_handler = self.extractor._get_format_handler('PNG')
        self.assertEqual(png_handler, self.extractor._process_png_specific)
        
        # Test GIF handler
        gif_handler = self.extractor._get_format_handler('GIF')
        self.assertEqual(gif_handler, self.extractor._process_gif_specific)
        
        # Test non-existent handler
        no_handler = self.extractor._get_format_handler('XYZ')
        self.assertIsNone(no_handler)

    @patch('importlib.import_module', side_effect=ImportError)
    def test_check_dependency_import_error(self, mock_import_module):
        """Test _check_dependency when import fails."""
        with self.assertLogs(self.extractor.logger, level='WARNING') as cm:
            extractor_for_test = PillowImageExtractor()
            self.assertFalse(extractor_for_test.pillow_available)
            self.assertIn("Pillow library not available. Image metadata extraction will not work.", cm.output[0])

    @patch('PIL.Image.open')
    def test_get_metadata_exif_tags_import_error(self, mock_image_open):
        """Test get_metadata when PIL.ExifTags cannot be imported."""
        mock_img = MagicMock()
        mock_img.width = 100
        mock_img.height = 100
        mock_img.format = 'JPEG'
        mock_img.mode = 'RGB'
        mock_img.info = {}
        mock_img._getexif = MagicMock(return_value={}) # No EXIF data for this test
        
        mock_image_open.return_value.__enter__.return_value = mock_img
        
        with patch('PIL.ExifTags.TAGS', new=None), patch('PIL.ExifTags.GPSTAGS', new=None):
            with patch.object(self.extractor, 'get_basic_metadata', return_value={'filename': 'test.jpg'}):
                metadata = self.extractor.get_metadata('test.jpg')
        
        self.assertIn('exif', metadata)
        self.assertIn('gps', metadata)
        self.assertIn('icc_profile', metadata)
        self.assertFalse(metadata['exif']) # Should be empty as TAGS is None

    @patch('PIL.Image.open')
    def test_extract_exif_data_no_exif(self, mock_image_open):
        """Test _extract_exif_data when no EXIF data is present."""
        mock_img = MagicMock()
        mock_img._getexif = MagicMock(return_value=None)
        mock_img.getexif = MagicMock(return_value=None)
        
        metadata = {"exif": {}, "gps": {}}
        self.extractor._extract_exif_data(mock_img, metadata, {}, {})
        self.assertFalse(metadata["exif"])
        self.assertFalse(metadata["gps"])

    @patch('PIL.Image.open')
    def test_extract_exif_data_empty_exif(self, mock_image_open):
        """Test _extract_exif_data when EXIF data is empty."""
        mock_img = MagicMock()
        mock_img._getexif = MagicMock(return_value={})
        
        metadata = {"exif": {}, "gps": {}}
        self.extractor._extract_exif_data(mock_img, metadata, {}, {})
        self.assertFalse(metadata["exif"])
        self.assertFalse(metadata["gps"])

    @patch('PIL.Image.open')
    def test_extract_exif_data_getexif_path(self, mock_image_open):
        """Test _extract_exif_data when img.getexif() is used."""
        mock_img = MagicMock()
        mock_img._getexif = None  # Simulate _getexif not being available
        mock_img.getexif = MagicMock(return_value={0x010F: 'Test Make'})
        
        metadata = {"exif": {}, "gps": {}}
        exif_tags = {0x010F: 'Make'}
        gps_tags = {}
        self.extractor._extract_exif_data(mock_img, metadata, exif_tags, gps_tags)
        self.assertIn('Make', metadata["exif"])
        self.assertEqual(metadata["exif"]['Make'], 'Test Make')

    def test_sanitize_exif_value_bytes(self):
        """Test _sanitize_exif_value with bytes."""
        self.assertEqual(self.extractor._sanitize_exif_value(b'some_bytes'), 'binary_data')

    def test_sanitize_exif_value_tuple_int(self):
        """Test _sanitize_exif_value with tuple of integers."""
        self.assertEqual(self.extractor._sanitize_exif_value((1, 2, 3)), (1, 2, 3))

    def test_sanitize_exif_value_iterable_exception(self):
        """Test _sanitize_exif_value with iterable that raises exception on list conversion."""
        class BadIterable:
            def __iter__(self):
                raise TypeError("Cannot iterate")
        self.assertEqual(
            self.extractor._sanitize_exif_value(BadIterable()),
            f"<{BadIterable.__module__}.{BadIterable.__qualname__}>",
        )

    def test_sanitize_exif_value_other(self):
        """Test _sanitize_exif_value with other types."""
        self.assertEqual(self.extractor._sanitize_exif_value(123), 123)
        self.assertEqual(self.extractor._sanitize_exif_value(1.23), 1.23)
        self.assertEqual(self.extractor._sanitize_exif_value("test"), "test")
        self.assertEqual(self.extractor._sanitize_exif_value(True), True)
        self.assertIsNone(self.extractor._sanitize_exif_value(None))

    def test_extract_date_from_exif_alt_format(self):
        """Test _extract_date_from_exif with alternative date format."""
        metadata = {'exif': {'DateTimeOriginal': '2022-01-01 10:00:00'}}
        self.extractor._extract_date_from_exif(metadata)
        self.assertEqual(metadata['creation_date'], datetime(2022, 1, 1, 10, 0, 0))

    def test_extract_date_from_exif_invalid_format(self):
        """Test _extract_date_from_exif with invalid date format."""
        metadata = {'exif': {'DateTimeOriginal': 'invalid-date'}}
        with patch.object(self.extractor.logger, 'debug') as mock_debug:
            self.extractor._extract_date_from_exif(metadata)
            self.assertNotIn('creation_date', metadata)
            mock_debug.assert_called_once()

    def test_extract_date_from_exif_non_string_date(self):
        """Test _extract_date_from_exif with non-string date value."""
        metadata = {'exif': {'DateTimeOriginal': 12345}}
        with patch.object(self.extractor.logger, 'debug') as mock_debug:
            self.extractor._extract_date_from_exif(metadata)
            self.assertNotIn('creation_date', metadata)
            mock_debug.assert_called_once()

    def test_process_gps_coordinates_exception(self):
        """Test _process_gps_coordinates with malformed GPS data."""
        metadata = {'gps': {'latitude': 'bad_lat', 'longitude': 'bad_lon'}}
        self.extractor._process_gps_coordinates(metadata)
        # The current implementation passes through malformed data as-is
        # This is actually the intended behavior for graceful error handling
        self.assertIn('decimal_latitude', metadata['gps'])
        self.assertEqual(metadata['gps']['decimal_latitude'], 'bad_lat')
        self.assertIn('decimal_longitude', metadata['gps'])
        self.assertEqual(metadata['gps']['decimal_longitude'], 'bad_lon')
        self.assertIn('maps_url', metadata['gps'])
        self.assertEqual(metadata['gps']['maps_url'], 'https://maps.google.com/maps?q=bad_lat,bad_lon')

    def test_convert_to_decimal_degrees_non_tuple(self):
        """Test _convert_to_decimal_degrees with non-tuple input."""
        self.assertEqual(self.extractor._convert_to_decimal_degrees("not_a_tuple"), "not_a_tuple")

    @patch('PIL.ImageCms.getOpenProfile', side_effect=Exception("Simulated ImageCms error"))
    @patch('PIL.ImageCms.getProfileDescription', side_effect=Exception("Simulated ImageCms error"))
    def test_extract_icc_profile_exception(self, mock_get_profile_description, mock_get_open_profile):
        """Test _extract_icc_profile when ImageCms operations raise exceptions."""
        mock_img = MagicMock()
        mock_img.info = {"icc_profile": b"some_profile_data"}
        metadata = {}
        with patch.object(self.extractor.logger, 'debug') as mock_debug:
            self.extractor._extract_icc_profile(mock_img, metadata)
            self.assertIn('has_icc_profile', metadata)
            self.assertTrue(metadata['has_icc_profile'])
            self.assertIn('icc_profile', metadata)
            self.assertIn('size', metadata['icc_profile'])
            self.assertNotIn('description', metadata['icc_profile'])
            mock_debug.assert_called_once()

    def test_extract_icc_profile_import_error(self):
        """Test _extract_icc_profile when ImageCms cannot be imported."""
        mock_img = MagicMock()
        mock_img.info = {"icc_profile": b"some_profile_data"}
        metadata = {}
        
        # Use patch.object to mock the import directly in the method's context
        # We need to patch where the import happens (inside the method)
        with patch('builtins.__import__') as mock_import:
            # Configure the mock to raise ImportError for PIL.ImageCms imports
            def side_effect(name, globals=None, locals=None, fromlist=(), level=0):
                if fromlist and 'ImageCms' in fromlist and name == 'PIL':
                    raise ImportError("No module named 'PIL.ImageCms'")
                # For all other imports, use the real import
                return __import__(name, globals, locals, fromlist, level)
            
            mock_import.side_effect = side_effect
            
            with patch.object(self.extractor.logger, 'debug') as mock_debug:
                self.extractor._extract_icc_profile(mock_img, metadata)
                self.assertIn('has_icc_profile', metadata)
                self.assertTrue(metadata['has_icc_profile'])
                self.assertIn('icc_profile', metadata)
                self.assertIn('size', metadata['icc_profile'])
                self.assertNotIn('description', metadata['icc_profile'])
                mock_debug.assert_called_once()

    @patch.object(PillowImageExtractor, '_estimate_jpeg_quality', side_effect=Exception("Quality estimate error"))
    def test_process_jpeg_specific_quality_exception(self, mock_estimate_quality):
        """Test _process_jpeg_specific when quality estimation raises an exception."""
        mock_img = MagicMock()
        mock_img.applist = [(b'APP0', b'')]
        mock_img.info = {"progression": True}
        
        result = self.extractor._process_jpeg_specific(mock_img, 'test.jpg')
        self.assertIn('jpeg_info', result)
        self.assertIn('markers', result['jpeg_info'])
        self.assertIn('progressive', result['jpeg_info'])
        self.assertNotIn('estimated_quality', result['jpeg_info'])

    def test_process_png_specific_non_bytes_chunk(self):
        """Test _process_png_specific with non-bytes chunk type."""
        mock_img = MagicMock()
        mock_img.png.chunks = [('IHDR', b''), (123, b'')] # 123 is not bytes
        mock_img.info = {"transparency": True}
        
        result = self.extractor._process_png_specific(mock_img, 'test.png')
        self.assertIn('png_info', result)
        self.assertIn('chunks', result['png_info'])
        self.assertIn('IHDR', result['png_info']['chunks'])
        self.assertIn(123, result['png_info']['chunks']) # Should be 123, not '123'
        self.assertTrue(result['png_info']['has_transparency'])

    def test_process_png_specific_animated(self):
        """Test _process_png_specific with animated PNG."""
        mock_img = MagicMock()
        mock_img.png.chunks = []
        mock_img.info = {"loop": 0, "duration": 100}
        
        result = self.extractor._process_png_specific(mock_img, 'animated.png')
        self.assertIn('png_info', result)
        self.assertTrue(result['png_info']['is_animated'])
        self.assertEqual(result['png_info']['frame_duration'], 100)
        self.assertEqual(result['png_info']['loop_count'], 0)

    def test_process_gif_specific_seek_exception(self):
        """Test _process_gif_specific when img.seek raises an exception other than EOFError."""
        mock_img = MagicMock()
        mock_img.info = {"duration": 100, "loop": 0, "transparency": True}
        mock_img.seek.side_effect = Exception("Simulated seek error")
        
        result = self.extractor._process_gif_specific(mock_img, 'test.gif')
        self.assertIn('gif_info', result)
        self.assertIn('is_animated', result['gif_info'])
        self.assertIn('frame_duration', result['gif_info'])
        self.assertIn('loop_count', result['gif_info'])
        self.assertIn('has_transparency', result['gif_info'])
        self.assertNotIn('frame_count', result['gif_info'])

    def test_process_tiff_specific_import_error(self):
        """Test _process_tiff_specific when TiffImagePlugin cannot be imported."""
        mock_img = MagicMock()
        mock_img.n_frames = 2
        
        # Mock the specific import that happens inside the method
        def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == 'PIL' and fromlist and 'TiffImagePlugin' in fromlist:
                raise ImportError("No module named 'PIL.TiffImagePlugin'")
            return __import__(name, globals, locals, fromlist, level)
        
        with patch('builtins.__import__', side_effect=mock_import):
            result = self.extractor._process_tiff_specific(mock_img, 'test.tif')
            self.assertFalse(result)  # Should return empty dict as no tiff_info is added

    def test_process_tiff_specific_no_n_frames(self):
        """Test _process_tiff_specific when img has no n_frames attribute."""
        mock_img = MagicMock()
        del mock_img.n_frames # Simulate no n_frames attribute
        
        result = self.extractor._process_tiff_specific(mock_img, 'test.tif')
        self.assertFalse(result)

    def test_process_tiff_specific_single_frame(self):
        """Test _process_tiff_specific with a single-frame TIFF."""
        mock_img = MagicMock()
        mock_img.n_frames = 1
        
        result = self.extractor._process_tiff_specific(mock_img, 'test.tif')
        self.assertFalse(result)

    def test_process_tiff_specific_multi_frame(self):
        """Test _process_tiff_specific with a multi-frame TIFF."""
        mock_img = MagicMock()
        mock_img.n_frames = 5
        
        result = self.extractor._process_tiff_specific(mock_img, 'test.tif')
        self.assertIn('tiff_info', result)
        self.assertEqual(result['tiff_info']['page_count'], 5)

    def test_process_webp_specific_animated_no_n_frames(self):
        """Test _process_webp_specific with animated WebP but no n_frames."""
        mock_img = MagicMock()
        mock_img.is_animated = True
        mock_img.info = {"lossless": True}
        del mock_img.n_frames # Simulate no n_frames attribute
        
        result = self.extractor._process_webp_specific(mock_img, 'test.webp')
        self.assertIn('webp_info', result)
        self.assertTrue(result['webp_info']['is_animated'])
        self.assertNotIn('frame_count', result['webp_info'])
        self.assertTrue(result['webp_info']['lossless'])

    def test_process_webp_specific_animated_with_n_frames(self):
        """Test _process_webp_specific with animated WebP and n_frames."""
        mock_img = MagicMock()
        mock_img.is_animated = True
        mock_img.n_frames = 10
        mock_img.info = {"lossless": False}
        
        result = self.extractor._process_webp_specific(mock_img, 'test.webp')
        self.assertIn('webp_info', result)
        self.assertTrue(result['webp_info']['is_animated'])
        self.assertEqual(result['webp_info']['frame_count'], 10)
        self.assertFalse(result['webp_info']['lossless'])

    def test_process_webp_specific_not_animated(self):
        """Test _process_webp_specific with non-animated WebP."""
        mock_img = MagicMock()
        mock_img.is_animated = False
        mock_img.info = {"lossless": False}
        
        result = self.extractor._process_webp_specific(mock_img, 'test.webp')
        self.assertIn('webp_info', result)
        self.assertNotIn('is_animated', result['webp_info'])
        self.assertFalse(result['webp_info']['lossless'])

    def test_process_webp_specific_no_lossless_info(self):
        """Test _process_webp_specific with WebP having no lossless info."""
        mock_img = MagicMock()
        mock_img.is_animated = True
        mock_img.n_frames = 5
        mock_img.info = {} # No lossless info
        
        result = self.extractor._process_webp_specific(mock_img, 'test.webp')
        self.assertIn('webp_info', result)
        self.assertTrue(result['webp_info']['is_animated'])
        self.assertEqual(result['webp_info']['frame_count'], 5)
        self.assertNotIn('lossless', result['webp_info'])

    @patch('PIL.Image.open')
    def test_get_metadata_unsupported_format(self, mock_image_open):
        """Test get_metadata with an unsupported image format."""
        mock_img = MagicMock()
        mock_img.width = 100
        mock_img.height = 100
        mock_img.format = 'XYZ'  # Unsupported format
        mock_img.mode = 'RGB'
        mock_img.info = {}
        mock_img._getexif = MagicMock(return_value={})
        
        mock_image_open.return_value.__enter__.return_value = mock_img
        
        with patch.object(self.extractor, 'get_basic_metadata', return_value={'filename': 'test.xyz'}):
            metadata = self.extractor.get_metadata('test.xyz')
        
        self.assertNotIn('xyz_info', metadata) # Should not have specific info for XYZ
        self.assertIn('format', metadata)
        self.assertEqual(metadata['format'], 'XYZ')

    def test_estimate_jpeg_quality_no_quantization_attr(self):
        """Test _estimate_jpeg_quality when img has no quantization attribute."""
        mock_img = MagicMock()
        del mock_img.quantization
        self.assertIsNone(self.extractor._estimate_jpeg_quality(mock_img))

    def test_estimate_jpeg_quality_empty_quantization(self):
        """Test _estimate_jpeg_quality when quantization is empty."""
        mock_img = MagicMock()
        mock_img.quantization = {}
        self.assertIsNone(self.extractor._estimate_jpeg_quality(mock_img))

    def test_estimate_jpeg_quality_empty_qtables_avg(self):
        """Test _estimate_jpeg_quality when qtables_avg is empty."""
        mock_img = MagicMock()
        mock_img.quantization = {'table1': []} # This will lead to empty qtables_avg
        self.assertIsNone(self.extractor._estimate_jpeg_quality(mock_img))

    def test_estimate_jpeg_quality_avg_le_1(self):
        """Test _estimate_jpeg_quality when avg_value <= 1."""
        mock_img = MagicMock()
        mock_img.quantization = {'table1': [1, 1, 1]} # Avg will be 1
        self.assertEqual(self.extractor._estimate_jpeg_quality(mock_img), 100)

    def test_estimate_jpeg_quality_avg_ge_100(self):
        """Test _estimate_jpeg_quality when avg_value >= 100."""
        mock_img = MagicMock()
        mock_img.quantization = {'table1': [100, 100, 100]} # Avg will be 100
        self.assertEqual(self.extractor._estimate_jpeg_quality(mock_img), 1)

    def test_generate_caption_no_camera_no_date(self):
        """Test _generate_caption with no camera info and no date."""
        metadata = {
            'filename': 'test.png',
            'width': 100,
            'height': 200,
            'format': 'PNG'
        }
        caption = self.extractor._generate_caption(metadata)
        self.assertEqual(caption, "100x200 PNG")

    def test_generate_caption_only_camera_no_date(self):
        """Test _generate_caption with only camera info and no date."""
        metadata = {
            'filename': 'test.jpg',
            'width': 500,
            'height': 500,
            'format': 'JPEG',
            'camera_make': 'Nikon',
            'camera_model': 'D850'
        }
        caption = self.extractor._generate_caption(metadata)
        self.assertEqual(caption, "500x500 JPEG taken with Nikon D850")

    def test_generate_caption_only_date_no_camera(self):
        """Test _generate_caption with only date and no camera info."""
        metadata = {
            'filename': 'test.gif',
            'width': 300,
            'height': 400,
            'format': 'GIF',
            'creation_date': datetime(2023, 7, 20)
        }
        caption = self.extractor._generate_caption(metadata)
        self.assertEqual(caption, "300x400 GIF on July 20, 2023")

    def test_generate_caption_no_dimensions_format(self):
        """Test _generate_caption with no dimensions or format."""
        metadata = {
            'filename': 'test.webp',
            'camera_make': 'Sony',
            'creation_date': datetime(2024, 1, 1)
        }
        caption = self.extractor._generate_caption(metadata)
        self.assertEqual(caption, "taken with Sony on January 01, 2024")

    def test_generate_caption_minimal(self):
        """Test _generate_caption with only filename."""
        metadata = {'filename': 'minimal.jpg'}
        caption = self.extractor._generate_caption(metadata)
        self.assertEqual(caption, "Image file: minimal.jpg")

if __name__ == '__main__':
    unittest.main()
