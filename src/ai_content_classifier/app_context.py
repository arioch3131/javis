"""
Application bootstrap helpers.

This module centralizes the construction of long-lived application services
so the UI layer can receive explicit dependencies instead of rebuilding them.
"""

from dataclasses import dataclass

from ai_content_classifier.controllers.llm_controller import LLMController
from ai_content_classifier.core.memory.metrics.performance_metrics import (
    PerformanceMetrics,
)
from ai_content_classifier.models.config_models import ConfigKey
from ai_content_classifier.repositories.config_repository import ConfigRepository
from ai_content_classifier.services.database.content_database_service import (
    ContentDatabaseService,
)
from ai_content_classifier.services.database.query_optimizer import QueryOptimizer
from ai_content_classifier.services.database.database_service import DatabaseService
from ai_content_classifier.services.i18n.i18n_service import get_i18n_service
from ai_content_classifier.services.llm.llm_service import LLMService
from ai_content_classifier.services.metadata.metadata_service import MetadataService
from ai_content_classifier.services.settings.config_service import ConfigService
from ai_content_classifier.services.thumbnail.thumbnail_service import ThumbnailService


@dataclass(slots=True)
class ApplicationServices:
    """Long-lived services shared across the application."""

    database_service: DatabaseService
    config_service: ConfigService
    query_optimizer: QueryOptimizer
    performance_metrics: PerformanceMetrics
    llm_service: LLMService
    llm_controller: LLMController
    content_database_service: ContentDatabaseService
    metadata_service: MetadataService
    thumbnail_service: ThumbnailService


def build_application_services(db_path: str) -> ApplicationServices:
    """Builds the shared service graph for the desktop application."""
    database_service = DatabaseService(db_path)

    config_repository = ConfigRepository(database_service)
    config_service = ConfigService(config_repository)
    config_service.initialize_default_settings()
    get_i18n_service().set_language(config_service.get(ConfigKey.LANGUAGE))

    performance_metrics = PerformanceMetrics(
        history_size=1000, enable_detailed_tracking=True
    )

    query_optimizer = QueryOptimizer(
        database_service=database_service,
        metrics=performance_metrics,
    )
    content_database_service = ContentDatabaseService(
        database_service=database_service,
        query_optimizer=query_optimizer,
        metrics=performance_metrics,
    )
    metadata_service = MetadataService(
        extractors=None,
    )
    thumbnail_service = ThumbnailService(
        thumbnail_size=(256, 256),
        enable_caching=True,
        enable_progressive_loading=False,
        use_qt=False,
        max_pool_size=10,
        max_cache_size=300,
        max_workers=3,
    )

    llm_service = LLMService(
        config_service=config_service,
        database_service=database_service,
        metrics=performance_metrics,
    )
    llm_controller = LLMController(
        config_service=config_service,
        llm_service=llm_service,
    )

    return ApplicationServices(
        database_service=database_service,
        config_service=config_service,
        query_optimizer=query_optimizer,
        performance_metrics=performance_metrics,
        llm_service=llm_service,
        llm_controller=llm_controller,
        content_database_service=content_database_service,
        metadata_service=metadata_service,
        thumbnail_service=thumbnail_service,
    )
