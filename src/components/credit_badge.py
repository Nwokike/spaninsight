"""Credit badge component — color-coded chip for the AppBar."""

from __future__ import annotations

import flet as ft

from core import theme, tokens


def build_credit_badge(credits: int) -> ft.Container:
    """Build a compact credit badge chip.

    Color-coded: green (>20), amber (5-20), red (<5).
    """
    if credits > 20:
        color = theme.CREDIT_HIGH
    elif credits >= 5:
        color = theme.CREDIT_MEDIUM
    else:
        color = theme.CREDIT_LOW

    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(
                    ft.Icons.BOLT_ROUNDED,
                    size=tokens.ICON_SM,
                    color=color,
                ),
                ft.Text(
                    str(credits),
                    size=tokens.FONT_SM,
                    weight=ft.FontWeight.W_600,
                    color=color,
                ),
            ],
            spacing=tokens.SPACE_XXS,
            tight=True,
        ),
        padding=ft.Padding(
            left=tokens.SPACE_SM,
            right=tokens.SPACE_MD,
            top=tokens.SPACE_XS,
            bottom=tokens.SPACE_XS,
        ),
        border_radius=tokens.RADIUS_PILL,
        bgcolor=ft.Colors.with_opacity(0.12, color),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.25, color)),
    )
