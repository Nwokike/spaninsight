"""Report view — displays pinned charts + descriptions with sharing.

PDF and PPTX exports are handled by the web dashboard at report.spaninsight.com,
not in-app. This keeps the Android APK ~20MB smaller.
"""

from __future__ import annotations

import base64
import logging

import flet as ft

from core import theme
from core.constants import API_BASE_URL
from core.state import state
from core.utils import figure_to_png_bytes
from components.chart_card import build_chart_card
from components.brand_header import build_brand_header
from services.ad_service import AdService
from services.api_client import request_with_retry

logger = logging.getLogger(__name__)


def build_report_view(
    page: ft.Page, on_back=None, ad_service: AdService | None = None
) -> ft.View:
    """Build the report view with sharing."""

    is_sharing = {"value": False}

    # ── Share Handler ────────────────────────────────────────────────

    async def on_share_report(e):
        if not state.charts or is_sharing["value"]:
            return

        is_sharing["value"] = True
        page.snack_bar = ft.SnackBar(
            ft.Text("Creating shareable link..."), duration=2000
        )
        page.snack_bar.open = True
        page.update()

        try:
            # Show interstitial ad during upload
            if ad_service:
                await ad_service.show_interstitial()

            report_json = _build_report_json()

            resp = await request_with_retry(
                "POST",
                f"{API_BASE_URL}/reports",
                json={
                    "user_uuid": state.user_uuid,
                    "report_json": report_json,
                },
                timeout=15.0,
            )
            if resp.status_code == 201:
                data = resp.json()
                url = data.get("url", "")
                await page.clipboard.set(url)
                page.snack_bar = ft.SnackBar(
                    content=ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE_ROUNDED,
                                color=theme.SUCCESS,
                                size=20,
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        "Link copied to clipboard!",
                                        weight=ft.FontWeight.W_600,
                                    ),
                                    ft.Text(
                                        "Open it in a browser to view, export PDF, or download PPTX.",
                                        size=12,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=12,
                    ),
                    duration=6000,
                )
                page.snack_bar.open = True
                page.update()
            else:
                page.snack_bar = ft.SnackBar(
                    ft.Text("Upload failed. Try again."), duration=3000
                )
                page.snack_bar.open = True
                page.update()

        except Exception as err:
            logger.exception("Share report failed")
            page.snack_bar = ft.SnackBar(
                ft.Text(f"Share failed: {err}", color=ft.Colors.WHITE),
                bgcolor=theme.ERROR,
                duration=4000,
            )
            page.snack_bar.open = True
            page.update()
        finally:
            is_sharing["value"] = False

    # ── Helpers ───────────────────────────────────────────────────────

    def _get_chart_png_bytes(chart: dict) -> bytes | None:
        """Get PNG bytes for a chart — prefer cached, fallback to figure."""
        if chart.get("figure_png"):
            return chart["figure_png"]
        fig = chart.get("figure")
        if fig is not None:
            try:
                fig.get_size_inches()
                png = figure_to_png_bytes(fig, dpi=150)
                chart["figure_png"] = png
                return png
            except Exception:
                pass
        return None

    def _build_report_json() -> dict:
        """Build JSON for R2 upload (Base64 chart images + descriptions)."""
        items = []
        for chart in state.charts:
            item = {
                "prompt": chart.get("prompt", ""),
                "description": chart.get("description", chart.get("insight", "")),
            }
            if chart.get("figure") or chart.get("figure_png"):
                try:
                    img_bytes = _get_chart_png_bytes(chart)
                    if img_bytes:
                        item["image_b64"] = base64.b64encode(img_bytes).decode("utf-8")
                except Exception:
                    pass
            items.append(item)

        return {
            "title": f"Spaninsight Report — {state.current_df_name or 'Analysis'}",
            "chart_count": len(items),
            "items": items,
        }

    # ── Content ──────────────────────────────────────────────────────

    if not state.charts:
        content = ft.Column(
            [
                build_brand_header(show_tagline=True, spacing_below=True),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(
                                ft.Icons.BAR_CHART_ROUNDED,
                                size=80,
                                color=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE),
                            ),
                            ft.Text(
                                "No report yet",
                                size=16,
                                weight="w500",
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            ft.Text(
                                "Pin analysis results to build your report.",
                                size=13,
                                color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
                            ),
                            ft.Container(height=20),
                            ft.FilledButton(
                                "Start Analysis",
                                icon=ft.Icons.ANALYTICS_ROUNDED,
                                on_click=lambda _: page.go("/analysis"),
                            ),
                        ],
                        horizontal_alignment="center",
                        spacing=8,
                    ),
                    alignment=ft.Alignment.CENTER,
                    padding=20,
                ),
            ],
            scroll="auto",
            expand=True,
        )
    else:

        def make_on_change(chart_dict):
            def _on_change(e):
                chart_dict["description"] = e.control.value

            return _on_change

        report_cards = [
            build_chart_card(
                index=i + 1,
                prompt=c.get("prompt", ""),
                figure=c.get("figure"),
                insight=c.get("description", c.get("insight", "")),
                code="",
                on_change=make_on_change(c),
            )
            for i, c in enumerate(state.charts)
        ]

        # Share info banner
        share_info = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.INFO_OUTLINE_ROUNDED, size=18, color=theme.PRIMARY
                    ),
                    ft.Text(
                        "Tap Share to get a public link. You can export PDF & PPTX from the web dashboard.",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        expand=True,
                    ),
                ],
                spacing=10,
            ),
            padding=ft.Padding(16, 12, 16, 12),
            margin=ft.Margin(20, 0, 20, 0),
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.06, theme.PRIMARY),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.15, theme.PRIMARY)),
        )

        content = ft.Column(
            [
                build_brand_header(show_tagline=True, spacing_below=True),
                ft.Container(
                    content=ft.Text(
                        f"Your report contains {len(state.charts)} insights",
                        size=13,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    padding=ft.Padding(20, 10, 0, 0),
                ),
                share_info,
                # FIX: Wrapped the column inside a container to properly apply the padding safely
                ft.Container(
                    content=ft.Column(controls=report_cards, spacing=16),
                    padding=20
                ),
                ft.Container(height=80),
            ],
            scroll="auto",
            expand=True,
        )

    appbar = ft.AppBar(
        title=ft.Text("Report", weight="bold"),
        bgcolor=ft.Colors.TRANSPARENT,
        actions=[
            ft.IconButton(
                ft.Icons.SHARE_ROUNDED,
                tooltip="Share — get public link with PDF & PPTX export",
                on_click=lambda e: page.run_task(on_share_report, e),
                visible=len(state.charts) > 0,
            ),
        ],
    )

    return ft.View(route="/report", appbar=appbar, controls=[content], padding=0)