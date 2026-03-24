from ai_content_classifier.services.shared.cache_runtime import OmniCacheRuntime


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
