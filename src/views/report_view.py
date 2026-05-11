"""Report view — displays all charts and insights from the current session."""

from __future__ import annotations

import flet as ft

from core import theme, tokens
from core.state import state
from components.chart_card import build_chart_card


def build_report_view(page: ft.Page) -> ft.View:
    """Build the session report tab."""

    # ── Handlers ────────────────────────────────────────────────────

    def on_share_report(e):
        """Phase 5: Upload to R2 and return a public link."""
        page.snack_bar = ft.SnackBar(
            content=ft.Text("Sharing reports is coming in Phase 5!"),
            duration=3000,
        )
        page.snack_bar.open = True
        page.update()

    def on_export_pdf(e):
        """Phase 5: Generate PDF locally."""
        page.snack_bar = ft.SnackBar(
            content=ft.Text("PDF export is coming in Phase 5!"),
            duration=3000,
        )
        page.snack_bar.open = True
        page.update()

    # ── Content ─────────────────────────────────────────────────────

    if not state.charts:
        content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(height=100),
                    ft.Icon(
                        ft.Icons.BAR_CHART_ROUNDED,
                        size=80,
                        color=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE),
                    ),
                    ft.Container(height=tokens.SPACE_MD),
                    ft.Text(
                        "No analysis report yet",
                        size=tokens.FONT_MD,
                        weight=ft.FontWeight.W_500,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Text(
                        "Run an analysis or Autopilot to build a report.",
                        size=tokens.FONT_SM,
                        color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
                    ),
                    ft.Container(height=tokens.SPACE_XL),
                    ft.ElevatedButton(
                        "Start Analysis",
                        icon=ft.Icons.ANALYTICS_ROUNDED,
                        on_click=lambda _: page.go("/analysis"),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
            ),
            expand=True,
            alignment=ft.Alignment.CENTER,
        )
    else:
        # Build the scrollable list of chart cards
        report_cards = [
            build_chart_card(
                index=i + 1,
                prompt=c.get("prompt", ""),
                figure=c.get("figure"),
                insight=c.get("description", c.get("insight", "")),
                code="",
            )
            for i, c in enumerate(state.charts)
        ]

        content = ft.Column(
            controls=[
                ft.Container(
                    content=ft.Text(
                        f"Your report contains {len(state.charts)} insights",
                        size=tokens.FONT_SM,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    padding=ft.Padding(tokens.SPACE_LG, tokens.SPACE_MD, 0, 0),
                ),
                ft.Column(
                    controls=report_cards,
                    spacing=tokens.SPACE_LG,
                    padding=tokens.SPACE_LG,
                ),
                # Bottom spacer for fab
                ft.Container(height=80),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    appbar = ft.AppBar(
        title=ft.Text("Report", weight=ft.FontWeight.W_600, size=tokens.FONT_XL),
        center_title=False,
        bgcolor=ft.Colors.TRANSPARENT,
        actions=[
            ft.IconButton(
                icon=ft.Icons.PICTURE_AS_PDF_ROUNDED,
                tooltip="Export PDF",
                on_click=on_export_pdf,
                visible=len(state.charts) > 0,
            ),
            ft.IconButton(
                icon=ft.Icons.SHARE_ROUNDED,
                tooltip="Share Link",
                on_click=on_share_report,
                visible=len(state.charts) > 0,
            ),
        ],
    )

    return ft.View(
        route="/report",
        appbar=appbar,
        controls=[content],
        padding=0,
    )
