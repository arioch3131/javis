from unittest.mock import MagicMock, patch

from ai_content_classifier.controllers.llm_controller import LLMController
from ai_content_classifier.models.config_models import ConfigKey
from ai_content_classifier.services.llm.llm_service import (
    ConnectionTestResult,
)


def test_update_config_emits_and_triggers_connection_test_when_url_changes():
    config_service = MagicMock()
    config_service.get.return_value = "http://localhost:1234"
    llm_service = MagicMock()
    llm_service.config_service = config_service
    llm_service.update_config.return_value = True

    with patch(
        "ai_content_classifier.controllers.llm_controller.QTimer.singleShot",
        side_effect=lambda _delay, fn: fn(),
    ):
        controller = LLMController(
            config_service=config_service, llm_service=llm_service
        )
        controller.test_connection = MagicMock()
        updated = []
        controller.configurationUpdated.connect(lambda: updated.append(True))

        controller.update_config()

    assert updated == [True]
    config_service.get.assert_called_with(ConfigKey.API_URL)
    controller.test_connection.assert_called_once_with("http://localhost:1234")


def test_test_connection_success_updates_state_and_emits_models():
    config_service = MagicMock()
    llm_service = MagicMock()
    llm_service.config_service = config_service
    llm_service.test_connection.return_value = ConnectionTestResult(
        success=True,
        message="ok",
        api_url="http://ok",
        response_time_ms=10.0,
        models=["m1", "m2"],
    )

    with patch(
        "ai_content_classifier.controllers.llm_controller.QTimer.singleShot",
        side_effect=lambda _delay, fn: fn(),
    ):
        controller = LLMController(
            config_service=config_service, llm_service=llm_service
        )
        statuses = []
        models = []
        controller.connectionStatusChanged.connect(
            lambda ok, msg: statuses.append((ok, msg))
        )
        controller.modelsRetrieved.connect(lambda items: models.append(items))

        controller.test_connection("http://ok")

    assert controller.is_connected is True
    assert controller.current_api_url == "http://ok"
    assert controller.current_models == ["m1", "m2"]
    assert statuses == [(True, "ok")]
    assert models == [["m1", "m2"]]


def test_classify_image_error_emits_operation_error():
    config_service = MagicMock()
    llm_service = MagicMock()
    llm_service.classify_image.side_effect = RuntimeError("boom")

    controller = LLMController(config_service=config_service, llm_service=llm_service)
    errors = []
    controller.operationError.connect(lambda op, msg: errors.append((op, msg)))

    result = controller.classify_image("/tmp/x.jpg", ["A", "B"])

    assert result is None
    assert len(errors) == 1
    assert errors[0][0] == "classify_image"
    assert "boom" in errors[0][1]


def test_compat_methods_and_cache_helpers():
    config_service = MagicMock()
    llm_service = MagicMock()
    llm_service.test_connection.return_value = ConnectionTestResult(
        success=True,
        message="connected",
        api_url="http://ok",
        response_time_ms=7.0,
        models=["foo"],
    )
    llm_service.get_cache_stats.return_value = {"hits": 1}

    controller = LLMController(config_service=config_service, llm_service=llm_service)

    ok, msg = controller.check_connection()
    assert ok is True
    assert msg == "connected"
    assert controller.list_models() == [{"name": "foo"}]
    assert controller.get_cache_stats() == {"hits": 1}

    controller.clear_cache()
    llm_service.clear_cache.assert_called_once()
    controller.shutdown()
    llm_service.shutdown.assert_called_once()


def test_update_config_error_path_emits_operation_error():
    config_service = MagicMock()
    llm_service = MagicMock()
    llm_service.update_config.side_effect = RuntimeError("bad update")
    llm_service.config_service = config_service
    controller = LLMController(config_service=config_service, llm_service=llm_service)
    errors = []
    controller.operationError.connect(lambda op, msg: errors.append((op, msg)))

    controller.update_config()

    assert errors
    assert errors[0][0] == "config_update"


