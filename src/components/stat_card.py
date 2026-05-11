"""Stat card component — glassmorphic metric display."""

from __future__ import annotations

import flet as ft

from core import theme, tokens


def build_stat_card(
    label: str,
    value: str,
    icon: str = ft.Icons.INFO_OUTLINE,
    color: str = theme.ACCENT,
) -> ft.Container:
    """Build a glassmorphic stat card showing a single metric."""
    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(icon, size=tokens.ICON_MD, color=color),
                        ft.Text(
                            label,
                            size=tokens.FONT_XS,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            weight=ft.FontWeight.W_500,
                        ),
                    ],
                    spacing=tokens.SPACE_SM,
                    tight=True,
                ),
                ft.Text(
                    value,
                    size=tokens.FONT_XXL,
                    weight=ft.FontWeight.W_700,
                ),
            ],
            spacing=tokens.SPACE_SM,
        ),
        padding=ft.Padding(
            left=tokens.SPACE_LG,
            right=tokens.SPACE_LG,
            top=tokens.SPACE_MD,
            bottom=tokens.SPACE_MD,
        ),
        border_radius=tokens.RADIUS_LG,
        bgcolor=theme.GLASS_BG,
        blur=ft.Blur(tokens.BLUR_SM, tokens.BLUR_SM, ft.BlurTileMode.MIRROR),
        border=ft.Border.all(1, theme.GLASS_BORDER_COLOR),
        expand=True,
    )
