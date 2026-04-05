import pytest
from ai_content_classifier.services.theme.theme_service import (
    ThemeService,
    ThemePalette,
)
from PyQt6.QtCore import QSettings
from ai_content_classifier.themes import AppTheme, ThemeMetrics, ThemeTypography
from ai_content_classifier.services.theme import theme_service as theme_module


class _DummyWidget:
    def __init__(self):
        self.stylesheet = ""
        self.palettes = []

    def setStyleSheet(self, value):
        self.stylesheet = value

    def apply_theme(self, palette):
        self.palettes.append(palette)


class _BrokenSettings:
    def setValue(self, *_args, **_kwargs):
        raise RuntimeError("settings write failed")

    def sync(self):
        raise RuntimeError("settings sync failed")


class TestThemeService:
    @pytest.fixture
    def theme_service(self):
        # Clear QSettings before each test to ensure a clean state
        settings = QSettings("Javis", "Themes")
        settings.clear()
        settings.sync()  # Ensure changes are written

        # Ensure a fresh instance for each test
        service = ThemeService()
        yield service
        # Optional: Clear settings after test as well, though 'clear' before should be enough
        settings.clear()
        settings.sync()

    def test_theme_service_instantiation(self, theme_service):
        assert isinstance(theme_service, ThemeService)
        assert theme_service.current_theme == "light"
        assert theme_service.current_palette is not None

    def test_get_available_themes(self, theme_service):
        themes = theme_service.get_available_themes()
        assert isinstance(themes, list)
        assert "light" in themes
        assert "dark" in themes

    def test_set_theme(self, theme_service):
        assert theme_service.set_theme("dark")
        assert theme_service.get_current_theme() == "dark"
        assert theme_service.get_current_palette().name == "dark"

        # Test setting a non-existent theme
        assert not theme_service.set_theme("non_existent_theme")
        assert theme_service.get_current_theme() == "dark"  # Should remain dark

    def test_get_current_palette(self, theme_service):
        palette = theme_service.get_current_palette()
        assert isinstance(palette, ThemePalette)
        assert palette.name == "light"  # Default theme

        theme_service.set_theme("dark")
        dark_palette = theme_service.get_current_palette()
        assert dark_palette.name == "dark"
        assert dark_palette.background == "#0f172a"  # Check a specific dark theme color

    def test_theme_definition_exposes_metrics_and_typography(self, theme_service):
        theme = theme_service.get_theme_definition()
        assert theme.name == "light"
        assert theme.metrics.sidebar_width_wide > theme.metrics.sidebar_width_compact
        assert theme.typography.font_family

    def test_register_theme_adds_new_theme(self, theme_service):
        custom_theme = AppTheme(
            name="graphite",
            display_name="Graphite",
            palette=ThemePalette(name="graphite", background="#1f1f1f"),
            metrics=ThemeMetrics(sidebar_width_wide=320),
            typography=ThemeTypography(font_family="Noto Sans"),
            is_dark=True,
        )

        assert theme_service.register_theme(custom_theme)
        assert "graphite" in theme_service.get_available_themes()
        assert theme_service.set_theme("graphite")
        assert theme_service.get_theme_definition().metrics.sidebar_width_wide == 320

    def test_export_import_theme_roundtrip_preserves_contract(
        self, theme_service, tmp_path
    ):
        export_path = tmp_path / "theme.json"
        assert theme_service.export_theme("dark", str(export_path))

        imported_service = ThemeService()
        imported_name = imported_service.import_theme(str(export_path))

        assert imported_name == "dark"
        imported_theme = imported_service.get_theme_definition("dark")
        assert imported_theme.is_dark is True
        assert imported_theme.palette.background == "#0f172a"
        assert imported_theme.metrics.preview_height_wide == 320

    def test_get_theme_definition_and_preview_fallback(self, theme_service):
        default_theme = theme_service.theme_registry.default_theme
        theme = theme_service.get_theme_definition("not_found")
        assert theme.name == default_theme
        assert theme_service.get_theme_preview("not_found") == {}

    def test_register_widget_and_apply_paths(self, theme_service):
        w1 = _DummyWidget()
        callback_calls = []
        theme_service.register_widget(
            w1, style_callback=lambda p: callback_calls.append(p.name)
        )
        assert callback_calls

        w2 = _DummyWidget()
        theme_service.apply_theme_to_widget(w2)
        assert w2.palettes

        class _BasicOnly:
            def __init__(self):
                self.stylesheet = ""

            def setStyleSheet(self, value):
                self.stylesheet = value

        w3 = _BasicOnly()
        theme_service.apply_theme_to_widget(w3)
        assert "QWidget" in w3.stylesheet

    def test_refresh_widgets_and_stylesheet_helpers(self, theme_service, monkeypatch):
        w = _DummyWidget()
        theme_service.registered_widgets = [w, None]
        theme_service.refresh_all_widgets()
        assert theme_service.registered_widgets == [w]

        themed = theme_service.get_themed_stylesheet(
            "color:{primary}; border:$outline;"
        )
        assert "#" in themed

        monkeypatch.setattr(
            theme_service,
            "get_theme_definition",
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        assert theme_service.get_themed_stylesheet("x") == "x"

    def test_custom_palette_save_and_load_guard_rails(self, theme_service, monkeypatch):
        custom = theme_service.create_custom_palette("my_theme", base_theme="missing")
        assert custom.name == "my_theme"
        assert "my_theme" in theme_service.palettes

        theme_service.current_theme = "dark"
        monkeypatch.setattr(theme_service, "settings", _BrokenSettings())
        theme_service.save_theme_preference()

        assert theme_service.export_theme("missing_theme", "/tmp/nope.json") is False
        assert theme_service.import_theme("/tmp/definitely_missing_theme.json") is None

    def test_global_theme_helpers(self, theme_service, monkeypatch):
        theme_module._theme_service_instance = None
        fake = theme_service
        monkeypatch.setattr(theme_module, "_theme_service_instance", fake)
        assert theme_module.get_theme_service() is fake

        widget = _DummyWidget()
        theme_module.apply_theme_to_widget(widget)
        assert widget in fake.registered_widgets

        themed = theme_module.get_themed_style("background:{background};")
        assert "background" in themed
