"""Report block editor — reorderable block cards with AI editing."""

from __future__ import annotations
import flet as ft
from core import theme, tokens


def build_report_block_card(
    block: dict,
    index: int,
    total: int,
    on_change,
    on_move,
) -> ft.Container:
    """Render one editable report block card with reorder arrows."""

    def _update_prompt(val):
        block["prompt"] = val

    def _update_desc(val):
        block["description"] = val
        on_change()

    # Chart image
    chart_widget = ft.Container(height=0)
    if block.get("figure_png_b64"):
        chart_widget = ft.Container(
            content=ft.Image(
                src=f"data:image/png;base64,{block['figure_png_b64']}",
                fit="contain",
                expand=True,
            ),
            height=240,
            border_radius=tokens.RADIUS_MD,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

    controls = [
        # Header with number + prompt
        ft.Row(
            [
                ft.Container(
                    content=ft.Text(
                        str(index + 1),
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
                ft.TextField(
                    value=block.get("prompt", ""),
                    border="none",
                    text_size=14,
                    text_style=ft.TextStyle(weight=ft.FontWeight.W_600),
                    expand=True,
                    content_padding=ft.Padding(4, 0, 4, 0),
                    max_lines=2,
                    on_change=lambda e: _update_prompt(e.control.value),
                ),
            ],
            spacing=tokens.SPACE_MD,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        # Chart
        chart_widget,
        # Description
        ft.Container(
            content=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.LIGHTBULB_OUTLINE_ROUNDED,
                        size=tokens.ICON_SM,
                        color=theme.ACCENT,
                    ),
                    ft.TextField(
                        value=block.get("description", ""),
                        multiline=True,
                        border=ft.InputBorder.NONE,
                        content_padding=0,
                        text_size=13,
                        expand=True,
                        on_change=lambda e: _update_desc(e.control.value),
                    ),
                ],
                spacing=tokens.SPACE_SM,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=tokens.SPACE_MD,
            border_radius=tokens.RADIUS_MD,
            bgcolor=ft.Colors.with_opacity(0.04, theme.ACCENT),
        ),
        # Reorder arrows
        ft.Row(
            [
                ft.IconButton(
                    ft.Icons.ARROW_UPWARD_ROUNDED,
                    icon_size=16,
                    disabled=index == 0,
                    on_click=lambda e, idx=index: on_move(idx, -1),
                ),
                ft.IconButton(
                    ft.Icons.ARROW_DOWNWARD_ROUNDED,
                    icon_size=16,
                    disabled=index == total - 1,
                    on_click=lambda e, idx=index: on_move(idx, 1),
                ),
                ft.Container(expand=True),
                ft.Text(
                    f"Block {index + 1} of {total}",
                    size=11,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
            spacing=0,
        ),
    ]

    return ft.Container(
        content=ft.Column(controls, spacing=8),
        padding=14,
        border_radius=12,
        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
        border=ft.Border.all(1, theme.GLASS_BORDER_COLOR),
    )


def build_report_editor(
    blocks: list[dict],
    title: str,
    description: str,
    on_blocks_changed,
    on_title_changed,
    on_desc_changed,
    on_save,
    on_share,
    on_back,
    on_import,
    on_ai_edit,
    on_voice_toggle,
    is_saving: bool = False,
    is_sharing: bool = False,
    is_recording: bool = False,
    is_transcribing: bool = False,
    is_ai_editing: bool = False,
    recording_time: int = 0,
    ai_prompt_text: str = "",
    recording_timer_ref: ft.Ref[ft.Text] | None = None,
) -> list[ft.Control]:
    """Build the full report editor UI. Returns list of controls."""
    controls = []

    # Header
    controls.append(
        ft.Container(
            content=ft.Column(
                [
                    ft.Text("Edit Report", weight="bold", size=16),
                    ft.TextField(
                        value=title,
                        label="Report Title",
                        border_radius=10,
                        on_change=lambda e: on_title_changed(e.control.value),
                    ),
                    ft.TextField(
                        value=description,
                        label="Description",
                        border_radius=10,
                        max_lines=3,
                        on_change=lambda e: on_desc_changed(e.control.value),
                    ),
                ],
                spacing=8,
            ),
            padding=20,
            margin=ft.Margin(20, 10, 20, 4),
            border_radius=16,
            bgcolor=theme.GLASS_BG,
            border=ft.Border.all(1, theme.GLASS_BORDER_COLOR),
        )
    )

    # Block cards
    total = len(blocks)

    def _move(idx, direction):
        j = idx + direction
        if 0 <= j < total:
            blocks[idx], blocks[j] = blocks[j], blocks[idx]
            on_blocks_changed()

    for i, block in enumerate(blocks):
        controls.append(
            ft.Container(
                content=build_report_block_card(
                    block, i, total, on_blocks_changed, _move
                ),
                margin=ft.Margin(20, 4, 20, 4),
            )
        )

    # Import from Analysis button
    controls.append(
        ft.Container(
            content=ft.OutlinedButton(
                "Import Block from Analysis",
                icon=ft.Icons.ADD_CHART_ROUNDED,
                on_click=lambda e: on_import(),
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
            ),
            padding=ft.Padding(20, 4, 20, 4),
        )
    )

    # AI edit section
    ai_field_ref = ft.Ref[ft.TextField]()
    controls.append(
        ft.Container(
            content=ft.Column(
                [
                    ft.Text("Edit with AI", weight="bold", size=13, color=theme.ACCENT),
                    ft.Row(
                        [
                            ft.TextField(
                                ref=ai_field_ref,
                                value=ai_prompt_text,
                                hint_text="e.g. 'Make descriptions more academic', 'Reorder by importance'...",
                                border_radius=10,
                                max_lines=2,
                                expand=True,
                                text_size=13,
                                disabled=is_ai_editing or is_recording,
                                on_change=lambda e: on_ai_edit("__set_text__", e.control.value),
                            ),
                            ft.Row(
                                [
                                    ft.Text(
                                        ref=recording_timer_ref,
                                        value=f"00:{recording_time:02d} / 01:00",
                                        size=11,
                                        color=theme.ERROR,
                                        weight="bold",
                                        visible=is_recording,
                                    ),
                                    ft.IconButton(
                                        ft.Icons.STOP_ROUNDED if is_recording else ft.Icons.MIC_ROUNDED,
                                        icon_color=theme.ERROR if is_recording else theme.ACCENT,
                                        tooltip="Stop" if is_recording else "Voice",
                                        on_click=on_voice_toggle,
                                        disabled=is_ai_editing,
                                    ),
                                ],
                                spacing=2,
                                vertical_alignment="center",
                            ),
                            ft.IconButton(
                                ft.Icons.AUTO_FIX_HIGH_ROUNDED,
                                icon_color=theme.ACCENT,
                                tooltip="Apply AI edit",
                                on_click=lambda e: on_ai_edit(
                                    "__submit__",
                                    ai_field_ref.current.value if ai_field_ref.current else "",
                                ),
                                disabled=is_ai_editing or is_recording,
                            ),
                        ],
                        spacing=4,
                        vertical_alignment="center",
                    ),
                    ft.ProgressBar(visible=is_ai_editing or is_transcribing),
                    ft.Row(
                        [
                            ft.ProgressRing(width=16, height=16, stroke_width=2),
                            ft.Text(
                                "Transcribing your voice..."
                                if is_transcribing
                                else "AI is editing your report...",
                                size=12,
                                color=theme.ACCENT,
                            ),
                        ],
                        spacing=8,
                        alignment="center",
                        visible=is_transcribing or is_ai_editing,
                    ),
                    ft.Divider(height=1, color=theme.GLASS_BORDER_COLOR),
                    ft.Row(
                        [
                            ft.FilledButton(
                                "Save",
                                icon=ft.Icons.SAVE_ROUNDED,
                                on_click=lambda e: on_save(),
                                disabled=is_saving or is_ai_editing,
                            ),
                            ft.OutlinedButton(
                                "Share",
                                icon=ft.Icons.SHARE_ROUNDED,
                                on_click=lambda e: on_share(),
                                disabled=is_sharing or is_ai_editing,
                            ),
                            ft.OutlinedButton(
                                "Back",
                                icon=ft.Icons.ARROW_BACK_ROUNDED,
                                on_click=lambda e: on_back(),
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.ProgressBar(visible=is_saving or is_sharing),
                ],
                spacing=8,
            ),
            padding=20,
            margin=ft.Margin(20, 8, 20, 8),
            border_radius=16,
            bgcolor=theme.GLASS_BG,
            border=ft.Border.all(1, theme.GLASS_BORDER_COLOR),
        )
    )

    controls.append(ft.Container(height=100))
    return controls
