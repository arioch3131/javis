from unittest.mock import MagicMock, patch

import pytest

from ai_content_classifier.models.config_models import ConfigKey
from ai_content_classifier.services.file.types import (
    FileOperationCode,
    FileOperationResult,
)
from ai_content_classifier.views.presenters.file_presenter import FilePresenter


class _FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args, **kwargs):
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class _FakeFileDetailsDialog:
    def __init__(self, _parent=None):
        self.previous_requested = _FakeSignal()
        self.next_requested = _FakeSignal()
        self.open_file_requested = _FakeSignal()
        self.clear_category_requested = _FakeSignal()

    def set_file_details(self, _details):
        return None

    def set_navigation_state(self, _has_previous, _has_next):
        return None

    def show(self):
        return None

    def raise_(self):
        return None

    def activateWindow(self):
        return None

    def close(self):
        return None


def test_visible_file_paths_prefers_main_window_current_files():
    main_window = MagicMock()
    main_window.current_files = [
        ("/tmp/filtered-a.png", "dir", "Cat", "image"),
        ("/tmp/filtered-b.png", "dir", "Cat", "image"),
    ]
    presenter = FilePresenter(main_window, MagicMock())
    presenter.displayed_files = [
        ("/tmp/unfiltered-a.png", "dir"),
        ("/tmp/unfiltered-b.png", "dir"),
        ("/tmp/unfiltered-c.png", "dir"),
    ]

    assert presenter._visible_file_paths() == [
        "/tmp/filtered-a.png",
        "/tmp/filtered-b.png",
    ]


def test_build_file_details_uses_column_confidence_with_metadata_fallback():
    main_window = MagicMock()
    presenter = FilePresenter(main_window, MagicMock())
    presenter.get_or_create_metadata = MagicMock(return_value={})
    presenter.get_or_create_thumbnail = MagicMock(return_value=None)

    content_item = MagicMock()
    content_item.content_type = "image"
    content_item.category = "Animals"
    content_item.tags = []
    content_item.classification_confidence = 0.82
    content_item.content_metadata = {"classification": {"confidence": 0.15}}
    presenter.db_service.get_content_by_path.return_value = content_item

    details = presenter._build_file_details("/tmp/red-panda.jpg")

    assert details["classification"]["confidence"] == 0.82


def test_build_file_details_falls_back_to_metadata_confidence():
    main_window = MagicMock()
    presenter = FilePresenter(main_window, MagicMock())
    presenter.get_or_create_metadata = MagicMock(return_value={})
    presenter.get_or_create_thumbnail = MagicMock(return_value=None)

    content_item = MagicMock()
    content_item.content_type = "image"
    content_item.category = "Animals"
    content_item.tags = []
    content_item.classification_confidence = None
    content_item.content_metadata = {"classification": {"confidence": 0.64}}
    presenter.db_service.get_content_by_path.return_value = content_item

    details = presenter._build_file_details("/tmp/red-panda.jpg")

    assert details["classification"]["confidence"] == 0.64


def test_clear_category_request_updates_db_details_and_visible_files():
    main_window = MagicMock()
    main_window.file_manager = MagicMock()
    presenter = FilePresenter(main_window, MagicMock())
    presenter._details_dialog = MagicMock()
    presenter._details_dialog_path = "/tmp/red-panda.jpg"
    presenter.db_service.clear_content_category = MagicMock(return_value=MagicMock())
    presenter._build_file_details = MagicMock(
        return_value={
            "file_path": "/tmp/red-panda.jpg",
            "classification": {"category": "Uncategorized"},
        }
    )

    presenter._on_clear_category_requested("/tmp/red-panda.jpg")

    presenter.db_service.clear_content_category.assert_called_once_with(
        "/tmp/red-panda.jpg"
    )
    presenter._details_dialog.set_file_details.assert_called_once()
    main_window.file_manager.refresh_and_emit_visible_files.assert_called_once()


def test_clear_category_request_ignores_empty_path():
    presenter = FilePresenter(MagicMock(), MagicMock())
    presenter.db_service.clear_content_category = MagicMock()

    presenter._on_clear_category_requested("")

    presenter.db_service.clear_content_category.assert_not_called()


def test_clear_category_request_stops_when_item_not_found():
    main_window = MagicMock()
    main_window.file_manager = MagicMock()
    presenter = FilePresenter(main_window, MagicMock())
    presenter._details_dialog = MagicMock()
    presenter._details_dialog_path = "/tmp/missing.jpg"
    presenter.db_service.clear_content_category = MagicMock(return_value=None)
    presenter.refresh_file_list = MagicMock()

    presenter._on_clear_category_requested("/tmp/missing.jpg")

    presenter._details_dialog.set_file_details.assert_not_called()
    main_window.file_manager.refresh_and_emit_visible_files.assert_not_called()
    presenter.refresh_file_list.assert_not_called()


