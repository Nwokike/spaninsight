"""Home view — landing dashboard with quick actions and branding."""

from __future__ import annotations

import flet as ft

from core import theme, tokens
from core.state import state
from core.constants import STORAGE_THEME
from components.credit_badge import build_credit_badge
from flet_secure_storage import SecureStorage


def build_home_view(
    page: ft.Page,
    on_import_file: callable,
    on_navigate: callable,
) -> ft.View:
    """Build the Home landing tab.

    Args:
        page: Flet page.
        on_import_file: Callback to start file import flow.
        on_navigate: Callback(route: str) for navigation.
    """

    # ── Hero section ────────────────────────────────────────────────
    hero = ft.Container(
        content=ft.Column(
            controls=[
                ft.Container(height=tokens.SPACE_LG),
                ft.Image(
                    src="logo.png",
                    width=200,
                    height=65,
                    fit=ft.BoxFit.CONTAIN,
                ),
                ft.Container(height=tokens.SPACE_SM),
                ft.Text(
                    "Privacy-First Data Intelligence",
                    size=tokens.FONT_SM,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=tokens.SPACE_XXL),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
        ),
    )

    # ── Quick action cards ──────────────────────────────────────────
    quick_actions = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(
                    "Quick Start",
                    size=tokens.FONT_MD,
                    weight=ft.FontWeight.W_600,
                ),
                ft.Container(height=tokens.SPACE_SM),
                ft.Row(
                    controls=[
                        _action_card(
                            icon=ft.Icons.UPLOAD_FILE_ROUNDED,
                            title="Import Data",
                            subtitle="CSV or Excel",
                            color=theme.PRIMARY,
                            on_click=on_import_file,
                        ),
                        _action_card(
                            icon=ft.Icons.ROCKET_LAUNCH_ROUNDED,
                            title="Autopilot",
                            subtitle="AI auto-report",
                            color=theme.ACCENT,
                            on_click=on_import_file,
                        ),
                    ],
                    spacing=tokens.SPACE_MD,
                ),
                ft.Container(height=tokens.SPACE_SM),
                ft.Row(
                    controls=[
                        _action_card(
                            icon=ft.Icons.DYNAMIC_FORM_ROUNDED,
                            title="Create Form",
                            subtitle="Coming soon",
                            color=theme.WARNING,
                            on_click=lambda e: on_navigate("/forms"),
                            disabled=True,
                        ),
                        _action_card(
                            icon=ft.Icons.ASSESSMENT_ROUNDED,
                            title="Reports",
                            subtitle=f"{len(state.charts)} charts",
                            color=theme.SUCCESS,
                            on_click=lambda e: on_navigate("/report"),
                            disabled=len(state.charts) == 0,
                        ),
                    ],
                    spacing=tokens.SPACE_MD,
                ),
            ],
            spacing=0,
        ),
        padding=ft.Padding(
            left=tokens.SPACE_LG,
            right=tokens.SPACE_LG,
            top=0,
            bottom=tokens.SPACE_LG,
        ),
    )

    # ── Privacy banner ──────────────────────────────────────────────
    privacy_banner = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(
                    ft.Icons.SHIELD_ROUNDED,
                    size=tokens.ICON_MD,
                    color=theme.SUCCESS,
                ),
                ft.Column(
                    controls=[
                        ft.Text(
                            "100% Privacy-First",
                            size=tokens.FONT_SM,
                            weight=ft.FontWeight.W_600,
                        ),
                        ft.Text(
                            "Your data never leaves your device. "
                            "All analysis runs locally.",
                            size=tokens.FONT_XS,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    spacing=tokens.SPACE_XXS,
                    expand=True,
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
        margin=ft.Margin(
            left=tokens.SPACE_LG,
            right=tokens.SPACE_LG,
            top=tokens.SPACE_SM,
            bottom=tokens.SPACE_SM,
        ),
        border_radius=tokens.RADIUS_LG,
        bgcolor=ft.Colors.with_opacity(0.06, theme.SUCCESS),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.15, theme.SUCCESS)),
    )

    # ── How it works ────────────────────────────────────────────────
    how_it_works = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(
                    "How It Works",
                    size=tokens.FONT_MD,
                    weight=ft.FontWeight.W_600,
                ),
                ft.Container(height=tokens.SPACE_SM),
                _step_row("1", "Import", "Upload a CSV or Excel file"),
                _step_row("2", "Analyze", "AI suggests insights or use Autopilot"),
                _step_row("3", "Share", "Export as PDF or share a public link"),
            ],
            spacing=tokens.SPACE_MD,
        ),
        padding=ft.Padding(
            left=tokens.SPACE_LG,
            right=tokens.SPACE_LG,
            top=tokens.SPACE_LG,
            bottom=tokens.SPACE_XXXL,
        ),
    )

    content = ft.Column(
        controls=[hero, quick_actions, privacy_banner, how_it_works],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=0,
    )

    appbar = ft.AppBar(
        title=ft.Text("Home", weight=ft.FontWeight.W_600, size=tokens.FONT_XL),
        center_title=False,
        bgcolor=ft.Colors.TRANSPARENT,
        actions=[
            ft.IconButton(
                icon=ft.Icons.LIGHT_MODE_ROUNDED if page.theme_mode == ft.ThemeMode.DARK else ft.Icons.DARK_MODE_ROUNDED,
                tooltip="Toggle Theme",
                on_click=lambda e: page.run_task(_toggle_theme, e, page),
            ),
            ft.Container(
                content=build_credit_badge(state.credits_remaining),
                margin=ft.Margin(0, 0, tokens.SPACE_LG, 0),
            ),
        ],
    )

    async def _toggle_theme(e, p: ft.Page):
        p.theme_mode = ft.ThemeMode.LIGHT if p.theme_mode == ft.ThemeMode.DARK else ft.ThemeMode.DARK
        state.theme_mode = p.theme_mode
        
        # Persist
        storage = SecureStorage()
        await storage.set(STORAGE_THEME, "light" if p.theme_mode == ft.ThemeMode.LIGHT else "dark")
        
        # Update icon directly to avoid full page reload
        e.control.icon = ft.Icons.LIGHT_MODE_ROUNDED if p.theme_mode == ft.ThemeMode.DARK else ft.Icons.DARK_MODE_ROUNDED
        p.update()


    return ft.View(route="/home", appbar=appbar, controls=[content], padding=0)


