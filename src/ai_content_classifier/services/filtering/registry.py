"""Plugin registry for content filters."""

from __future__ import annotations

from typing import Dict, Iterable, Optional

from ai_content_classifier.services.filtering.types import FilterPlugin


class FilterRegistry:
    """Runtime registry mapping filter keys to plugin implementations."""

    def __init__(self) -> None:
        self._plugins: Dict[str, FilterPlugin] = {}

    def register(self, plugin: FilterPlugin) -> None:
        key = str(getattr(plugin, "key", "")).strip()
        if not key:
            raise ValueError("Filter plugin key cannot be empty.")
        if key in self._plugins:
            raise ValueError(f"Filter plugin already registered for key '{key}'.")
        self._plugins[key] = plugin

    def resolve(self, key: str) -> Optional[FilterPlugin]:
        return self._plugins.get(key)

    def keys(self) -> Iterable[str]:
        return self._plugins.keys()
