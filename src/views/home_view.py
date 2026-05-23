"""Home view — marketing landing dashboard with quick actions and branding."""

from __future__ import annotations

import datetime
import json
from typing import Callable

import flet as ft

from core import theme, tokens
from core.state import state
from core.constants import STORAGE_THEME
from components.credit_badge import build_credit_badge
from components.brand_header import build_brand_header


def build_home_view(
    page: ft.Page,
    on_import_file: Callable,
    on_navigate: Callable,
    storage=None,
) -> ft.View:
    """Build the Home landing tab."""

    # ── Hero section ────────────────────────────────────────────────
    hero = build_brand_header(show_tagline=True, spacing_below=True)

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
                            subtitle="File or Database",
                            color=theme.PRIMARY,
                            on_click=lambda e: on_import_file(e, autopilot=False),
                        ),
                        _action_card(
                            icon=ft.Icons.ROCKET_LAUNCH_ROUNDED,
                            title="Autopilot",
                            subtitle="AI auto-report",
                            color=theme.ACCENT,
                            on_click=lambda e: on_import_file(e, autopilot=True),
                        ),
                    ],
                    spacing=tokens.SPACE_MD,
                ),
                ft.Container(height=tokens.SPACE_SM),
                ft.Row(
                    controls=[
                        _action_card(
                            icon=ft.Icons.DYNAMIC_FORM_ROUNDED,
                            title="Create Survey",
                            subtitle="AI-powered forms",
                            color=theme.WARNING,
                            on_click=lambda e: on_navigate("/forms"),
                        ),
                        _action_card(
                            icon=ft.Icons.ASSESSMENT_ROUNDED,
                            title="Reports",
                            subtitle=f"{len(state.user_reports or [])} report{'s' if len(state.user_reports or []) != 1 else ''}",
                            color=theme.SUCCESS,
                            on_click=lambda e: on_navigate("/reports"),
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

    # ── What you can do ─────────────────────────────────────────────
    features = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(
                    "What Spaninsight Does",
                    size=tokens.FONT_MD,
                    weight=ft.FontWeight.W_600,
                ),
                ft.Container(height=tokens.SPACE_SM),
                _feature_card(
                    ft.Icons.AUTO_AWESOME_ROUNDED,
                    "AI-Powered Analysis",
                    "Import any CSV or Excel file. AI suggests insights, "
                    "writes Python code, and generates charts — great for "
                    "research projects, business reports, or personal data.",
                    theme.PRIMARY,
                ),
                _feature_card(
                    ft.Icons.DYNAMIC_FORM_ROUNDED,
                    "Smart Surveys",
                    "Describe a questionnaire in plain English or voice. AI generates it. "
                    "Share a link, collect responses, and analyze — great for research, feedback, and more.",
                    theme.WARNING,
                ),
                _feature_card(
                    ft.Icons.ROCKET_LAUNCH_ROUNDED,
                    "Autopilot Mode",
                    "One tap. AI runs multiple analysis passes, generates charts, "
                    "writes descriptions, and builds a complete report for presentations.",
                    theme.ACCENT,
                ),
                _feature_card(
                    ft.Icons.SHARE_ROUNDED,
                    "Export & Share",
                    "Share a public link to your interactive web report. "
                    "Anyone can view your insights or export to PDF/PPTX from their browser.",
                    theme.SUCCESS,
                ),
                _feature_card(
                    ft.Icons.MIC_ROUNDED,
                    "Voice Commands",
                    "Speak your analysis request in a 60-second voice note. "
                    "Spaninsight transcribes it and runs the analysis for you.",
                    "#9C27B0",
                ),
            ],
            spacing=tokens.SPACE_MD,
        ),
        padding=ft.Padding(
            left=tokens.SPACE_LG,
            right=tokens.SPACE_LG,
            top=tokens.SPACE_LG,
            bottom=tokens.SPACE_SM,
        ),
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
                _step_row("1", "Import", "Upload a CSV or Excel file (up to 100MB)"),
                _step_row("2", "Analyze", "AI suggests insights or use Autopilot"),
                _step_row(
                    "3", "Share", "Get a public link to your interactive web report"
                ),
            ],
            spacing=tokens.SPACE_MD,
        ),
        padding=ft.Padding(
            left=tokens.SPACE_LG,
            right=tokens.SPACE_LG,
            top=tokens.SPACE_LG,
            bottom=tokens.SPACE_SM,
        ),
    )

    # ── Credits info ────────────────────────────────────────────────
    credits_info = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.BOLT_ROUNDED, size=20, color=theme.ACCENT),
                ft.Column(
                    [
                        ft.Text(
                            "50 Free Credits Daily",
                            size=tokens.FONT_SM,
                            weight=ft.FontWeight.W_600,
                        ),
                        ft.Text(
                            "Each analysis costs 1 credit. Invite friends for +10 bonus credits per referral.",
                            size=tokens.FONT_XS,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
            ],
            spacing=tokens.SPACE_MD,
            vertical_alignment="center",
        ),
        padding=ft.Padding(
            tokens.SPACE_LG, tokens.SPACE_MD, tokens.SPACE_LG, tokens.SPACE_MD
        ),
        margin=ft.Margin(tokens.SPACE_LG, 0, tokens.SPACE_LG, tokens.SPACE_LG),
        border_radius=tokens.RADIUS_LG,
        bgcolor=ft.Colors.with_opacity(0.06, theme.ACCENT),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.15, theme.ACCENT)),
    )

    # ── Recent Analyses ─────────────────────────────────────────────
    recent_col = ft.Ref[ft.Column]()

    async def load_recent(p: ft.Page):
        if not storage:
            return
        try:
            recent_str = await storage.get("recent_analyses")
            recent = json.loads(recent_str) if recent_str else []
        except Exception:
            recent = []

        if not recent:
            if recent_col.current:
                recent_col.current.controls = [
                    ft.Text(
                        "No recent analyses yet. Import a dataset to get started!",
                        size=tokens.FONT_XS,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        italic=True,
                    )
                ]
                recent_col.current.update()
            return

        controls = []

        async def on_delete_session(session_to_delete, e):
            try:
                recent_str = await storage.get("recent_analyses")
                cur_recent = json.loads(recent_str) if recent_str else []
                cur_recent = [
                    s
                    for s in cur_recent
                    if s.get("file_path") != session_to_delete.get("file_path")
                ]
                await storage.set("recent_analyses", json.dumps(cur_recent))
                # Reload list
                page.run_task(load_recent, page)
            except Exception:
                pass

        def make_delete_handler(session_item):
            return lambda e: page.run_task(on_delete_session, session_item, e)

        def make_restore_handler(session_item):
            def _restore(e):
                state.session_to_restore = session_item
                on_navigate("/analysis")

            return _restore

        for session in recent:
            time_val = session.get("timestamp", 0)
            try:
                dt = datetime.datetime.fromtimestamp(time_val)
                time_str = dt.strftime("%b %d, %Y %I:%M %p")
            except Exception:
                time_str = "Recent"

            controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.ANALYTICS_ROUNDED, color=theme.PRIMARY, size=22
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        session.get("df_name", "Dataset"),
                                        size=tokens.FONT_SM,
                                        weight=ft.FontWeight.W_600,
                                    ),
                                    ft.Text(
                                        f"{session.get('df_rows', 0):,} rows | {session.get('df_cols', 0)} cols | {time_str}",
                                        size=tokens.FONT_XS,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                icon_color=theme.ERROR,
                                tooltip="Delete Session",
                                on_click=make_delete_handler(session),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    padding=12,
                    border_radius=12,
                    bgcolor=theme.GLASS_BG,
                    border=ft.Border.all(1, theme.GLASS_BORDER_COLOR),
                    on_click=make_restore_handler(session),
                    ink=True,
                )
            )

        if recent_col.current:
            recent_col.current.controls = controls
            recent_col.current.update()

    recent_section = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(
                    "Recent Analyses",
                    size=tokens.FONT_MD,
                    weight=ft.FontWeight.W_600,
                ),
                ft.Container(height=tokens.SPACE_SM),
                ft.Column(
                    ref=recent_col,
                    spacing=8,
                    controls=[ft.ProgressRing(width=20, height=20, stroke_width=2)],
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

    # ── Offline warning banner ──────────────────────────────────────
    offline_banner = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(
                    ft.Icons.WIFI_OFF_ROUNDED,
                    size=tokens.ICON_SM,
                    color=theme.WARNING,
                ),
                ft.Text(
                    "Gateway offline — using local analytical fallbacks",
                    size=tokens.FONT_XS,
                    weight=ft.FontWeight.W_500,
                ),
            ],
            spacing=tokens.SPACE_SM,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        padding=10,
        bgcolor=ft.Colors.with_opacity(0.1, theme.WARNING),
        border=ft.Border(
            bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.2, theme.WARNING))
        ),
        visible=not state.gateway_online,
    )

    content = ft.Column(
        controls=[
            offline_banner,
            hero,
            quick_actions,
            recent_section,
            privacy_banner,
            features,
            how_it_works,
            credits_info,
            ft.Container(height=80),
        ],
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
                icon=ft.Icons.LIGHT_MODE_ROUNDED
                if page.theme_mode == ft.ThemeMode.DARK
                else ft.Icons.DARK_MODE_ROUNDED,
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
        is_dark = p.theme_mode == ft.ThemeMode.DARK or (
            p.theme_mode == ft.ThemeMode.SYSTEM
            and p.platform_brightness == ft.Brightness.DARK
        )
        p.theme_mode = ft.ThemeMode.LIGHT if is_dark else ft.ThemeMode.DARK
        state.theme_mode = p.theme_mode

        # Persist
        if storage:
            await storage.set(
                STORAGE_THEME, "light" if p.theme_mode == ft.ThemeMode.LIGHT else "dark"
            )

        # Update icon directly to avoid full page reload
        e.control.icon = (
            ft.Icons.LIGHT_MODE_ROUNDED
            if p.theme_mode == ft.ThemeMode.DARK
            else ft.Icons.DARK_MODE_ROUNDED
        )
        p.update()

    page.run_task(load_recent, page)
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


def _feature_card(icon: str, title: str, desc: str, color: str) -> ft.Container:
    """Build a marketing feature card."""
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Container(
                    content=ft.Icon(icon, size=24, color=color),
                    width=44,
                    height=44,
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.1, color),
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Column(
                    controls=[
                        ft.Text(title, size=tokens.FONT_SM, weight=ft.FontWeight.W_600),
                        ft.Text(
                            desc,
                            size=tokens.FONT_XS,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            max_lines=3,
                            overflow="ellipsis",
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
            ],
            spacing=tokens.SPACE_MD,
            vertical_alignment="start",
        ),
        padding=14,
        border_radius=12,
        bgcolor=theme.GLASS_BG,
        border=ft.Border.all(1, theme.GLASS_BORDER_COLOR),
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
