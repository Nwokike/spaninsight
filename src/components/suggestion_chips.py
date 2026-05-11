"""Suggestion chips — compact AI analysis action pills.

Renders as tiny, tappable pills in a wrapping row. NOT large cards.
The AI generates these dynamically after analyzing the dataset schema.
"""

from __future__ import annotations

import flet as ft

from core import theme, tokens


def build_suggestion_chips(
    suggestions: list[dict],
    on_select: callable,
    is_loading: bool = False,
) -> ft.Column:
    """Build a wrap of tiny suggestion pills.

    Args:
        suggestions: List of dicts with "label", "icon", "prompt" keys.
        on_select: Callback(prompt: str) when a chip is tapped.
        is_loading: Show disabled state during AI call.
    """
    if not suggestions:
        return ft.Column()

    pills = []
    for s in suggestions:
        label = s.get("label", "Analyze")
        icon_text = s.get("icon", "📊")
        prompt = s.get("prompt", "")

        pill = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(icon_text, size=12),
                    ft.Text(
                        label,
                        size=11,
                        weight=ft.FontWeight.W_500,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
                spacing=4,
                tight=True,
            ),
            padding=ft.Padding(left=10, right=10, top=6, bottom=6),
            border_radius=20,
            bgcolor=ft.Colors.with_opacity(0.06, theme.PRIMARY),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.15, theme.PRIMARY)),
            on_click=lambda e, p=prompt: on_select(p) if not is_loading else None,
            ink=True,
            disabled=is_loading,
        )
        pills.append(pill)

    return ft.Column(
        controls=[
            ft.Text(
                "✨ Suggestions",
                size=tokens.FONT_XS,
                weight=ft.FontWeight.W_600,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Row(
                controls=pills,
                wrap=True,
                spacing=6,
                run_spacing=6,
            ),
        ],
        spacing=6,
    )
