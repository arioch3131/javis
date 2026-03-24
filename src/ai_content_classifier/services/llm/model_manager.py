import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ai_content_classifier.core.logger import LoggableMixin, logging
from ai_content_classifier.models.config_models import ConfigKey
from ai_content_classifier.services.settings.config_service import ConfigService
from ai_content_classifier.services.llm.api_client import LLMApiClient
from ai_content_classifier.services.shared.cache_runtime import get_cache_runtime


class ModelStatus(Enum):
    """Enumeration of possible model states."""

    UNKNOWN = "unknown"
    AVAILABLE = "available"
    DOWNLOADING = "downloading"
    FAILED = "failed"
    CACHED = "cached"
    UPDATING = "updating"


@dataclass
class ModelInfo:
    """
    Comprehensive information about a model.

    Contains all relevant metadata about a model including version,
    size, capabilities, and current status.
    """

    name: str
    size: Optional[int] = None
    digest: Optional[str] = None
    modified_at: Optional[str] = None
    status: ModelStatus = ModelStatus.UNKNOWN
    version: Optional[str] = None
    family: Optional[str] = None
    format: Optional[str] = None
    parameter_size: Optional[str] = None
    quantization_level: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    last_used: Optional[float] = None
    use_count: int = 0
    download_progress: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Parse additional information from model name."""
        self._parse_model_name()

    def _parse_model_name(self):
        """Extract version, family and other info from model name."""
        if not self.name:
            return

        # Parse common naming patterns like "llama2:7b", "mistral:7b-instruct"
        if ":" in self.name:
            base_name, tag = self.name.split(":", 1)
            self.family = base_name

            # Try to extract parameter size
            if "b" in tag.lower():
                import re

                size_match = re.search(r"(\d+\.?\d*)b", tag.lower())
                if size_match:
                    self.parameter_size = f"{size_match.group(1)}B"

            # Check for quantization info
            if "q" in tag.lower():
                quant_match = re.search(r"q(\d+)", tag.lower())
                if quant_match:
                    self.quantization_level = f"Q{quant_match.group(1)}"

            # Extract capabilities from tag
            capabilities_map = {
                "instruct": "instruction_following",
                "chat": "conversational",
                "code": "code_generation",
                "vision": "multimodal_vision",
                "embed": "embeddings",
            }

            for key, capability in capabilities_map.items():
                if key in tag.lower():
                    self.capabilities.append(capability)

    @property
    def is_available(self) -> bool:
        """Check if model is available for use."""
        return self.status in [ModelStatus.AVAILABLE, ModelStatus.CACHED]

    @property
    def is_downloading(self) -> bool:
        """Check if model is currently downloading."""
        return self.status == ModelStatus.DOWNLOADING

    @property
    def has_error(self) -> bool:
        """Check if model has an error."""
        return self.status == ModelStatus.FAILED

    @property
    def size_mb(self) -> Optional[float]:
        """Get model size in MB."""
        if self.size:
            return self.size / (1024 * 1024)
        return None

    @property
    def size_gb(self) -> Optional[float]:
        """Get model size in GB."""
        if self.size:
            return self.size / (1024 * 1024 * 1024)
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert ModelInfo to dictionary for serialization."""
        return {
            "name": self.name,
            "size": self.size,
            "size_mb": self.size_mb,
            "size_gb": self.size_gb,
            "digest": self.digest,
            "modified_at": self.modified_at,
            "status": self.status.value,
            "version": self.version,
            "family": self.family,
            "format": self.format,
            "parameter_size": self.parameter_size,
            "quantization_level": self.quantization_level,
            "capabilities": self.capabilities,
            "tags": self.tags,
            "last_used": self.last_used,
            "use_count": self.use_count,
            "download_progress": self.download_progress,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


@dataclass
class ModelCache:
    """
    Intelligent cache for model information and status.

    Manages caching of model lists, status, and metadata with
    configurable TTL and intelligent invalidation.
    """

    cache_ttl: int = 300  # 5 minutes default TTL
    max_cache_size: int = 1000

    def __post_init__(self):
        self._lock = threading.RLock()
        runtime = get_cache_runtime()
        self._models_cache = runtime.memory_cache(
            "llm:model_manager:models",
            default_ttl=self.cache_ttl,
        )
        self._api_url_cache = runtime.memory_cache(
            "llm:model_manager:api_urls",
            default_ttl=self.cache_ttl,
        )

    def get_models(self, api_url: str) -> Optional[List[ModelInfo]]:
        """Get cached models for an API URL."""
        with self._lock:
            return self._api_url_cache.get(api_url, default=None)

    def set_models(self, api_url: str, models: List[ModelInfo]):
        """Cache models for an API URL."""
        with self._lock:
            self._api_url_cache.set(api_url, models)

            # Update individual model cache
            for model in models:
                self._models_cache.set(model.name, model)

    def get_model(self, model_name: str) -> Optional[ModelInfo]:
        """Get cached model info."""
        with self._lock:
            return self._models_cache.get(model_name, default=None)

    def set_model(self, model: ModelInfo):
        """Cache individual model info."""
        with self._lock:
            self._models_cache.set(model.name, model)

    def update_model_status(
        self,
        model_name: str,
        status: ModelStatus,
        progress: float = 0.0,
        error_message: Optional[str] = None,
    ):
        """Update model status in cache."""
        with self._lock:
            model = self._models_cache.get(model_name, default=None)
            if model is None:
                return
            model.status = status
            model.download_progress = progress
            if error_message:
                model.error_message = error_message
            self._models_cache.set(model_name, model)

    def invalidate_model(self, model_name: str):
        """Invalidate cached model info."""
        with self._lock:
            self._models_cache.delete(model_name)

    def invalidate_api_url(self, api_url: str):
        """Invalidate cached models for an API URL."""
        with self._lock:
            self._api_url_cache.delete(api_url)

    def clear_all(self):
        """Clear all cached data."""
        with self._lock:
            self._models_cache.clear()
            self._api_url_cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            model_stats = self._models_cache.get_stats()
            api_url_stats = self._api_url_cache.get_stats()
            return {
                "total_models": self._models_cache.size(),
                "valid_models": self._models_cache.size(),
                "api_urls_cached": self._api_url_cache.size(),
                "cache_ttl": self.cache_ttl,
                "max_cache_size": self.max_cache_size,
                "cache_hit_ratio": model_stats.get("hit_rate", 0.0),
                "model_cache_stats": model_stats,
                "api_url_cache_stats": api_url_stats,
            }


class ModelManager(LoggableMixin):
    """
    Enhanced model manager for LLM lifecycle and operations.

    This class handles model discovery, availability checking, downloading,
    and caching with advanced features like versioning, status tracking,
    and performance monitoring.
    """

    def __init__(
        self,
        api_client: LLMApiClient,
        config_service: ConfigService,
        log_level: int = logging.INFO,
    ):
        """
        Initialize the enhanced model manager.

        Args:
            api_client (LLMApiClient): API client to use for model operations.
            log_level: The logging level to use (default: logging.INFO)
        """
        self.api_client = api_client
        self.config_service = config_service
        self.__init_logger__(log_level)

        # Initialize cache and state tracking
        self.cache = ModelCache(
            cache_ttl=self.config_service.get(ConfigKey.API_CONNECTION_TIMEOUT)
            * 5,  # 5x list timeout
            max_cache_size=1000,
        )

        # Track download operations
        self._download_status: Dict[str, Dict[str, Any]] = {}
        self._download_lock = threading.RLock()

        # Model usage statistics
        self._usage_stats: Dict[str, Dict[str, Any]] = {}
        self._stats_lock = threading.RLock()

        # Callback function that will be called when model status changes
        self.on_model_status_changed: Optional[Callable[[str, str], None]] = None

        self.logger.info(
            "Enhanced ModelManager initialized with caching and versioning support"
        )

    @staticmethod
    def _normalize_model_name(model_name: str) -> str:
        """Return the base family name for tagged model identifiers."""
        return (model_name or "").split(":", 1)[0].strip().lower()

    def _matches_model_name(self, requested_name: str, candidate: ModelInfo) -> bool:
        """Match exact names first, then family aliases like `llava` vs `llava:latest`."""
        requested = (requested_name or "").strip()
        if not requested or not candidate.name:
            return False

        if candidate.name == requested:
            return True

        requested_base = self._normalize_model_name(requested)
        candidate_base = self._normalize_model_name(candidate.name)
        candidate_family = (candidate.family or "").strip().lower()

        return requested_base in {candidate_base, candidate_family}

    def list_models(self, api_url: str, force_refresh: bool = False) -> List[ModelInfo]:
        """
        Retrieve a list of all available models from the LLM service.

        Args:
            api_url (str): The base URL for the LLM API service to query.
            force_refresh (bool): Force refresh of cache, ignore cached data.

        Returns:
            List[ModelInfo]: List of enhanced model information objects.
        """

        # Try cache first unless force refresh
        if not force_refresh:
            cached_models = self.cache.get_models(api_url)
            if cached_models:
                self.logger.debug(
                    f"Retrieved {len(cached_models)} models from cache for {api_url}"
                )
                return cached_models

        self.logger.debug(f"Fetching fresh model list from API at {api_url}")

        # Ensure the API client is configured with the correct URL
        if self.api_client.api_url != api_url:
            self.logger.debug(
                f"Updating API client URL from {self.api_client.api_url} to {api_url}"
            )
            self.api_client.api_url = api_url

        try:
            # Get raw model data from API
            raw_models = self.api_client.list_models()

            # Convert to enhanced ModelInfo objects
            models = []
            for raw_model in raw_models:
                model_info = self._create_model_info(raw_model)
                models.append(model_info)

            # Cache the results
            self.cache.set_models(api_url, models)

            self.logger.info(f"Retrieved and cached {len(models)} models from API")
            return models

        except Exception as e:
            self.logger.error(
                f"Failed to retrieve models from {api_url}: {e}", exc_info=True
            )

            # Try to return stale cache data if available
            cached_models = self.cache.get_models(api_url)
            if cached_models:
                self.logger.warning("Returning stale cached data due to API failure")
                return cached_models

            return []

    def _create_model_info(self, raw_model: Dict[str, Any]) -> ModelInfo:
        """Convert raw model data to ModelInfo object."""
        model_info = ModelInfo(
            name=raw_model.get("name", ""),
            size=raw_model.get("size"),
            digest=raw_model.get("digest"),
            modified_at=raw_model.get("modified_at"),
            status=ModelStatus.AVAILABLE,
            metadata=raw_model,
        )

        # Extract additional info from details if available
        details = raw_model.get("details", {})
        if details:
            model_info.format = details.get("format")
            model_info.family = details.get("family")
            model_info.parameter_size = details.get("parameter_size")
            model_info.quantization_level = details.get("quantization_level")

        return model_info

    def get_model_info(
        self, api_url: str, model_name: str, force_refresh: bool = False
    ) -> Optional[ModelInfo]:
        """
        Get detailed information about a specific model.

        Args:
            api_url (str): The base URL for the LLM API service.
            model_name (str): Name of the model to get info for.
            force_refresh (bool): Force refresh from API.

        Returns:
            Optional[ModelInfo]: Model information or None if not found.
        """
        # Try cache first
        if not force_refresh:
            cached_model = self.cache.get_model(model_name)
            if cached_model:
                self.logger.debug(f"Retrieved model info for '{model_name}' from cache")
                return cached_model

        # Get from full model list
        models = self.list_models(api_url, force_refresh)
        for model in models:
            if self._matches_model_name(model_name, model):
                self.logger.debug(f"Found model info for '{model_name}' in fresh list")
                return model

        self.logger.warning(f"Model '{model_name}' not found in available models")
        return None

    def pull_model(self, api_url: str, model_name: str) -> bool:
        """
        Download a model from the LLM service to make it available locally.

        Args:
            api_url (str): The base URL for the LLM API service.
            model_name (str): Identifier of the model to download.

        Returns:
            bool: True if download was successful, False if it failed.
        """
        self.logger.info(f"Initiating download of model: '{model_name}' from {api_url}")

        # Update download tracking
        with self._download_lock:
            self._download_status[model_name] = {
                "status": "starting",
                "progress": 0.0,
                "start_time": time.time(),
                "api_url": api_url,
            }

        # Update cache with downloading status
        self.cache.update_model_status(model_name, ModelStatus.DOWNLOADING)

        # Ensure the API client is configured with the correct URL
        if self.api_client.api_url != api_url:
            self.logger.debug(
                f"Updating API client URL from {self.api_client.api_url} to {api_url}"
            )
            self.api_client.api_url = api_url

        # Set up progress callback
        original_callback = self.api_client.on_model_status_changed

        def progress_callback(status: str, message: str):
            self._handle_download_progress(model_name, status, message)
            if original_callback:
                original_callback(status, message)

        self.api_client.on_model_status_changed = progress_callback

        try:
            # Call the updated pull_model method (without api_url parameter)
            result = self.api_client.pull_model(model_name)

            # Update final status
            if result:
                self.cache.update_model_status(model_name, ModelStatus.AVAILABLE)
                with self._download_lock:
                    if model_name in self._download_status:
                        self._download_status[model_name].update(
                            {
                                "status": "completed",
                                "progress": 100.0,
                                "end_time": time.time(),
                            }
                        )
                self.logger.info(f"Model '{model_name}' download succeeded")
            else:
                self.cache.update_model_status(
                    model_name, ModelStatus.FAILED, error_message="Download failed"
                )
                with self._download_lock:
                    if model_name in self._download_status:
                        self._download_status[model_name].update(
                            {"status": "failed", "end_time": time.time()}
                        )
                self.logger.error(f"Model '{model_name}' download failed")

            # Invalidate cache to get fresh model list
            self.cache.invalidate_api_url(api_url)

            return result

        except Exception as e:
            self.logger.exception(
                f"Exception occurred while downloading model '{model_name}': {str(e)}"
            )
            self.cache.update_model_status(
                model_name, ModelStatus.FAILED, error_message=str(e)
            )
            with self._download_lock:
                if model_name in self._download_status:
                    self._download_status[model_name].update(
                        {"status": "error", "error": str(e), "end_time": time.time()}
                    )
            return False

        finally:
            # Restore original callback
            self.api_client.on_model_status_changed = original_callback

    def _handle_download_progress(self, model_name: str, status: str, message: str):
        """Handle download progress updates."""
        progress = 0.0

        # Try to extract progress percentage from message
        if "%" in message:
            import re

            match = re.search(r"(\d+)%", message)
            if match:
                progress = float(match.group(1))

        # Update cache
        if status == "downloading":
            self.cache.update_model_status(
                model_name, ModelStatus.DOWNLOADING, progress
            )

        # Update download tracking
        with self._download_lock:
            if model_name in self._download_status:
                self._download_status[model_name].update(
                    {
                        "status": status,
                        "progress": progress,
                        "last_message": message,
                        "last_update": time.time(),
                    }
                )

        self.logger.debug(
            f"Download progress for '{model_name}': {progress}% - {message}"
        )

    def ensure_model_available(
        self, api_url: str, model_name: str, auto_download: bool = False
    ) -> bool:
        """
        Check if the model is available and optionally download it.

        CORRECTION: auto_download=False by default to avoid unwanted downloads

        Args:
            api_url (str): The base URL for the LLM API service.
            model_name (str): Name of the model to check and potentially download.
            auto_download (bool): Whether to automatically download if not available

        Returns:
            bool: True if the model is available (or downloaded if auto_download=True)
        """
        self.logger.debug(
            f"Checking availability of model: '{model_name}' from {api_url}"
        )

        # Record usage
        self._record_model_usage(model_name)

        # Check cache first for quick response
        cached_model = self.cache.get_model(model_name)
        if cached_model and cached_model.is_available:
            message = f"Model '{model_name}' is available (cached)"
            self.logger.debug(message)
            if self.on_model_status_changed:
                self.on_model_status_changed("success", message)
            return True

        # Check if model is currently downloading
        if cached_model and cached_model.is_downloading:
            message = f"Model '{model_name}' is currently downloading"
            self.logger.info(message)
            if self.on_model_status_changed:
                self.on_model_status_changed("downloading", message)
            return False

        # Get fresh model list to verify availability
        available_models = self.list_models(api_url)
        model_exists = any(
            self._matches_model_name(model_name, model) for model in available_models
        )

        if model_exists:
            # Model is already available
            message = f"Model '{model_name}' is available for use"
            self.logger.info(message)
            if self.on_model_status_changed:
                self.on_model_status_changed("success", message)
            return True
        else:
            # CORRECTION: Do NOT automatically download by default
            if auto_download:
                # Model needs to be downloaded (only if explicitly requested)
                message = f"Model '{model_name}' not available locally, initiating download..."
                self.logger.info(message)
                if self.on_model_status_changed:
                    self.on_model_status_changed("pending", message)

                # Attempt to download the model
                download_success = self.pull_model(api_url, model_name)

                # Update status based on download result
                if download_success:
                    success_message = f"Successfully downloaded model '{model_name}'"
                    self.logger.info(success_message)
                    if self.on_model_status_changed:
                        self.on_model_status_changed("success", success_message)
                else:
                    failure_message = f"Failed to download model '{model_name}'"
                    self.logger.error(failure_message)
                    if self.on_model_status_changed:
                        self.on_model_status_changed("error", failure_message)

                return download_success
            else:
                # CORRECTION: Just indicate that the model is not available
                message = f"Model '{model_name}' not available locally"
                self.logger.info(message)
                if self.on_model_status_changed:
                    self.on_model_status_changed("not_available", message)
                return False

    def _record_model_usage(self, model_name: str):
        """Record model usage statistics."""
        with self._stats_lock:
            if model_name not in self._usage_stats:
                self._usage_stats[model_name] = {
                    "use_count": 0,
                    "first_used": time.time(),
                    "last_used": time.time(),
                }

            self._usage_stats[model_name]["use_count"] += 1
            self._usage_stats[model_name]["last_used"] = time.time()

        # Update cache as well
        cached_model = self.cache.get_model(model_name)
        if cached_model:
            cached_model.use_count = self._usage_stats[model_name]["use_count"]
            cached_model.last_used = self._usage_stats[model_name]["last_used"]
            self.cache.set_model(cached_model)

    def clear_cache(self):
        """Clear all cached data."""
        self.cache.clear_all()
        self.logger.info("Model cache cleared")
