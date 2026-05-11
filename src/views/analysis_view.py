"""Analysis view — block-chain data analysis workspace.

Architecture:
  Block 0 (Initial): Data table + AI description + first suggestions
  Block N (Result):   Chart + AI description + expandable code + new suggestions

After each block, describe & suggest fire IN PARALLEL.
Context = always Block 0 + last block.
Pin to Report = chart/table + AI description only (no code, no suggestions).
"""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from core import theme, tokens
from core.state import state
from core.constants import COST_SUGGEST, COST_CUSTOM_PROMPT, COST_AUTOPILOT
from components.credit_badge import build_credit_badge
from components.file_import_card import build_file_import_card
from components.stat_card import build_stat_card
from components.data_preview import build_data_preview
from components.suggestion_chips import build_suggestion_chips
from services import ai_service, file_service, sandbox
from services.file_service import FileValidationError
from services.file_picker_service import FilePickerService

logger = logging.getLogger(__name__)


def build_analysis_view(
    page: ft.Page,
    credit_service,
) -> ft.View:
    """Build the Analysis tab view."""

    # ── Refs ─────────────────────────────────────────────────────────
    content_column = ft.Ref[ft.Column]()
    custom_prompt_field = ft.Ref[ft.TextField]()
    autopilot_enabled = ft.Ref[ft.Switch]()

    # ── Block storage ────────────────────────────────────────────────
    # Block 0: {"type": "initial", "description": str, "suggestions": list}
    # Block N: {"type": "analysis", "prompt": str, "code": str,
    #           "figure": obj, "stdout": str, "result": str,
    #           "description": str, "suggestions": list, "pinned": bool}
    blocks: list[dict] = []

    # ── File Picker ──────────────────────────────────────────────────
    def _on_file_result(file):
        page.run_task(_process_file, file)

    file_picker_svc = FilePickerService(page, on_result=_on_file_result)

    # ── Handlers ─────────────────────────────────────────────────────

    def on_pick_file(e):
        file_picker_svc.pick_data_file()

    async def _process_file(file):
        """Load file → create Block 0 (describe + suggest in parallel)."""
        if not file.path:
            _show_error("Could not access the selected file.")
            return

        state.is_loading = True
        _rebuild(page)

        try:
            df = file_service.load_dataframe(file.path)
            state.set_dataframe(df, file.name)
            state.current_df_summary = file_service.get_data_summary(df)

            state.is_analyzing = True
            _rebuild(page)

            # Spend 1 credit for initial describe+suggest
            success, _ = await credit_service.spend(COST_SUGGEST)
            if not success:
                state.suggestions = ai_service._fallback_suggestions()
                blocks.append({
                    "type": "initial",
                    "description": "Dataset loaded. Not enough credits for AI description.",
                    "suggestions": state.suggestions,
                })
                state.is_analyzing = False
                state.is_loading = False
                _rebuild(page)
                return

            # Fire describe + suggest in parallel
            desc_task = ai_service.describe_dataset(state.current_df_summary)
            suggest_task = ai_service.suggest(state.current_df_summary)
            description, suggestions = await asyncio.gather(desc_task, suggest_task)

            state.suggestions = suggestions
            blocks.clear()
            blocks.append({
                "type": "initial",
                "description": description,
                "suggestions": suggestions,
            })

            state.is_analyzing = False

        except FileValidationError as err:
            _show_error(str(err))
            state.clear_data()
        except Exception as err:
            _show_error(f"Failed to load file: {err}")
            state.clear_data()
            logger.exception("File load error")
        finally:
            state.is_loading = False
            state.credits_remaining = await credit_service.get_balance()
            _rebuild(page)

            # Auto-trigger autopilot if enabled
            if (
                state.current_df is not None
                and autopilot_enabled.current
                and autopilot_enabled.current.value
            ):
                await run_autopilot()

    async def on_suggestion_selected(prompt: str, is_autopilot: bool = False):
        """Run an analysis → create Block N (describe + suggest in parallel)."""
        if state.current_df is None or state.is_analyzing:
            return

        state.is_analyzing = True
        _rebuild(page)

        try:
            # Credit check (skip if autopilot — paid upfront)
            if not is_autopilot:
                success, _ = await credit_service.spend(COST_SUGGEST)
                if not success:
                    _show_error("Not enough credits. Credits reset daily!")
                    state.is_analyzing = False
                    _rebuild(page)
                    return

            # 1. Generate code
            code = await ai_service.generate_code(prompt, state.current_df_summary)
            if not code:
                _show_error("AI could not generate code. Try again.")
                state.is_analyzing = False
                _rebuild(page)
                return

            # 2. Execute in sandbox
            result = sandbox.execute_code(code, state.current_df)
            if not result["success"]:
                _show_error(f"Execution error: {result['error']}")
                state.is_analyzing = False
                _rebuild(page)
                return

            # Build the raw result data for AI context
            result_data = {
                "prompt": prompt,
                "code": code,
                "stdout": result.get("stdout", ""),
                "result": str(result.get("result", "")),
            }

            # 3. Fire describe + suggest in parallel
            # Context = Block 0 description + this result
            block0_desc = blocks[0]["description"] if blocks else ""

            desc_task = ai_service.describe_result(block0_desc, result_data)
            suggest_task = ai_service.suggest(
                state.current_df_summary,
                initial_description=block0_desc,
                latest_result=result_data,
            )
            description, suggestions = await asyncio.gather(desc_task, suggest_task)

            # 4. Create Block N
            block = {
                "type": "analysis",
                "prompt": prompt,
                "code": code,
                "figure": result["figure"],
                "stdout": result.get("stdout", ""),
                "result": result.get("result", ""),
                "description": description,
                "suggestions": suggestions,
                "pinned": is_autopilot,  # auto-pin in autopilot
            }
            blocks.append(block)

            # Update state suggestions to the latest
            state.suggestions = suggestions

            # Auto-pin in autopilot mode
            if is_autopilot:
                state.charts.append({
                    "prompt": prompt,
                    "figure": result["figure"],
                    "description": description,
                })

        except Exception as err:
            _show_error(f"Analysis failed: {err}")
            logger.exception("Analysis error")
        finally:
            state.is_analyzing = False
            state.credits_remaining = await credit_service.get_balance()
            if not is_autopilot:
                _rebuild(page)

    async def run_autopilot():
        """Run all suggestions automatically. 15 credits upfront."""
        if not state.suggestions:
            return

        success, _ = await credit_service.spend(COST_AUTOPILOT)
        if not success:
            _show_error(
                f"Not enough credits for Autopilot ({COST_AUTOPILOT} needed). "
                "Credits reset daily!"
            )
            return

        state.is_analyzing = True
        state.charts.clear()
        _rebuild(page)

        try:
            for i, sug in enumerate(state.suggestions):
                logger.info("Autopilot: step %d/%d", i + 1, len(state.suggestions))
                await on_suggestion_selected(sug["prompt"], is_autopilot=True)

            page.route = "/report"
            page.update()
        except Exception as e:
            _show_error(f"Autopilot failed: {e}")
        finally:
            state.is_analyzing = False
            state.credits_remaining = await credit_service.get_balance()
            _rebuild(page)

    async def on_custom_prompt(e):
        if not custom_prompt_field.current:
            return
        prompt = custom_prompt_field.current.value.strip()
        if not prompt:
            return

        success, _ = await credit_service.spend(COST_CUSTOM_PROMPT)
        if not success:
            _show_error("Not enough credits for a custom prompt (costs 3).")
            return

        custom_prompt_field.current.value = ""
        page.update()
        await on_suggestion_selected(prompt)

    def on_clear_data(e):
        import matplotlib.pyplot as plt
        plt.close("all")
        state.clear_data()
        blocks.clear()
        _rebuild(page)

    def on_pin_block(index: int):
        """Pin a block's chart + description to the report."""
        if index < 0 or index >= len(blocks):
            return
        block = blocks[index]
        if block.get("pinned"):
            page.snack_bar = ft.SnackBar(
                content=ft.Text("Already in report."), duration=2000)
            page.snack_bar.open = True
            page.update()
            return

        block["pinned"] = True
        state.charts.append({
            "prompt": block.get("prompt", "Data Overview"),
            "figure": block.get("figure"),
            "description": block.get("description", ""),
        })
        page.snack_bar = ft.SnackBar(
            content=ft.Text("📌 Pinned to report!"), duration=2000)
        page.snack_bar.open = True
        _rebuild(page)

    # ── Error helper ─────────────────────────────────────────────────

    def _show_error(msg: str):
        page.snack_bar = ft.SnackBar(
            content=ft.Text(msg, color=ft.Colors.WHITE),
            bgcolor=theme.ERROR, duration=4000)
        page.snack_bar.open = True
        page.update()

    # ── UI Builders ──────────────────────────────────────────────────

    def _build_terminal(code: str) -> ft.Container:
        """Collapsible terminal-style code view."""
        return ft.Container(
            content=ft.Column(
                controls=[
                    # Terminal header
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Container(width=10, height=10, border_radius=5, bgcolor="#FF5F57"),
                                        ft.Container(width=10, height=10, border_radius=5, bgcolor="#FEBC2E"),
                                        ft.Container(width=10, height=10, border_radius=5, bgcolor="#28C840"),
                                    ],
                                    spacing=6,
                                ),
                                ft.Text(
                                    "analysis.py",
                                    size=10,
                                    color=ft.Colors.with_opacity(0.5, "#FFFFFF"),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        padding=ft.Padding(12, 8, 12, 8),
                        bgcolor="#1A1A2E",
                        border_radius=ft.BorderRadius(
                            top_left=tokens.RADIUS_MD,
                            top_right=tokens.RADIUS_MD,
                            bottom_left=0,
                            bottom_right=0,
                        ),
                    ),
                    # Code body
                    ft.Container(
                        content=ft.Text(
                            code,
                            font_family="RobotoMono",
                            size=11,
                            color="#E0E0E0",
                            selectable=True,
                        ),
                        padding=ft.Padding(12, 10, 12, 12),
                        bgcolor="#0D0D1A",
                        border_radius=ft.BorderRadius(
                            top_left=0,
                            top_right=0,
                            bottom_left=tokens.RADIUS_MD,
                            bottom_right=tokens.RADIUS_MD,
                        ),
                        max_height=180,
                    ),
                ],
                spacing=0,
            ),
            border_radius=tokens.RADIUS_MD,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.15, "#FFFFFF")),
        )

    def _build_block_card(block: dict, index: int) -> ft.Container:
        """Build a single block card with expandable Advanced section."""
        is_initial = block["type"] == "initial"
        controls: list[ft.Control] = []

        # ── Header ──────────────────────────────────────────
        if is_initial:
            controls.append(
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.DATASET_ROUNDED, size=16, color=theme.ACCENT),
                        ft.Text("Data Overview", size=tokens.FONT_SM, weight=ft.FontWeight.W_600),
                    ],
                    spacing=6,
                )
            )
        else:
            controls.append(
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=14, color=theme.ACCENT),
                        ft.Text(
                            block.get("prompt", ""),
                            size=tokens.FONT_SM,
                            weight=ft.FontWeight.W_600,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            expand=True,
                        ),
                    ],
                    spacing=6,
                )
            )

        # ── Chart (Block N only) ────────────────────────────
        if not is_initial and block.get("figure"):
            try:
                import flet_charts as fch
                controls.append(
                    ft.Container(
                        content=fch.MatplotlibChart(
                            figure=block["figure"], expand=True),
                        height=260,
                        border_radius=tokens.RADIUS_MD,
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    )
                )
            except Exception:
                pass

        # ── AI Description ──────────────────────────────────
        desc = block.get("description", "")
        if desc:
            controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.LIGHTBULB_OUTLINE_ROUNDED, size=14, color=theme.ACCENT),
                            ft.Text(
                                desc,
                                size=tokens.FONT_SM,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                expand=True,
                            ),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    padding=ft.Padding(10, 8, 10, 8),
                    border_radius=tokens.RADIUS_SM,
                    bgcolor=ft.Colors.with_opacity(0.04, theme.ACCENT),
                )
            )

        # ── Expandable Advanced Section (code view) ─────────
        if not is_initial and block.get("code"):
            advanced_content = ft.Container(
                content=_build_terminal(block["code"]),
                visible=False,
            )

            def toggle_advanced(e, container=advanced_content):
                container.visible = not container.visible
                e.control.icon = (
                    ft.Icons.EXPAND_LESS_ROUNDED
                    if container.visible
                    else ft.Icons.CODE_ROUNDED
                )
                e.control.tooltip = (
                    "Hide code" if container.visible else "Show code"
                )
                page.update()

            controls.append(
                ft.Row(
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.CODE_ROUNDED,
                            icon_size=16,
                            tooltip="Show code",
                            on_click=toggle_advanced,
                            style=ft.ButtonStyle(
                                padding=ft.Padding(4, 4, 4, 4),
                            ),
                        ),
                        ft.Text("Advanced", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                    spacing=2,
                )
            )
            controls.append(advanced_content)

        # ── Pin to Report button ────────────────────────────
        if not is_initial:
            is_pinned = block.get("pinned", False)
            controls.append(
                ft.Row(
                    controls=[
                        ft.TextButton(
                            text="Pinned ✓" if is_pinned else "Pin to Report",
                            icon=ft.Icons.PUSH_PIN_ROUNDED if is_pinned else ft.Icons.PUSH_PIN_OUTLINED,
                            style=ft.ButtonStyle(
                                color=theme.SUCCESS if is_pinned else ft.Colors.ON_SURFACE_VARIANT,
                                padding=ft.Padding(8, 4, 8, 4),
                            ),
                            disabled=is_pinned,
                            on_click=lambda e, idx=index: on_pin_block(idx),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                )
            )

        # ── Suggestions (latest block's suggestions) ────────
        sug = block.get("suggestions", [])
        if sug:
            controls.append(
                build_suggestion_chips(
                    suggestions=sug,
                    on_select=lambda p: page.run_task(on_suggestion_selected, p),
                    is_loading=state.is_analyzing,
                )
            )

        return ft.Container(
            content=ft.Column(controls=controls, spacing=8),
            padding=ft.Padding(14, 12, 14, 12),
            margin=ft.Margin(tokens.SPACE_LG, 4, tokens.SPACE_LG, 4),
            border_radius=tokens.RADIUS_LG,
            bgcolor=theme.GLASS_BG,
            border=ft.Border.all(1, theme.GLASS_BORDER_COLOR),
        )

    # ── Build all content ────────────────────────────────────────────

    def _build_content() -> list[ft.Control]:
        controls: list[ft.Control] = []

        if state.current_df is None:
            # ── Import screen ────────────────────────────────
            controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Container(height=tokens.SPACE_XXXL),
                            ft.Image(
                                src="logo.png", width=180, height=60,
                                fit=ft.BoxFit.CONTAIN),
                            ft.Container(height=tokens.SPACE_SM),
                            ft.Text(
                                "Privacy-First Data Intelligence",
                                size=tokens.FONT_SM,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Container(height=tokens.SPACE_XXL),
                            build_file_import_card(
                                on_pick=on_pick_file,
                                is_loading=state.is_loading,
                            ),
                            ft.Container(height=tokens.SPACE_LG),
                            ft.Container(
                                content=ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.ROCKET_LAUNCH_ROUNDED,
                                                size=tokens.ICON_MD, color=theme.ACCENT),
                                        ft.Text("Autopilot Mode",
                                                size=tokens.FONT_SM,
                                                weight=ft.FontWeight.W_500),
                                        ft.Switch(
                                            ref=autopilot_enabled,
                                            value=True,
                                            active_color=theme.PRIMARY,
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    spacing=tokens.SPACE_MD,
                                ),
                                tooltip="Auto-generates a full report after upload",
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=0,
                    ),
                    padding=ft.Padding(
                        tokens.SPACE_LG, 0, tokens.SPACE_LG, tokens.SPACE_XXL),
                )
            )
        else:
            # ── File info bar ────────────────────────────────
            controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.DESCRIPTION_ROUNDED,
                                    size=tokens.ICON_MD, color=theme.ACCENT),
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        state.current_df_name,
                                        size=tokens.FONT_MD,
                                        weight=ft.FontWeight.W_600,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Text(
                                        f"{state.current_df_rows:,} rows × "
                                        f"{len(state.current_df_columns)} columns",
                                        size=tokens.FONT_XS,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                ],
                                spacing=2, expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE_ROUNDED,
                                icon_size=tokens.ICON_MD,
                                tooltip="Clear data",
                                on_click=on_clear_data,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=tokens.SPACE_MD,
                    ),
                    padding=ft.Padding(
                        tokens.SPACE_LG, tokens.SPACE_SM,
                        tokens.SPACE_SM, tokens.SPACE_SM),
                )
            )

            # ── Stat cards ───────────────────────────────────
            controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            build_stat_card(
                                label="Rows",
                                value=f"{state.current_df_rows:,}",
                                icon=ft.Icons.TABLE_ROWS_ROUNDED,
                                color=theme.ACCENT,
                            ),
                            build_stat_card(
                                label="Cols",
                                value=str(len(state.current_df_columns)),
                                icon=ft.Icons.VIEW_COLUMN_ROUNDED,
                                color=theme.PRIMARY_LIGHT,
                            ),
                            build_stat_card(
                                label="Credits",
                                value=str(state.credits_remaining),
                                icon=ft.Icons.BOLT_ROUNDED,
                                color=theme.SUCCESS,
                            ),
                        ],
                        spacing=tokens.SPACE_SM,
                    ),
                    padding=ft.Padding(
                        tokens.SPACE_LG, tokens.SPACE_SM,
                        tokens.SPACE_LG, tokens.SPACE_SM),
                )
            )

            # ── Data table (always visible as part of Block 0) ──
            controls.append(
                ft.Container(
                    content=build_data_preview(state.current_df),
                    padding=ft.Padding(
                        tokens.SPACE_LG, tokens.SPACE_SM,
                        tokens.SPACE_LG, tokens.SPACE_SM),
                )
            )

            # ── Loading indicator ────────────────────────────
            if state.is_analyzing:
                controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.ProgressRing(width=18, height=18, stroke_width=2),
                                ft.Text("AI is analyzing...",
                                        size=tokens.FONT_SM,
                                        color=ft.Colors.ON_SURFACE_VARIANT),
                            ],
                            spacing=tokens.SPACE_MD,
                        ),
                        padding=ft.Padding(
                            tokens.SPACE_LG, tokens.SPACE_LG,
                            tokens.SPACE_LG, tokens.SPACE_SM),
                    )
                )

            # ── Render all blocks ────────────────────────────
            for idx, block in enumerate(blocks):
                controls.append(_build_block_card(block, idx))

            # ── Custom prompt input (always at bottom) ───────
            if not state.is_analyzing:
                controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.TextField(
                                    ref=custom_prompt_field,
                                    hint_text="Ask about your data...",
                                    hint_style=ft.TextStyle(size=tokens.FONT_SM),
                                    text_size=tokens.FONT_SM,
                                    border_radius=tokens.RADIUS_LG,
                                    expand=True,
                                    max_lines=2,
                                    on_submit=lambda e: page.run_task(
                                        on_custom_prompt, e),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.SEND_ROUNDED,
                                    icon_color=theme.PRIMARY,
                                    tooltip="Send (3 credits)",
                                    on_click=lambda e: page.run_task(
                                        on_custom_prompt, e),
                                ),
                            ],
                            spacing=tokens.SPACE_SM,
                            vertical_alignment=ft.CrossAxisAlignment.END,
                        ),
                        padding=ft.Padding(
                            tokens.SPACE_LG, tokens.SPACE_SM,
                            tokens.SPACE_SM, tokens.SPACE_SM),
                    )
                )

            controls.append(ft.Container(height=tokens.SPACE_XXXL))

        return controls

    def _rebuild(p: ft.Page):
        if content_column.current:
            content_column.current.controls = _build_content()
            p.update()

    # ── Auto-trigger file picker from Home ───────────────────────────
    if state.trigger_file_picker:
        state.trigger_file_picker = False

        async def _auto_pick():
            file_picker_svc.pick_data_file()

        page.run_task(_auto_pick)

    # ── AppBar ───────────────────────────────────────────────────────
    appbar = ft.AppBar(
        title=ft.Text("Analysis", weight=ft.FontWeight.W_600, size=tokens.FONT_XL),
        center_title=False,
        bgcolor=ft.Colors.TRANSPARENT,
        actions=[
            ft.Container(
                content=build_credit_badge(state.credits_remaining),
                margin=ft.Margin(0, 0, tokens.SPACE_LG, 0),
            ),
        ],
    )

    return ft.View(
        route="/analysis",
        appbar=appbar,
        controls=[
            ft.Column(
                ref=content_column,
                controls=_build_content(),
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
        ],
        padding=0,
    )
