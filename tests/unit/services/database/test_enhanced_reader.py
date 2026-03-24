from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ai_content_classifier.services.database.operations.enhanced_reader import (
    EnhancedContentReader,
)


class TestEnhancedContentReader:
    @pytest.fixture
    def mock_db_service(self):
        return MagicMock()

    @pytest.fixture
    def mock_query_optimizer(self):
        return MagicMock()

    @pytest.fixture
    def mock_metrics(self):
        return SimpleNamespace(visible_items=0, total_files=0)

    @pytest.fixture
    def mock_legacy_reader(self):
        return MagicMock()

    @pytest.fixture
    def reader(self, mock_db_service, mock_query_optimizer, mock_metrics, mock_legacy_reader):
        with patch(
            "ai_content_classifier.services.database.operations.enhanced_reader.ContentReader",
            return_value=mock_legacy_reader,
        ) as patched_reader:
            enhanced = EnhancedContentReader(mock_db_service, mock_query_optimizer, mock_metrics)
            enhanced._patched_content_reader = patched_reader
            return enhanced

    def test_init_wires_dependencies_and_builds_legacy_reader(
        self, reader, mock_db_service, mock_query_optimizer, mock_metrics, mock_legacy_reader
    ):
        assert reader.database_service is mock_db_service
        assert reader.query_optimizer is mock_query_optimizer
        assert reader.metrics is mock_metrics
        assert reader._legacy_reader is mock_legacy_reader
        reader._patched_content_reader.assert_called_once_with(mock_db_service)

    def test_find_items_with_external_session_delegates_to_legacy(
        self, reader, mock_legacy_reader, mock_query_optimizer
    ):
        session = MagicMock()
        expected = [MagicMock(), MagicMock()]
        mock_legacy_reader.find_items.return_value = expected

        result = reader.find_items(
            content_filter="cf",
            sort_by="path",
            sort_desc=True,
            limit=10,
            offset=3,
            eager_load=True,
            custom_filter=["x"],
            session=session,
        )

        assert result == expected
        mock_legacy_reader.find_items.assert_called_once_with(
            "cf",
            "path",
            True,
            10,
            3,
            True,
            ["x"],
            session,
        )
        mock_query_optimizer.execute_cached.assert_not_called()

    def test_find_items_without_session_uses_cache_and_updates_visible_items(
        self, reader, mock_legacy_reader, mock_query_optimizer, mock_metrics
    ):
        expected = [MagicMock(), MagicMock(), MagicMock()]
        fake_session = MagicMock()
        mock_legacy_reader.find_items.return_value = expected

        with patch.object(reader, "_build_cache_key", return_value="cache-key") as key_builder:
            def _exec(query_builder, cache_key):
                assert cache_key == "cache-key"
                return query_builder(fake_session)

            mock_query_optimizer.execute_cached.side_effect = _exec
            result = reader.find_items(content_filter="cf", sort_by="date_modified")

        assert result == expected
        key_builder.assert_called_once()
        mock_query_optimizer.execute_cached.assert_called_once()
        mock_legacy_reader.find_items.assert_called_once_with(
            "cf",
            "date_modified",
            False,
            None,
            0,
            False,
            None,
            fake_session,
        )
        assert mock_metrics.visible_items == 3

    def test_count_all_items_with_external_session_delegates_to_legacy(
        self, reader, mock_legacy_reader, mock_query_optimizer
    ):
        session = MagicMock()
        mock_legacy_reader.count_all_items.return_value = 42

        result = reader.count_all_items(session=session)

        assert result == 42
        mock_legacy_reader.count_all_items.assert_called_once_with(session)
        mock_query_optimizer.execute_cached.assert_not_called()

    def test_count_all_items_without_session_uses_cache_and_updates_metrics(
        self, reader, mock_legacy_reader, mock_query_optimizer, mock_metrics
    ):
        fake_session = MagicMock()
        mock_legacy_reader.count_all_items.return_value = 17

        def _exec(query_builder, cache_key):
            assert cache_key == "count_all_items"
            return query_builder(fake_session)

        mock_query_optimizer.execute_cached.side_effect = _exec
        result = reader.count_all_items()

        assert result == 17
        mock_query_optimizer.execute_cached.assert_called_once()
        mock_legacy_reader.count_all_items.assert_called_once_with(fake_session)
        assert mock_metrics.total_files == 17

    def test_getattr_delegates_to_legacy_reader(self, reader, mock_legacy_reader):
        mock_legacy_reader.custom_method.return_value = "delegated"

        result = reader.custom_method("arg1", kw="value")

        assert result == "delegated"
        mock_legacy_reader.custom_method.assert_called_once_with("arg1", kw="value")

    def test_build_cache_key_is_stable_for_same_arguments(self, reader):
        key1 = reader._build_cache_key("find_items", {"a": 1}, ["x", "y"], 10)
        key2 = reader._build_cache_key("find_items", {"a": 1}, ["x", "y"], 10)
        key3 = reader._build_cache_key("find_items", {"a": 2}, ["x", "y"], 10)

        assert key1 == key2
        assert key1 != key3
