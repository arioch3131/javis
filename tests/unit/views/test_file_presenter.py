import os
from pathlib import Path
from unittest.mock import MagicMock

from ai_content_classifier.views.presenters.file_presenter import FilePresenter


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


def test_save_thumbnail_uses_centralized_cache_directory(tmp_path, monkeypatch):
    class _DummyThumbnail:
        def save(self, output_path: str, *_args, **_kwargs):
            Path(output_path).write_bytes(b"thumb")
            return True

    cache_root = tmp_path / "cache-root"
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_root))

    source_dir = tmp_path / "images"
    source_dir.mkdir(parents=True)
    source_path = source_dir / "photo.jpg"
    source_path.write_bytes(b"source")

    presenter = FilePresenter(MagicMock(), MagicMock())
    output_path = presenter._save_thumbnail_to_disk(_DummyThumbnail(), str(source_path))

    assert output_path is not None
    assert os.path.exists(output_path)
    assert f"{os.sep}.thumbnails{os.sep}" not in output_path
    assert str(cache_root / "Javis" / "thumbnails") in output_path


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