def _action_card(
    icon: str,
    title: str,
    subtitle: str,
    color: str,
    on_click=None,
    disabled: bool = False,
) -> ft.Container:
    """Build a quick action card."""
    opacity = 0.4 if disabled else 1.0
    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Container(
                    content=ft.Icon(icon, size=tokens.ICON_XL, color=color),
                    width=52,
                    height=52,
                    border_radius=tokens.RADIUS_LG,
                    bgcolor=ft.Colors.with_opacity(0.1, color),
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Text(
                    title,
                    size=tokens.FONT_SM,
                    weight=ft.FontWeight.W_600,
                ),
                ft.Text(
                    subtitle,
                    size=tokens.FONT_XXS,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
            spacing=tokens.SPACE_SM,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        expand=True,
        padding=tokens.SPACE_LG,
        border_radius=tokens.RADIUS_XL,
        bgcolor=theme.GLASS_BG,
        border=ft.Border.all(1, theme.GLASS_BORDER_COLOR),
        on_click=on_click if not disabled else None,
        ink=not disabled,
        opacity=opacity,
    )


def _step_row(number: str, title: str, desc: str) -> ft.Row:
    """Build a numbered step row."""
    return ft.Row(
        controls=[
            ft.Container(
                content=ft.Text(
                    number,
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
            ft.Column(
                controls=[
                    ft.Text(title, size=tokens.FONT_SM, weight=ft.FontWeight.W_600),
                    ft.Text(
                        desc,
                        size=tokens.FONT_XS,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=tokens.SPACE_XXS,
                expand=True,
            ),
        ],
        spacing=tokens.SPACE_MD,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
