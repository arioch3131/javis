import unittest
import requests
import base64
import logging

from unittest.mock import Mock, patch, MagicMock

from ai_content_classifier.models.config_models import ConfigKey

from ai_content_classifier.services.llm.api_client import LLMApiClient, retry_on_failure


# Mock ConfigService for testing - VERSION ROBUSTE
class MockConfigService:
    def get(self, key):
        # Utiliser des valeurs réalistes basées sur les erreurs observées
        if key == ConfigKey.API_MAX_RETRIES:
            return 1
        elif key == ConfigKey.API_RETRY_BACKOFF:
            return 0.1
        elif key == ConfigKey.API_CONNECTION_TIMEOUT:
            return 5  # Valeur réelle utilisée par le code
        elif key == ConfigKey.API_GENERATE_TIMEOUT:
            return 5  # Valeur réelle utilisée par le code
        elif key == ConfigKey.API_URL:
            return "http://localhost:11434"
        elif key == ConfigKey.IMAGE_MODEL:
            return "mock_image_model"
        elif key == ConfigKey.DOCUMENT_MODEL:
            return "mock_document_model"
        elif key == ConfigKey.IMAGE_PROMPT:
            return "Analyze image: {image_path} for categories: {categories}"
        elif key == ConfigKey.DOCUMENT_PROMPT:
            return "Analyze document: {document_path} for categories: {categories}"
        elif key == ConfigKey.CONFIDENCE_THRESHOLD:
            return 0.7
        # Default return for unhandled keys
        return 5


class TestRetryOnFailureDecorator(unittest.TestCase):
    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_config_service = MockConfigService()
        self.mock_self = Mock()
        self.mock_self.config_service = self.mock_config_service
        self.mock_self.logger = self.mock_logger

    def test_success_on_first_attempt(self):
        mock_func = Mock(return_value="Success")
        mock_func.__name__ = "mock_func"
        decorated_func = retry_on_failure(max_retries=1, backoff_factor=0.1)(mock_func)

        result = decorated_func(self.mock_self)
        self.assertEqual(result, "Success")
        mock_func.assert_called_once()

    def test_retry_on_exception_and_then_success(self):
        mock_func = Mock(
            side_effect=[requests.exceptions.RequestException("Error"), "Success"]
        )
        mock_func.__name__ = "mock_func"
        decorated_func = retry_on_failure(max_retries=1, backoff_factor=0.1)(mock_func)

        result = decorated_func(self.mock_self)
        self.assertEqual(result, "Success")
        self.assertEqual(mock_func.call_count, 2)
        self.mock_logger.warning.assert_called_once()

    def test_all_retries_fail(self):
        mock_func = Mock(side_effect=requests.exceptions.RequestException("Error"))
        mock_func.__name__ = "mock_func"
        decorated_func = retry_on_failure(max_retries=1, backoff_factor=0.1)(mock_func)

        with self.assertRaises(requests.exceptions.RequestException):
            decorated_func(self.mock_self)
        self.assertEqual(mock_func.call_count, 2)
        self.mock_logger.error.assert_called_once()

    def test_non_retriable_exception(self):
        mock_func = Mock(side_effect=ValueError("Non-retriable error"))
        mock_func.__name__ = "mock_func"
        decorated_func = retry_on_failure(max_retries=1, backoff_factor=0.1)(mock_func)

        with self.assertRaises(ValueError):
            decorated_func(self.mock_self)
        mock_func.assert_called_once()
        self.mock_logger.error.assert_called_once()

    @patch("time.sleep", return_value=None)
    def test_backoff_factor_applied(self, mock_sleep):
        mock_func = Mock(
            side_effect=[requests.exceptions.RequestException("Error"), "Success"]
        )
        mock_func.__name__ = "mock_func"
        decorated_func = retry_on_failure(max_retries=1, backoff_factor=0.5)(mock_func)

        decorated_func(self.mock_self)
        mock_sleep.assert_called_once_with(0.5)


