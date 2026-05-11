"""Chart card — individual chart + insight for the report view."""

from __future__ import annotations

import flet as ft
import flet_charts as fch

from core import theme, tokens


def build_chart_card(
    index: int,
    prompt: str,
    figure,
    insight: str,
    code: str = "",
) -> ft.Container:
    """Build a single chart card with its AI insight.

    Args:
        index: Chart number (1-based).
        prompt: The analysis prompt that generated this chart.
        figure: Matplotlib figure object.
        insight: AI-generated interpretation text.
        code: The Python code that generated the chart.
    """
    # Chart widget
    chart_widget = ft.Container(height=10)  # fallback
    if figure:
        chart_widget = ft.Container(
            content=fch.MatplotlibChart(figure=figure, expand=True),
            height=280,
            border_radius=tokens.RADIUS_MD,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

    return ft.Container(
        content=ft.Column(
            controls=[
                # Header
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Text(
                                str(index),
                                size=tokens.FONT_SM,
                                weight=ft.FontWeight.W_700,
                                color=ft.Colors.WHITE,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            width=28,
                            height=28,
                            border_radius=14,
                            bgcolor=theme.PRIMARY,
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Text(
                            prompt,
                            size=tokens.FONT_SM,
                            weight=ft.FontWeight.W_600,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            expand=True,
                        ),
                    ],
                    spacing=tokens.SPACE_MD,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                # Chart
                chart_widget,
                # Insight
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.LIGHTBULB_OUTLINE_ROUNDED,
                                size=tokens.ICON_SM,
                                color=theme.ACCENT,
                            ),
                            ft.Text(
                                insight or "No interpretation available.",
                                size=tokens.FONT_SM,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                expand=True,
                            ),
                        ],
                        spacing=tokens.SPACE_SM,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    padding=ft.Padding(
                        left=tokens.SPACE_MD,
                        right=tokens.SPACE_MD,
                        top=tokens.SPACE_MD,
                        bottom=tokens.SPACE_MD,
                    ),
                    border_radius=tokens.RADIUS_MD,
                    bgcolor=ft.Colors.with_opacity(0.04, theme.ACCENT),
                ),
            ],
            spacing=tokens.SPACE_MD,
        ),
        padding=tokens.SPACE_LG,
        border_radius=tokens.RADIUS_XL,
        bgcolor=theme.GLASS_BG,
        blur=ft.Blur(tokens.BLUR_SM, tokens.BLUR_SM, ft.BlurTileMode.MIRROR),
        border=ft.Border.all(1, theme.GLASS_BORDER_COLOR),
    )