def test_build_file_data_uses_batched_find_items_instead_of_n_plus_one():
    presenter = FilePresenter(MagicMock(), MagicMock())
    presenter.db_service.find_items.return_value = [
        MagicMock(path="/tmp/a.jpg", category="Animals", content_type="image"),
        MagicMock(path="/tmp/b.pdf", category="Docs", content_type="document"),
    ]

    file_data = presenter._build_file_data(
        [("/tmp/a.jpg", "/tmp"), ("/tmp/b.pdf", "/tmp")]
    )

    assert file_data == [
        ("/tmp/a.jpg", "/tmp", "Animals", "image"),
        ("/tmp/b.pdf", "/tmp", "Docs", "document"),
    ]
    presenter.db_service.find_items.assert_called_once()
    presenter.db_service.get_content_by_path.assert_not_called()


def test_build_file_data_batches_when_input_is_large():
    presenter = FilePresenter(MagicMock(), MagicMock())
    files = [(f"/tmp/{idx}.jpg", "/tmp") for idx in range(1205)]
    presenter.db_service.find_items.side_effect = [
        [MagicMock(path="/tmp/0.jpg", category="A", content_type="image")],
        [MagicMock(path="/tmp/801.jpg", category="B", content_type="image")],
    ]

    file_data = presenter._build_file_data(files)

    assert len(file_data) == 1205
    assert presenter.db_service.find_items.call_count == 2


def test_file_presenter_registers_disk_adapter_from_settings(monkeypatch):
    runtime = MagicMock()
    runtime.register_thumbnail_disk_adapter.return_value = True
    cache_handle = MagicMock()
    runtime.memory_cache.return_value = cache_handle

    monkeypatch.setattr(
        "ai_content_classifier.views.presenters.file_presenter.get_cache_runtime",
        lambda: runtime,
    )

    config_service = MagicMock()
    config_values = {
        ConfigKey.THUMBNAIL_CACHE_ENABLED: True,
        ConfigKey.THUMBNAIL_CACHE_TTL_SEC: 1200,
        ConfigKey.THUMBNAIL_CACHE_CLEANUP_INTERVAL_SEC: 45,
        ConfigKey.THUMBNAIL_CACHE_MAX_SIZE_MB: 512,
        ConfigKey.THUMBNAIL_CACHE_RENEW_ON_HIT: True,
        ConfigKey.THUMBNAIL_CACHE_RENEW_THRESHOLD: 0.75,
    }
    config_service.get.side_effect = lambda key: config_values[key]

    presenter = FilePresenter(MagicMock(), MagicMock(), config_service=config_service)

    assert presenter.thumbnail_cache is cache_handle
    runtime.register_thumbnail_disk_adapter.assert_called_once()
    runtime.memory_cache.assert_called_once()
    assert runtime.memory_cache.call_args.kwargs["adapter"] == "thumbnail_disk"


def test_get_or_create_thumbnail_pixmap_uses_cached_payload(monkeypatch):
    presenter = FilePresenter(MagicMock(), MagicMock())
    payload = b"png-bytes"
    sentinel_pixmap = object()

    presenter.thumbnail_cache.get = MagicMock(return_value=payload)
    presenter._pixmap_from_png_bytes = MagicMock(return_value=sentinel_pixmap)
    monkeypatch.setattr(
        "ai_content_classifier.views.presenters.file_presenter.is_image_file",
        lambda _path: True,
    )
    monkeypatch.setattr(
        "ai_content_classifier.views.presenters.file_presenter.os.path.exists",
        lambda _path: True,
    )

    out = presenter.get_or_create_thumbnail_pixmap("/tmp/example.jpg")
    assert out is sentinel_pixmap
    presenter._pixmap_from_png_bytes.assert_called_once_with(payload)


def test_get_or_create_thumbnail_pixmap_generates_and_stores_bytes(monkeypatch):
    presenter = FilePresenter(MagicMock(), MagicMock())
    sentinel_pixmap = object()
    presenter.thumbnail_cache.get = MagicMock(return_value=None)
    presenter.thumbnail_cache.set = MagicMock(return_value=True)
    presenter._thumbnail_to_png_bytes = MagicMock(return_value=b"generated-png")
    presenter._pixmap_from_png_bytes = MagicMock(return_value=sentinel_pixmap)
    presenter.thumbnail_service = MagicMock()
    presenter.thumbnail_service.create_thumbnail.return_value = MagicMock(
        success=True,
        thumbnail=object(),
    )
    monkeypatch.setattr(
        "ai_content_classifier.views.presenters.file_presenter.is_image_file",
        lambda _path: True,
    )
    monkeypatch.setattr(
        "ai_content_classifier.views.presenters.file_presenter.os.path.exists",
        lambda _path: True,
    )

    out = presenter.get_or_create_thumbnail_pixmap("/tmp/new.jpg")
    assert out is sentinel_pixmap
    presenter.thumbnail_cache.set.assert_called_once()
    assert isinstance(presenter.thumbnail_cache.set.call_args.args[1], bytes)


