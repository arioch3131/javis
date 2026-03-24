"""Core theme contracts used by the UI theme system."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from typing import Any, Dict


@dataclass(slots=True)
class ThemePalette:
    """Semantic color tokens exposed to widgets and stylesheets."""

    name: str
    primary: str = "#3b82f6"
    primary_light: str = "#60a5fa"
    primary_dark: str = "#1d4ed8"
    secondary: str = "#6b7280"
    secondary_light: str = "#9ca3af"
    secondary_dark: str = "#374151"
    accent: str = "#10b981"
    accent_light: str = "#34d399"
    accent_dark: str = "#059669"
    warning: str = "#f59e0b"
    warning_light: str = "#fbbf24"
    warning_dark: str = "#d97706"
    error: str = "#ef4444"
    error_light: str = "#f87171"
    error_dark: str = "#dc2626"
    error_container: str = "#fee2e2"
    success: str = "#22c55e"
    success_light: str = "#4ade80"
    success_dark: str = "#16a34a"
    background: str = "#ffffff"
    surface: str = "#f8fafc"
    surface_variant: str = "#f1f5f9"
    outline: str = "#e2e8f0"
    outline_variant: str = "#cbd5e1"
    on_background: str = "#0f172a"
    on_surface: str = "#1e293b"
    on_surface_variant: str = "#475569"
    on_outline: str = "#64748b"
    on_secondary: str = "#ffffff"
    hover: str = "#f3f4f6"
    pressed: str = "#e5e7eb"
    focused: str = "#dbeafe"
    disabled: str = "#f9fafb"
    disabled_text: str = "#9ca3af"
    shadow_light: str = "rgba(0, 0, 0, 0.05)"
    shadow_medium: str = "rgba(0, 0, 0, 0.1)"
    shadow_strong: str = "rgba(0, 0, 0, 0.25)"
    overlay_light: str = "rgba(255, 255, 255, 0.8)"
    overlay_medium: str = "rgba(255, 255, 255, 0.9)"
    overlay_strong: str = "rgba(255, 255, 255, 0.95)"

    def clone(self, *, name: str | None = None, **overrides: str) -> "ThemePalette":
        """Return a copy with optional overrides."""
        data = self.to_dict()
        if name is not None:
            data["name"] = name
        data.update(overrides)
        return self.__class__(**data)

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "ThemePalette":
        allowed = {field.name for field in fields(cls)}
        values = {"name": name}
        for key, value in data.items():
            if key in allowed and key != "name":
                values[key] = value
        return cls(**values)


@dataclass(slots=True)
class ThemeMetrics:
    """Layout and sizing tokens used by the UI shell."""

    spacing_xs: int = 4
    spacing_sm: int = 8
    spacing_md: int = 12
    spacing_lg: int = 16
    spacing_xl: int = 24
    radius_sm: int = 6
    radius_md: int = 10
    radius_lg: int = 14
    radius_xl: int = 20
    radius_pill: int = 999
    border_width: int = 1
    focus_width: int = 2
    button_height: int = 40
    control_height: int = 36
    sidebar_width_wide: int = 300
    sidebar_width_medium: int = 220
    sidebar_width_compact: int = 168
    preview_height_wide: int = 320
    preview_height_medium: int = 250
    thumbnail_slider_width_wide: int = 140
    thumbnail_slider_width_medium: int = 120
    thumbnail_slider_width_compact: int = 110
    thumbnail_slider_width_small: int = 90

    def clone(self, **overrides: int) -> "ThemeMetrics":
        return replace(self, **overrides)

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ThemeMetrics":
        allowed = {field.name for field in fields(cls)}
        values = {key: value for key, value in data.items() if key in allowed}
        return cls(**values)


@dataclass(slots=True)
class ThemeTypography:
    """Typography tokens used across the application."""

    font_family: str = "Segoe UI"
    font_family_monospace: str = "Consolas"
    font_size_xs: int = 11
    font_size_sm: int = 12
    font_size_md: int = 13
    font_size_lg: int = 16
    font_size_xl: int = 22
    font_weight_normal: int = 400
    font_weight_medium: int = 500
    font_weight_semibold: int = 600
    font_weight_bold: int = 700

    def clone(self, **overrides: int | str) -> "ThemeTypography":
        return replace(self, **overrides)

    def to_dict(self) -> Dict[str, int | str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ThemeTypography":
        allowed = {field.name for field in fields(cls)}
        values = {key: value for key, value in data.items() if key in allowed}
        return cls(**values)


@dataclass(slots=True)
class AppTheme:
    """Complete theme definition consumed by the theme registry and service."""

    name: str
    display_name: str
    palette: ThemePalette
    metrics: ThemeMetrics = field(default_factory=ThemeMetrics)
    typography: ThemeTypography = field(default_factory=ThemeTypography)
    is_dark: bool = False

    def clone(self, *, name: str | None = None, **palette_overrides: str) -> "AppTheme":
        theme_name = name or self.name
        return AppTheme(
            name=theme_name,
            display_name=theme_name.replace("_", " ").title(),
            palette=self.palette.clone(name=theme_name, **palette_overrides),
            metrics=self.metrics.clone(),
            typography=self.typography.clone(),
            is_dark=self.is_dark,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "is_dark": self.is_dark,
            "palette": self.palette.to_dict(),
            "metrics": self.metrics.to_dict(),
            "typography": self.typography.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppTheme":
        name = str(data.get("name", "custom"))
        display_name = str(data.get("display_name", name.replace("_", " ").title()))
        palette = ThemePalette.from_dict(name, data.get("palette", {}))
        metrics = ThemeMetrics.from_dict(data.get("metrics", {}))
        typography = ThemeTypography.from_dict(data.get("typography", {}))
        return cls(
            name=name,
            display_name=display_name,
            palette=palette,
            metrics=metrics,
            typography=typography,
            is_dark=bool(data.get("is_dark", False)),
        )

    def to_token_map(self) -> Dict[str, Any]:
        tokens: Dict[str, Any] = {}
        tokens.update(self.palette.to_dict())
        tokens.update(self.metrics.to_dict())
        tokens.update(self.typography.to_dict())
        tokens["theme_name"] = self.name
        tokens["theme_display_name"] = self.display_name
        tokens["theme_is_dark"] = "true" if self.is_dark else "false"
        return tokens
