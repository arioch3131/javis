from unittest.mock import MagicMock

from ai_content_classifier.services.i18n.i18n_service import get_i18n_service
from ai_content_classifier.views.handlers.signal_router import SignalRouter
from ai_content_classifier.views.events.event_types import EventType


def test_connection_status_updates_llm_chip_state():
    main_window = MagicMock()
    router = SignalRouter(main_window)
    router.status_presenter = MagicMock()

    router._on_connection_status_updated("connected", "Connected to Ollama v0.6.0")

    router.status_presenter.update_connection_status.assert_called_once_with(
        "Connected to Ollama v0.6.0",
        is_connected=True,
    )


def test_filter_failed_uses_category_specific_notification():
    main_window = MagicMock()
    event_bus = MagicMock()
    router = SignalRouter(main_window, event_bus=event_bus)
    router.status_presenter = MagicMock()

    router._on_filter_failed(
        code="database_error",
        error_message="connection lost",
        active_filters={"category": ["Work"]},
    )

    event_bus.publish.assert_called_once()
    kwargs = event_bus.publish.call_args.kwargs
    assert kwargs["event_type"] == EventType.FILTER_ERROR
    assert kwargs["payload"]["code"] == "database_error"
    router.status_presenter.update_status.assert_called_once_with(
        "Filter not applied: database unavailable", is_busy=False
    )
    router.status_presenter.log_message.assert_called_once_with(
        "❌ Database error while applying filters: connection lost", "ERROR"
    )


def test_filter_failed_uses_french_templates_when_language_is_fr():
    main_window = MagicMock()
    event_bus = MagicMock()
    router = SignalRouter(main_window, event_bus=event_bus)
    router.status_presenter = MagicMock()
    i18n = get_i18n_service()

    previous_lang = i18n.language
    try:
        i18n.set_language("fr")
        router._on_filter_failed(
            code="validation_error",
            error_message="operateur invalide",
            active_filters={"extension": [".jpg"]},
        )
    finally:
        i18n.set_language(previous_lang)

    router.status_presenter.update_status.assert_called_once_with(
        "Filtre non applique: valeur de filtre invalide", is_busy=False
    )
    router.status_presenter.log_message.assert_called_once_with(
        "⚠️ Erreur de validation du filtre: operateur invalide", "WARNING"
    )
