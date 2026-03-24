from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ai_content_classifier.services.database.core.query_optimizer import QueryOptimizer


class TestQueryOptimizer:
    @pytest.fixture
    def mock_db_service(self):
        db_service = MagicMock()
        db_service.Session = MagicMock(return_value=MagicMock())
        return db_service

    @pytest.fixture
    def mock_runtime(self):
        runtime = MagicMock()
        runtime.get.return_value = None
        runtime.set.return_value = True
        return runtime

    @pytest.fixture
    def optimizer(self, mock_db_service, mock_runtime):
        with patch(
            "ai_content_classifier.services.database.core.query_optimizer.get_cache_runtime",
            return_value=mock_runtime,
        ):
            return QueryOptimizer(database_service=mock_db_service, cache_pool=None, metrics=None)

    def test_execute_cached_with_external_session_bypasses_cache(self, optimizer, mock_runtime):
        external_session = MagicMock()
        query_builder = MagicMock(return_value=["external"])

        result = optimizer.execute_cached(query_builder, cache_key="k", session=external_session)

        assert result == ["external"]
        query_builder.assert_called_once_with(external_session)
        mock_runtime.get.assert_not_called()
        mock_runtime.set.assert_not_called()

    def test_execute_cached_cache_hit_records_hit(self, mock_db_service, mock_runtime):
        metrics = SimpleNamespace(cache_hits=0, cache_misses=0)
        with patch(
            "ai_content_classifier.services.database.core.query_optimizer.get_cache_runtime",
            return_value=mock_runtime,
        ):
            optimizer = QueryOptimizer(
                database_service=mock_db_service, cache_pool=None, metrics=metrics
            )

        cached_value = [{"id": 1}]
        mock_runtime.get.return_value = cached_value

        result = optimizer.execute_cached(lambda _s: [{"id": 2}], cache_key="fixed-key")

        assert result == cached_value
        assert metrics.cache_hits == 1
        assert metrics.cache_misses == 0
        mock_runtime.get.assert_called_once_with("query:fixed-key", default=None, adapter="memory")
        mock_runtime.set.assert_not_called()

    def test_execute_cached_cache_miss_sets_cache_and_records_miss(
        self, optimizer, mock_runtime, mock_db_service
    ):
        query_obj = MagicMock()
        query_obj.all.return_value = ["fresh"]
        query_builder = MagicMock(return_value=query_obj)

        result = optimizer.execute_cached(query_builder, cache_key="miss-key")

        assert result == ["fresh"]
        mock_runtime.get.assert_called_once_with("query:miss-key", default=None, adapter="memory")
        mock_runtime.set.assert_called_once_with(
            "query:miss-key", ["fresh"], ttl=300, adapter="memory"
        )
        mock_db_service.Session.return_value.close.assert_called_once()

    def test_execute_cached_generates_key_when_missing(self, optimizer):
        with patch.object(optimizer, "_generate_cache_key", return_value="generated-key") as gen:
            optimizer.execute_cached(lambda _s: ["x"])
        gen.assert_called_once()

    def test_execute_cached_legacy_pool_exceptions_are_swallowed(self, mock_db_service, mock_runtime):
        cache_pool = MagicMock()
        cache_pool.acquire_context.side_effect = RuntimeError("pool failed")

        with patch(
            "ai_content_classifier.services.database.core.query_optimizer.get_cache_runtime",
            return_value=mock_runtime,
        ):
            optimizer = QueryOptimizer(database_service=mock_db_service, cache_pool=cache_pool)

        result = optimizer.execute_cached(lambda _s: [42], cache_key="legacy-error")

        assert result == [42]

    def test_execute_query_returns_non_query_result(self, optimizer, mock_db_service):
        result = optimizer._execute_query(lambda _s: {"ok": True}, None)

        assert result == {"ok": True}
        mock_db_service.Session.return_value.close.assert_called_once()

    def test_execute_query_does_not_close_external_session(self, optimizer):
        session = MagicMock()
        query = MagicMock()
        query.all.return_value = ["row"]

        result = optimizer._execute_query(lambda _s: query, session)

        assert result == ["row"]
        session.close.assert_not_called()

    def test_generate_cache_key_with_source(self, optimizer):
        def query_builder(_session):
            return []

        with patch("inspect.getsource", return_value="SELECT * FROM table"):
            key = optimizer._generate_cache_key(query_builder)

        assert key.startswith("query_")
        assert len(key) > len("query_")

    def test_generate_cache_key_fallback_when_source_unavailable(self, optimizer):
        def query_builder(_session):
            return []

        with patch("inspect.getsource", side_effect=OSError("no source")):
            key = optimizer._generate_cache_key(query_builder)

        assert key == f"query_{id(query_builder)}"

    def test_record_cache_hit_and_miss_guarded_without_metrics(self, optimizer):
        # No metrics configured -> should not raise.
        optimizer._record_cache_hit()
        optimizer._record_cache_miss()

    def test_record_cache_hit_and_miss_when_metric_fields_missing(self, mock_db_service, mock_runtime):
        metrics = SimpleNamespace()
        with patch(
            "ai_content_classifier.services.database.core.query_optimizer.get_cache_runtime",
            return_value=mock_runtime,
        ):
            optimizer = QueryOptimizer(database_service=mock_db_service, metrics=metrics)

        optimizer._record_cache_hit()
        optimizer._record_cache_miss()

        assert not hasattr(metrics, "cache_hits")
        assert not hasattr(metrics, "cache_misses")
