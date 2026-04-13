# services/llm/llm_service.py
"""
Unified LLM Service with integrated CategoryAnalyzer.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ai_content_classifier.core.logger import LoggableMixin
from ai_content_classifier.core.memory.metrics.performance_metrics import (
    PerformanceMetrics,
)
from ai_content_classifier.models.config_models import ConfigKey
from ai_content_classifier.services.llm.api_client import LLMApiClient
from ai_content_classifier.services.llm.category_analyzer import (
    CategoryAnalyzer,
    CategoryExtractionConfig,
)
from ai_content_classifier.services.llm.model_manager import ModelManager
from ai_content_classifier.services.database.database_service import DatabaseService
from ai_content_classifier.services.file.file_type_service import FileTypeService
from ai_content_classifier.services.preprocessing.text_extraction_service import (
    TextExtractionService,
)
from ai_content_classifier.services.settings.config_service import ConfigService
from ai_content_classifier.services.shared.cache_runtime import get_cache_runtime


class ClassificationStatus(Enum):
    """Status values for classification operations."""

    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ClassificationResult:
    """Result payload for a single content classification."""

    category: str
    confidence: float
    processing_time: float = 0.0
    status: ClassificationStatus = ClassificationStatus.COMPLETED
    model_used: str = ""
    cache_hit: bool = False
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    extraction_method: str = ""
    extraction_details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Converts the result to a serializable dictionary."""
        return {
            "category": self.category,
            "confidence": self.confidence,
            "processing_time": self.processing_time,
            "status": self.status.value,
            "model_used": self.model_used,
            "cache_hit": self.cache_hit,
            "error_message": self.error_message,
            "metadata": self.metadata or {},
            "extraction_method": self.extraction_method,
            "extraction_details": self.extraction_details,
        }


@dataclass
class ConnectionTestResult:
    """Result payload for connection checks."""

    success: bool
    message: str
    api_url: str
    response_time_ms: float
    models: List[str] = None
    error_details: str = ""

    def __post_init__(self):
        if self.models is None:
            self.models = []


