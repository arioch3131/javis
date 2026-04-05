from unittest.mock import MagicMock

from ai_content_classifier.views.handlers.signal_router import SignalRouter


def test_connection_status_updates_llm_chip_state():
    main_window = MagicMock()
    router = SignalRouter(main_window)
    router.status_presenter = MagicMock()

    router._on_connection_status_updated("connected", "Connected to Ollama v0.6.0")

    router.status_presenter.update_connection_status.assert_called_once_with(
        "Connected to Ollama v0.6.0",
        is_connected=True,
    )