class TestLLMApiClient(unittest.TestCase):
    def setUp(self):
        self.api_url = "http://localhost:11434"
        self.config_service = MockConfigService()
        self.client = LLMApiClient(
            self.api_url, self.config_service, log_level=logging.DEBUG
        )
        self.client.logger = MagicMock()
        self.client.logger.isEnabledFor.return_value = True
        self.client.on_connection_status_changed = MagicMock()
        self.client.on_model_status_changed = MagicMock()

    @patch("requests.get")
    def test_check_connection_success(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"version": "0.1.32"}
        mock_get.return_value = mock_response

        success, message = self.client.check_connection()

        # Test des comportements essentiels
        self.assertTrue(success)
        self.assertIn("Connected to Ollama v0.1.32", message)

        # Vérifier que la bonne URL a été appelée avec un timeout
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], f"{self.api_url}/api/version")
        self.assertIn("timeout", kwargs)
        self.client.on_connection_status_changed.assert_called_once_with(True, message)

    @patch("requests.get", side_effect=requests.exceptions.Timeout("Timeout error"))
    @patch("time.sleep", return_value=None)
    def test_check_connection_timeout(self, mock_sleep, mock_get):
        success, message = self.client.check_connection()

        # Test du comportement essentiel
        self.assertFalse(success)
        self.assertIn("Connection timeout", message)
        self.assertIn("Timeout error", message)

        # Vérifier qu'il y a eu des tentatives (au moins 1)
        self.assertGreater(mock_get.call_count, 0)
        self.client.on_connection_status_changed.assert_called_once_with(False, message)

    @patch(
        "requests.get",
        side_effect=requests.exceptions.ConnectionError("Connection refused"),
    )
    @patch("time.sleep", return_value=None)
    def test_check_connection_refused(self, mock_sleep, mock_get):
        success, message = self.client.check_connection()

        # Test du comportement essentiel
        self.assertFalse(success)
        self.assertIn("Connection refused", message)

        # Vérifier qu'il y a eu des tentatives (plus d'une à cause des retries)
        self.assertGreater(mock_get.call_count, 1)
        self.client.on_connection_status_changed.assert_called_once_with(False, message)

    @patch(
        "ai_content_classifier.services.llm.api_client.LLMApiClient._check_connection_internal",
        side_effect=requests.exceptions.RequestException("Generic request error"),
    )
    def test_check_connection_request_exception(self, mock_internal):
        success, message = self.client.check_connection()
        self.assertFalse(success)
        self.assertIn("API request error", message)
        self.client.logger.error.assert_called_once_with(message)
        self.client.on_connection_status_changed.assert_called_once_with(False, message)

    @patch(
        "ai_content_classifier.services.llm.api_client.LLMApiClient._check_connection_internal",
        side_effect=Exception("Unexpected error"),
    )
    def test_check_connection_general_exception(self, mock_internal):
        success, message = self.client.check_connection()
        self.assertFalse(success)
        self.assertIn("An unexpected error occurred", message)
        self.client.logger.error.assert_called_once_with(message, exc_info=True)
        self.client.on_connection_status_changed.assert_called_once_with(False, message)

    @patch("requests.get")
    def test_list_models_success(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "model1"}, {"name": "model2"}]
        }
        mock_get.return_value = mock_response

        models = self.client.list_models()

        # Test du comportement essentiel
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0]["name"], "model1")

        # Vérifier l'URL appelée
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], f"{self.api_url}/api/tags")
        self.client.logger.debug.assert_called_with("Available models: model1, model2")
        self.client.logger.isEnabledFor.assert_called_with(logging.DEBUG)

    @patch(
        "requests.get", side_effect=requests.exceptions.RequestException("API error")
    )
    @patch("time.sleep", return_value=None)
    def test_list_models_failure(self, mock_sleep, mock_get):
        models = self.client.list_models()

        # Test du comportement essentiel
        self.assertEqual(len(models), 0)
        self.assertGreater(mock_get.call_count, 0)

    @patch(
        "ai_content_classifier.services.llm.api_client.LLMApiClient._list_models_internal",
        side_effect=Exception("Unexpected model list error"),
    )
    def test_list_models_general_exception(self, mock_internal):
        models = self.client.list_models()
        self.assertEqual(models, [])
        self.client.logger.error.assert_called_once_with(
            "Failed to retrieve models: Unexpected model list error", exc_info=True
        )

    @patch("requests.post")
    @patch("time.sleep", return_value=None)
    def test_pull_model_success(self, mock_sleep, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'{"status": "downloading", "progress": 10, "total": 100}',
            b'{"status": "downloading", "progress": 50, "total": 100}',
            b'{"status": "success"}',
        ]
        mock_post.return_value = mock_response

        result = self.client.pull_model("test_model")

        # Test du comportement essentiel
        self.assertTrue(result)

        # Vérifier l'appel
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], f"{self.api_url}/api/pull")
        self.assertEqual(kwargs["json"], {"name": "test_model"})
        self.assertTrue(kwargs["stream"])
        self.client.on_model_status_changed.assert_any_call(
            "downloading", "Downloading test_model: 10.0%"
        )
        self.client.on_model_status_changed.assert_any_call(
            "downloading", "Downloading test_model: 50.0%"
        )
        self.client.on_model_status_changed.assert_called_with(
            "success", "Model test_model downloaded successfully"
        )

    @patch("requests.post")
    @patch("time.sleep", return_value=None)
    def test_pull_model_failure(self, mock_sleep, mock_post):
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        result = self.client.pull_model("test_model")

        # Test du comportement essentiel
        self.assertFalse(result)
        self.client.on_model_status_changed.assert_called_once_with(
            "error", "Failed to download model. HTTP 400: Bad Request"
        )

    @patch("requests.post")
    @patch("time.sleep", return_value=None)
    def test_pull_model_invalid_json(self, mock_sleep, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'{"status": "downloading", "progress": 10, "total": 100}',
            b"invalid json",
            b'{"status": "success"}',
        ]
        mock_post.return_value = mock_response

        result = self.client.pull_model("test_model")
        self.assertTrue(result)  # Should still succeed if some lines are valid
        self.client.logger.warning.assert_called_with(unittest.mock.ANY)
        self.client.logger.warning.assert_called_once()

    @patch("requests.post")
    @patch("time.sleep", return_value=None)
    @patch("time.time")
    def test_pull_model_status_only_logging(self, mock_time, mock_sleep, mock_post):
        mock_time.side_effect = [
            0,
            6,
            12,
            18,
            20,
        ]  # Simulate time passing to trigger log_interval and final time calculation

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'{"status": "pulling manifest"}',
            b'{"status": "verifying checksum"}',
            b'{"status": "success"}',
        ]
        mock_post.return_value = mock_response

        result = self.client.pull_model("test_model")
        self.assertTrue(result)
        self.client.logger.info.assert_any_call(
            "Model download status: pulling manifest"
        )
        self.client.logger.info.assert_any_call(
            "Model download status: verifying checksum"
        )
        self.client.on_model_status_changed.assert_any_call(
            "downloading", "pulling manifest"
        )
        self.client.on_model_status_changed.assert_any_call(
            "downloading", "verifying checksum"
        )
        self.client.on_model_status_changed.assert_called_with(
            "success", "Model test_model downloaded successfully"
        )

    @patch("requests.post", side_effect=Exception("Pull model unexpected error"))
    @patch("time.sleep", return_value=None)
    def test_pull_model_general_exception(self, mock_sleep, mock_post):
        result = self.client.pull_model("test_model")
        self.assertFalse(result)
        self.client.logger.error.assert_called_once_with(
            "Failed to download model: Pull model unexpected error", exc_info=True
        )
        self.client.on_model_status_changed.assert_called_once_with(
            "error", "Failed to download model: Pull model unexpected error"
        )

    @patch("requests.post")
    @patch("time.sleep", return_value=None)
    def test_generate_success(self, mock_sleep, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Generated text"}
        mock_post.return_value = mock_response

        response = self.client.generate("test_model", "test prompt")

        # Test du comportement essentiel
        self.assertEqual(response, "Generated text")

        # Vérifier l'appel de base
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], f"{self.api_url}/api/generate")
        expected_json = {
            "model": "test_model",
            "prompt": "test prompt",
            "stream": False,
        }
        self.assertEqual(kwargs["json"], expected_json)

    @patch("requests.post")
    @patch("time.sleep", return_value=None)
    def test_generate_with_response_format_schema(self, mock_sleep, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": '{"category":"Work"}'}
        mock_post.return_value = mock_response

        schema = {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": ["Work", "Personal"]}
            },
            "required": ["category"],
        }

        response = self.client.generate(
            "test_model",
            "test prompt",
            response_format=schema,
        )

        self.assertEqual(response, '{"category":"Work"}')
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertIn("format", kwargs["json"])
        self.assertEqual(kwargs["json"]["format"], schema)

    @patch(
        "requests.post",
        side_effect=requests.exceptions.RequestException("Generation error"),
    )
    @patch("time.sleep", return_value=None)
    def test_generate_failure(self, mock_sleep, mock_post):
        response = self.client.generate("test_model", "test prompt")

        # Test du comportement essentiel
        self.assertEqual(response, "")
        self.assertGreater(mock_post.call_count, 0)

    @patch("os.path.exists", return_value=True)
    @patch(
        "builtins.open", new_callable=unittest.mock.mock_open, read_data=b"image_data"
    )
    @patch("requests.post")
    @patch("time.sleep", return_value=None)
    def test_generate_with_image(self, mock_sleep, mock_post, mock_open, mock_exists):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Image analyzed"}
        mock_post.return_value = mock_response

        image_path = "/tmp/test_image.jpg"
        response = self.client.generate(
            "test_model", "analyze image", images=[image_path]
        )

        # Test du comportement essentiel
        self.assertEqual(response, "Image analyzed")

        # Vérifier que l'image a été encodée et incluse
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn("images", kwargs["json"])

        expected_encoded_image = base64.b64encode(b"image_data").decode("utf-8")
        self.assertEqual(kwargs["json"]["images"], [expected_encoded_image])

        # Vérifier la lecture du fichier
        mock_exists.assert_called_once_with(image_path)
        mock_open.assert_called_once_with(image_path, "rb")

    @patch("os.path.exists", return_value=False)
    @patch("requests.post")
    @patch("time.sleep", return_value=None)
    def test_generate_with_non_existent_image(self, mock_sleep, mock_post, mock_exists):
        response = self.client.generate(
            "test_model", "analyze image", images=["/tmp/non_existent.jpg"]
        )

        # Test du comportement essentiel
        self.assertEqual(response, "")
        mock_post.assert_not_called()
        self.client.logger.warning.assert_called_once_with(
            "Image file not found: /tmp/non_existent.jpg"
        )

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", side_effect=IOError("File read error"))
    @patch("requests.post")
    @patch("time.sleep", return_value=None)
    def test_generate_image_encoding_exception(
        self, mock_sleep, mock_post, mock_open, mock_exists
    ):
        image_path = "/tmp/test_image.jpg"
        response = self.client.generate(
            "test_model", "analyze image", images=[image_path]
        )
        self.assertEqual(response, "")
        self.client.logger.error.assert_called_once_with(
            f"Failed to encode image {image_path}: File read error"
        )
        mock_post.assert_not_called()

    @patch(
        "ai_content_classifier.services.llm.api_client.LLMApiClient._generate_internal",
        side_effect=Exception("Unexpected generation error"),
    )
    def test_generate_general_exception(self, mock_internal):
        response = self.client.generate("test_model", "test prompt")
        self.assertEqual(response, "")
        self.client.logger.error.assert_called_once_with(
            "Generation error: Unexpected generation error", exc_info=True
        )


if __name__ == "__main__":
    unittest.main()