def test_test_connection_failure_and_exception_paths():
    config_service = MagicMock()
    llm_service = MagicMock()
    llm_service.config_service = config_service
    llm_service.test_connection.return_value = ConnectionTestResult(
        success=False,
        message="nope",
        api_url="http://bad",
        response_time_ms=2.0,
        models=[],
    )
    controller = LLMController(config_service=config_service, llm_service=llm_service)

    statuses = []
    errors = []
    controller.connectionStatusChanged.connect(
        lambda ok, msg: statuses.append((ok, msg))
    )
    controller.operationError.connect(lambda op, msg: errors.append((op, msg)))

    controller.test_connection("http://bad")
    assert statuses == [(False, "nope")]
    assert errors == []
    assert controller.is_connected is False

    llm_service.test_connection.side_effect = RuntimeError("network")
    controller.test_connection("http://err")
    assert controller.is_connected is False
    assert errors
    assert errors[-1][0] == "connection_test"


def test_test_connection_skips_when_in_progress():
    config_service = MagicMock()
    llm_service = MagicMock()
    llm_service.config_service = config_service
    controller = LLMController(config_service=config_service, llm_service=llm_service)
    controller._connection_test_in_progress = True

    controller.test_connection("http://skip")

    llm_service.test_connection.assert_not_called()


def test_emit_on_main_thread_and_execute_callback_error(monkeypatch):
    import threading

    config_service = MagicMock()
    llm_service = MagicMock()
    controller = LLMController(config_service=config_service, llm_service=llm_service)

    called = []
    real_current_thread = threading.current_thread
    real_main_thread = threading.main_thread
    monkeypatch.setattr(
        "ai_content_classifier.controllers.llm_controller.threading.current_thread",
        lambda: object(),
    )
    monkeypatch.setattr(
        "ai_content_classifier.controllers.llm_controller.threading.main_thread",
        lambda: object(),
    )
    controller._emit_on_main_thread(lambda: called.append(True))
    assert called == [True]
    monkeypatch.setattr(
        "ai_content_classifier.controllers.llm_controller.threading.current_thread",
        real_current_thread,
    )
    monkeypatch.setattr(
        "ai_content_classifier.controllers.llm_controller.threading.main_thread",
        real_main_thread,
    )

    controller._execute_main_thread_callback(
        lambda: (_ for _ in ()).throw(RuntimeError("cb fail"))
    )


def test_classify_document_status_models_cache_and_compat_branches():
    config_service = MagicMock()
    llm_service = MagicMock()
    llm_service.classify_document.return_value = "doc-ok"
    llm_service.classify_image.return_value = "img-ok"
    controller = LLMController(config_service=config_service, llm_service=llm_service)

    assert controller.classify_document("/tmp/a.txt", ["A"]) == "doc-ok"
    assert controller.classify_image("/tmp/a.jpg", ["A"]) == "img-ok"
    controller.current_api_url = "http://x"
    controller.current_models = ["m1"]
    assert controller.get_connection_status() == (False, "http://x")
    models = controller.get_available_models()
    models.append("m2")
    assert controller.current_models == ["m1"]

    llm_service.get_cache_stats.side_effect = RuntimeError("cache boom")
    assert controller.get_cache_stats() == {}
    llm_service.clear_cache.side_effect = RuntimeError("clear boom")
    errors = []
    controller.operationError.connect(lambda op, msg: errors.append((op, msg)))
    controller.clear_cache()
    assert errors[-1][0] == "clear_cache"

    llm_service.shutdown.side_effect = RuntimeError("shutdown boom")
    controller.shutdown()

    llm_service.test_connection.return_value = ConnectionTestResult(
        success=False,
        message="no",
        api_url="",
        response_time_ms=1.0,
        models=[],
    )
    assert controller.list_models() == []
    llm_service.test_connection.side_effect = RuntimeError("oops")
    assert controller.check_connection() == (False, "oops")
    assert controller.list_models() == []
    assert errors[-1][0] == "list_models"
