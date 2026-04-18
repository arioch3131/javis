from ai_content_classifier.services.filtering.registry import FilterRegistry


class _Plugin:
    key = "sample"

    def validate(self, criterion):
        return None

    def to_db_clause(self, criterion):
        return []

    def apply_memory(self, items, criterion, context):
        return items


def test_registry_register_and_resolve():
    registry = FilterRegistry()
    plugin = _Plugin()

    registry.register(plugin)

    assert registry.resolve("sample") is plugin
    assert list(registry.keys()) == ["sample"]


def test_registry_rejects_duplicate_key():
    registry = FilterRegistry()
    registry.register(_Plugin())

    try:
        registry.register(_Plugin())
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("duplicate plugin key should raise")
