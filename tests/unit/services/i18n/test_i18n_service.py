from __future__ import annotations

import json

import pytest

from ai_content_classifier.services.i18n import i18n_service as i18n_module


@pytest.fixture(autouse=True)
def _reset_singleton():
    i18n_module._i18n_service_instance = None
    yield
    i18n_module._i18n_service_instance = None


@pytest.fixture
def i18n(tmp_path):
    resources = tmp_path / "resources" / "i18n"
    resources.mkdir(parents=True)
    (resources / "en.json").write_text(
        json.dumps(
            {
                "hello": "Hello",
                "nested": {"label": "English label"},
                "welcome": "Hello {name}",
            }
        ),
        encoding="utf-8",
    )
    (resources / "fr.json").write_text(
        json.dumps({"hello": "Bonjour", "nested": {"label": "Etiquette"}}),
        encoding="utf-8",
    )

    service = i18n_module.I18nService(default_language="fr")
    service._resources_dir = resources
    service.set_language("fr")
    return service


def test_set_language_and_translate_with_fallback(i18n):
    assert i18n.language == "fr"
    assert i18n.translate("hello") == "Bonjour"
    assert i18n.translate("nested.label") == "Etiquette"
    assert i18n.translate("welcome", name="Ada") == "Hello Ada"
    assert i18n.translate("missing.key", default="Fallback") == "Fallback"
    assert i18n.translate("", default="x") == "x"


def test_set_language_system_and_format_failure(i18n):
    i18n.set_language("system")
    assert i18n.language == "en"
    assert i18n.translate("welcome", default="x", bad="value") == "Hello {name}"


def test_load_catalog_missing_invalid_and_non_dict(tmp_path):
    resources = tmp_path / "resources" / "i18n"
    resources.mkdir(parents=True)
    (resources / "en.json").write_text('"just a string"', encoding="utf-8")
    (resources / "broken.json").write_text("{invalid json", encoding="utf-8")

    service = i18n_module.I18nService(default_language="en")
    service._resources_dir = resources

    service._load_catalog("missing")
    assert service._catalogs["missing"] == {}

    service._load_catalog("en")
    assert service._catalogs["en"] == {}

    service._load_catalog("broken")
    assert service._catalogs["broken"] == {}


def test_resolve_handles_nested_and_invalid_shapes():
    catalog = {"a": {"b": 3}}
    assert i18n_module.I18nService._resolve(catalog, "a.b") == 3
    assert i18n_module.I18nService._resolve(catalog, "a.c") is None
    assert i18n_module.I18nService._resolve({"a": 1}, "a.b") is None


def test_get_i18n_service_singleton_and_tr(monkeypatch):
    resources = {"ui": {"title": "Main title"}}

    original_load = i18n_module.I18nService._load_catalog

    def fake_load(self, language):
        self._catalogs[language] = resources if language == "en" else {}

    monkeypatch.setattr(i18n_module.I18nService, "_load_catalog", fake_load)
    first = i18n_module.get_i18n_service()
    second = i18n_module.get_i18n_service()
    assert first is second
    assert i18n_module.tr("ui.title") == "Main title"

    monkeypatch.setattr(i18n_module.I18nService, "_load_catalog", original_load)
