from ai_content_classifier.services.filtering.plugins.extension_filter import (
    ExtensionFilterPlugin,
)
from ai_content_classifier.services.filtering.types import FilterCriterion


def test_extension_filter_validate_and_contains_mode():
    plugin = ExtensionFilterPlugin()

    assert plugin.validate(FilterCriterion(key="extension", op="range", value="png"))
    assert plugin.validate(FilterCriterion(key="extension", op="contains", value=" "))
    assert plugin.validate(FilterCriterion(key="extension", op="in", value=[]))

    assert (
        plugin.validate(FilterCriterion(key="extension", op="contains", value="png"))
        is None
    )


def test_extension_filter_apply_memory_and_normalization():
    plugin = ExtensionFilterPlugin()
    items = [
        ("/tmp/a.jpeg", "/tmp"),
        ("/tmp/b.jpg", "/tmp"),
        ("/tmp/c.txt", "/tmp"),
    ]

    contains_filtered = plugin.apply_memory(
        items,
        FilterCriterion(key="extension", op="contains", value="jp"),
        context={},
    )
    assert contains_filtered == [("/tmp/a.jpeg", "/tmp"), ("/tmp/b.jpg", "/tmp")]

    in_filtered = plugin.apply_memory(
        items,
        FilterCriterion(key="extension", op="in", value=["jpg", " .txt ", None]),
        context={},
    )
    assert in_filtered == [("/tmp/b.jpg", "/tmp"), ("/tmp/c.txt", "/tmp")]

    assert (
        plugin.apply_memory(
            items,
            FilterCriterion(key="extension", op="eq", value=[]),
            context={},
        )
        == []
    )
