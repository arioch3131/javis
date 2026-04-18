from types import SimpleNamespace
from unittest.mock import patch

from ai_content_classifier.services.filtering.plugins.year_filter import (
    YearFilterPlugin,
)
from ai_content_classifier.services.filtering.types import FilterCriterion


def test_year_filter_uses_metadata_fallback():
    plugin = YearFilterPlugin()
    items = [("/tmp/a.jpg", "/tmp"), ("/tmp/b.jpg", "/tmp")]

    content_map = {
        "/tmp/a.jpg": SimpleNamespace(
            year_taken=None,
            date_created=None,
            date_modified=None,
            date_indexed=None,
            content_metadata={"DateTimeOriginal": "2021:09:11 18:30:00"},
        ),
        "/tmp/b.jpg": SimpleNamespace(
            year_taken=2023,
            date_created=None,
            date_modified=None,
            date_indexed=None,
            content_metadata=None,
        ),
    }

    filtered = plugin.apply_memory(
        items,
        FilterCriterion(key="year", op="in", value=[2021]),
        context={"get_content_map": lambda _items: content_map},
    )

    assert filtered == [("/tmp/a.jpg", "/tmp")]


def test_year_filter_validate_and_range_resolution():
    plugin = YearFilterPlugin()

    assert plugin.validate(FilterCriterion(key="year", op="contains", value="2020"))
    assert plugin.validate(FilterCriterion(key="year", op="in", value=["x"]))
    assert (
        plugin.validate(
            FilterCriterion(key="year", op="range", value={"start": 2020, "end": 2021})
        )
        is None
    )

    years = plugin._resolve_target_years(
        FilterCriterion(key="year", op="range", value={"start": 2023, "end": 2021})
    )
    assert years == {2021, 2022, 2023}


def test_year_filter_handles_missing_context_and_mtime_failures():
    plugin = YearFilterPlugin()
    items = [("/tmp/a.jpg", "/tmp")]
    criterion = FilterCriterion(key="year", op="eq", value=2022)

    assert plugin.apply_memory(items, criterion, context={}) == []

    content_map = {
        "/tmp/a.jpg": SimpleNamespace(
            year_taken=None,
            date_created=None,
            date_modified=None,
            date_indexed=None,
            content_metadata=None,
        )
    }
    with patch(
        "ai_content_classifier.services.filtering.plugins.year_filter.os.path.getmtime",
        side_effect=OSError("no file"),
    ):
        assert (
            plugin.apply_memory(
                items,
                criterion,
                context={"get_content_map": lambda _items: content_map},
            )
            == []
        )
