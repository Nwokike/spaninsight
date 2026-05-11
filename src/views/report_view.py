"""Report view — compiled dashboard of all charts and insights from an analysis session."""

from __future__ import annotations

import logging

import flet as ft

from core import theme, tokens
from core.state import state
from components.chart_card import build_chart_card

logger = logging.getLogger(__name__)


def build_report_view(
    page: ft.Page,
    on_back: callable,
    on_export_pdf: callable | None = None,
    on_share: callable | None = None,
) -> ft.View:
    """Build the report dashboard showing all generated charts and insights.

    Args:
        page: Flet page object.
        on_back: Callback to navigate back.
        on_export_pdf: Callback for PDF export (Phase 5).
        on_share: Callback for public URL sharing (Phase 5).
    """
    charts = state.charts
    filename = state.current_df_name or "Untitled Dataset"
    total_rows = state.current_df_rows

    # ── Header stats ────────────────────────────────────────────────
    header = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.DESCRIPTION_ROUNDED,
                            size=tokens.ICON_MD,
                            color=theme.ACCENT,
                        ),
                        ft.Text(
                            filename,
                            size=tokens.FONT_MD,
                            weight=ft.FontWeight.W_600,
                            expand=True,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=tokens.SPACE_SM,
                ),
                ft.Row(
                    controls=[
                        _mini_stat(
                            ft.Icons.INSIGHTS_ROUNDED,
                            f"{len(charts)} analyses",
                        ),
                        _mini_stat(
                            ft.Icons.TABLE_ROWS_ROUNDED,
                            f"{total_rows:,} rows",
                        ),
                    ],
                    spacing=tokens.SPACE_LG,
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
    )

    # ── Chart cards ─────────────────────────────────────────────────
    chart_cards = []
    for i, chart_data in enumerate(charts):
        card = build_chart_card(
            index=i + 1,
            prompt=chart_data.get("prompt", "Analysis"),
            figure=chart_data.get("figure"),
            insight=chart_data.get("insight", ""),
            code=chart_data.get("code", ""),
        )
        chart_cards.append(
            ft.Container(
                content=card,
                padding=ft.Padding(
                    left=tokens.SPACE_LG,
                    right=tokens.SPACE_LG,
                    top=tokens.SPACE_SM,
                    bottom=tokens.SPACE_SM,
                ),
            )
        )

    # ── Empty state ─────────────────────────────────────────────────
    if not chart_cards:
        chart_cards = [
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Container(height=tokens.SPACE_XXXXL),
                        ft.Icon(
                            ft.Icons.ANALYTICS_OUTLINED,
                            size=tokens.ICON_HERO,
                            color=ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE),
                        ),
                        ft.Text(
                            "No analyses yet",
                            size=tokens.FONT_LG,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            "Run an analysis to build your report",
                            size=tokens.FONT_SM,
                            color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=tokens.SPACE_MD,
                ),
                alignment=ft.Alignment.CENTER,
            )
        ]

    # ── Action buttons (Phase 5 stubs) ──────────────────────────────
    action_row = ft.Container(
        content=ft.Row(
            controls=[
                ft.OutlinedButton(
                    text="Export PDF",
                    icon=ft.Icons.PICTURE_AS_PDF_ROUNDED,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_MD),
                    ),
                    on_click=on_export_pdf,
                    disabled=on_export_pdf is None or len(charts) == 0,
                ),
                ft.FilledButton(
                    text="Share Report",
                    icon=ft.Icons.SHARE_ROUNDED,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_MD),
                    ),
                    on_click=on_share,
                    disabled=on_share is None or len(charts) == 0,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=tokens.SPACE_MD,
        ),
        padding=ft.Padding(
            left=tokens.SPACE_LG,
            right=tokens.SPACE_LG,
            top=tokens.SPACE_LG,
            bottom=tokens.SPACE_XXL,
        ),
    )

    # ── Assemble scrollable content ─────────────────────────────────
    content = ft.Column(
        controls=[header, *chart_cards, action_row],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=0,
    )

    appbar = ft.AppBar(
        leading=ft.IconButton(
            icon=ft.Icons.ARROW_BACK_ROUNDED,
            on_click=lambda e: on_back(),
        ),
        title=ft.Text("Report", weight=ft.FontWeight.W_600, size=tokens.FONT_XL),
        center_title=False,
        bgcolor=ft.Colors.TRANSPARENT,
        actions=[
            ft.Container(
                content=ft.Text(
                    f"{len(charts)} charts",
                    size=tokens.FONT_XS,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                margin=ft.Margin(0, 0, tokens.SPACE_LG, 0),
            ),
        ],
    )

    return ft.View(
        route="/report",
        appbar=appbar,
        controls=[content],
        padding=0,
    )


def _mini_stat(icon: str, text: str) -> ft.Row:
    return ft.Row(
        controls=[
            ft.Icon(icon, size=tokens.ICON_SM, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Text(text, size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT),
        ],
        spacing=tokens.SPACE_XS,
        tight=True,
    )
