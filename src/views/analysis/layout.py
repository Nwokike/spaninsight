import logging
import flet as ft
from core import theme, utils
from core.state import state
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
    on_export_data,
)
from views.analysis.ui_components import build_block_card, build_db_import_card

logger = logging.getLogger(__name__)


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
    top_section_switcher = ft.AnimatedSwitcher(
        content=top_section,
        transition=ft.AnimatedSwitcherTransition.FADE,
        duration=300,
        switch_in_curve=ft.AnimationCurve.EASE_OUT,
        switch_out_curve=ft.AnimationCurve.EASE_IN,
    )
    blocks_list = ft.Column(
        spacing=16
    )  # <-- FIXED: Changed from ListView to standard Column
    loading_section = ft.Container()
    input_section = ft.Container()

    # <-- FIXED: Added scroll="auto" here so the entire page scrolls natively on any laptop
    main_column = ft.Column(
        controls=[top_section_switcher, blocks_list, loading_section, input_section],
        expand=True,
        scroll="auto",
    )
    view_state.content_column = ft.Ref[ft.Column]()
    view_state.content_column.current = main_column

    # Centered glowing status card inside the overlay
    autopilot_overlay_card = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.ProgressRing(
                            width=22, height=22, stroke_width=3, color=theme.PRIMARY
                        ),
                        ft.Text("Autopilot is running...", weight="bold", size=15),
                    ],
                    spacing=12,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Container(height=4),
                ft.Text(
                    "SpanInsight is analyzing your data recursively. Sit back and watch the insights compile in real-time!",
                    size=12,
                    color=ft.Colors.ON_SURFACE,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(
                    content=ft.Text(
                        "Status: Initializing...",
                        size=11,
                        italic=True,
                        color=theme.PRIMARY,
                    ),
                    alignment=ft.Alignment.CENTER,
                ),
                (
                    lambda: ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(
                                    "SPONSORED",
                                    size=8,
                                    weight=ft.FontWeight.W_700,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    letter_spacing=1,
                                ),
                                utils.get_banner_ad(
                                    unit_id="ca-app-pub-5679949845754640/5628404223",
                                    width=320,
                                    height=50,
                                ),
                            ],
                            horizontal_alignment="center",
                            spacing=4,
                        ),
                        alignment=ft.alignment.center,
                        padding=8,
                        border_radius=12,
                        bgcolor=theme.GLASS_BG,
                        border=ft.Border.all(1, theme.GLASS_BORDER_COLOR),
                        margin=ft.Margin(0, 4, 0, 4),
                    )
                )()
                if page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)
                else ft.Container(),
                ft.Container(height=8),
                ft.Row(
                    [
                        ft.FilledButton(
                            "Stop Autopilot",
                            icon=ft.Icons.STOP_ROUNDED,
                            style=ft.ButtonStyle(
                                bgcolor=theme.ERROR,
                                shape=ft.RoundedRectangleBorder(radius=10),
                            ),
                            on_click=lambda e: (
                                setattr(state, "autopilot_cancelled", True)
                                or view_state.rebuild()
                            ),
                        )
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
            spacing=8,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=20,
        width=340,
        border_radius=16,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        shadow=ft.BoxShadow(
            blur_radius=25,
            color=ft.Colors.with_opacity(0.4, ft.Colors.BLACK),
            offset=ft.Offset(0, 8),
        ),
    )

    # Positioned transparent glassmorphic overlay covering the stack
    autopilot_overlay = ft.Container(
        top=0,
        bottom=0,
        left=0,
        right=0,
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.BLACK),
        blur=ft.Blur(sigma_x=1.5, sigma_y=1.5),
        alignment=ft.Alignment.CENTER,
        content=autopilot_overlay_card,
        visible=False,
    )

    def _update_top_section():
        expects_dataset = bool(state.current_df_name)
        has_dataframe = state.current_df is not None

        if expects_dataset and not has_dataframe:
            # Beautiful warning banner for locating/linking dataset
            warning_card = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.WARNING_ROUNDED,
                                    color=theme.WARNING,
                                    size=28,
                                ),
                                ft.Text(
                                    f"{state.current_df_name} (Not loaded locally)",
                                    size=16,
                                    weight=ft.FontWeight.W_600,
                                    color=theme.WARNING,
                                ),
                            ],
                            spacing=10,
                        ),
                        ft.Text(
                            "Spaninsight is 100% privacy-first: your raw data is never uploaded to the cloud gateway. "
                            "Because of this, you must obtain the original file from the creator/collaborator of this project. "
                            "Once you have a copy, locate and link the file below to re-execute the analysis recipe and enable dataset exports.",
                            size=13,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Container(height=4),
                        ft.Row(
                            controls=[
                                ft.FilledButton(
                                    "Locate & Link Dataset",
                                    icon=ft.Icons.FILE_OPEN_ROUNDED,
                                    style=ft.ButtonStyle(
                                        bgcolor=theme.PRIMARY,
                                        shape=ft.RoundedRectangleBorder(radius=12),
                                    ),
                                    on_click=on_pick_file,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=12,
                ),
                padding=20,
                border_radius=16,
                bgcolor=ft.Colors.with_opacity(0.04, theme.WARNING),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.2, theme.WARNING)),
            )

            top_section.content = ft.Column(
                [
                    build_brand_header(show_tagline=True, spacing_below=True),
                    warning_card,
                ],
                horizontal_alignment="center",
            )
            top_section.padding = 20
            top_section.expand = False
            return

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
                if page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS):
                    loading_controls.append(ft.Container(height=20))
                    loading_controls.append(
                        (
                            lambda: ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text(
                                            "SPONSORED",
                                            size=8,
                                            weight=ft.FontWeight.W_700,
                                            color=ft.Colors.ON_SURFACE_VARIANT,
                                            letter_spacing=1,
                                        ),
                                        utils.get_banner_ad(
                                            unit_id="ca-app-pub-5679949845754640/5628404223",
                                            width=320,
                                            height=50,
                                        ),
                                    ],
                                    horizontal_alignment="center",
                                    spacing=4,
                                ),
                                alignment=ft.alignment.center,
                                padding=8,
                                border_radius=12,
                                bgcolor=theme.GLASS_BG,
                                border=ft.Border.all(1, theme.GLASS_BORDER_COLOR),
                            )
                        )()
                    )
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

                def toggle_import_mode(mode):
                    view_state.import_mode = mode
                    view_state.rebuild()

                # Premium glassmorphic mode selection segmented bar
                mode_selector = ft.Container(
                    content=ft.Row(
                        [
                            ft.TextButton(
                                "File Upload",
                                icon=ft.Icons.UPLOAD_FILE_ROUNDED,
                                style=ft.ButtonStyle(
                                    color=theme.PRIMARY
                                    if view_state.import_mode == "file"
                                    else ft.Colors.ON_SURFACE_VARIANT,
                                    bgcolor=ft.Colors.with_opacity(0.1, theme.PRIMARY)
                                    if view_state.import_mode == "file"
                                    else ft.Colors.TRANSPARENT,
                                    shape=ft.RoundedRectangleBorder(radius=12),
                                ),
                                on_click=lambda e: toggle_import_mode("file"),
                            ),
                            ft.TextButton(
                                "SQL Database",
                                icon=ft.Icons.STORAGE_ROUNDED,
                                style=ft.ButtonStyle(
                                    color=theme.PRIMARY
                                    if view_state.import_mode == "database"
                                    else ft.Colors.ON_SURFACE_VARIANT,
                                    bgcolor=ft.Colors.with_opacity(0.1, theme.PRIMARY)
                                    if view_state.import_mode == "database"
                                    else ft.Colors.TRANSPARENT,
                                    shape=ft.RoundedRectangleBorder(radius=12),
                                ),
                                on_click=lambda e: toggle_import_mode("database"),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=12,
                    ),
                    margin=ft.Margin(0, 0, 0, 10),
                )

                import_widget = (
                    build_file_import_card(on_pick_file, False)
                    if view_state.import_mode == "file"
                    else build_db_import_card(view_state)
                )

                top_section.content = ft.Column(
                    [
                        build_brand_header(show_tagline=True, spacing_below=True),
                        mode_selector,
                        import_widget,
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
                                disabled=state.is_analyzing,
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
                    ft.Row(
                        [
                            ft.OutlinedButton(
                                "Download Cleaned Dataset",
                                icon=ft.Icons.DOWNLOAD_ROUNDED,
                                on_click=lambda e: page.run_task(
                                    on_export_data, view_state
                                ),
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=12),
                                    color=theme.SUCCESS,
                                    overlay_color=ft.Colors.with_opacity(
                                        0.08, theme.SUCCESS
                                    ),
                                ),
                                disabled=state.is_analyzing,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        visible=state.dataset_modified,
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

        controls = []
        is_mobile = page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)
        for i, b in enumerate(state.analysis_blocks):
            controls.append(build_block_card(view_state, b, i))
            if is_mobile and (i + 1) % 4 == 0:
                import flet_ads as fta

                controls.append(
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(
                                    "SPONSORED",
                                    size=8,
                                    weight=ft.FontWeight.W_700,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    letter_spacing=1,
                                ),
                                fta.BannerAd(
                                    unit_id="ca-app-pub-5679949845754640/5628404223",
                                    width=320,
                                    height=50,
                                ),
                            ],
                            horizontal_alignment="center",
                            spacing=4,
                        ),
                        alignment=ft.alignment.center,
                        padding=8,
                        border_radius=12,
                        bgcolor=theme.GLASS_BG,
                        border=ft.Border.all(1, theme.GLASS_BORDER_COLOR),
                        margin=ft.Margin(20, 8, 20, 8),
                    )
                )
        blocks_list.controls = controls

        if state.is_analyzing:
            from views.analysis.ui_components import build_skeleton_loader

            blocks_list.controls.append(build_skeleton_loader())

    def _update_bottom_sections():
        expects_dataset = bool(state.current_df_name)
        has_dataframe = state.current_df is not None

        if not expects_dataset and not has_dataframe:
            loading_section.visible = False
            input_section.visible = False
            autopilot_overlay.visible = False
            return

        if state.is_analyzing and getattr(state, "autopilot_running", False):
            progress_text = getattr(state, "autopilot_progress", "") or "AI thinking..."
            loading_section.visible = False
            input_section.visible = False

            # Show overlay and update its status dynamically
            autopilot_overlay.visible = True
            step_text_container = autopilot_overlay_card.content.controls[3]
            step_text_container.content.value = f"Status: {progress_text}"
        else:
            autopilot_overlay.visible = False
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
            is_missing_local = expects_dataset and not has_dataframe
            is_loading = state.is_analyzing

            tf.disabled = is_rec or is_trans or is_missing_local or is_loading
            send_btn.disabled = is_rec or is_trans or is_missing_local or is_loading

            action_row.controls[0].visible = is_rec
            action_row.controls[1].visible = is_trans
            mic_btn = action_row.controls[2]
            mic_btn.icon = ft.Icons.STOP_ROUNDED if is_rec else ft.Icons.MIC_ROUNDED
            mic_btn.icon_color = theme.ERROR if is_rec else ft.Colors.ON_SURFACE_VARIANT
            mic_btn.disabled = is_trans or is_missing_local or is_loading

            if is_missing_local:
                tf.hint_text = (
                    f"Locate raw '{state.current_df_name}' to run AI analysis..."
                )
            else:
                tf.hint_text = "Describe an analysis or tap mic..."

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
        except Exception as ex:
            logger.exception("Rebuild failed in analysis view: %s", ex)

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

    stack = ft.Stack(
        controls=[main_column, autopilot_overlay],
        expand=True,
    )

    return ft.View(
        route="/analysis",
        appbar=ft.AppBar(
            title=ft.Text("Analysis Engine", weight="bold"),
            bgcolor=ft.Colors.TRANSPARENT,
        ),
        controls=[stack],
        padding=0,
    )
