import logging
import flet as ft
from core import theme, tokens
from core.state import state
from components.data_preview import build_data_preview
from components.suggestion_chips import build_suggestion_chips
from views.analysis.state import AnalysisState
from views.analysis.handlers import on_rerun_code, on_suggestion_selected, on_pin_block

logger = logging.getLogger(__name__)

def build_chart_container(block: dict) -> ft.Container | None:
    figure = block.get("figure")
    if not figure:
        return None
    try:
        import flet_charts as fch
        return ft.Container(
            content=fch.MatplotlibChart(figure=figure, expand=True),
            height=280,
        )
    except Exception as e:
        logger.error("Failed to render chart: %s", e)
        return None

def build_text_output_container(result_val, stdout_val) -> ft.Container | None:
    import pandas as pd
    import numpy as np

    if isinstance(result_val, (np.ndarray, pd.Index, list)):
        try:
            result_val = pd.DataFrame(result_val)
        except Exception:
            pass

    if isinstance(result_val, pd.DataFrame):
        if not result_val.empty:
            return ft.Container(
                content=build_data_preview(result_val),
                padding=ft.Padding(0, 10, 0, 10),
            )
        result_val = "Empty DataFrame"
    elif isinstance(result_val, pd.Series):
        if not result_val.empty:
            return ft.Container(
                content=build_data_preview(result_val.to_frame()),
                padding=ft.Padding(0, 10, 0, 10),
            )
        result_val = "Empty Series"

    output_text = str(result_val) if result_val is not None else ""
    if not output_text or output_text.strip() == "None":
        output_text = str(stdout_val) if stdout_val is not None else ""

    if not output_text or not output_text.strip() or output_text.strip() == "None":
        return None

    return ft.Container(
        content=ft.Text(
            output_text, size=12, font_family="RobotoMono", color="#E0E0E0"
        ),
        padding=10,
        bgcolor="#0D0D1A",
        border_radius=8,
    )

def build_terminal(view_state: AnalysisState, code: str, block_index: int = -1) -> ft.Container:
    code_field = ft.Ref[ft.TextField]()

    def _on_run(e):
        if code_field.current and block_index >= 0:
            new_code = code_field.current.value
            view_state.page.run_task(on_rerun_code, view_state, block_index, new_code)

    return ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Container(width=8, height=8, border_radius=4, bgcolor="#FF5F57"),
                                    ft.Container(width=8, height=8, border_radius=4, bgcolor="#FEBC2E"),
                                    ft.Container(width=8, height=8, border_radius=4, bgcolor="#28C840"),
                                ],
                                spacing=4,
                            ),
                            ft.Text("analysis.py", size=10, color="#888888"),
                            ft.TextButton(
                                "▶ Run",
                                icon=ft.Icons.PLAY_ARROW_ROUNDED,
                                style=ft.ButtonStyle(color="#28C840"),
                                on_click=_on_run,
                            ) if block_index >= 0 else ft.Container(),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    padding=ft.Padding(10, 6, 10, 6),
                    bgcolor="#1A1A2E",
                    border_radius=ft.BorderRadius(top_left=8, top_right=8, bottom_left=0, bottom_right=0),
                ),
                ft.Container(
                    content=ft.TextField(
                        ref=code_field,
                        value=code,
                        multiline=True,
                        min_lines=3,
                        max_lines=20,
                        text_size=11,
                        text_style=ft.TextStyle(font_family="RobotoMono", color="#E0E0E0"),
                        border_color=ft.Colors.TRANSPARENT,
                        bgcolor=ft.Colors.TRANSPARENT,
                        cursor_color="#28C840",
                        filled=False,
                    ),
                    padding=ft.Padding(12, 6, 12, 12),
                    bgcolor="#0D0D1A",
                    border_radius=ft.BorderRadius(top_left=0, top_right=0, bottom_left=8, bottom_right=8),
                ),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        margin=ft.Margin(0, 4, 0, 8),
    )

