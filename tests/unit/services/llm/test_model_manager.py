import unittest
import time
import threading
import logging

from unittest.mock import patch, MagicMock

from ai_content_classifier.services.llm.model_manager import (
    ModelStatus,
    ModelInfo,
    ModelCache,
    ModelManager,
)
from ai_content_classifier.services.shared.cache_runtime import NamespacedMemoryCache


# Mock LoggableMixin pour les tests
class MockLoggableMixin:
    def __init_logger__(self, log_level):
        self.logger = MagicMock()


class TestModelStatus(unittest.TestCase):
    """Tests pour l'énumération ModelStatus."""

    def test_enum_values(self):
        """Test que toutes les valeurs de l'enum sont correctes."""
        expected_values = {
            "UNKNOWN": "unknown",
            "AVAILABLE": "available",
            "DOWNLOADING": "downloading",
            "FAILED": "failed",
            "CACHED": "cached",
            "UPDATING": "updating",
        }

        for attr_name, expected_value in expected_values.items():
            self.assertTrue(hasattr(ModelStatus, attr_name))
            self.assertEqual(getattr(ModelStatus, attr_name).value, expected_value)

    def test_enum_comparison(self):
        """Test la comparaison des valeurs enum."""
        self.assertEqual(ModelStatus.AVAILABLE, ModelStatus.AVAILABLE)
        self.assertNotEqual(ModelStatus.AVAILABLE, ModelStatus.DOWNLOADING)


class TestModelInfo(unittest.TestCase):
    """Tests pour la classe ModelInfo."""

    def setUp(self):
        """Configuration initiale pour chaque test."""
        self.basic_model_data = {
            "name": "llama2:7b-instruct",
            "size": 3825819648,  # ~3.6GB
            "digest": "sha256:abc123def456",
            "modified_at": "2023-11-01T10:00:00Z",
        }

    def test_basic_initialization(self):
        """Test l'initialisation basique de ModelInfo."""
        model = ModelInfo(name="test-model")

        self.assertEqual(model.name, "test-model")
        self.assertIsNone(model.size)
        self.assertIsNone(model.digest)
        self.assertEqual(model.status, ModelStatus.UNKNOWN)
        self.assertEqual(model.use_count, 0)
        self.assertEqual(model.download_progress, 0.0)
        self.assertIsInstance(model.capabilities, list)
        self.assertIsInstance(model.tags, list)
        self.assertIsInstance(model.metadata, dict)

    def test_full_initialization(self):
        """Test l'initialisation complète avec tous les paramètres."""
        model = ModelInfo(
            name="llama2:7b-instruct",
            size=3825819648,
            digest="sha256:abc123def456",
            modified_at="2023-11-01T10:00:00Z",
            status=ModelStatus.AVAILABLE,
            version="1.0",
            family="llama2",
            format="gguf",
            parameter_size="7B",
            quantization_level="Q4",
            capabilities=["instruction_following"],
            tags=["latest"],
            last_used=time.time(),
            use_count=5,
            download_progress=100.0,
            metadata={"custom": "data"},
        )

        self.assertEqual(model.name, "llama2:7b-instruct")
        self.assertEqual(model.size, 3825819648)
        self.assertEqual(model.status, ModelStatus.AVAILABLE)
        self.assertEqual(model.use_count, 5)
        self.assertIn("instruction_following", model.capabilities)

    def test_parse_model_name_with_tag(self):
        """Test le parsing du nom de modèle avec tag."""
        model = ModelInfo(name="llama2:7b-instruct")

        self.assertEqual(model.family, "llama2")
        self.assertEqual(model.parameter_size, "7B")
        self.assertIn("instruction_following", model.capabilities)

    def test_parse_model_name_with_quantization(self):
        """Test le parsing du nom de modèle avec quantisation."""
        model = ModelInfo(name="mistral:7b-q4")

        self.assertEqual(model.family, "mistral")
        self.assertEqual(model.parameter_size, "7B")
        self.assertEqual(model.quantization_level, "Q4")

    def test_parse_model_name_with_capabilities(self):
        """Test le parsing des capacités depuis le nom."""
        test_cases = [
            ("model:chat", ["conversational"]),
            ("model:code", ["code_generation"]),
            ("model:vision", ["multimodal_vision"]),
            ("model:embed", ["embeddings"]),
            ("model:instruct", ["instruction_following"]),
        ]

        for name, expected_capabilities in test_cases:
            model = ModelInfo(name=name)
            for capability in expected_capabilities:
                self.assertIn(capability, model.capabilities)

    def test_parse_model_name_without_tag(self):
        """Test le parsing d'un nom de modèle sans tag."""
        model = ModelInfo(name="simple-model")

        self.assertIsNone(model.family)
        self.assertIsNone(model.parameter_size)
        self.assertIsNone(model.quantization_level)

    def test_parse_model_name_empty(self):
        """Test le parsing d'un nom de modèle vide."""
        model = ModelInfo(name="")

        self.assertIsNone(model.family)
        self.assertIsNone(model.parameter_size)

    def test_is_available_property(self):
        """Test la propriété is_available."""
        # Test AVAILABLE
        model = ModelInfo(name="test", status=ModelStatus.AVAILABLE)
        self.assertTrue(model.is_available)

        # Test CACHED
        model.status = ModelStatus.CACHED
        self.assertTrue(model.is_available)

        # Test DOWNLOADING
        model.status = ModelStatus.DOWNLOADING
        self.assertFalse(model.is_available)

        # Test FAILED
        model.status = ModelStatus.FAILED
        self.assertFalse(model.is_available)

    def test_is_downloading_property(self):
        """Test la propriété is_downloading."""
        model = ModelInfo(name="test", status=ModelStatus.DOWNLOADING)
        self.assertTrue(model.is_downloading)

        model.status = ModelStatus.AVAILABLE
        self.assertFalse(model.is_downloading)

    def test_has_error_property(self):
        """Test la propriété has_error."""
        model = ModelInfo(name="test", status=ModelStatus.FAILED)
        self.assertTrue(model.has_error)

        model.status = ModelStatus.AVAILABLE
        self.assertFalse(model.has_error)

    def test_size_properties(self):
        """Test les propriétés de taille (MB et GB)."""
        # Test avec une taille de 3.6GB
        model = ModelInfo(name="test", size=3825819648)  # 3.6GB en bytes

        self.assertAlmostEqual(model.size_mb, 3648.5859375, places=7)
        self.assertAlmostEqual(model.size_gb, 3.5630722045898438, places=10)

        # Test sans taille
        model.size = None
        self.assertIsNone(model.size_mb)
        self.assertIsNone(model.size_gb)

    def test_to_dict(self):
        """Test la conversion en dictionnaire."""
        model = ModelInfo(
            name="test-model",
            size=1073741824,  # 1GB
            digest="sha256:test",
            status=ModelStatus.AVAILABLE,
            capabilities=["test_capability"],
        )

        result = model.to_dict()

        self.assertIsInstance(result, dict)
        self.assertEqual(result["name"], "test-model")
        self.assertEqual(result["size"], 1073741824)
        self.assertEqual(result["size_mb"], 1024.0)
        self.assertEqual(result["size_gb"], 1.0)
        self.assertEqual(result["status"], "available")
        self.assertIn("test_capability", result["capabilities"])


