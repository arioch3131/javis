from __future__ import annotations

import types

import pytest

from ai_content_classifier.services.shared import dependency_manager as dm


class _DummyCache:
    def __init__(self) -> None:
        self._data = {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        return True

    def clear(self):
        self._data.clear()

    def size(self):
        return len(self._data)


class _DummyRuntime:
    def __init__(self) -> None:
        self.cache = _DummyCache()

    def memory_cache(self, _namespace, default_ttl=300):
        _ = default_ttl
        return self.cache


@pytest.fixture
def manager(monkeypatch):
    monkeypatch.setattr(dm, "get_cache_runtime", lambda: _DummyRuntime())
    monkeypatch.setattr(
        dm.importlib,
        "import_module",
        lambda path: (_ for _ in ()).throw(ImportError(f"missing: {path}")),
    )
    mgr = dm.DependencyManager()
    mgr.logger = types.SimpleNamespace(
        info=lambda *a, **k: None,
        debug=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )
    return mgr


@pytest.fixture(autouse=True)
def _reset_global_manager():
    dm.reset_dependency_manager()
    yield
    dm.reset_dependency_manager()


def test_initial_check_populates_cache_and_stats(manager):
    total = len(manager._dependencies)
    stats = manager.get_stats()
    assert total > 0
    assert stats["total_dependencies"] == total
    assert stats["checks_performed"] == total
    assert stats["failed_imports"] == total
    assert stats["available_dependencies"] == 0
    assert stats["cache_size"] == total


def test_is_available_unknown_and_cache_hit(manager):
    assert manager.is_available("does_not_exist") is False
    before = manager._stats["cache_hits"]
    assert manager.is_available("pdfminer") is False
    assert manager._stats["cache_hits"] == before + 1


def test_get_version_only_for_available_dependency(manager):
    dep = manager._dependencies["pdfminer"]
    dep.is_available = False
    dep.version = "1.0.0"
    assert manager.get_version("pdfminer") is None

    dep.is_available = True
    assert manager.get_version("pdfminer") == "1.0.0"
    assert manager.get_version("unknown") is None


def test_get_fallback_chain_filters_by_category_capability_and_priority(manager):
    for dep in manager._dependencies.values():
        dep.is_available = False

    manager._dependencies["pdfminer"].is_available = True
    manager._dependencies["pdfminer"].priority = dm.DependencyPriority.MEDIUM

    manager._dependencies["docx"].is_available = True
    manager._dependencies["docx"].category = dm.DependencyCategory.PDF_EXTRACTION
    manager._dependencies["docx"].priority = dm.DependencyPriority.HIGH
    manager._dependencies["docx"].capabilities = ["pdf_text_extraction"]

    chain = manager.get_fallback_chain(
        dm.DependencyCategory.PDF_EXTRACTION, "pdf_text_extraction"
    )
    assert chain == ["docx", "pdfminer"]


def test_perform_dependency_check_custom_test_success_and_failure(manager):
    dep_ok = dm.DependencyInfo(
        name="custom_ok",
        module_path="custom.ok",
        category=dm.DependencyCategory.SYSTEM_UTILITIES,
        priority=dm.DependencyPriority.LOW,
        test_function=lambda: True,
    )
    dep_ko = dm.DependencyInfo(
        name="custom_ko",
        module_path="custom.ko",
        category=dm.DependencyCategory.SYSTEM_UTILITIES,
        priority=dm.DependencyPriority.LOW,
        test_function=lambda: False,
    )

    assert manager._perform_dependency_check(dep_ok) is True
    assert dep_ok.is_available is True
    assert manager._perform_dependency_check(dep_ko) is False
    assert dep_ko.import_error == "Custom test failed"


def test_perform_dependency_check_import_success_and_version_conversion(
    manager, monkeypatch
):
    class _Version:
        def __str__(self):
            return "2.3.4"

    fake_module = types.SimpleNamespace(VERSION=_Version())
    monkeypatch.setattr(dm.importlib, "import_module", lambda _path: fake_module)

    dep = dm.DependencyInfo(
        name="ok",
        module_path="pkg.ok",
        category=dm.DependencyCategory.SECURITY,
        priority=dm.DependencyPriority.LOW,
    )
    assert manager._perform_dependency_check(dep) is True
    assert dep.is_available is True
    assert dep.version == "2.3.4"
    assert dep.import_error is None


def test_perform_dependency_check_handles_import_error_and_unexpected(
    manager, monkeypatch
):
    dep = dm.DependencyInfo(
        name="err",
        module_path="pkg.err",
        category=dm.DependencyCategory.SECURITY,
        priority=dm.DependencyPriority.LOW,
    )

    monkeypatch.setattr(
        dm.importlib,
        "import_module",
        lambda _path: (_ for _ in ()).throw(ImportError("no module")),
    )
    assert manager._perform_dependency_check(dep) is False
    assert dep.version is None
    assert dep.import_error == "no module"

    monkeypatch.setattr(
        dm.importlib,
        "import_module",
        lambda _path: (_ for _ in ()).throw(RuntimeError("kaboom")),
    )
    assert manager._perform_dependency_check(dep) is False
    assert dep.import_error == "Unexpected error: kaboom"


def test_cached_helpers_clear_cache_missing_dependencies_and_stats(manager):
    for dep in manager._dependencies.values():
        dep.is_available = False

    manager._dependencies["pdfminer"].is_available = True
    manager._dependencies["pdfminer"].capabilities = ["pdf_text_extraction"]
    manager._dependencies["docx"].is_available = True
    manager._dependencies["docx"].capabilities = ["docx_text_extraction"]
    manager._dependencies["hachoir"].is_available = True

    assert "pdfminer" in manager.get_pdf_extractors()
    assert "docx" in manager.get_document_processors()
    assert "hachoir" in manager.get_metadata_extractors()

    assert manager.get_pdf_extractors.cache_info().currsize > 0
    assert manager.get_document_processors.cache_info().currsize > 0
    assert manager.get_metadata_extractors.cache_info().currsize > 0

    missing_all = manager.get_missing_dependencies()
    assert len(missing_all) < len(manager._dependencies)
    missing_system = manager.get_missing_dependencies(
        dm.DependencyCategory.SYSTEM_UTILITIES
    )
    assert all(
        dep.category == dm.DependencyCategory.SYSTEM_UTILITIES for dep in missing_system
    )

    stats = manager.get_stats()
    assert "cache_hit_ratio" in stats
    assert stats["availability_ratio"] >= 0

    manager.clear_cache()
    assert manager.get_pdf_extractors.cache_info().currsize == 0
    assert manager.get_document_processors.cache_info().currsize == 0
    assert manager.get_metadata_extractors.cache_info().currsize == 0


def test_get_dependency_manager_singleton_and_reset(monkeypatch):
    monkeypatch.setattr(dm, "get_cache_runtime", lambda: _DummyRuntime())
    monkeypatch.setattr(
        dm.importlib,
        "import_module",
        lambda path: (_ for _ in ()).throw(ImportError(f"missing: {path}")),
    )

    first = dm.get_dependency_manager()
    second = dm.get_dependency_manager()
    assert first is second

    dm.reset_dependency_manager()
    third = dm.get_dependency_manager()
    assert third is not first