def build_block_card(view_state: AnalysisState, block: dict, index: int) -> ft.Container:
    is_initial = block["type"] == "initial"
    is_failed = block.get("failed", False)
    controls: list[ft.Control] = []

    if is_initial:
        controls.append(
            ft.Row(
                [
                    ft.Icon(ft.Icons.DATASET_ROUNDED, size=16, color=theme.ACCENT),
                    ft.Text("Dataset Overview", weight="bold"),
                ],
                spacing=8,
            )
        )
    else:
        header_color = theme.ERROR if is_failed else theme.ACCENT
        controls.append(
            ft.Row(
                [
                    ft.Icon(
                        ft.Icons.ERROR_OUTLINE_ROUNDED if is_failed else ft.Icons.AUTO_AWESOME_ROUNDED,
                        size=14,
                        color=header_color,
                    ),
                    ft.Text(
                        block["prompt"],
                        weight="bold",
                        expand=True,
                        max_lines=2,
                        overflow="ellipsis",
                    ),
                ],
                spacing=8,
            )
        )

    if is_initial:
        describe_data = block.get("describe_data")
        if describe_data is not None:
            try:
                desc_cols = [
                    ft.DataColumn(ft.Text("Stat", size=tokens.FONT_XS, weight=ft.FontWeight.W_600))
                ] + [
                    ft.DataColumn(ft.Text(str(c)[:15], size=tokens.FONT_XS, weight=ft.FontWeight.W_600))
                    for c in describe_data.columns[:20]
                ]
                desc_rows = []
                for stat_name in describe_data.index:
                    cells = [
                        ft.DataCell(ft.Text(str(stat_name), size=tokens.FONT_XS, weight="w500"))
                    ]
                    for c in describe_data.columns[:20]:
                        val = describe_data.loc[stat_name, c]
                        display = str(val) if val != "" else "—"
                        if len(display) > 12:
                            display = display[:10] + "…"
                        cells.append(ft.DataCell(ft.Text(display, size=tokens.FONT_XS)))
                    desc_rows.append(ft.DataRow(cells=cells))

                controls.append(
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Icon(ft.Icons.QUERY_STATS_ROUNDED, size=14, color=theme.PRIMARY),
                                        ft.Text("Statistical Summary (df.describe)", size=12, weight="w600"),
                                    ],
                                    spacing=6,
                                ),
                                ft.Container(
                                    content=ft.Row(
                                        [
                                            ft.DataTable(
                                                columns=desc_cols,
                                                rows=desc_rows,
                                                heading_row_height=34,
                                                data_row_max_height=30,
                                                column_spacing=12,
                                                border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                                                border_radius=8,
                                            )
                                        ],
                                        scroll=ft.ScrollMode.AUTO,
                                    ),
                                    border_radius=8,
                                ),
                            ],
                            spacing=6,
                        ),
                        padding=ft.Padding(0, 8, 0, 8),
                    )
                )

                col_chips = []
                for c in describe_data.columns[:20]:
                    dtype_str = "?"
                    null_ct = 0
                    if state.current_df is not None and c in state.current_df.columns:
                        dtype_str = str(state.current_df[c].dtype)
                        null_ct = int(state.current_df[c].isnull().sum())
                    
                    null_color = theme.ERROR if null_ct > 0 else theme.SUCCESS
                    col_chips.append(
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text(str(c)[:18], size=11, weight="w600", max_lines=1, overflow="ellipsis"),
                                    ft.Text(dtype_str, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ft.Text(f"{null_ct} null" if null_ct > 0 else "0 null", size=10, color=null_color),
                                ],
                                spacing=2,
                                horizontal_alignment="center",
                            ),
                            padding=ft.Padding(8, 6, 8, 6),
                            border_radius=8,
                            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                            width=90,
                        )
                    )
                if col_chips:
                    controls.append(
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Icon(ft.Icons.VIEW_COLUMN_ROUNDED, size=14, color=theme.ACCENT),
                                            ft.Text("Column Info", size=12, weight="w600"),
                                        ],
                                        spacing=6,
                                    ),
                                    ft.Container(
                                        content=ft.Row(col_chips, spacing=6),
                                        padding=ft.Padding(0, 4, 0, 0),
                                    ),
                                ],
                                spacing=6,
                            ),
                            padding=ft.Padding(0, 4, 0, 8),
                        )
                    )
            except Exception as ex:
                logger.error("Block 0 describe render failed: %s", ex)

    if not is_initial:
        has_chart = False
        if block.get("figure"):
            chart_ui = build_chart_container(block)
            if chart_ui:
                controls.append(chart_ui)
                has_chart = True

        if not has_chart:
            text_ui = build_text_output_container(block.get("result"), block.get("stdout"))
            if text_ui:
                controls.append(text_ui)

    desc = block.get("description", "")
    controls.append(
        ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.LIGHTBULB_OUTLINE_ROUNDED, size=16, color=theme.ACCENT),
                    ft.Text(desc, size=tokens.FONT_SM, color=ft.Colors.ON_SURFACE_VARIANT, expand=True),
                ],
                vertical_alignment="start",
            ),
            padding=12,
            bgcolor=ft.Colors.with_opacity(0.05, theme.ACCENT),
            border_radius=8,
        )
    )

    code = block.get("code", "")
    if code:
        adv = ft.Ref[ft.Container]()

        def toggle(e, ref=adv):
            ref.current.visible = not ref.current.visible
            view_state.page.update()

        controls.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED, size=20, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("View Code", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                    alignment="center",
                    spacing=4,
                ),
                on_click=toggle,
                ink=True,
                padding=ft.Padding(0, 4, 0, 0),
                alignment=ft.Alignment.CENTER,
            )
        )
        controls.append(
            ft.Container(ref=adv, content=build_terminal(view_state, code, index), visible=False)
        )

    if not is_initial:
        action_row = []
        if is_failed:
            action_row.append(
                ft.TextButton(
                    "Retry with AI",
                    icon=ft.Icons.REFRESH_ROUNDED,
                    on_click=lambda e, p=block["prompt"]: view_state.page.run_task(on_suggestion_selected, view_state, p),
                    style=ft.ButtonStyle(color=theme.WARNING),
                )
            )
        is_pinned = block.get("pinned", False)
        if not is_failed:
            action_row.append(
                ft.TextButton(
                    "Pinned" if is_pinned else "Pin to Report",
                    icon=ft.Icons.PUSH_PIN_ROUNDED if is_pinned else ft.Icons.PUSH_PIN_OUTLINED,
                    on_click=lambda e, idx=index: on_pin_block(view_state, idx),
                    disabled=is_pinned,
                    style=ft.ButtonStyle(color=theme.SUCCESS if is_pinned else theme.PRIMARY),
                )
            )
        controls.append(ft.Row(action_row, alignment=ft.MainAxisAlignment.END))

    sug = block.get("suggestions", [])
    if sug:
        controls.append(
            ft.Divider(height=1, thickness=0.5, color=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))
        )
        controls.append(
            build_suggestion_chips(
                sug,
                lambda p: view_state.page.run_task(on_suggestion_selected, view_state, p),
                state.is_analyzing,
            )
        )

    return ft.Container(
        content=ft.Column(controls, spacing=10),
        padding=16,
        margin=ft.Margin(tokens.SPACE_LG, 8, tokens.SPACE_LG, 8),
        border_radius=16,
        bgcolor=theme.GLASS_BG,
        border=ft.Border.all(1, theme.GLASS_BORDER_COLOR),
    )
