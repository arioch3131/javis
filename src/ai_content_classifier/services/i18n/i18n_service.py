"""
Lightweight i18n service backed by JSON catalogs.

This is intended as a practical first step for progressive internationalization:
- centralized language selection
- key-based translations with fallback
- no hard dependency on Qt Linguist workflow
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_content_classifier.core.logger import LoggableMixin


class I18nService(LoggableMixin):
    """Simple translation service with fallback to English and default text."""

    def __init__(self, default_language: str = "en"):
        self.__init_logger__()
        self._catalogs: dict[str, dict[str, Any]] = {}
        self._language = default_language or "en"
        self._resources_dir = Path(__file__).resolve().parents[2] / "resources" / "i18n"

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, language: str) -> None:
        lang = (language or "en").strip().lower()
        if lang == "system":
            # Keep behavior deterministic for now.
            lang = "en"
        self._language = lang
        self._load_catalog(lang)
        self._load_catalog("en")
        self.logger.info("i18n language set to '%s'", self._language)

    def translate(self, key: str, default: str | None = None, **kwargs: Any) -> str:
        if not key:
            return default or ""

        # Current language first, then English fallback.
        translated = self._resolve(self._catalogs.get(self._language, {}), key)
        if translated is None and self._language != "en":
            translated = self._resolve(self._catalogs.get("en", {}), key)
        if translated is None:
            translated = default if default is not None else key

        if kwargs:
            try:
                translated = str(translated).format(**kwargs)
            except Exception:
                self.logger.debug(
                    "i18n format failed for key '%s' with kwargs=%s",
                    key,
                    kwargs,
                )
        return str(translated)

    def _load_catalog(self, language: str) -> None:
        if language in self._catalogs:
            return

        catalog_path = self._resources_dir / f"{language}.json"
        if not catalog_path.exists():
            self._catalogs[language] = {}
            return

        try:
            with catalog_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            self._catalogs[language] = data if isinstance(data, dict) else {}
        except Exception as exc:
            self.logger.warning("Failed to load catalog '%s': %s", catalog_path, exc)
            self._catalogs[language] = {}

    @staticmethod
    def _resolve(catalog: dict[str, Any], key: str) -> Any:
        current: Any = catalog
        for part in key.split("."):
            if not isinstance(current, dict):
                return None
            if part not in current:
                return None
            current = current[part]
        return current


_i18n_service_instance: I18nService | None = None


def get_i18n_service() -> I18nService:
    global _i18n_service_instance
    if _i18n_service_instance is None:
        _i18n_service_instance = I18nService()
        _i18n_service_instance.set_language("en")
    return _i18n_service_instance


def tr(key: str, default: str | None = None, **kwargs: Any) -> str:
    return get_i18n_service().translate(key, default=default, **kwargs)
