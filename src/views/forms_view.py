"""Forms view — Phase 3 stub with coming soon state."""

from __future__ import annotations

import flet as ft

from core import theme, tokens


def build_forms_view(page: ft.Page) -> ft.View:
    """Build the Forms tab view (Phase 3 placeholder)."""

    content = ft.Column(
        controls=[
            ft.Container(height=60),
            ft.Container(
                content=ft.Icon(
                    ft.Icons.DYNAMIC_FORM_ROUNDED,
                    size=80,
                    color=ft.Colors.with_opacity(0.3, theme.PRIMARY),
                ),
                width=120,
                height=120,
                border_radius=60,
                bgcolor=ft.Colors.with_opacity(0.06, theme.PRIMARY),
                alignment=ft.Alignment.CENTER,
            ),
            ft.Container(height=tokens.SPACE_XL),
            ft.Text(
                "Smart Forms",
                size=tokens.FONT_XXL,
                weight=ft.FontWeight.W_700,
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Text(
                "Create surveys with AI, collect responses,\n"
                "and analyze them \u2014 all in one place.",
                size=tokens.FONT_SM,
                color=ft.Colors.ON_SURFACE_VARIANT,
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Container(height=tokens.SPACE_XL),
            ft.Container(
                content=ft.Text(
                    "COMING SOON",
                    size=tokens.FONT_XS,
                    weight=ft.FontWeight.W_700,
                    color=theme.PRIMARY_LIGHT,
                ),
                padding=ft.Padding(
                    left=tokens.SPACE_LG,
                    right=tokens.SPACE_LG,
                    top=tokens.SPACE_SM,
                    bottom=tokens.SPACE_SM,
                ),
                border_radius=tokens.RADIUS_PILL,
                bgcolor=ft.Colors.with_opacity(0.1, theme.PRIMARY),
            ),
            ft.Container(height=tokens.SPACE_XXXL),
            ft.Container(
                content=ft.Column(
                    controls=[
                        _feature_row(
                            ft.Icons.MIC_ROUNDED,
                            "Describe your form with voice or text",
                        ),
                        _feature_row(
                            ft.Icons.SHARE_ROUNDED,
                            "Share a link to collect responses",
                        ),
                        _feature_row(
                            ft.Icons.ANALYTICS_ROUNDED,
                            "Analyze responses with AI",
                        ),
                    ],
                    spacing=tokens.SPACE_LG,
                ),
                padding=ft.Padding(
                    left=tokens.SPACE_XXXL,
                    right=tokens.SPACE_XXXL,
                    top=0,
                    bottom=0,
                ),
            ),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    appbar = ft.AppBar(
        title=ft.Text("Forms", weight=ft.FontWeight.W_600, size=tokens.FONT_XL),
        center_title=False,
        bgcolor=ft.Colors.TRANSPARENT,
    )

    return ft.View(route="/forms", appbar=appbar, controls=[content], padding=0)


def _feature_row(icon: str, text: str) -> ft.Row:
    return ft.Row(
        controls=[
            ft.Container(
                content=ft.Icon(icon, size=tokens.ICON_MD, color=theme.ACCENT),
                width=36,
                height=36,
                border_radius=tokens.RADIUS_SM,
                bgcolor=ft.Colors.with_opacity(0.08, theme.ACCENT),
                alignment=ft.Alignment.CENTER,
            ),
            ft.Text(text, size=tokens.FONT_SM, color=ft.Colors.ON_SURFACE_VARIANT, expand=True),
        ],
        spacing=tokens.SPACE_MD,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