class TestModelCache(unittest.TestCase):
    """Tests pour la classe ModelCache."""

    def setUp(self):
        """Configuration initiale pour chaque test."""
        self.cache = ModelCache(cache_ttl=10, max_cache_size=5)
        self.cache.clear_all()
        self.test_models = [
            ModelInfo(name="model1", status=ModelStatus.AVAILABLE),
            ModelInfo(name="model2", status=ModelStatus.DOWNLOADING),
            ModelInfo(name="model3", status=ModelStatus.FAILED),
        ]
        self.test_api_url = "http://localhost:11434"

    def tearDown(self):
        self.cache.clear_all()

    def test_initialization(self):
        """Test l'initialisation du cache."""
        cache = ModelCache()
        _LockType = type(threading.RLock())

        self.assertEqual(cache.cache_ttl, 300)  # Default 5 minutes
        self.assertEqual(cache.max_cache_size, 1000)
        self.assertIsInstance(cache._models_cache, NamespacedMemoryCache)
        self.assertIsInstance(cache._api_url_cache, NamespacedMemoryCache)
        self.assertIsInstance(cache._lock, _LockType)

    def test_custom_initialization(self):
        """Test l'initialisation avec des paramètres personnalisés."""
        cache = ModelCache(cache_ttl=60, max_cache_size=100)

        self.assertEqual(cache.cache_ttl, 60)
        self.assertEqual(cache.max_cache_size, 100)

    def test_set_and_get_models(self):
        """Test la mise en cache et récupération des modèles pour une API URL."""
        # Set models
        self.cache.set_models(self.test_api_url, self.test_models)

        # Get models (should return cached models)
        cached_models = self.cache.get_models(self.test_api_url)

        self.assertIsNotNone(cached_models)
        self.assertEqual(len(cached_models), 3)
        self.assertEqual(cached_models[0].name, "model1")

    def test_get_models_cache_miss(self):
        """Test la récupération de modèles non mis en cache."""
        result = self.cache.get_models("http://unknown-url")
        self.assertIsNone(result)

    def test_get_models_cache_expired(self):
        """Test la récupération de modèles avec cache expiré."""
        # Set models
        self.cache.set_models(self.test_api_url, self.test_models)

        # Mock time to simulate cache expiration
        with patch("time.time", return_value=time.time() + self.cache.cache_ttl + 1):
            result = self.cache.get_models(self.test_api_url)
            self.assertIsNone(result)

    def test_set_and_get_individual_model(self):
        """Test la mise en cache et récupération d'un modèle individuel."""
        model = self.test_models[0]

        # Set model
        self.cache.set_model(model)

        # Get model
        cached_model = self.cache.get_model("model1")

        self.assertIsNotNone(cached_model)
        self.assertEqual(cached_model.name, "model1")
        self.assertEqual(cached_model.status, ModelStatus.AVAILABLE)

    def test_get_individual_model_cache_miss(self):
        """Test la récupération d'un modèle non mis en cache."""
        result = self.cache.get_model("unknown_model")
        self.assertIsNone(result)

    def test_get_individual_model_cache_expired(self):
        """Test la récupération d'un modèle avec cache expiré."""
        model = self.test_models[0]
        self.cache.set_model(model)

        with patch("time.time", return_value=time.time() + self.cache.cache_ttl + 1):
            result = self.cache.get_model("model1")
            self.assertIsNone(result)

    def test_update_model_status(self):
        """Test la mise à jour du statut d'un modèle."""
        # Set initial model
        model = self.test_models[0]
        self.cache.set_model(model)

        # Update status
        self.cache.update_model_status(
            "model1", ModelStatus.DOWNLOADING, progress=50.0, error_message="Test error"
        )

        # Check updated model
        updated_model = self.cache.get_model("model1")
        self.assertEqual(updated_model.status, ModelStatus.DOWNLOADING)
        self.assertEqual(updated_model.download_progress, 50.0)
        self.assertEqual(updated_model.error_message, "Test error")

    def test_update_model_status_nonexistent(self):
        """Test la mise à jour du statut d'un modèle inexistant."""
        # Should not raise an exception
        self.cache.update_model_status("nonexistent", ModelStatus.FAILED)

        # Model should still not exist
        result = self.cache.get_model("nonexistent")
        self.assertIsNone(result)

    def test_invalidate_model(self):
        """Test l'invalidation d'un modèle spécifique."""
        model = self.test_models[0]
        self.cache.set_model(model)

        # Verify model is cached
        self.assertIsNotNone(self.cache.get_model("model1"))

        # Invalidate model
        self.cache.invalidate_model("model1")

        # Verify model is no longer cached
        self.assertIsNone(self.cache.get_model("model1"))

    def test_invalidate_api_url(self):
        """Test l'invalidation du cache pour une API URL."""
        self.cache.set_models(self.test_api_url, self.test_models)

        # Verify models are cached
        self.assertIsNotNone(self.cache.get_models(self.test_api_url))

        # Invalidate API URL
        self.cache.invalidate_api_url(self.test_api_url)

        # Verify models are no longer cached for this URL
        self.assertIsNone(self.cache.get_models(self.test_api_url))

    def test_clear_all(self):
        """Test la suppression complète du cache."""
        # Populate cache
        self.cache.set_models(self.test_api_url, self.test_models)
        self.cache.set_model(ModelInfo(name="individual_model"))

        # Clear all
        self.cache.clear_all()

        # Verify everything is cleared
        self.assertIsNone(self.cache.get_models(self.test_api_url))
        self.assertIsNone(self.cache.get_model("individual_model"))
        self.assertIsNone(self.cache.get_model("model1"))

    def test_cache_cleanup(self):
        """Test le nettoyage automatique du cache."""
        # Create a cache with small max size
        small_cache = ModelCache(cache_ttl=10, max_cache_size=2)

        # Add more models than max size
        models = [
            ModelInfo(name=f"model{i}", status=ModelStatus.AVAILABLE) for i in range(5)
        ]

        for model in models:
            small_cache.set_model(model)
            time.sleep(0.01)  # Small delay to ensure different timestamps

        # Current omni-cache backed implementation keeps all explicit inserts.
        stats = small_cache.get_cache_stats()
        self.assertEqual(stats["total_models"], 5)

    def test_get_cache_stats(self):
        """Test la récupération des statistiques du cache."""
        # Add some models
        self.cache.set_models(self.test_api_url, self.test_models[:2])
        self.cache.set_model(self.test_models[2])

        stats = self.cache.get_cache_stats()

        self.assertIsInstance(stats, dict)
        self.assertIn("total_models", stats)
        self.assertIn("valid_models", stats)
        self.assertIn("api_urls_cached", stats)
        self.assertIn("cache_ttl", stats)
        self.assertIn("max_cache_size", stats)
        self.assertIn("cache_hit_ratio", stats)

        self.assertEqual(stats["total_models"], 3)
        self.assertEqual(stats["api_urls_cached"], 1)
        self.assertEqual(stats["cache_ttl"], 10)
        self.assertEqual(stats["max_cache_size"], 5)