class LLMService(LoggableMixin):
    """
    Unified LLM service with integrated CategoryAnalyzer - FIXED VERSION.
    """

    def __init__(
        self,
        config_service: ConfigService,
        database_service: Optional[DatabaseService] = None,
        cache_pool: Optional[Any] = None,
        metrics: Optional[PerformanceMetrics] = None,
        cache_size: int = 1000,
    ):
        """
        Initializes the LLM service with robust error handling.

        Args:
            config_service: Configuration service instance.
            database_service: Database service instance.
            cache_pool: Optional legacy cache object kept for backward compatibility.
            metrics: PerformanceMetrics instance for tracking.
        """
        super().__init__()
        self.__init_logger__()
        self.config_service = config_service
        self.database_service = database_service
        self.cache_pool = cache_pool
        self.metrics = metrics
        self._cache_runtime = get_cache_runtime()
        self.cache = self._cache_runtime.memory_cache(
            "llm:classification",
            default_ttl=1800,
        )

        # Initialize API client and ModelManager with the configured URL.
        try:
            api_url = self.config_service.get(ConfigKey.API_URL)
            self.logger.debug(f"LLMService: Retrieved API URL: {api_url}")
            self.api_client = LLMApiClient(api_url, self.config_service)
            self.logger.debug("LLMService: LLMApiClient initialized.")
            self.model_manager = ModelManager(self.api_client, self.config_service)
            self.logger.debug("LLMService: ModelManager initialized.")
        except Exception as e:
            self.logger.error(
                f"LLMService: Error initializing API client or ModelManager: {e}",
                exc_info=True,
            )
            self.api_client = None
            self.model_manager = None

        # CategoryAnalyzer with configurable confidence threshold
        try:
            confidence_threshold = self.config_service.get(
                ConfigKey.CONFIDENCE_THRESHOLD
            )
            self.category_analyzer = CategoryAnalyzer(
                config=CategoryExtractionConfig(
                    min_confidence_score=confidence_threshold
                ),
                log_level=self.logger.level,
            )
        except Exception as e:
            self.logger.error(f"Error initializing CategoryAnalyzer: {e}")
            self.category_analyzer = None

        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="LLM")
        self.text_extraction_service = TextExtractionService()

        self.stats = {
            "classifications_performed": 0,
            "cache_hits": 0,
            "successful_classifications": 0,
            "failed_classifications": 0,
            "average_confidence": 0.0,
            "extraction_methods_used": {},
        }

        self.logger.info("LLMService initialized with ConfigService.")

    @staticmethod
    def _make_cache_key(content_path: str, categories: List[str], model: str) -> str:
        categories_key = ",".join(sorted(categories))
        return f"{content_path}|{categories_key}|{model}"

    @staticmethod
    def _clone_cached_result(result: ClassificationResult) -> ClassificationResult:
        return ClassificationResult(
            category=result.category,
            confidence=result.confidence,
            processing_time=result.processing_time,
            status=result.status,
            model_used=result.model_used,
            cache_hit=True,
            error_message=result.error_message,
            metadata=result.metadata,
            extraction_method=result.extraction_method,
            extraction_details=result.extraction_details,
        )

    def update_config(self) -> bool:
        """Updates the service configuration from the ConfigService."""
        self.logger.info("Updating LLM service configuration from ConfigService.")
        old_url = self.api_client.api_url if self.api_client else None
        new_url = self.config_service.get(ConfigKey.API_URL)
        url_changed = old_url != new_url

        if url_changed:
            try:
                self.api_client = LLMApiClient(new_url, self.config_service)
                self.model_manager = ModelManager(self.api_client, self.config_service)
                self.cache.clear()
                self.logger.info(f"API client updated for {new_url}")
            except Exception as e:
                self.logger.error(f"Error updating API client: {e}")

        confidence_threshold = self.config_service.get(ConfigKey.CONFIDENCE_THRESHOLD)
        if self.category_analyzer:
            self.category_analyzer.config.min_confidence_score = confidence_threshold

        return url_changed

    def test_connection(self, api_url: str = None) -> ConnectionTestResult:
        """
        Quick connection test to the LLM API.

        Returns:
            ConnectionTestResult with test details
        """
        """
        Quick connection test to the LLM API.

        Args:
            api_url: URL of the API to test (uses current config if None)

        Returns:
            ConnectionTestResult with test details
        """
        if not self.api_client:
            return ConnectionTestResult(
                success=False,
                message="API Client not initialized",
                api_url=api_url or "N/A",
                response_time_ms=0.0,
                error_details="Service not available",
            )

        start_time = time.time()
        test_url = api_url or self.config_service.get(ConfigKey.API_URL)

        try:
            # If a different URL is provided, create a temporary client
            if api_url and api_url != self.config_service.get(ConfigKey.API_URL):
                temp_client = LLMApiClient(api_url, self.config_service)
                success, message = temp_client.check_connection()

                models = []
                if success:
                    try:
                        models_data = temp_client.list_models()
                        models = [
                            m.get("name", "") if isinstance(m, dict) else str(m)
                            for m in models_data
                        ]
                    except Exception as e:
                        self.logger.warning(
                            f"Could not retrieve models for {api_url}: {e}"
                        )
            else:
                # Use the main client
                success, message = self.api_client.check_connection()

                models = []
                if success:
                    try:
                        models_data = self.api_client.list_models()
                        models = [
                            m.get("name", "") if isinstance(m, dict) else str(m)
                            for m in models_data
                        ]
                    except Exception as e:
                        self.logger.warning(f"Could not retrieve models: {e}")

            response_time = (time.time() - start_time) * 1000

            return ConnectionTestResult(
                success=success,
                message=message,
                api_url=test_url,
                response_time_ms=response_time,
                models=models,
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ConnectionTestResult(
                success=False,
                message=f"Connection failed: {str(e)}",
                api_url=test_url,
                response_time_ms=response_time,
                error_details=str(e),
            )

    def classify_image(
        self, image_path: str, categories: List[str]
    ) -> ClassificationResult:
        """
        Classifies an image into the given categories.

        Args:
            image_path: Path to the image
            categories: List of possible categories

        Returns:
            ClassificationResult with the result
        """
        return self._classify_content(image_path, categories, "image")

    def classify_document(
        self, document_path: str, categories: List[str]
    ) -> ClassificationResult:
        """
        Classifies a document into the given categories.

        Args:
            document_path: Path to the document
            categories: List of possible categories

        Returns:
            ClassificationResult with the result
        """
        return self._classify_content(document_path, categories, "document")

    def _classify_content(
        self, content_path: str, categories: List[str], content_type: str
    ) -> ClassificationResult:
        """
        Unified internal classification with CategoryAnalyzer.

        Args:
            content_path: Content path
            categories: Possible categories
            content_type: "image" or "document"

        Returns:
            ClassificationResult with true calculated confidence
        """
        start_time = time.time()

        # Update statistics
        self.stats["classifications_performed"] += 1

        # Preliminary checks
        if not self.api_client:
            return self._create_error_result(
                "API Client not available", time.time() - start_time, "unknown"
            )

        if not categories:
            return self._create_error_result(
                "No categories provided", time.time() - start_time, "unknown"
            )

        # Model and prompt selection
        if content_type == "image":
            model = self.config_service.get(ConfigKey.IMAGE_MODEL)
            prompt_template = self.config_service.get(ConfigKey.IMAGE_PROMPT)
        else:
            model = self.config_service.get(ConfigKey.DOCUMENT_MODEL)
            prompt_template = self.config_service.get(ConfigKey.DOCUMENT_PROMPT)

        # Check cache first
        cache_key = self._make_cache_key(content_path, categories, model)
        cached_result = self.cache.get(cache_key, default=None)
        if cached_result:
            self.logger.debug(f"Cache hit for {content_path}")
            self.stats["cache_hits"] += 1
            return self._clone_cached_result(cached_result)

        try:
            resolved_model = model

            # Check model availability if model_manager is available
            if self.model_manager:
                if not self.model_manager.ensure_model_available(
                    self.config_service.get(ConfigKey.API_URL), model
                ):
                    self.stats["failed_classifications"] += 1
                    return self._create_error_result(
                        f"Model {model} not available", time.time() - start_time, model
                    )

                model_info = self.model_manager.get_model_info(
                    self.config_service.get(ConfigKey.API_URL), model
                )
                if model_info and model_info.name:
                    resolved_model = model_info.name
                    if resolved_model != model:
                        self.logger.info(
                            "Resolved configured model '%s' to available model '%s'",
                            model,
                            resolved_model,
                        )

            # Prepare prompt
            categories_str = ", ".join(categories)

            format_kwargs = {"categories": categories_str}
            if content_type == "image":
                format_kwargs["image_path"] = content_path
            else:
                format_kwargs["document_path"] = content_path
                format_kwargs["document_excerpt"] = self._build_document_excerpt(
                    content_path
                )

            prompt = prompt_template.format(**format_kwargs)
            prompt += (
                "\n\nReturn only valid JSON matching the schema. "
                "The 'confidence' field must be a float between 0.0 and 1.0 inclusive. "
                "Do not use percentages and do not return values like 90 or 90%."
            )
            response_schema = self._build_category_response_schema(categories)

            # Specific processing based on type
            if content_type == "image":
                try:
                    response = self.api_client.generate(
                        model_name=resolved_model,
                        prompt=prompt,
                        images=[content_path],  # Pass image path
                        response_format=response_schema,
                    )
                    self.logger.info(f"LLM Response (Image): {response}")
                except Exception as e:
                    raise Exception(f"Error processing image: {str(e)}")
            else:
                try:
                    # For documents, use generate without images
                    response = self.api_client.generate(
                        model_name=resolved_model,
                        prompt=prompt,
                        images=None,  # No image for documents
                        response_format=response_schema,
                    )
                    self.logger.debug(f"LLM Response (Document): {response}")
                except Exception as e:
                    raise Exception(f"Error processing document: {str(e)}")

            # ===== EXTRACTION WITH CATEGORYANALYZER OR FALLBACK =====
            structured_result = self._extract_category_from_structured_response(
                response, categories
            )
            if structured_result is not None:
                final_category, final_confidence = structured_result
                extraction_method = "structured_json_schema"
                extraction_details = (
                    "Category and confidence parsed from structured JSON response"
                )
                self.stats["extraction_methods_used"][extraction_method] = (
                    self.stats["extraction_methods_used"].get(extraction_method, 0) + 1
                )
            elif self.category_analyzer:
                # Use sophisticated CategoryAnalyzer
                extraction_result = (
                    self.category_analyzer.extract_category_with_confidence(
                        response, categories
                    )
                )

                # Update extraction statistics
                method = extraction_result.method
                if method not in self.stats["extraction_methods_used"]:
                    self.stats["extraction_methods_used"][method] = 0
                self.stats["extraction_methods_used"][method] += 1

                final_category = extraction_result.category
                final_confidence = extraction_result.confidence
                extraction_method = extraction_result.method
                extraction_details = extraction_result.details

            else:
                # Fallback to basic extraction if CategoryAnalyzer is unavailable
                self.logger.warning(
                    "CategoryAnalyzer unavailable, using basic extraction"
                )
                final_category = self._extract_category_basic(response, categories)
                final_confidence = 0.5  # Arbitrary confidence for basic method
                extraction_method = "basic_fallback"
                extraction_details = "CategoryAnalyzer unavailable"

                # Statistics for fallback
                if extraction_method not in self.stats["extraction_methods_used"]:
                    self.stats["extraction_methods_used"][extraction_method] = 0
                self.stats["extraction_methods_used"][extraction_method] += 1

            processing_time = time.time() - start_time

            # Build result with true confidence
            result = ClassificationResult(
                category=final_category,
                confidence=final_confidence,
                processing_time=processing_time,
                status=ClassificationStatus.COMPLETED,
                model_used=resolved_model,
                cache_hit=False,
                extraction_method=extraction_method,
                extraction_details=extraction_details,
            )

            # Cache result
            self.cache.set(cache_key, result)

            # Update statistics
            self.stats["successful_classifications"] += 1
            self._update_average_confidence(final_confidence)

            self.logger.debug(
                f"Classification successful: {final_category} "
                f"(confidence: {final_confidence:.2f}, "
                f"method: {extraction_method})"
            )

            return result

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Classification error {content_type}: {str(e)}"

            result = self._create_error_result(error_msg, processing_time, model)

            self.stats["failed_classifications"] += 1
            self.logger.error(error_msg, exc_info=True)
            return result

    def _build_document_excerpt(self, document_path: str) -> str:
        """
        Build a compact text excerpt for document classification.

        Uses a head+tail strategy to preserve both context and conclusions while
        keeping prompt size bounded.
        """
        try:
            configured_max = int(
                self.config_service.get(ConfigKey.PREPROCESS_TEXT_MAX_LENGTH)
            )
        except (TypeError, ValueError):
            configured_max = 12000

        # Keep prompts under control for novice-friendly defaults.
        excerpt_max_chars = max(500, min(configured_max, 12000))
        extraction = self.text_extraction_service.extract_text_for_llm(
            document_path, max_length=excerpt_max_chars * 2
        )

        if not extraction.success or extraction.is_empty:
            self.logger.debug(
                "Document text extraction failed/empty for %s: %s",
                document_path,
                extraction.error_message if extraction else "unknown error",
            )
            return ""

        text = extraction.text.strip()
        if len(text) <= excerpt_max_chars:
            return text

        head_size = int(excerpt_max_chars * 0.7)
        tail_size = excerpt_max_chars - head_size
        return f"{text[:head_size]}\n...\n{text[-tail_size:]}"

    def _extract_category_basic(self, response: str, categories: List[str]) -> str:
        """
        Basic extraction method if CategoryAnalyzer is unavailable.

        This method is a simple fallback that looks for direct matches.
        """
        if not response:
            return "unknown"

        response_lower = response.lower().strip()

        # Look for direct match
        for category in categories:
            if category.lower() in response_lower:
                return category

        # Look by words
        words = response_lower.split()
        for word in words:
            for category in categories:
                if word == category.lower():
                    return category

        return "unknown"

    def _build_category_response_schema(self, categories: List[str]) -> Dict[str, Any]:
        """Builds the Ollama JSON schema used to constrain output to one category."""
        return {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": categories,
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
            },
            "required": ["category", "confidence"],
        }

    def _extract_category_from_structured_response(
        self, response_text: str, categories: List[str]
    ) -> Optional[Tuple[str, float]]:
        """Returns (category, confidence) from a structured JSON response if valid."""
        if not response_text:
            return None

        try:
            parsed = json.loads(response_text)
        except (TypeError, json.JSONDecodeError):
            return None

        if not isinstance(parsed, dict):
            return None

        raw_category = parsed.get("category")
        if not isinstance(raw_category, str):
            return None
        raw_confidence = parsed.get("confidence")

        target = raw_category.strip()
        if not target:
            return None
        confidence = self._normalize_confidence(raw_confidence)

        for category in categories:
            if category == target:
                return category, confidence
            if category.lower() == target.lower():
                return category, confidence

        return None

    @staticmethod
    def _normalize_confidence(value: Any) -> float:
        """Normalizes confidence to a [0, 1] float, defaults to 1.0 if invalid."""
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.endswith("%"):
                stripped = stripped[:-1].strip()
                try:
                    confidence = float(stripped) / 100.0
                except (TypeError, ValueError):
                    return 1.0
                return max(0.0, min(1.0, confidence))
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 1.0
        if 1.0 < confidence <= 100.0:
            confidence /= 100.0
        return max(0.0, min(1.0, confidence))

    def _create_error_result(
        self, error_message: str, processing_time: float, model: str
    ) -> ClassificationResult:
        """Creates a standardized error result."""
        return ClassificationResult(
            category="unknown",
            confidence=0.0,
            status=ClassificationStatus.FAILED,
            error_message=error_message,
            processing_time=processing_time,
            model_used=model,
            extraction_method="error",
            extraction_details=error_message,
        )

    def _update_average_confidence(self, new_confidence: float) -> None:
        """Updates the average confidence incrementally."""
        successful = self.stats["successful_classifications"]
        if successful == 1:
            self.stats["average_confidence"] = new_confidence
        else:
            current_avg = self.stats["average_confidence"]
            self.stats["average_confidence"] = (
                (current_avg * (successful - 1)) + new_confidence
            ) / successful

    def _is_image_file(self, file_path: str) -> bool:
        """Determines if a file is an image based on its extension."""
        return FileTypeService.is_image_file(file_path)

    def get_extraction_statistics(
        self, response_text: str, categories: List[str]
    ) -> Dict[str, any]:
        """
        Gets detailed statistics on category extraction.

        This method directly uses the CategoryAnalyzer to analyze
        a response text and provide insights into the extraction process.

        Args:
            response_text: Response text to analyze
            categories: Available categories

        Returns:
            Dict with detailed statistics
        """
        if not self.category_analyzer:
            return {"error": "CategoryAnalyzer not available"}

        return self.category_analyzer.get_extraction_statistics(
            response_text, categories
        )

    def clear_cache(self) -> None:
        """Clear cached classification results."""
        self.cache.clear()
        self.logger.info("LLM classification cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Expose cache statistics for controller/UI consumers."""
        stats = self.cache.get_stats()
        stats["cache_size"] = self.cache.size()
        return stats

    def shutdown(self, log: bool = True) -> None:
        """Cleans up resources when the service is shut down."""
        try:
            if getattr(self, "_is_shutdown", False):
                return

            if hasattr(self, "_executor"):
                self._executor.shutdown(wait=True)

            self._is_shutdown = True
            if log:
                self.logger.info("LLMService properly shut down")
        except Exception as e:
            if log:
                self.logger.error(f"Error during shutdown: {e}")

    def __del__(self):
        """Cleans up on destruction."""
        try:
            # Avoid logging during interpreter shutdown (streams may already be closed).
            self.shutdown(log=False)
        except (AttributeError, RuntimeError):
            pass  # Avoid errors during destruction
