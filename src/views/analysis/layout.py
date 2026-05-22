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


def build_analysis_view(page: ft.Page, credit_service, report_service=None) -> ft.View:
    view_state = AnalysisState(page, credit_service, report_service)

    if not hasattr(state, "analysis_blocks"):
        state.analysis_blocks = []

    def _on_file_result(file):
        page.run_task(process_file, view_state, file)

    view_state.file_picker_svc = FilePickerService(page, on_result=_on_file_result)

    def on_pick_file(e):
        view_state.file_picker_svc.pick_data_file()

    def on_autopilot_toggle_handler(e):
        state.autopilot_enabled = e.control.value

    # --- STATEFUL DOM CONTAINERS ---
    top_section = ft.Container()
    blocks_list = ft.Column(
        spacing=16
    )  # <-- FIXED: Changed from ListView to standard Column
    loading_section = ft.Container()
    input_section = ft.Container()

    # <-- FIXED: Added scroll="auto" here so the entire page scrolls natively on any laptop
    main_column = ft.Column(
        controls=[top_section, blocks_list, loading_section, input_section],
        expand=True,
        scroll="auto",
    )
    view_state.content_column = ft.Ref[ft.Column]()
    view_state.content_column.current = main_column

    def _update_top_section():
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
                        ft.Text(
                            "Large Excel files may take up to 60 seconds",
                            size=12,
                            italic=True,
                        )
                    )
                top_section.content = ft.Column(
                    loading_controls, horizontal_alignment="center", spacing=16
                )
                top_section.alignment = ft.Alignment.CENTER
                top_section.expand = True
            else:
                top_section.content = ft.Column(
                    [
                        build_brand_header(show_tagline=True, spacing_below=True),
                        build_file_import_card(on_pick_file, False),
                        ft.Container(height=20),
                        ft.Row(
                            [
                                ft.Icon(
                                    ft.Icons.ROCKET_LAUNCH_ROUNDED, color=theme.ACCENT
                                ),
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
                )
                top_section.padding = 20
                top_section.expand = False
        else:
            top_section.content = ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.DESCRIPTION_ROUNDED, color=theme.ACCENT),
                            ft.Column(
                                [
                                    ft.Text(
                                        state.current_df_name, weight="bold", size=16
                                    ),
                                    ft.Text(
                                        f"{state.current_df_rows:,} rows | {len(state.current_df_columns)} cols",
                                        size=12,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.IconButton(
                                ft.Icons.CLOSE_ROUNDED,
                                on_click=lambda e: on_clear_data(view_state, e),
                            ),
                        ]
                    ),
                    ft.Row(
                        [
                            build_stat_card(
                                "Rows",
                                f"{state.current_df_rows:,}",
                                ft.Icons.TABLE_ROWS_ROUNDED,
                                theme.ACCENT,
                            ),
                            build_stat_card(
                                "Cols",
                                str(len(state.current_df_columns)),
                                ft.Icons.VIEW_COLUMN_ROUNDED,
                                theme.PRIMARY,
                            ),
                            build_stat_card(
                                "Credits",
                                str(state.credits_remaining),
                                ft.Icons.BOLT_ROUNDED,
                                theme.SUCCESS,
                            ),
                        ],
                        spacing=10,
                    ),
                    build_data_preview(state.current_df),
                ],
                spacing=15,
            )
            top_section.padding = ft.Padding(20, 10, 20, 10)
            top_section.expand = False

    def _update_blocks():
        if state.current_df is None:
            blocks_list.controls.clear()
            return

        if len(blocks_list.controls) == len(state.analysis_blocks):
            blocks_list.controls = [
                build_block_card(view_state, b, i)
                for i, b in enumerate(state.analysis_blocks)
            ]
        elif len(blocks_list.controls) < len(state.analysis_blocks):
            for i in range(len(blocks_list.controls), len(state.analysis_blocks)):
                blocks_list.controls.append(
                    build_block_card(view_state, state.analysis_blocks[i], i)
                )
        else:
            blocks_list.controls.clear()

    def _update_bottom_sections():
        if state.current_df is None:
            loading_section.visible = False
            input_section.visible = False
            return

        if state.is_analyzing:
            progress_text = getattr(state, "autopilot_progress", "") or "AI thinking..."
            controls = [
                ft.ProgressRing(width=16, height=16),
                ft.Text(progress_text, size=13, expand=True),
            ]
            if getattr(state, "autopilot_progress", ""):
                controls.append(
                    ft.TextButton(
                        "Stop",
                        icon=ft.Icons.STOP_ROUNDED,
                        icon_color=theme.ERROR,
                        on_click=lambda e: (
                            setattr(state, "autopilot_cancelled", True)
                            or view_state.rebuild()
                        ),
                    )
                )

            loading_section.content = ft.Row(controls, alignment="center", spacing=10)
            loading_section.padding = ft.Padding(0, 16, 0, 16)
            loading_section.visible = True
            input_section.visible = False
        else:
            loading_section.visible = False
            if not input_section.content:
                input_section.content = ft.Row(
                    [
                        ft.TextField(
                            ref=view_state.custom_prompt_field,
                            hint_text="Describe an analysis or tap mic...",
                            expand=True,
                            border_radius=12,
                            on_submit=lambda e: page.run_task(
                                on_custom_prompt, view_state, e
                            ),
                        ),
                        ft.Row(
                            [
                                ft.Text(
                                    ref=view_state.recording_timer,
                                    value="00:00 / 01:00",
                                    size=12,
                                    color=theme.ERROR,
                                    weight="bold",
                                    visible=False,
                                ),
                                ft.ProgressRing(
                                    width=16, height=16, stroke_width=2, visible=False
                                ),
                                ft.IconButton(
                                    ft.Icons.MIC_ROUNDED,
                                    icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                    tooltip="Voice",
                                    on_click=lambda e: page.run_task(
                                        on_voice_toggle, view_state, e
                                    ),
                                ),
                            ],
                            spacing=4,
                            vertical_alignment="center",
                        ),
                        ft.IconButton(
                            ft.Icons.SEND_ROUNDED,
                            icon_color=theme.PRIMARY,
                            on_click=lambda e: page.run_task(
                                on_custom_prompt, view_state, e
                            ),
                        ),
                    ]
                )

            input_section.padding = ft.Padding(20, 10, 10, 30)
            input_section.visible = True

            tf = input_section.content.controls[0]
            action_row = input_section.content.controls[1]
            send_btn = input_section.content.controls[2]

            is_rec = view_state.is_recording["value"]
            is_trans = view_state.is_transcribing["value"]

            tf.disabled = is_rec or is_trans
            send_btn.disabled = is_rec or is_trans

            action_row.controls[0].visible = is_rec
            action_row.controls[1].visible = is_trans
            mic_btn = action_row.controls[2]
            mic_btn.icon = ft.Icons.STOP_ROUNDED if is_rec else ft.Icons.MIC_ROUNDED
            mic_btn.icon_color = theme.ERROR if is_rec else ft.Colors.ON_SURFACE_VARIANT
            mic_btn.disabled = is_trans

    def _rebuild():
        try:
            if page.route == "/analysis":
                _update_top_section()
                _update_blocks()
                _update_bottom_sections()
                page.update()

                # <-- FIXED: Restored auto-scroll-to-bottom on update
                async def do_scroll():
                    try:
                        if view_state.content_column.current:
                            await view_state.content_column.current.scroll_to(
                                offset=-1, duration=300
                            )
                    except Exception:
                        pass

                page.run_task(do_scroll)
        except Exception:
            pass

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
                type(
                    "File",
                    (),
                    {"path": file_path, "name": session.get("df_name", "Dataset")},
                )(),
            )

    _rebuild()

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
        controls=[main_column],
        padding=0,
    )
