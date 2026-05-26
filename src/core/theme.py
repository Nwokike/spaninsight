"""Design system — colour palette, gradients, and Material 3 theme.

Every colour used anywhere in Spaninsight lives here.
"""

from __future__ import annotations

import flet as ft

# ── Brand Palette ───────────────────────────────────────────────────
PRIMARY = "#6C63FF"  # Electric indigo
PRIMARY_DARK = "#5A52D5"  # Pressed state
PRIMARY_LIGHT = "#8B83FF"  # Hover state
ACCENT = "#00D9FF"  # Cyan data glow
ACCENT_DIM = "#00A8C6"  # Subdued accent

SUCCESS = "#00E676"
WARNING = "#FFB74D"
ERROR = "#FF5252"

# ── Dark Mode Surfaces ──────────────────────────────────────────────
DARK_BG_1 = "#0A0B14"  # Deepest background
DARK_BG_2 = "#0D0F1A"  # Primary background
DARK_SURFACE = "#141627"  # Card surface
DARK_SURFACE_2 = "#1C1E33"  # Elevated surface
DARK_BORDER = "#2A2D4A"  # Subtle borders
DARK_TEXT = "#EEEEF5"  # Primary text
DARK_TEXT_DIM = "#8E90A6"  # Secondary text

LIGHT_BG = "#F5F6FA"
LIGHT_SURFACE = "#FFFFFF"
LIGHT_SURFACE_2 = "#F0F1F8"
LIGHT_BORDER = "#E0E1EC"
LIGHT_TEXT = "#1A1B2E"
LIGHT_TEXT_DIM = "#6B6D82"

# ── Glassmorphism ───────────────────────────────────────────────────
GLASS_BG_OPACITY = 0.06
GLASS_BORDER_OPACITY = 0.12
GLASS_BG = ft.Colors.with_opacity(GLASS_BG_OPACITY, ft.Colors.WHITE)
GLASS_BORDER_COLOR = ft.Colors.with_opacity(GLASS_BORDER_OPACITY, ft.Colors.WHITE)

LIGHT_GLASS_BG = ft.Colors.with_opacity(0.06, ft.Colors.BLACK)
LIGHT_GLASS_BORDER = ft.Colors.with_opacity(0.10, ft.Colors.BLACK)

# ── Shadows ─────────────────────────────────────────────────────────
SHADOW_PRIMARY = ft.Colors.with_opacity(0.25, PRIMARY)
SHADOW_DARK = ft.Colors.with_opacity(0.15, "#000000")

# ── Credit Badge Colours ────────────────────────────────────────────
CREDIT_HIGH = SUCCESS  # > 20 credits
CREDIT_MEDIUM = WARNING  # 5–20 credits
CREDIT_LOW = ERROR  # < 5 credits


# ── Gradient Builders ───────────────────────────────────────────────
def dark_gradient() -> ft.LinearGradient:
    """Deep space gradient for dark mode."""
    return ft.LinearGradient(
        begin=ft.Alignment.TOP_CENTER,
        end=ft.Alignment.BOTTOM_CENTER,
        colors=[DARK_BG_1, DARK_BG_2, "#0F1020"],
    )


def light_gradient() -> ft.LinearGradient:
    """Subtle gradient for light mode."""
    return ft.LinearGradient(
        begin=ft.Alignment.TOP_CENTER,
        end=ft.Alignment.BOTTOM_CENTER,
        colors=["#ECEDF5", LIGHT_BG, "#F8F9FD"],
    )


def accent_gradient() -> ft.LinearGradient:
    """Vibrant gradient for primary action buttons."""
    return ft.LinearGradient(
        begin=ft.Alignment.BOTTOM_LEFT,
        end=ft.Alignment.TOP_RIGHT,
        colors=[PRIMARY, "#8B83FF", ACCENT],
    )


def adaptive_glass_bg(page: ft.Page | None = None):
    """Return glass background color appropriate for current theme."""
    if page and page.theme_mode == ft.ThemeMode.LIGHT:
        return LIGHT_GLASS_BG
    return GLASS_BG


def adaptive_glass_border(page: ft.Page | None = None):
    """Return glass border color appropriate for current theme."""
    if page and page.theme_mode == ft.ThemeMode.LIGHT:
        return LIGHT_GLASS_BORDER
    return GLASS_BORDER_COLOR


class AppTheme:
    """Build Material 3 themes for Spaninsight."""

    @staticmethod
    def get_dark_theme() -> ft.Theme:
        return ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=PRIMARY,
                secondary=ACCENT,
                surface=DARK_BG_2,
                on_surface=DARK_TEXT,
                on_surface_variant=DARK_TEXT_DIM,
                error=ERROR,
                on_primary=ft.Colors.WHITE,
                on_secondary=ft.Colors.BLACK,
                outline=DARK_BORDER,
                surface_container_highest=DARK_SURFACE_2,
            ),
            navigation_bar_theme=ft.NavigationBarTheme(
                label_text_style=ft.TextStyle(size=10, weight=ft.FontWeight.W_500)
            ),
            visual_density=ft.VisualDensity.COMFORTABLE,
        )

    @staticmethod
    def get_light_theme() -> ft.Theme:
        return ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=PRIMARY,
                secondary=ACCENT,
                surface=LIGHT_BG,
                on_surface=LIGHT_TEXT,
                on_surface_variant=LIGHT_TEXT_DIM,
                error=ERROR,
                on_primary=ft.Colors.WHITE,
                on_secondary=ft.Colors.BLACK,
                outline=LIGHT_BORDER,
                surface_container_highest=LIGHT_SURFACE_2,
            ),
            navigation_bar_theme=ft.NavigationBarTheme(
                label_text_style=ft.TextStyle(size=10, weight=ft.FontWeight.W_500)
            ),
            visual_density=ft.VisualDensity.COMFORTABLE,
        )
