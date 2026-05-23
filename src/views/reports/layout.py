"""Reports view layout and UI builder."""

from __future__ import annotations

import flet as ft
from core import theme

from components.brand_header import build_brand_header
from components.report_editor import build_report_editor

from .state import ReportsState
from . import handlers


def build_report_view(
    page: ft.Page,
    report_service=None,
    ad_service=None,
    storage=None,
    credit_service=None,
) -> ft.View:
    ui_state = ReportsState(page)

    def _rebuild():
        if not ui_state.content_column.current:
            return
        if ui_state.editor_active["value"]:
            ui_state.content_column.current.controls = _build_editor_content()
        else:
            ui_state.content_column.current.controls = _build_dashboard_content()
        page.update()

    ui_state.rebuild_fn = _rebuild

    def _build_report_card(report: dict) -> ft.Container:
        block_count = len(report.get("blocks", []))
        import datetime

        try:
            dt = datetime.datetime.fromtimestamp(report.get("created_at", 0))
            time_str = dt.strftime("%b %d, %Y")
        except Exception:
            time_str = ""

        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.ASSESSMENT_ROUNDED,
                            color=theme.PRIMARY,
                            size=24,
                        ),
                        width=44,
                        height=44,
                        border_radius=12,
                        bgcolor=ft.Colors.with_opacity(0.1, theme.PRIMARY),
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Column(
                        [
                            ft.Text(
                                report.get("title", "Untitled Report"),
                                weight=ft.FontWeight.W_600,
                                size=14,
                                max_lines=1,
                                overflow="ellipsis",
                            ),
                            ft.Text(
                                f"{block_count} block{'s' if block_count != 1 else ''} · {report.get('dataset_name', '')} · {time_str}",
                                size=11,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                max_lines=1,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Text(
                                    "Shared" if report.get("share_url") else "",
                                    size=10,
                                    color=theme.SUCCESS,
                                ),
                                visible=bool(report.get("share_url")),
                            ),
                            ft.Icon(
                                ft.Icons.CHEVRON_RIGHT_ROUNDED,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=4,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=14,
            border_radius=14,
            bgcolor=theme.GLASS_BG,
            border=ft.Border.all(1, theme.GLASS_BORDER_COLOR),
            on_click=lambda e, r=report: page.run_task(
                handlers.on_open_report, page, ui_state, r, report_service
            ),
            ink=True,
        )

    def _build_dashboard_content() -> list[ft.Control]:
        controls = []
        controls.append(build_brand_header(show_tagline=True, spacing_below=True))

        controls.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Text("Your Reports", size=18, weight=ft.FontWeight.W_700),
                        ft.Container(expand=True),
                        ft.IconButton(
                            ft.Icons.REFRESH_ROUNDED,
                            tooltip="Refresh",
                            on_click=lambda e: page.run_task(
                                handlers.load_reports, page, ui_state, report_service
                            ),
                        ),
                    ],
                ),
                padding=ft.Padding(20, 10, 20, 0),
            )
        )

        if ui_state.is_loading["value"]:
            controls.append(
                ft.Container(
                    content=ft.Column(
                        [ft.ProgressRing(width=30, height=30, stroke_width=3)],
                        horizontal_alignment="center",
                    ),
                    padding=40,
                    alignment=ft.Alignment.CENTER,
                )
            )
        elif not ui_state.user_reports:
            controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Container(height=40),
                            ft.Icon(
                                ft.Icons.ASSESSMENT_OUTLINED,
                                size=64,
                                color=ft.Colors.with_opacity(
                                    0.15, ft.Colors.ON_SURFACE
                                ),
                            ),
                            ft.Text(
                                "No reports yet",
                                size=16,
                                weight="w500",
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            ft.Text(
                                "Pin analysis results or use Autopilot to create your first report.",
                                size=13,
                                color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
                                text_align="center",
                            ),
                            ft.Container(height=16),
                            ft.FilledButton(
                                "Start Analysis",
                                icon=ft.Icons.ANALYTICS_ROUNDED,
                                on_click=lambda _: page.go("/analysis"),
                            ),
                        ],
                        horizontal_alignment="center",
                        spacing=8,
                    ),
                    padding=20,
                    alignment=ft.Alignment.CENTER,
                )
            )
        else:
            for report in ui_state.user_reports:
                controls.append(
                    ft.Container(
                        content=_build_report_card(report),
                        margin=ft.Margin(20, 4, 20, 4),
                    )
                )

        controls.append(ft.Container(height=100))
        return controls

    def _build_editor_content() -> list[ft.Control]:
        if ui_state.is_arranging["value"]:
            return [
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Container(height=80),
                            ft.ProgressRing(width=40, height=40, stroke_width=3),
                            ft.Text(
                                "AI is arranging your report...",
                                size=14,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            ft.Text(
                                "Optimizing order, polishing descriptions",
                                size=12,
                                color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
                            ),
                        ],
                        horizontal_alignment="center",
                        spacing=12,
                    ),
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                )
            ]

        return build_report_editor(
            blocks=ui_state.editor_blocks,
            title=ui_state.draft_title["value"],
            description=ui_state.draft_desc["value"],
            on_blocks_changed=_rebuild,
            on_title_changed=lambda v: ui_state.draft_title.update({"value": v}),
            on_desc_changed=lambda v: ui_state.draft_desc.update({"value": v}),
            on_save=lambda: page.run_task(
                handlers.on_save, page, ui_state, report_service
            ),
            on_share=lambda: page.run_task(
                handlers.on_share, page, ui_state, report_service, ad_service
            ),
            on_back=lambda: handlers.on_back(page, ui_state, report_service),
            on_import=lambda: handlers.on_import(page, ui_state),
            on_ai_edit=lambda action, text: page.run_task(
                handlers.on_ai_edit, page, ui_state, action, text
            ),
            on_voice_toggle=lambda e: page.run_task(
                handlers.on_voice_toggle, page, ui_state
            ),
            is_saving=ui_state.is_saving["value"],
            is_sharing=ui_state.is_sharing["value"],
            is_recording=ui_state.is_recording["value"],
            is_transcribing=ui_state.is_transcribing["value"],
            is_ai_editing=ui_state.is_ai_editing["value"],
            recording_time=ui_state.recording_time["value"],
            ai_prompt_text=ui_state.ai_prompt_text["value"],
            recording_timer_ref=ui_state.recording_timer_ref,
            on_delete=lambda: page.run_task(
                handlers.on_delete_report,
                page,
                ui_state,
                ui_state.active_report["data"]["id"],
                report_service,
            )
            if ui_state.active_report["data"]
            else None,
        )

    page.run_task(handlers.load_reports, page, ui_state, report_service)

    return ft.View(
        route="/reports",
        appbar=ft.AppBar(
            title=ft.Text("Reports", weight="bold"),
            bgcolor=ft.Colors.TRANSPARENT,
        ),
        controls=[
            ft.Column(
                ref=ui_state.content_column,
                controls=_build_dashboard_content(),
                scroll="auto",
                expand=True,
            ),
        ],
        padding=0,
    )
