import flet as ft
from core import theme
from core.state import state
from components.credit_badge import build_credit_badge
from components.file_import_card import build_file_import_card
from components.stat_card import build_stat_card
from components.data_preview import build_data_preview
from components.brand_header import build_brand_header
from services.file_picker_service import FilePickerService
from views.analysis.state import AnalysisState
from views.analysis.handlers import (
    process_file,
    on_clear_data,
    on_custom_prompt,
    on_voice_toggle,
)
from views.analysis.ui_components import build_block_card

def build_analysis_view(page: ft.Page, credit_service) -> ft.View:
    view_state = AnalysisState(page, credit_service)
    
    if not hasattr(state, "analysis_blocks"):
        state.analysis_blocks = []

    def _on_file_result(file):
        page.run_task(process_file, view_state, file)

    view_state.file_picker_svc = FilePickerService(page, on_result=_on_file_result)

    def on_pick_file(e):
        view_state.file_picker_svc.pick_data_file()

    def on_autopilot_toggle_handler(e):
        state.autopilot_enabled = e.control.value

    def _build_content() -> list[ft.Control]:
        res = []
        if state.current_df is None:
            if state.is_loading:
                fname = view_state.loading_file_name["value"] or "data"
                fsize = view_state.loading_file_size["value"]
                size_mb = fsize / (1024 * 1024) if fsize else 0
                load_msg = f"Loading {fname}..."
                if size_mb > 0:
                    load_msg = f"Loading {fname} ({size_mb:.1f} MB)..."

                loading_controls = [
                    ft.Container(height=150),
                    ft.ProgressRing(width=40, height=40, stroke_width=3),
                    ft.Text(load_msg, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                ]
                if size_mb > 5 and fname.lower().endswith(".xlsx"):
                    loading_controls.append(
                        ft.Text("Large Excel files may take up to 60 seconds", size=12, color=ft.Colors.ON_SURFACE_VARIANT, italic=True)
                    )
                elif size_mb > 10:
                    loading_controls.append(
                        ft.Text("Large files may take a moment to process", size=12, color=ft.Colors.ON_SURFACE_VARIANT, italic=True)
                    )

                res.append(
                    ft.Container(
                        content=ft.Column(loading_controls, horizontal_alignment="center", spacing=16),
                        expand=True,
                        alignment=ft.Alignment.CENTER,
                    )
                )
            else:
                res.append(
                    ft.Container(
                        content=ft.Column(
                            [
                                build_brand_header(show_tagline=True, spacing_below=True),
                                build_file_import_card(on_pick_file, False),
                                ft.Container(height=20),
                                ft.Row(
                                    [
                                        ft.Icon(ft.Icons.ROCKET_LAUNCH_ROUNDED, color=theme.ACCENT),
                                        ft.Text("Autopilot Mode", weight="w500"),
                                        ft.Switch(
                                            ref=view_state.autopilot_enabled_ref,
                                            value=getattr(state, "autopilot_enabled", True),
                                            active_color=theme.PRIMARY,
                                            on_change=on_autopilot_toggle_handler,
                                        ),
                                    ],
                                    alignment="center",
                                    spacing=10,
                                ),
                            ],
                            horizontal_alignment="center",
                        ),
                        padding=20,
                    )
                )
        else:
            res.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.DESCRIPTION_ROUNDED, color=theme.ACCENT),
                            ft.Column(
                                [
                                    ft.Text(state.current_df_name, weight="bold", size=16),
                                    ft.Text(
                                        f"{state.current_df_rows:,} rows | {len(state.current_df_columns)} cols",
                                        size=12,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.IconButton(ft.Icons.CLOSE_ROUNDED, on_click=lambda e: on_clear_data(view_state, e)),
                        ]
                    ),
                    padding=ft.Padding(20, 10, 20, 10),
                )
            )

            res.append(
                ft.Container(
                    ft.Row(
                        [
                            build_stat_card("Rows", f"{state.current_df_rows:,}", ft.Icons.TABLE_ROWS_ROUNDED, theme.ACCENT),
                            build_stat_card("Cols", str(len(state.current_df_columns)), ft.Icons.VIEW_COLUMN_ROUNDED, theme.PRIMARY),
                            build_stat_card("Credits", str(state.credits_remaining), ft.Icons.BOLT_ROUNDED, theme.SUCCESS),
                        ],
                        spacing=10,
                    ),
                    padding=ft.Padding(20, 0, 20, 10),
                )
            )

            res.append(
                ft.Container(
                    build_data_preview(state.current_df),
                    padding=ft.Padding(20, 0, 20, 10),
                )
            )

            for i, b in enumerate(state.analysis_blocks):
                res.append(build_block_card(view_state, b, i))

            if state.is_analyzing:
                progress_text = getattr(state, "autopilot_progress", "") or "AI thinking..."
                loading_controls = [
                    ft.ProgressRing(width=16, height=16),
                    ft.Text(progress_text, size=13, expand=True),
                ]
                if getattr(state, "autopilot_progress", ""):
                    loading_controls.append(
                        ft.TextButton(
                            "Stop",
                            icon=ft.Icons.STOP_ROUNDED,
                            icon_color=theme.ERROR,
                            on_click=lambda e: (setattr(state, "autopilot_cancelled", True) or view_state.rebuild()),
                        )
                    )
                res.append(
                    ft.Container(
                        content=ft.Row(loading_controls, alignment="center", spacing=10),
                        padding=ft.Padding(0, 16, 0, 16),
                    )
                )

            if not state.is_analyzing:
                res.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.TextField(
                                    ref=view_state.custom_prompt_field,
                                    hint_text="Describe an analysis or tap mic...",
                                    expand=True,
                                    border_radius=12,
                                    on_submit=lambda e: page.run_task(on_custom_prompt, view_state, e),
                                    disabled=view_state.is_recording["value"] or view_state.is_transcribing["value"],
                                ),
                                ft.Row(
                                    [
                                        ft.Text(
                                            ref=view_state.recording_timer,
                                            value=f"00:{view_state.recording_time['value']:02d} / 01:00",
                                            size=12,
                                            color=theme.ERROR,
                                            weight="bold",
                                            visible=view_state.is_recording["value"],
                                        ),
                                        ft.ProgressRing(
                                            width=16,
                                            height=16,
                                            stroke_width=2,
                                            visible=view_state.is_transcribing["value"],
                                        ),
                                        ft.IconButton(
                                            ft.Icons.STOP_ROUNDED if view_state.is_recording["value"] else ft.Icons.MIC_ROUNDED,
                                            icon_color=theme.ERROR if view_state.is_recording["value"] else ft.Colors.ON_SURFACE_VARIANT,
                                            tooltip="Stop" if view_state.is_recording["value"] else "Voice",
                                            on_click=lambda e: page.run_task(on_voice_toggle, view_state, e),
                                            disabled=view_state.is_transcribing["value"],
                                        ),
                                    ],
                                    spacing=4,
                                    vertical_alignment="center",
                                ),
                                ft.IconButton(
                                    ft.Icons.SEND_ROUNDED,
                                    icon_color=theme.PRIMARY,
                                    on_click=lambda e: page.run_task(on_custom_prompt, view_state, e),
                                    disabled=view_state.is_recording["value"] or view_state.is_transcribing["value"],
                                ),
                            ]
                        ),
                        padding=ft.Padding(20, 10, 10, 10),
                    )
                )

            res.append(ft.Container(height=100))

        return res

    def _rebuild():
        if view_state.content_column.current:
            view_state.content_column.current.controls = _build_content()
            async def do_scroll():
                try:
                    await view_state.content_column.current.scroll_to(offset=-1, duration=500)
                except Exception:
                    pass
            page.run_task(do_scroll)
            page.update()

    view_state.rebuild_fn = _rebuild

    if getattr(state, "trigger_file_picker", False):
        state.trigger_file_picker = False
        view_state.file_picker_svc.pick_data_file()

    if getattr(state, "session_to_restore", None):
        session = state.session_to_restore
        state.session_to_restore = None
        file_path = session.get("file_path", "")
        if file_path and state.current_df is None:
            page.run_task(
                process_file,
                view_state,
                type("File", (), {"path": file_path, "name": session.get("df_name", "Dataset")})(),
            )

    return ft.View(
        route="/analysis",
        appbar=ft.AppBar(
            title=ft.Text("Analysis Engine", weight="bold"),
            actions=[
                ft.Container(
                    build_credit_badge(state.credits_remaining),
                    margin=ft.Margin(0, 0, 20, 0),
                )
            ],
        ),
        controls=[
            ft.Column(
                ref=view_state.content_column,
                controls=_build_content(),
                scroll="auto",
                expand=True,
            )
        ],
        padding=0,
    )
