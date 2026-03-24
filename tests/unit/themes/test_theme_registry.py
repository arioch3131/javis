from ai_content_classifier.themes import (
    AppTheme,
    ThemeMetrics,
    ThemePalette,
    ThemeRegistry,
    ThemeTypography,
    build_default_theme_registry,
)


def test_default_theme_registry_contains_builtin_themes():
    registry = build_default_theme_registry()

    assert "light" in registry
    assert "dark" in registry
    assert registry.default_theme == "light"


def test_theme_contract_can_be_serialized_and_restored():
    theme = AppTheme(
        name="graphite",
        display_name="Graphite",
        palette=ThemePalette(name="graphite", background="#202020", primary="#4f8cff"),
        metrics=ThemeMetrics(sidebar_width_compact=172),
        typography=ThemeTypography(font_family="IBM Plex Sans"),
        is_dark=True,
    )

    restored = AppTheme.from_dict(theme.to_dict())

    assert restored.name == "graphite"
    assert restored.palette.primary == "#4f8cff"
    assert restored.metrics.sidebar_width_compact == 172
    assert restored.typography.font_family == "IBM Plex Sans"
    assert restored.is_dark is True


def test_theme_registry_rejects_duplicate_names_without_replace():
    registry = ThemeRegistry()
    theme = AppTheme(
        name="custom",
        display_name="Custom",
        palette=ThemePalette(name="custom"),
    )

    registry.register(theme)

    try:
        registry.register(theme)
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("expected duplicate registration to fail")