def test_open_file_request_uses_file_service_and_does_not_warn_on_success():
    main_window = MagicMock()
    main_window.file_manager = MagicMock()
    main_window.file_manager.file_service.open_file.return_value = MagicMock(
        success=True, message="ok"
    )
    presenter = FilePresenter(main_window, MagicMock())

    with patch(
        "ai_content_classifier.views.presenters.file_presenter.QMessageBox.warning"
    ) as warning_mock:
        presenter._on_open_file_requested("/tmp/example.png")

    main_window.file_manager.file_service.open_file.assert_called_once_with(
        "/tmp/example.png"
    )
    warning_mock.assert_not_called()


def test_open_file_request_shows_warning_on_failure():
    main_window = MagicMock()
    main_window.file_manager = MagicMock()
    main_window.file_manager.file_service.open_file.return_value = FileOperationResult(
        success=False,
        code=FileOperationCode.FILE_NOT_FOUND,
        message="File not found.",
        data={"path": "/tmp/missing.png"},
    )
    presenter = FilePresenter(main_window, MagicMock())

    with patch(
        "ai_content_classifier.views.presenters.file_presenter.QMessageBox.warning"
    ) as warning_mock:
        presenter._on_open_file_requested("/tmp/missing.png")

    warning_mock.assert_called_once()
    assert warning_mock.call_args.args[2] == (
        "File not found.\n"
        "Please verify the file still exists and refresh the file list."
    )


@pytest.mark.parametrize(
    ("operation_code", "service_message", "expected_ui_message"),
    [
        (
            FileOperationCode.FILE_NOT_FOUND,
            "File not found.",
            "File not found.\nPlease verify the file still exists and refresh the file list.",
        ),
        (
            FileOperationCode.NO_DEFAULT_APP,
            "No default application is available.",
            "No default app is configured for this file type.\nPlease set a default application and try again.",
        ),
        (
            FileOperationCode.ACCESS_DENIED,
            "Access denied while opening this file.",
            "Access denied while opening this file.\nPlease check file permissions and try again.",
        ),
        (
            FileOperationCode.UNKNOWN_ERROR,
            "Unexpected system error.",
            "Unexpected system error.\nPlease try again, and check system logs if the problem persists.",
        ),
    ],
)
def test_open_file_request_shows_actionable_error_message_to_ui(
    operation_code, service_message, expected_ui_message
):
    main_window = MagicMock()
    main_window.file_manager = MagicMock()
    main_window.file_manager.file_service.open_file.return_value = FileOperationResult(
        success=False,
        code=operation_code,
        message=service_message,
        data={"path": "/tmp/failure.txt"},
    )
    presenter = FilePresenter(main_window, MagicMock())

    with patch(
        "ai_content_classifier.views.presenters.file_presenter.QMessageBox.warning"
    ) as warning_mock:
        presenter._on_open_file_requested("/tmp/failure.txt")

    main_window.file_manager.file_service.open_file.assert_called_once_with(
        "/tmp/failure.txt"
    )
    warning_mock.assert_called_once_with(main_window, "Open file", expected_ui_message)


@pytest.mark.parametrize(
    ("operation_code", "service_message", "expected_ui_message"),
    [
        (
            FileOperationCode.FILE_NOT_FOUND,
            "File not found.",
            "File not found.\nPlease verify the file still exists and refresh the file list.",
        ),
        (
            FileOperationCode.NO_DEFAULT_APP,
            "No default application is available.",
            "No default app is configured for this file type.\nPlease set a default application and try again.",
        ),
        (
            FileOperationCode.ACCESS_DENIED,
            "Access denied while opening this file.",
            "Access denied while opening this file.\nPlease check file permissions and try again.",
        ),
        (
            FileOperationCode.UNKNOWN_ERROR,
            "Unexpected system error.",
            "Unexpected system error.\nPlease try again, and check system logs if the problem persists.",
        ),
    ],
)
def test_open_file_details_dialog_signal_shows_actionable_error_message_to_ui(
    operation_code, service_message, expected_ui_message
):
    main_window = MagicMock()
    main_window.file_manager = MagicMock()
    main_window.file_manager.file_service.open_file.return_value = FileOperationResult(
        success=False,
        code=operation_code,
        message=service_message,
        data={"path": "/tmp/from-dialog.txt"},
    )
    presenter = FilePresenter(main_window, MagicMock())
    presenter._build_file_details = MagicMock(
        return_value={
            "file_path": "/tmp/from-dialog.txt",
            "metadata": {"size_formatted": "1 KB", "extension": ".txt"},
            "content_type": "document",
            "classification": {"category": "Uncategorized"},
        }
    )

    with (
        patch(
            "ai_content_classifier.views.presenters.file_presenter.FileDetailsDialog",
            _FakeFileDetailsDialog,
        ),
        patch(
            "ai_content_classifier.views.presenters.file_presenter.QMessageBox.warning"
        ) as warning_mock,
    ):
        presenter.open_file_details_dialog("/tmp/from-dialog.txt")
        assert presenter._details_dialog is not None
        presenter._details_dialog.open_file_requested.emit("/tmp/from-dialog.txt")

    main_window.file_manager.file_service.open_file.assert_called_once_with(
        "/tmp/from-dialog.txt"
    )
    warning_mock.assert_called_once_with(main_window, "Open file", expected_ui_message)

    if presenter._details_dialog is not None:
        presenter._details_dialog.close()
