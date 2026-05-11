"""Suggestion chips — AI analysis action buttons."""

from __future__ import annotations

import flet as ft

from core import theme, tokens


def build_suggestion_chips(
    suggestions: list[dict],
    on_select: callable,
    is_loading: bool = False,
) -> ft.Column:
    """Build a column of suggestion action buttons.

    Args:
        suggestions: List of dicts with "label", "icon", "prompt" keys.
        on_select: Callback(prompt: str) when a chip is tapped.
        is_loading: Show shimmer/disabled state during AI call.
    """
    if not suggestions:
        return ft.Container()

    chips = []
    for i, s in enumerate(suggestions):
        label = s.get("label", "Analyze")
        icon_text = s.get("icon", "📊")
        prompt = s.get("prompt", "")

        chip = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(icon_text, size=tokens.FONT_LG),
                    ft.Text(
                        label,
                        size=tokens.FONT_SM,
                        weight=ft.FontWeight.W_500,
                        expand=True,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Icon(
                        ft.Icons.ARROW_FORWARD_ROUNDED,
                        size=tokens.ICON_SM,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=tokens.SPACE_MD,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(
                left=tokens.SPACE_LG,
                right=tokens.SPACE_LG,
                top=tokens.SPACE_MD,
                bottom=tokens.SPACE_MD,
            ),
            border_radius=tokens.RADIUS_LG,
            bgcolor=ft.Colors.with_opacity(0.05, theme.PRIMARY),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, theme.PRIMARY)),
            on_click=lambda e, p=prompt: on_select(p) if not is_loading else None,
            ink=True,
            disabled=is_loading,
            animate=ft.Animation(tokens.ANIM_FAST_MS, ft.AnimationCurve.EASE_OUT),
        )
        chips.append(chip)

    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(
                    ft.Icons.AUTO_AWESOME_ROUNDED,
                    size=tokens.ICON_MD,
                    color=theme.PRIMARY_LIGHT,
                ),
                ft.Text(
                    "AI Suggestions",
                    size=tokens.FONT_MD,
                    weight=ft.FontWeight.W_600,
                ),
            ],
            spacing=tokens.SPACE_SM,
        ),
        padding=ft.Padding(left=tokens.SPACE_XS, top=0, right=0, bottom=tokens.SPACE_XS),
    )

    return ft.Column(
        controls=[header, *chips],
        spacing=tokens.SPACE_SM,
    )
