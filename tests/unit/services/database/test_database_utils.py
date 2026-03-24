import hashlib
from datetime import datetime, date
from unittest.mock import MagicMock, patch, mock_open

from ai_content_classifier.services.database import utils

class TestUtils:

    # --- Tests for serialize_metadata_for_json ---

    def test_serialize_metadata_for_json_none_input(self):
        assert utils.serialize_metadata_for_json(None) is None

    def test_serialize_metadata_for_json_empty_dict(self):
        assert utils.serialize_metadata_for_json({}) == {}

    def test_serialize_metadata_for_json_basic_types(self):
        metadata = {
            "string_key": "value",
            "int_key": 123,
            "float_key": 1.23,
            "bool_key": True,
            "none_key": None
        }
        assert utils.serialize_metadata_for_json(metadata) == metadata

    def test_serialize_metadata_for_json_datetime_and_date(self):
        dt_obj = datetime(2023, 1, 1, 10, 30, 0)
        d_obj = date(2023, 1, 1)
        metadata = {"datetime_key": dt_obj, "date_key": d_obj}
        expected = {"datetime_key": dt_obj.isoformat(), "date_key": d_obj.isoformat()}
        assert utils.serialize_metadata_for_json(metadata) == expected

    def test_serialize_metadata_for_json_nested_structures(self):
        dt_obj = datetime(2023, 1, 1)
        metadata = {
            "nested_dict": {"key": "value", "date": dt_obj},
            "nested_list": [1, "two", dt_obj, {"sub": True}]
        }
        expected = {
            "nested_dict": {"key": "value", "date": dt_obj.isoformat()},
            "nested_list": [1, "two", dt_obj.isoformat(), {"sub": True}]
        }
        assert utils.serialize_metadata_for_json(metadata) == expected

    def test_serialize_metadata_for_json_non_json_serializable(self):
        class NonSerializable:
            def __str__(self):
                return "NonSerializableObject"
        
        metadata = {"obj": NonSerializable()}
        expected = {"obj": "NonSerializableObject"}
        assert utils.serialize_metadata_for_json(metadata) == expected

    def test_serialize_metadata_for_json_serialization_error_fallback(self):
        # Simulate an object that raises an error during str() conversion
        class ErrorOnStr:
            def __str__(self):
                raise ValueError("Cannot convert")
        
        metadata = {"bad_obj": ErrorOnStr()}
        # The outer try-except in serialize_metadata_for_json catches this
        assert "error" in utils.serialize_metadata_for_json(metadata)

    # --- Tests for compute_file_hash ---

    @patch('os.path.exists', return_value=False)
    def test_compute_file_hash_non_existent_file(self, mock_exists):
        assert utils.compute_file_hash("/nonexistent/path") is None
        mock_exists.assert_called_once_with("/nonexistent/path")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=b'')
    def test_compute_file_hash_empty_file(self, mock_open, mock_exists):
        assert utils.compute_file_hash("/empty/file.txt") == hashlib.sha256(b'').hexdigest()
        mock_open.assert_called_once_with("/empty/file.txt", "rb")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=b'test data')
    def test_compute_file_hash_small_file(self, mock_open, mock_exists):
        expected_hash = hashlib.sha256(b'test data').hexdigest()
        assert utils.compute_file_hash("/small/file.txt") == expected_hash
        mock_open.assert_called_once_with("/small/file.txt", "rb")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open')
    def test_compute_file_hash_large_file_chunks(self, mock_open, mock_exists):
        # Simulate reading in chunks
        mock_file_handle = MagicMock()
        mock_file_handle.__iter__.return_value = [b'chunk1', b'chunk2', b'chunk3']
        mock_file_handle.read.side_effect = [b'chunk1', b'chunk2', b'chunk3', b''] # For iter(lambda: f.read(4096), b'')
        mock_open.return_value.__enter__.return_value = mock_file_handle

        expected_hash = hashlib.sha256(b'chunk1chunk2chunk3').hexdigest()
        assert utils.compute_file_hash("/large/file.bin") == expected_hash
        mock_open.assert_called_once_with("/large/file.bin", "rb")

    @patch('os.path.exists', side_effect=Exception("OS error"))
    def test_compute_file_hash_os_error(self, mock_exists):
        assert utils.compute_file_hash("/error/path") is None
        mock_exists.assert_called_once_with("/error/path")

    # --- Tests for detect_content_type ---

    @patch('ai_content_classifier.services.database.utils.FileTypeService')
    def test_detect_content_type_image(self, MockFileTypeService):
        MockFileTypeService.get_file_category_name.return_value = "Image"
        assert utils.detect_content_type("test.jpg") == "image"
        MockFileTypeService.get_file_category_name.assert_called_once_with("test.jpg")

    @patch('ai_content_classifier.services.database.utils.FileTypeService')
    def test_detect_content_type_document(self, MockFileTypeService):
        MockFileTypeService.get_file_category_name.return_value = "Document"
        assert utils.detect_content_type("test.pdf") == "document"

    @patch('ai_content_classifier.services.database.utils.FileTypeService')
    def test_detect_content_type_other(self, MockFileTypeService):
        MockFileTypeService.get_file_category_name.return_value = "Other"
        assert utils.detect_content_type("test.xyz") == "content_item"

    @patch('ai_content_classifier.services.database.utils.FileTypeService')
    def test_detect_content_type_case_insensitivity(self, MockFileTypeService):
        MockFileTypeService.get_file_category_name.return_value = "IMAGE"
        assert utils.detect_content_type("test.JPG") == "image"

    @patch('ai_content_classifier.services.database.utils.FileTypeService')
    def test_detect_content_type_empty_path(self, MockFileTypeService):
        MockFileTypeService.get_file_category_name.return_value = "Other"
        assert utils.detect_content_type("") == "content_item"
