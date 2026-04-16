from inspect import signature
from types import SimpleNamespace
from unittest.mock import MagicMock

from ai_content_classifier.services.database.content_reader import ContentReader
from ai_content_classifier.services.database.types import DatabaseOperationCode


class TestContentReader:
    def test_init_wires_dependencies(self):
        db_service = MagicMock()
        query_optimizer = MagicMock()
        metrics = SimpleNamespace(visible_items=0, total_files=0)

        reader = ContentReader(db_service, query_optimizer, metrics)

        assert reader.database_service is db_service
        assert reader.query_optimizer is query_optimizer
        assert reader.metrics is metrics

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
        reader = ContentReader(db_service, query_optimizer, metrics)

        result = reader.find_items()

        assert result.success is True
        assert result.code == DatabaseOperationCode.OK
        assert len(result.data["items"]) == 2
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
        reader = ContentReader(db_service, query_optimizer, metrics)

        result = reader.count_all_items()

        assert result.success is True
        assert result.code == DatabaseOperationCode.OK
        assert result.data["count"] == 12
        assert metrics.total_files == 12
        query_optimizer.execute_cached.assert_called_once()

    def test_find_items_signature_is_stable(self):
        assert isinstance(
            signature(ContentReader.find_items), type(signature(lambda: None))
        )
