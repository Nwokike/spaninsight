"""Home view — marketing landing dashboard with quick actions and branding."""

from __future__ import annotations

import logging
from typing import Callable

import flet as ft

from core import theme, tokens
from core.state import state
from components.brand_header import build_brand_header

logger = logging.getLogger(__name__)


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
                            "Each analysis costs 1 credit. Your balance resets automatically every day at midnight UTC.",
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

    # ── Workspaces Section ───────────────────────────────────────────
    workspaces_grid = ft.Ref[ft.ResponsiveRow]()
    from services.project_service import ProjectService

    project_service = ProjectService(page, storage)

    def _stat_badge(icon: str, label: str) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(icon, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(label, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                spacing=4,
            ),
            padding=ft.Padding(6, 2, 6, 2),
            border_radius=6,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
        )

    async def load_workspaces(p: ft.Page):
        if not storage:
            return

        controls = []

        async def on_delete_project(pid_to_delete, e):
            e.control.disabled = True
            p.update()
            try:
                await project_service.delete_project(pid_to_delete)
                p.run_task(load_workspaces, p)
            except Exception as ex:
                logger.error("Failed to delete project from home: %s", ex)

        def make_delete_handler(pid_item):
            return lambda e: p.run_task(on_delete_project, pid_item, e)

        def make_restore_handler(pid_item):
            async def _restore(e):
                state.active_project_id = pid_item
                await storage.set("spaninsight_active_project_id", pid_item)

                # Auto trigger background DataFrame reload if file path is available
                proj = state.user_projects[pid_item]
                fpath = proj.get("current_file_path", "")
                if fpath:
                    import asyncio
                    import os
                    from services import file_service

                    if os.path.exists(fpath):
                        try:
                            # PERFORMANCE FIX: Reload dataset in a background thread to prevent UI freezing on switch
                            df = await asyncio.to_thread(
                                file_service.load_dataframe, fpath
                            )
                            state.set_dataframe(
                                df, proj.get("current_df_name", "Dataset")
                            )
                            state.current_df_summary = await asyncio.to_thread(
                                file_service.get_data_summary, df
                            )
                        except Exception:
                            state.clear_data()
                    else:
                        state.clear_data()
                else:
                    state.clear_data()

                on_navigate("/analysis")

            return lambda e: p.run_task(_restore, e)

        for pid, proj in state.user_projects.items():
            is_active = pid == state.active_project_id
            block_ct = len(proj.get("analysis_blocks", []))
            report_ct = len(proj.get("user_reports", []))
            form_ct = len(proj.get("forms", []))

            is_local = pid.startswith("loc_")
            display_id = "Local Only" if is_local else f"PIN: {pid}"

            card = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.WORKSPACES_ROUNDED,
                                    color=theme.PRIMARY
                                    if is_active
                                    else ft.Colors.ON_SURFACE_VARIANT,
                                    size=22,
                                ),
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            proj.get("title", "Workspace"),
                                            size=tokens.FONT_SM,
                                            weight=ft.FontWeight.W_600,
                                            max_lines=1,
                                            overflow="ellipsis",
                                        ),
                                        ft.Text(
                                            "Active Workspace"
                                            if is_active
                                            else display_id,
                                            size=tokens.FONT_XS,
                                            color=theme.PRIMARY
                                            if is_active
                                            else ft.Colors.ON_SURFACE_VARIANT,
                                            weight=ft.FontWeight.W_500
                                            if is_active
                                            else ft.FontWeight.NORMAL,
                                        ),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                    icon_color=theme.ERROR,
                                    icon_size=18,
                                    tooltip="Delete Workspace",
                                    on_click=make_delete_handler(pid),
                                    visible=len(state.user_projects) > 1,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Container(height=2),
                        ft.Text(
                            proj.get("description")
                            or "Collaborative AI analytical workspace.",
                            size=tokens.FONT_XS,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            max_lines=2,
                            overflow="ellipsis",
                        ),
                        ft.Container(height=4),
                        ft.Row(
                            controls=[
                                _stat_badge(
                                    ft.Icons.ANALYTICS_ROUNDED,
                                    f"{block_ct} step{'s' if block_ct != 1 else ''}",
                                ),
                                _stat_badge(
                                    ft.Icons.ASSESSMENT_ROUNDED,
                                    f"{report_ct} report{'s' if report_ct != 1 else ''}",
                                ),
                                _stat_badge(
                                    ft.Icons.DYNAMIC_FORM_ROUNDED,
                                    f"{form_ct} form{'s' if form_ct != 1 else ''}",
                                ),
                            ],
                            spacing=6,
                        ),
                    ],
                    spacing=4,
                ),
                padding=14,
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.04, theme.PRIMARY)
                if is_active
                else theme.GLASS_BG,
                border=ft.Border.all(
                    1.5 if is_active else 1,
                    theme.PRIMARY if is_active else theme.GLASS_BORDER_COLOR,
                ),
                on_click=make_restore_handler(pid),
                ink=True,
                col={"sm": 12, "md": 6},
            )
            controls.append(card)

        if workspaces_grid.current:
            workspaces_grid.current.controls = controls
            workspaces_grid.current.update()

    from components.project_switcher import _show_switcher_dialog

    recent_section = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(
                            "Your Workspaces",
                            size=tokens.FONT_MD,
                            weight=ft.FontWeight.W_600,
                            expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.ADD_ROUNDED,
                            icon_color=theme.PRIMARY,
                            tooltip="Create New Workspace",
                            on_click=lambda e: _show_switcher_dialog(
                                page, project_service
                            ),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.LOGIN_ROUNDED,
                            icon_color=theme.PRIMARY,
                            tooltip="Join Collaborative Workspace",
                            on_click=lambda e: _show_switcher_dialog(
                                page, project_service
                            ),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Container(height=tokens.SPACE_SM),
                ft.ResponsiveRow(
                    ref=workspaces_grid,
                    spacing=8,
                    run_spacing=8,
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
    )

    page.run_task(load_workspaces, page)
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
