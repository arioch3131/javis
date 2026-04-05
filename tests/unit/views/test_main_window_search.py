from unittest.mock import MagicMock

from ai_content_classifier.views.main_window.main import MainWindow


def test_matches_search_is_accent_and_separator_tolerant():
    window = MainWindow.__new__(MainWindow)

    assert window._matches_search(
        ("/tmp/mon_fichier-ete.jpg", "/tmp", "Icônes été", "image"),
        "icones ete",
    )
    assert window._matches_search(
        ("/tmp/mon_fichier-ete.jpg", "/tmp", "Icônes été", "image"),
        "mon fichier",
    )


def test_set_search_query_is_debounced_until_timer_fires():
    window = MainWindow.__new__(MainWindow)
    window._search_timer = MagicMock()
    window._refresh_displayed_files = MagicMock()
    window._pending_search_query = ""
    window._search_query = ""

    window.set_search_query("panda")

    assert window._pending_search_query == "panda"
    assert window._search_query == ""
    window._search_timer.start.assert_called_once_with(180)


def test_refresh_displayed_files_updates_only_active_view():
    window = MainWindow.__new__(MainWindow)
    window.current_view_mode = "grid"
    window._search_query = ""
    window._sort_mode = "Name"
    window._raw_visible_files = [("/tmp/example.png", "/tmp", "Animals", "image")]
    window._search_index = [
        (
            window._raw_visible_files[0],
            window._build_search_haystack(window._raw_visible_files[0]),
        )
    ]
    window.thumbnail_grid_widget = MagicMock()
    window.file_list_widget = MagicMock()
    window.columns_widget = MagicMock()
    window._has_received_file_data = True
    window.ui_builder = MagicMock()
    window._update_file_statistics = MagicMock()

    window._refresh_displayed_files()

    window.thumbnail_grid_widget.set_file_data.assert_called_once()
    window.file_list_widget.set_file_data.assert_not_called()
    assert window.columns_widget.addTopLevelItem.call_count == 0
