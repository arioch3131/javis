"""Theme registry used to store and retrieve application themes."""

from __future__ import annotations

from collections import OrderedDict
from typing import Iterable

from ai_content_classifier.themes.base import AppTheme


class ThemeRegistry:
    """Ordered registry of available application themes."""

    def __init__(
        self, themes: Iterable[AppTheme] | None = None, default_theme: str = "light"
    ):
        self._themes: "OrderedDict[str, AppTheme]" = OrderedDict()
        self.default_theme = default_theme
        if themes:
            for theme in themes:
                self.register(theme, replace=True)

    def register(self, theme: AppTheme, *, replace: bool = False) -> None:
        if theme.name in self._themes and not replace:
            raise ValueError(f"Theme '{theme.name}' is already registered")
        self._themes[theme.name] = theme

    def get(self, name: str) -> AppTheme:
        return self._themes[name]

    def names(self) -> list[str]:
        return list(self._themes.keys())

    def items(self):
        return self._themes.items()

    def values(self):
        return self._themes.values()

    def __contains__(self, name: str) -> bool:
        return name in self._themes
