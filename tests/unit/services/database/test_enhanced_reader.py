from inspect import signature
from types import SimpleNamespace
from unittest.mock import MagicMock

from ai_content_classifier.services.database.content_reader import ContentReader
from ai_content_classifier.services.database.operations.enhanced_reader import (
    EnhancedContentReader,
)


class TestEnhancedContentReader:
    def test_init_wires_parent_reader_dependencies(self):
        db_service = MagicMock()
        query_optimizer = MagicMock()
        metrics = SimpleNamespace(visible_items=0, total_files=0)

        reader = EnhancedContentReader(db_service, query_optimizer, metrics)

        assert isinstance(reader, ContentReader)
        assert reader.database_service is db_service
        assert reader.query_optimizer is query_optimizer
        assert reader.metrics is metrics

    def test_explicit_api_surface_matches_content_reader(self):
        # Parity guard for the merged reader contract.
        assert set(dir(EnhancedContentReader)).issuperset(set(dir(ContentReader)))

    def test_find_items_uses_cache_and_updates_metrics(self):
        db_service = MagicMock()
        session = MagicMock()
        query = MagicMock()
        query.options.return_value = query
        query.all.return_value = [MagicMock(), MagicMock()]
        session.query.return_value = query
        db_service.Session.return_value = session

        query_optimizer = MagicMock()

        def _exec(query_builder, cache_key):
            assert cache_key
            return query_builder(session)

        query_optimizer.execute_cached.side_effect = _exec

        metrics = SimpleNamespace(visible_items=0, total_files=0)
        reader = EnhancedContentReader(db_service, query_optimizer, metrics)

        results = reader.find_items()

        assert len(results) == 2
        assert metrics.visible_items == 2
        query_optimizer.execute_cached.assert_called_once()

    def test_count_all_items_uses_cache_and_updates_metrics(self):
        db_service = MagicMock()
        session = MagicMock()
        query = MagicMock()
        query.scalar.return_value = 12
        session.query.return_value = query
        db_service.Session.return_value = session

        query_optimizer = MagicMock()

        def _exec(query_builder, cache_key):
            assert cache_key == "count_all_items"
            return query_builder(session)

        query_optimizer.execute_cached.side_effect = _exec

        metrics = SimpleNamespace(visible_items=0, total_files=0)
        reader = EnhancedContentReader(db_service, query_optimizer, metrics)

        count = reader.count_all_items()

        assert count == 12
        assert metrics.total_files == 12
        query_optimizer.execute_cached.assert_called_once()

    def test_find_items_signature_stays_compatible(self):
        assert signature(EnhancedContentReader.find_items) == signature(
            ContentReader.find_items
        )
