"""
Unit tests for the ThumbnailService utility functions.
"""

import os
import tempfile
import unittest
import shutil
from unittest import mock

from ai_content_classifier.services.thumbnail.utils import (
    safe_get_file_size,
    safe_file_exists,
    safe_is_directory,
    safe_get_file_extension,
    safe_get_mime_type,
    validate_image_path,
    validate_thumbnail_size,
    validate_quality_factor,
    format_file_size,
    create_directory_safely,
    get_cache_key,
    is_image_file,
    get_image_files_in_directory,
    calculate_aspect_ratio_size,
    sanitize_filename,
)

class TestThumbnailUtils(unittest.TestCase):
    """Test cases for thumbnail utilities."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.txt")
        self.image_file = os.path.join(self.temp_dir, "a_test_image.jpg")
        self.image_file2 = os.path.join(self.temp_dir, "b_test_image2.png")
        self.image_file3 = os.path.join(self.temp_dir, "c_test_image3.gif")
        self.raw_image_file = os.path.join(self.temp_dir, "test_image.raw")
        self.no_ext_file = os.path.join(self.temp_dir, "filewithnoext")
        self.subdir = os.path.join(self.temp_dir, "subdir")
        os.makedirs(self.subdir)
        self.image_in_subdir = os.path.join(self.subdir, "sub_image.png")

        with open(self.test_file, "w") as f:
            f.write("test content")
        with open(self.image_file, "w") as f:
            f.write("fake image")
        with open(self.image_file2, "w") as f:
            f.write("fake image 2")
        with open(self.image_file3, "w") as f:
            f.write("fake image 3")
        with open(self.raw_image_file, "w") as f:
            f.write("fake raw image")
        with open(self.no_ext_file, "w") as f:
            f.write("fake content")
        with open(self.image_in_subdir, "w") as f:
            f.write("fake image 4")

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @mock.patch('os.path.getsize', side_effect=OSError('mocked error'))
    def test_safe_get_file_size_exception(self, mock_getsize):
        self.assertEqual(safe_get_file_size(self.test_file), 0)

    @mock.patch('os.path.isfile', side_effect=OSError('mocked error'))
    def test_safe_file_exists_exception(self, mock_isfile):
        self.assertFalse(safe_file_exists(self.test_file))

    @mock.patch('os.path.isdir', side_effect=OSError('mocked error'))
    def test_safe_is_directory_exception(self, mock_isdir):
        self.assertFalse(safe_is_directory(self.temp_dir))

    def test_safe_get_file_size(self):
        self.assertGreater(safe_get_file_size(self.test_file), 0)
        self.assertEqual(safe_get_file_size("nonexistent.txt"), 0)

    def test_safe_file_exists(self):
        self.assertTrue(safe_file_exists(self.test_file))
        self.assertFalse(safe_file_exists("nonexistent.txt"))

    def test_safe_is_directory(self):
        self.assertTrue(safe_is_directory(self.temp_dir))
        self.assertFalse(safe_is_directory(self.test_file))

    def test_safe_get_file_extension(self):
        self.assertEqual(safe_get_file_extension(self.image_file), ".jpg")
        self.assertEqual(safe_get_file_extension(None), "")

    def test_safe_get_mime_type(self):
        self.assertEqual(safe_get_mime_type(self.image_file), "image/jpeg")
        self.assertIsNone(safe_get_mime_type("file.unknownextension"))
        with mock.patch('mimetypes.guess_type', side_effect=Exception('mocked error')):
            self.assertIsNone(safe_get_mime_type(self.test_file))

    def test_validate_image_path(self):
        self.assertTrue(validate_image_path(self.image_file)[0])
        self.assertFalse(validate_image_path(None)[0])
        self.assertFalse(validate_image_path("   ")[0])
        self.assertFalse(validate_image_path("nonexistent.jpg")[0])
        self.assertFalse(validate_image_path(self.no_ext_file)[0])
        with self.assertLogs('ai_content_classifier.services.thumbnail.utils', level='DEBUG') as cm:
            is_valid, error = validate_image_path(self.raw_image_file)
            self.assertTrue(is_valid)
            self.assertIn("Unusual image extension", cm.output[0])

    def test_validate_thumbnail_size(self):
        self.assertTrue(validate_thumbnail_size((128, 128))[0])
        self.assertTrue(validate_thumbnail_size(None)[0])
        self.assertFalse(validate_thumbnail_size("invalid")[0])
        self.assertFalse(validate_thumbnail_size((128, 0))[0])
        self.assertFalse(validate_thumbnail_size((128, 5000))[0])
        self.assertFalse(validate_thumbnail_size((128,))[0])
        self.assertFalse(validate_thumbnail_size(("128", "128a"))[0])

    def test_validate_quality_factor(self):
        self.assertTrue(validate_quality_factor(0.5)[0])
        self.assertFalse(validate_quality_factor(-0.1)[0])
        self.assertFalse(validate_quality_factor(1.5)[0])
        self.assertFalse(validate_quality_factor("invalid")[0])

    def test_format_file_size(self):
        self.assertEqual(format_file_size(500), "500 B")
        self.assertEqual(format_file_size(0), "0 B")
        self.assertEqual(format_file_size(1024), "1.0 KB")
        self.assertEqual(format_file_size(1024*1024), "1.0 MB")

    @mock.patch('os.makedirs', side_effect=OSError('mocked error'))
    def test_create_directory_safely_exception(self, mock_makedirs):
        self.assertFalse(create_directory_safely("new_dir"))

    def test_create_directory_safely(self):
        new_dir = os.path.join(self.temp_dir, "new_dir")
        self.assertTrue(create_directory_safely(new_dir))
        self.assertTrue(os.path.isdir(new_dir))

    @mock.patch('os.path.getmtime', side_effect=OSError('mocked error'))
    def test_get_cache_key_exception(self, mock_getmtime):
        key = get_cache_key(self.image_file, (128, 128))
        self.assertIsNotNone(key)

    def test_get_cache_key(self):
        key1 = get_cache_key(self.image_file, (128, 128))
        key2 = get_cache_key(self.image_file, (128, 128))
        self.assertEqual(key1, key2)

    def test_is_image_file(self):
        self.assertTrue(is_image_file("test.jpg"))
        self.assertFalse(is_image_file("test.txt"))
        self.assertTrue(is_image_file(self.image_file, check_content=True))
        with mock.patch('ai_content_classifier.services.thumbnail.utils.safe_get_mime_type', return_value='application/zip'):
            self.assertFalse(is_image_file(self.image_file, check_content=True))

    @mock.patch('os.walk', side_effect=OSError('mocked error'))
    def test_get_image_files_in_directory_exception(self, mock_walk):
        self.assertEqual(get_image_files_in_directory(self.temp_dir, recursive=True), [])

    def test_get_image_files_in_directory(self):
        # Non-recursive, max_files
        files = get_image_files_in_directory(self.temp_dir, max_files=2)
        self.assertEqual(len(files), 2)
        # Recursive, max_files
        files_recursive = get_image_files_in_directory(self.temp_dir, recursive=True, max_files=3)
        self.assertEqual(len(files_recursive), 3)

    def test_get_image_files_in_invalid_directory(self):
        self.assertEqual(get_image_files_in_directory("nonexistent_dir"), [])

    def test_calculate_aspect_ratio_size(self):
        original = (1920, 1080)
        target = (200, 200)
        self.assertEqual(calculate_aspect_ratio_size(original, target, "contain"), (200, 112))
        self.assertEqual(calculate_aspect_ratio_size(original, target, "cover"), (355, 200))
        self.assertEqual(calculate_aspect_ratio_size((0,0), target), target)
        with self.assertRaises(ValueError):
            calculate_aspect_ratio_size(original, target, "invalid")

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename('a'*300+'.txt', max_length=10), 'aaaaaa.txt')
        self.assertEqual(sanitize_filename('\x01\x02\x03'), 'thumbnail')

if __name__ == "__main__":
    unittest.main(verbosity=2)
