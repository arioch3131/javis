from unittest.mock import MagicMock

from ai_content_classifier.services.shared.cache_runtime import (
    NamespacedMemoryCache,
    OmniCacheRuntime,
    SmartPoolHandle,
)


def test_cache_runtime_returns_fallback_values_without_manager():
    runtime = OmniCacheRuntime()
    runtime._initialized = True
    runtime._manager = None

    assert runtime.is_available() is False
    assert runtime.get("missing", default="fallback") == "fallback"
    assert runtime.set("k", "v") is False
    assert runtime.delete("k") is False
    assert runtime.clear() is False


def test_cache_runtime_singleton_getter():
    from ai_content_classifier.services.shared.cache_runtime import get_cache_runtime

    assert get_cache_runtime() is get_cache_runtime()


def test_namespaced_memory_cache_tracks_stats_and_keys():
    runtime = OmniCacheRuntime()
    runtime._initialized = True
    runtime._manager = object()

    store = {}

    def runtime_get(key, default=None, adapter="memory"):
        return store.get((adapter, key), default)

    def runtime_set(key, value, ttl=None, adapter="memory"):
        store[(adapter, key)] = value
        return True

    def runtime_delete(key, adapter="memory"):
        store.pop((adapter, key), None)
        return True

    runtime.get = runtime_get
    runtime.set = runtime_set
    runtime.delete = runtime_delete

    cache = NamespacedMemoryCache(runtime=runtime, namespace="meta:", default_ttl=123)

    assert cache.set("a", 1) is True
    assert cache.size() == 1
    assert cache.get("a", default=None) == 1

    default_marker = object()
    assert cache.get("missing", default=default_marker) is default_marker

    stats = cache.get_stats()
    assert stats["namespace"] == "meta"
    assert stats["entries"] == 1
    assert stats["hits"] == 1
    assert stats["misses"] == 1

    assert cache.delete("a") is True
    assert cache.size() == 0

    cache.set("b", 2)
    cache.clear()
    assert cache.size() == 0
    assert cache.get_stats()["hits"] == 0
    assert cache.get_stats()["misses"] == 0


class _Wrapped:
    def __init__(self, obj):
        self._obj = obj


class _Factory:
    def create(self):
        return object()

    def validate(self, _obj):
        return True

    def reset(self, _obj):
        return True

    def destroy(self, _obj):
        return None

    def get_key(self, *_args, **_kwargs):
        raise RuntimeError("key error")


class _Runtime:
    def __init__(self):
        self.manager = MagicMock()
        self.register_smartpool_adapter = MagicMock(return_value=True)


def test_smartpool_handle_acquire_release_shutdown_and_default_stats():
    runtime = _Runtime()
    adapter = MagicMock()
    adapter.get.return_value = _Wrapped({"v": 1})
    runtime.manager.get_adapter.return_value = adapter

    handle = SmartPoolHandle(runtime=runtime, name="pool", factory=_Factory())
    obj_id, key, obj = handle.acquire()
    assert key == "default_pool_key"
    assert obj == {"v": 1}

    handle.release(obj_id, key, obj)
    adapter.put.assert_called_once()

    handle.clear()
    adapter.clear.assert_called()

    adapter.get_detailed_smartpool_stats.side_effect = RuntimeError("stats error")
    stats = handle.get_stats()
    assert stats["hits"] == 0
    assert stats["total_memory_objects"] == 0

    handle.shutdown()
    runtime.manager.remove_adapter.assert_called_once_with("pool")