class TestModelManager(unittest.TestCase):
    """Tests pour la classe ModelManager."""

    def setUp(self):
        """Configuration initiale pour chaque test."""
        # Mock dependencies
        self.mock_api_client = MagicMock()
        self.mock_config_service = MagicMock()

        # Configure mock config service
        self.mock_config_service.get.return_value = 30  # Timeout value

        # Create manager with mocked dependencies
        self.manager = ModelManager(
            api_client=self.mock_api_client,
            config_service=self.mock_config_service,
            log_level=logging.DEBUG,
        )
        self.manager.cache.clear_all()

        # Mock the logger to avoid actual logging
        self.manager.logger = MagicMock()

        # Test data
        self.test_api_url = "http://localhost:11434"
        self.raw_model_data = [
            {
                "name": "llama2:7b",
                "size": 3825819648,
                "digest": "sha256:abc123",
                "modified_at": "2023-11-01T10:00:00Z",
                "details": {
                    "format": "gguf",
                    "family": "llama",
                    "parameter_size": "7B",
                },
            },
            {
                "name": "mistral:7b-instruct",
                "size": 4161061888,
                "digest": "sha256:def456",
                "modified_at": "2023-11-02T10:00:00Z",
                "details": {
                    "format": "gguf",
                    "family": "mistral",
                    "parameter_size": "7B",
                },
            },
        ]

    def tearDown(self):
        """Nettoyage après chaque test."""
        self.manager.cache.clear_all()

    # === TESTS D'INITIALISATION ===

    def test_initialization_success(self):
        """Test l'initialisation réussie du ModelManager."""
        _LockType = type(threading.RLock())
        self.assertIsNotNone(self.manager.api_client)
        self.assertIsNotNone(self.manager.config_service)
        self.assertIsInstance(self.manager.cache, ModelCache)
        self.assertIsInstance(self.manager._download_status, dict)
        self.assertIsInstance(self.manager._usage_stats, dict)
        self.assertIsInstance(self.manager._download_lock, _LockType)
        self.assertIsInstance(self.manager._stats_lock, _LockType)

    def test_initialization_with_custom_config(self):
        """Test l'initialisation avec une configuration personnalisée."""
        # Mock différente valeur de timeout
        self.mock_config_service.get.return_value = 60

        manager = ModelManager(
            api_client=self.mock_api_client, config_service=self.mock_config_service
        )

        # Le cache TTL devrait être 5x le timeout
        self.assertEqual(manager.cache.cache_ttl, 300)  # 60 * 5

    # === TESTS DE CRÉATION DE MODELINFO ===

    def test_create_model_info_basic(self):
        """Test la création d'un ModelInfo basique."""
        raw_model = self.raw_model_data[0]
        model_info = self.manager._create_model_info(raw_model)

        self.assertIsInstance(model_info, ModelInfo)
        self.assertEqual(model_info.name, "llama2:7b")
        self.assertEqual(model_info.size, 3825819648)
        self.assertEqual(model_info.digest, "sha256:abc123")
        self.assertEqual(model_info.status, ModelStatus.AVAILABLE)
        self.assertEqual(model_info.format, "gguf")
        self.assertEqual(model_info.family, "llama")
        self.assertEqual(model_info.parameter_size, "7B")

    def test_create_model_info_with_details(self):
        """Test la création d'un ModelInfo avec détails."""
        raw_model = self.raw_model_data[1]
        model_info = self.manager._create_model_info(raw_model)

        self.assertEqual(model_info.family, "mistral")
        self.assertEqual(model_info.parameter_size, "7B")
        self.assertEqual(model_info.format, "gguf")

    def test_create_model_info_minimal(self):
        """Test la création d'un ModelInfo avec données minimales."""
        raw_model = {"name": "simple-model"}
        model_info = self.manager._create_model_info(raw_model)

        self.assertEqual(model_info.name, "simple-model")
        self.assertEqual(model_info.status, ModelStatus.AVAILABLE)
        self.assertIsNone(model_info.size)

    # === TESTS DE LIST_MODELS ===

    def test_list_models_success_no_cache(self):
        """Test la récupération de modèles sans cache."""
        # Configure mock API client
        self.mock_api_client.list_models.return_value = self.raw_model_data
        self.mock_api_client.api_url = "different_url"

        result = self.manager.list_models(self.test_api_url)

        # Verify API client was updated and called
        self.assertEqual(self.mock_api_client.api_url, self.test_api_url)
        self.mock_api_client.list_models.assert_called_once()

        # Verify results
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], ModelInfo)
        self.assertEqual(result[0].name, "llama2:7b")

    def test_list_models_from_cache(self):
        """Test la récupération de modèles depuis le cache."""
        # Pre-populate cache
        cached_models = [ModelInfo(name="cached_model", status=ModelStatus.AVAILABLE)]
        self.manager.cache.set_models(self.test_api_url, cached_models)

        result = self.manager.list_models(self.test_api_url)

        # API should not be called
        self.mock_api_client.list_models.assert_not_called()

        # Should return cached models
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "cached_model")

    def test_list_models_force_refresh(self):
        """Test la récupération forcée (ignore le cache)."""
        # Pre-populate cache
        cached_models = [ModelInfo(name="cached_model")]
        self.manager.cache.set_models(self.test_api_url, cached_models)

        # Configure API response
        self.mock_api_client.list_models.return_value = self.raw_model_data

        result = self.manager.list_models(self.test_api_url, force_refresh=True)

        # API should be called despite cache
        self.mock_api_client.list_models.assert_called_once()
        self.assertEqual(len(result), 2)

    def test_list_models_api_failure_with_cache(self):
        """Test la gestion d'échec API avec cache disponible."""
        # Pre-populate cache
        cached_models = [ModelInfo(name="cached_model")]
        self.manager.cache.set_models(self.test_api_url, cached_models)

        # Configure API to fail
        self.mock_api_client.list_models.side_effect = Exception("API Error")

        result = self.manager.list_models(self.test_api_url, force_refresh=True)

        # Should return stale cache
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "cached_model")

    def test_list_models_api_failure_no_cache(self):
        """Test la gestion d'échec API sans cache."""
        # Configure API to fail
        self.mock_api_client.list_models.side_effect = Exception("API Error")

        result = self.manager.list_models(self.test_api_url)

        # Should return empty list
        self.assertEqual(len(result), 0)

    # === TESTS DE GET_MODEL_INFO ===

    def test_get_model_info_from_cache(self):
        """Test la récupération d'info modèle depuis le cache."""
        # Pre-populate cache
        model = ModelInfo(name="test_model", status=ModelStatus.AVAILABLE)
        self.manager.cache.set_model(model)

        result = self.manager.get_model_info(self.test_api_url, "test_model")

        self.assertIsNotNone(result)
        self.assertEqual(result.name, "test_model")
        # API should not be called
        self.mock_api_client.list_models.assert_not_called()

    def test_get_model_info_from_api(self):
        """Test la récupération d'info modèle depuis l'API."""
        # Configure API response
        self.mock_api_client.list_models.return_value = self.raw_model_data

        result = self.manager.get_model_info(self.test_api_url, "llama2:7b")

        self.assertIsNotNone(result)
        self.assertEqual(result.name, "llama2:7b")
        self.mock_api_client.list_models.assert_called_once()

    def test_get_model_info_not_found(self):
        """Test la récupération d'un modèle inexistant."""
        # Configure API response
        self.mock_api_client.list_models.return_value = self.raw_model_data

        result = self.manager.get_model_info(self.test_api_url, "nonexistent")

        self.assertIsNone(result)

    def test_get_model_info_force_refresh(self):
        """Test la récupération forcée d'info modèle."""
        # Pre-populate cache
        model = ModelInfo(name="test_model", status=ModelStatus.CACHED)
        self.manager.cache.set_model(model)

        # Configure API response
        self.mock_api_client.list_models.return_value = [
            {"name": "test_model", "status": "available"}
        ]

        self.manager.get_model_info(self.test_api_url, "test_model", force_refresh=True)

        # API should be called despite cache
        self.mock_api_client.list_models.assert_called_once()

    # === TESTS DE PULL_MODEL ===

    def test_pull_model_success(self):
        """Test le téléchargement réussi d'un modèle."""
        # Configure API client
        self.mock_api_client.pull_model.return_value = True
        self.mock_api_client.api_url = "different_url"

        result = self.manager.pull_model(self.test_api_url, "test_model")

        # Verify API client was updated and called
        self.assertEqual(self.mock_api_client.api_url, self.test_api_url)
        self.mock_api_client.pull_model.assert_called_once_with("test_model")

        self.assertTrue(result)

        # Verify download status tracking
        self.assertIn("test_model", self.manager._download_status)
        self.assertEqual(
            self.manager._download_status["test_model"]["status"], "completed"
        )

    def test_pull_model_failure(self):
        """Test l'échec de téléchargement d'un modèle."""
        # Configure API client to fail
        self.mock_api_client.pull_model.return_value = False

        result = self.manager.pull_model(self.test_api_url, "test_model")

        self.assertFalse(result)

        # Verify failure status tracking
        self.assertEqual(
            self.manager._download_status["test_model"]["status"], "failed"
        )

    def test_pull_model_exception(self):
        """Test la gestion d'exception lors du téléchargement."""
        # Configure API client to raise exception
        self.mock_api_client.pull_model.side_effect = Exception("Download error")

        result = self.manager.pull_model(self.test_api_url, "test_model")

        self.assertFalse(result)

        # Verify error status tracking
        self.assertEqual(self.manager._download_status["test_model"]["status"], "error")

    def test_pull_model_progress_callback(self):
        """Test le callback de progression du téléchargement."""
        # Configure API client
        self.mock_api_client.pull_model.return_value = True
        original_callback = MagicMock()
        self.mock_api_client.on_model_status_changed = original_callback

        # Mock progress callback to be called during download
        def simulate_progress(model_name):
            # Simulate the callback being called
            self.manager._handle_download_progress(
                model_name, "downloading", "50% complete"
            )
            return True

        self.mock_api_client.pull_model.side_effect = simulate_progress

        result = self.manager.pull_model(self.test_api_url, "test_model")

        self.assertTrue(result)

    # === TESTS DE ENSURE_MODEL_AVAILABLE ===

    def test_ensure_model_available_cached_available(self):
        """Test ensure_model_available avec modèle en cache disponible."""
        # Mock cached available model
        available_model = ModelInfo(name="test", status=ModelStatus.AVAILABLE)
        self.manager.cache.set_model(available_model)

        result = self.manager.ensure_model_available(self.test_api_url, "test")

        self.assertTrue(result)

    def test_ensure_model_available_currently_downloading(self):
        """Test ensure_model_available avec modèle en cours de téléchargement."""
        # Mock downloading model
        downloading_model = ModelInfo(name="test", status=ModelStatus.DOWNLOADING)
        self.manager.cache.set_model(downloading_model)

        result = self.manager.ensure_model_available(self.test_api_url, "test")

        self.assertFalse(result)

    def test_ensure_model_available_exists_in_list(self):
        """Test ensure_model_available avec modèle existant dans la liste."""
        # Mock list_models to return model
        with patch.object(self.manager, "list_models") as mock_list:
            mock_list.return_value = [
                ModelInfo(name="test", status=ModelStatus.AVAILABLE)
            ]

            result = self.manager.ensure_model_available(self.test_api_url, "test")

            self.assertTrue(result)

    def test_ensure_model_available_matches_family_alias(self):
        """Allow config names like 'llava' to match API names like 'llava:latest'."""
        with patch.object(self.manager, "list_models") as mock_list:
            mock_list.return_value = [
                ModelInfo(name="llava:latest", status=ModelStatus.AVAILABLE)
            ]

            result = self.manager.ensure_model_available(self.test_api_url, "llava")

            self.assertTrue(result)

    def test_get_model_info_matches_family_alias(self):
        """get_model_info should resolve family aliases from the model list."""
        with patch.object(self.manager, "list_models") as mock_list:
            mock_list.return_value = [
                ModelInfo(name="llava:latest", status=ModelStatus.AVAILABLE)
            ]

            result = self.manager.get_model_info(self.test_api_url, "llava")

            self.assertIsNotNone(result)
            self.assertEqual(result.name, "llava:latest")

    def test_ensure_model_available_not_available_no_auto_download(self):
        """Test ensure_model_available sans téléchargement automatique."""
        # Mock list_models to return empty list (model not available)
        with patch.object(self.manager, "list_models", return_value=[]):
            result = self.manager.ensure_model_available(
                self.test_api_url, "test", auto_download=False
            )

            self.assertFalse(result)

    def test_ensure_model_available_with_auto_download_success(self):
        """Test ensure_model_available avec téléchargement automatique réussi."""
        # Mock list_models to return empty list initially
        with (
            patch.object(self.manager, "list_models", return_value=[]),
            patch.object(self.manager, "pull_model", return_value=True),
        ):
            result = self.manager.ensure_model_available(
                self.test_api_url, "test", auto_download=True
            )

            self.assertTrue(result)

    def test_ensure_model_available_with_auto_download_failure(self):
        """Test ensure_model_available avec téléchargement automatique échoué."""
        # Mock list_models to return empty list and pull_model to fail
        with (
            patch.object(self.manager, "list_models", return_value=[]),
            patch.object(self.manager, "pull_model", return_value=False),
        ):
            result = self.manager.ensure_model_available(
                self.test_api_url, "test", auto_download=True
            )

            self.assertFalse(result)

    def test_ensure_model_available_usage_tracking(self):
        """Test le suivi d'utilisation lors de ensure_model_available."""
        # Mock list_models to return available model
        with patch.object(self.manager, "list_models") as mock_list:
            mock_list.return_value = [
                ModelInfo(name="test", status=ModelStatus.AVAILABLE)
            ]

            # Call multiple times
            self.manager.ensure_model_available(self.test_api_url, "test")
            self.manager.ensure_model_available(self.test_api_url, "test")

            # Verify usage is tracked
            self.assertIn("test", self.manager._usage_stats)
            self.assertEqual(self.manager._usage_stats["test"]["use_count"], 2)

    # === TESTS DE USAGE STATISTICS ===

    def test_record_model_usage(self):
        """Test l'enregistrement de l'utilisation d'un modèle."""
        # Record usage multiple times
        self.manager._record_model_usage("test_model")
        self.manager._record_model_usage("test_model")

        self.assertIn("test_model", self.manager._usage_stats)
        self.assertEqual(self.manager._usage_stats["test_model"]["use_count"], 2)
        self.assertIsNotNone(self.manager._usage_stats["test_model"]["first_used"])
        self.assertIsNotNone(self.manager._usage_stats["test_model"]["last_used"])

    # === TESTS DE CACHE MANAGEMENT ===

    def test_clear_cache(self):
        """Test la suppression du cache."""
        # Populate cache
        model = ModelInfo(name="test", status=ModelStatus.AVAILABLE)
        self.manager.cache.set_model(model)

        # Clear cache
        self.manager.clear_cache()

        # Verify cache is cleared
        self.assertIsNone(self.manager.cache.get_model("test"))

    # === TESTS D'EXCEPTIONS ET CAS D'ERREUR ===

    def test_handle_download_progress_with_percentage(self):
        """Test la gestion du progrès de téléchargement avec pourcentage."""
        # Simulate download progress callback
        self.manager._download_status["test_model"] = {
            "status": "starting",
            "progress": 0.0,
        }
        self.manager._handle_download_progress(
            "test_model", "downloading", "Downloaded 75%"
        )

        # Verify progress is extracted and stored
        self.assertIn("test_model", self.manager._download_status)
        self.assertEqual(self.manager._download_status["test_model"]["progress"], 75.0)

    def test_handle_download_progress_without_percentage(self):
        """Test la gestion du progrès de téléchargement sans pourcentage."""
        self.manager._download_status["test_model"] = {
            "status": "starting",
            "progress": 0.0,
        }
        self.manager._handle_download_progress(
            "test_model", "downloading", "Downloading..."
        )

        # Progress should default to 0.0
        self.assertEqual(self.manager._download_status["test_model"]["progress"], 0.0)

    def test_manager_with_callback(self):
        """Test le manager avec callback de statut."""
        callback = MagicMock()
        self.manager.on_model_status_changed = callback

        # Mock ensure_model_available to trigger callback
        with patch.object(self.manager, "list_models") as mock_list:
            mock_list.return_value = [
                ModelInfo(name="test", status=ModelStatus.AVAILABLE)
            ]

            self.manager.ensure_model_available(self.test_api_url, "test")

            # Verify callback was called
            callback.assert_called()

    # === TESTS DE CAS RÉELS ===

    def test_realistic_model_workflow(self):
        """Test un workflow réaliste complet."""
        # 1. List models (empty initially)
        self.mock_api_client.list_models.return_value = []
        models = self.manager.list_models(self.test_api_url)
        self.assertEqual(len(models), 0)

        # 2. Try to ensure model available (should fail without auto_download)
        available = self.manager.ensure_model_available(self.test_api_url, "llama2:7b")
        self.assertFalse(available)

        # 3. Pull model
        self.mock_api_client.pull_model.return_value = True
        success = self.manager.pull_model(self.test_api_url, "llama2:7b")
        self.assertTrue(success)

        # 4. List models again (should now include the model)
        self.mock_api_client.list_models.return_value = [self.raw_model_data[0]]
        models = self.manager.list_models(self.test_api_url, force_refresh=True)
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].name, "llama2:7b")

        # 5. Ensure model available (should now succeed)
        available = self.manager.ensure_model_available(self.test_api_url, "llama2:7b")
        self.assertTrue(available)

    def test_concurrent_operations(self):
        """Test les opérations concurrentes."""
        # This is a simplified test for thread safety
        # In a real scenario, you'd want more sophisticated threading tests

        def mock_pull_model(model_name):
            # Simulate a successful download with a small delay
            time.sleep(0.05)
            return True

        with patch.object(
            self.mock_api_client, "pull_model", side_effect=mock_pull_model
        ):

            def pull_model_concurrent(model_name):
                return self.manager.pull_model(self.test_api_url, model_name)

            # Create multiple threads
            threads = []
            model_names = [f"model_{i}" for i in range(3)]
            for model_name in model_names:
                thread = threading.Thread(
                    target=pull_model_concurrent, args=(model_name,)
                )
                threads.append(thread)
                thread.start()

            # Wait for all threads
            for thread in threads:
                thread.join()

            # Verify all downloads were tracked
            self.assertEqual(len(self.manager._download_status), 3)
            for model_name in model_names:
                self.assertIn(model_name, self.manager._download_status)
                self.assertEqual(
                    self.manager._download_status[model_name]["status"], "completed"
                )

    # === TESTS DE PERFORMANCE ===

    def test_cache_performance(self):
        """Test les performances du cache."""
        # Add many models to test cache cleanup
        large_model_list = [
            ModelInfo(name=f"model_{i}", status=ModelStatus.AVAILABLE)
            for i in range(self.manager.cache.max_cache_size + 10)
        ]

        self.manager.cache.set_models(self.test_api_url, large_model_list)

        # Current omni-cache backed implementation stores all explicit inserts.
        stats = self.manager.cache.get_cache_stats()
        self.assertEqual(stats["total_models"], self.manager.cache.max_cache_size + 10)

    # === TESTS DE CONFIGURATION EDGE CASES ===

    def test_invalid_api_client(self):
        """Test avec un API client invalide."""
        # This would typically be caught at initialization
        # but we can test error handling in methods

        self.mock_api_client.list_models.side_effect = AttributeError("Invalid client")

        result = self.manager.list_models(self.test_api_url)
        self.assertEqual(len(result), 0)

    def test_empty_model_response(self):
        """Test avec une réponse vide de l'API."""
        self.mock_api_client.list_models.return_value = []

        result = self.manager.list_models(self.test_api_url)
        self.assertEqual(len(result), 0)

    def test_malformed_model_data(self):
        """Test avec des données de modèle malformées."""
        malformed_data = [
            {"name": ""},  # Empty name
            {"size": "invalid"},  # Invalid size
            {},  # Empty dict
            {"name": "valid_model", "size": 1000},  # Valid model
        ]

        self.mock_api_client.list_models.return_value = malformed_data

        # Should handle malformed data gracefully
        result = self.manager.list_models(self.test_api_url)

        # Should still create ModelInfo objects, even with missing/invalid data
        self.assertEqual(len(result), 4)


if __name__ == "__main__":
    # Configuration pour les tests
    unittest.TestLoader.sortTestMethodsUsing = None
    unittest.main(verbosity=2)
