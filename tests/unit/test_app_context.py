from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from ai_content_classifier import app_context


def test_build_application_services_wires_all_dependencies(monkeypatch):
    db_obj = object()
    repo_obj = object()
    perf_obj = object()
    query_obj = object()
    content_obj = object()
    metadata_obj = object()
    thumb_obj = object()
    llm_obj = object()
    controller_obj = object()

    db_ctor = MagicMock(return_value=db_obj)
    repo_ctor = MagicMock(return_value=repo_obj)
    perf_ctor = MagicMock(return_value=perf_obj)
    query_ctor = MagicMock(return_value=query_obj)
    content_ctor = MagicMock(return_value=content_obj)
    metadata_ctor = MagicMock(return_value=metadata_obj)
    thumb_ctor = MagicMock(return_value=thumb_obj)
    llm_ctor = MagicMock(return_value=llm_obj)
    controller_ctor = MagicMock(return_value=controller_obj)

    config_service = SimpleNamespace()
    config_service.initialize_default_settings = MagicMock()
    config_service.get = MagicMock(return_value="fr")
    config_ctor = MagicMock(return_value=config_service)

    i18n = SimpleNamespace(set_language=MagicMock())

    monkeypatch.setattr(app_context, "DatabaseService", db_ctor)
    monkeypatch.setattr(app_context, "ConfigRepository", repo_ctor)
    monkeypatch.setattr(app_context, "ConfigService", config_ctor)
    monkeypatch.setattr(app_context, "PerformanceMetrics", perf_ctor)
    monkeypatch.setattr(app_context, "QueryOptimizer", query_ctor)
    monkeypatch.setattr(app_context, "ContentDatabaseService", content_ctor)
    monkeypatch.setattr(app_context, "MetadataService", metadata_ctor)
    monkeypatch.setattr(app_context, "ThumbnailService", thumb_ctor)
    monkeypatch.setattr(app_context, "LLMService", llm_ctor)
    monkeypatch.setattr(app_context, "LLMController", controller_ctor)
    monkeypatch.setattr(app_context, "get_i18n_service", lambda: i18n)

    services = app_context.build_application_services("/tmp/app.db")

    db_ctor.assert_called_once_with("/tmp/app.db")
    repo_ctor.assert_called_once_with(db_obj)
    config_ctor.assert_called_once_with(repo_obj)
    config_service.initialize_default_settings.assert_called_once()
    config_service.get.assert_called_once_with(app_context.ConfigKey.LANGUAGE)
    i18n.set_language.assert_called_once_with("fr")

    perf_ctor.assert_called_once_with(history_size=1000, enable_detailed_tracking=True)
    query_ctor.assert_called_once_with(database_service=db_obj, metrics=perf_obj)
    content_ctor.assert_called_once_with(
        database_service=db_obj,
        query_optimizer=query_obj,
        metrics=perf_obj,
    )
    metadata_ctor.assert_called_once_with(extractors=None)
    thumb_ctor.assert_called_once_with(
        thumbnail_size=(256, 256),
        enable_caching=True,
        enable_progressive_loading=False,
        use_qt=False,
        max_pool_size=10,
        max_cache_size=300,
        max_workers=3,
    )
    llm_ctor.assert_called_once_with(
        config_service=config_service,
        database_service=db_obj,
        metrics=perf_obj,
    )
    controller_ctor.assert_called_once_with(
        config_service=config_service,
        llm_service=llm_obj,
    )

    assert services.database_service is db_obj
    assert services.config_service is config_service
    assert services.query_optimizer is query_obj
    assert services.performance_metrics is perf_obj
    assert services.llm_service is llm_obj
    assert services.llm_controller is controller_obj
    assert services.content_database_service is content_obj
    assert services.metadata_service is metadata_obj
    assert services.thumbnail_service is thumb_obj
