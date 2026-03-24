"""Predefined application themes built on top of the theme contracts."""

from __future__ import annotations

from ai_content_classifier.themes.base import (
    AppTheme,
    ThemeMetrics,
    ThemePalette,
    ThemeTypography,
)
from ai_content_classifier.themes.registry import ThemeRegistry


def _base_theme(name: str, display_name: str, *, is_dark: bool = False) -> AppTheme:
    return AppTheme(
        name=name,
        display_name=display_name,
        is_dark=is_dark,
        palette=ThemePalette(name=name),
        metrics=ThemeMetrics(),
        typography=ThemeTypography(),
    )


def build_default_theme_registry() -> ThemeRegistry:
    light = _base_theme("light", "Light")

    dark = _base_theme("dark", "Dark", is_dark=True)
    dark.palette = dark.palette.clone(
        primary="#60a5fa",
        primary_light="#93c5fd",
        primary_dark="#3b82f6",
        background="#0f172a",
        surface="#1e293b",
        surface_variant="#334155",
        outline="#475569",
        outline_variant="#64748b",
        on_background="#f8fafc",
        on_surface="#e2e8f0",
        on_surface_variant="#cbd5e1",
        on_outline="#94a3b8",
        hover="#334155",
        pressed="#475569",
        focused="#1e40af",
        disabled="#1e293b",
        disabled_text="#64748b",
        overlay_light="rgba(0, 0, 0, 0.8)",
        overlay_medium="rgba(0, 0, 0, 0.9)",
        overlay_strong="rgba(0, 0, 0, 0.95)",
        error_container="#4c1d1d",
    )

    blue = _base_theme("blue", "Blue")
    blue.palette = blue.palette.clone(
        primary="#1e40af",
        primary_light="#3b82f6",
        primary_dark="#1e3a8a",
        accent="#0ea5e9",
        accent_light="#38bdf8",
        accent_dark="#0284c7",
        background="#eff6ff",
        surface="#dbeafe",
        surface_variant="#bfdbfe",
    )

    nature = _base_theme("nature", "Nature")
    nature.palette = nature.palette.clone(
        primary="#16a34a",
        primary_light="#22c55e",
        primary_dark="#15803d",
        accent="#059669",
        accent_light="#10b981",
        accent_dark="#047857",
        background="#f0fdf4",
        surface="#dcfce7",
        surface_variant="#bbf7d0",
    )

    purple = _base_theme("purple", "Purple")
    purple.palette = purple.palette.clone(
        primary="#7c3aed",
        primary_light="#8b5cf6",
        primary_dark="#6d28d9",
        accent="#a855f7",
        accent_light="#c084fc",
        accent_dark="#9333ea",
        background="#faf5ff",
        surface="#f3e8ff",
        surface_variant="#e9d5ff",
    )

    return ThemeRegistry([light, dark, blue, nature, purple], default_theme="light")
