"""Analysis view — block-chain data analysis workspace.

Architecture:
  Block 0 (Initial): Data table + AI description + first suggestions
  Block N (Result):   Chart + AI description + expandable code + new suggestions

Live Updates:
  Blocks are appended immediately after code execution.
  Descriptions and suggestions load in the background (parallel).
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
    # Block 0: {"type": "initial", "description": str, "suggestions": list, "pinned": bool}
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
        """Load file → create Block 0."""
        if not file.path:
            _show_error("Could not access the selected file.")
            return

        state.is_loading = True
        _rebuild(page)

        try:
            df = file_service.load_dataframe(file.path)
            state.set_dataframe(df, file.name)
            state.current_df_summary = file_service.get_data_summary(df)

            # Create Block 0 placeholder
            block0 = {
                "type": "initial",
                "description": "Analyzing dataset schema...",
                "suggestions": [],
                "pinned": False,
            }
            blocks.clear()
            blocks.append(block0)
            _rebuild(page)

            # Background AI tasks
            async def load_initial_ai():
                success, _ = await credit_service.spend(COST_SUGGEST)
                if not success:
                    block0["description"] = "Dataset loaded. AI description unavailable (no credits)."
                    block0["suggestions"] = ai_service._fallback_suggestions()
                else:
                    # Parallel describe + suggest
                    desc_task = ai_service.describe_dataset(state.current_df_summary)
                    suggest_task = ai_service.suggest(state.current_df_summary)
                    description, suggestions = await asyncio.gather(desc_task, suggest_task)
                    block0["description"] = description
                    block0["suggestions"] = suggestions
                    state.suggestions = suggestions
                
                state.credits_remaining = await credit_service.get_balance()
                _rebuild(page)
                
                # Trigger autopilot if enabled
                if autopilot_enabled.current and autopilot_enabled.current.value:
                    await run_autopilot()

            page.run_task(load_initial_ai)

        except FileValidationError as err:
            _show_error(str(err))
            state.clear_data()
        except Exception as err:
            _show_error(f"Failed to load file: {err}")
            state.clear_data()
            logger.exception("File load error")
        finally:
            state.is_loading = False
            _rebuild(page)

    async def on_suggestion_selected(prompt: str, is_autopilot: bool = False):
        """Run analysis → append block → background describe/suggest."""
        if state.current_df is None or state.is_analyzing:
            return

        state.is_analyzing = True
        _rebuild(page)

        try:
            if not is_autopilot:
                success, _ = await credit_service.spend(COST_SUGGEST)
                if not success:
                    _show_error("Not enough credits.")
                    state.is_analyzing = False
                    _rebuild(page)
                    return

            # 1. Generate code (essential step)
            code = await ai_service.generate_code(prompt, state.current_df_summary)
            if not code:
                _show_error("AI failed to generate code. Please try a different prompt.")
                state.is_analyzing = False
                _rebuild(page)
                return

            # 2. Execute
            result = sandbox.execute_code(code, state.current_df)
            if not result["success"]:
                _show_error(f"Execution Error: {result['error']}")
                state.is_analyzing = False
                _rebuild(page)
                return

            # 3. Create block immediately
            block = {
                "type": "analysis",
                "prompt": prompt,
                "code": code,
                "figure": result["figure"],
                "stdout": result.get("stdout", ""),
                "result": result.get("result", ""),
                "description": "Generating insight...",
                "suggestions": [],
                "pinned": is_autopilot,
            }
            blocks.append(block)
            _rebuild(page)

            # 4. Background tasks: Describe + Suggest
            async def load_block_ai(b):
                block0_desc = blocks[0]["description"] if blocks else ""
                res_data = {
                    "prompt": b["prompt"],
                    "code": b["code"],
                    "stdout": b["stdout"],
                    "result": str(b["result"]),
                }
                
                desc_task = ai_service.describe_result(block0_desc, res_data)
                suggest_task = ai_service.suggest(
                    state.current_df_summary,
                    initial_description=block0_desc,
                    latest_result=res_data,
                )
                
                description, suggestions = await asyncio.gather(desc_task, suggest_task)
                b["description"] = description
                b["suggestions"] = suggestions
                state.suggestions = suggestions
                
                # Auto-pin for autopilot
                if is_autopilot:
                    state.charts.append({
                        "prompt": b["prompt"],
                        "figure": b["figure"],
                        "description": description,
                    })
                
                _rebuild(page)

            page.run_task(load_block_ai, block)

        except Exception as err:
            _show_error(f"Analysis failed: {err}")
            logger.exception("Analysis error")
        finally:
            state.is_analyzing = False
            state.credits_remaining = await credit_service.get_balance()
            if not is_autopilot:
                _rebuild(page)

    async def run_autopilot():
        if not state.suggestions: return
        success, _ = await credit_service.spend(COST_AUTOPILOT)
        if not success:
            _show_error(f"Not enough credits for Autopilot.")
            return

        state.is_analyzing = True
        state.charts.clear()
        _rebuild(page)

        try:
            for sug in state.suggestions:
                await on_suggestion_selected(sug["prompt"], is_autopilot=True)
            page.route = "/report"
            page.update()
        except Exception as e:
            _show_error(f"Autopilot interrupted: {e}")
        finally:
            state.is_analyzing = False
            state.credits_remaining = await credit_service.get_balance()
            _rebuild(page)

    async def on_custom_prompt(e):
        if not custom_prompt_field.current: return
        prompt = custom_prompt_field.current.value.strip()
        if not prompt: return

        success, _ = await credit_service.spend(COST_CUSTOM_PROMPT)
        if not success:
            _show_error("Not enough credits for custom analysis.")
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
        if index < 0 or index >= len(blocks): return
        block = blocks[index]
        if block.get("pinned"):
            page.snack_bar = ft.SnackBar(ft.Text("Already in report."), duration=2000)
            page.snack_bar.open = True
            page.update()
            return

        block["pinned"] = True
        state.charts.append({
            "prompt": block.get("prompt", "Data Overview"),
            "figure": block.get("figure"),
            "description": block.get("description", ""),
        })
        page.snack_bar = ft.SnackBar(ft.Text("📌 Pinned to report!"), duration=2000)
        page.snack_bar.open = True
        _rebuild(page)

    # ── UI Helpers ───────────────────────────────────────────────────

    def _show_error(msg: str):
        page.snack_bar = ft.SnackBar(ft.Text(msg, color=ft.Colors.WHITE), bgcolor=theme.ERROR)
        page.snack_bar.open = True
        page.update()

    def _build_terminal(code: str) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Container(width=8, height=8, border_radius=4, bgcolor="#FF5F57"),
                                        ft.Container(width=8, height=8, border_radius=4, bgcolor="#FEBC2E"),
                                        ft.Container(width=8, height=8, border_radius=4, bgcolor="#28C840"),
                                    ],
                                    spacing=4,
                                ),
                                ft.Text("analysis.py", size=10, color="#666666"),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        padding=ft.Padding(10, 6, 10, 6),
                        bgcolor="#1A1A2E",
                        border_radius=ft.BorderRadius(top_left=8, top_right=8, bottom_left=0, bottom_right=0),
                    ),
                    ft.Container(
                        content=ft.Text(code, font_family="RobotoMono", size=11, color="#E0E0E0", selectable=True),
                        padding=12,
                        bgcolor="#0D0D1A",
                        border_radius=ft.BorderRadius(top_left=0, top_right=0, bottom_left=8, bottom_right=8),
                        height=200,
                    ),
                ],
                spacing=0,
            ),
            margin=ft.Margin(0, 4, 0, 8),
        )

    def _build_block_card(block: dict, index: int) -> ft.Container:
        is_initial = block["type"] == "initial"
        controls: list[ft.Control] = []

        # 1. Header
        if is_initial:
            controls.append(ft.Row([ft.Icon(ft.Icons.DATASET_ROUNDED, size=16, color=theme.ACCENT), ft.Text("Dataset Overview", weight="bold")], spacing=8))
        else:
            controls.append(ft.Row([ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=14, color=theme.ACCENT), ft.Text(block["prompt"], weight="bold", expand=True)], spacing=8))

        # 2. Chart
        if not is_initial and block.get("figure"):
            try:
                import flet_charts as fch
                controls.append(ft.Container(content=fch.MatplotlibChart(block["figure"], expand=True), height=280))
            except Exception: pass

        # 3. Description
        desc = block.get("description", "")
        controls.append(
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.LIGHTBULB_OUTLINE_ROUNDED, size=16, color=theme.ACCENT),
                    ft.Text(desc, size=tokens.FONT_SM, color=ft.Colors.ON_SURFACE_VARIANT, expand=True)
                ], vertical_alignment="start"),
                padding=12, bgcolor=ft.Colors.with_opacity(0.05, theme.ACCENT), border_radius=8
            )
        )

        # 4. Advanced (Code)
        if not is_initial and block.get("code"):
            adv = ft.Ref[ft.Container]()
            def toggle(e):
                adv.current.visible = not adv.current.visible
                e.control.text = "Hide Code" if adv.current.visible else "View Code"
                page.update()

            controls.append(ft.TextButton("View Code", icon=ft.Icons.CODE_ROUNDED, on_click=toggle))
            controls.append(ft.Container(ref=adv, content=_build_terminal(block["code"]), visible=False))

        # 5. Actions (Pin)
        is_pinned = block.get("pinned", False)
        controls.append(
            ft.Row([
                ft.TextButton(
                    "Pinned" if is_pinned else "Pin to Report",
                    icon=ft.Icons.PUSH_PIN_ROUNDED if is_pinned else ft.Icons.PUSH_PIN_OUTLINED,
                    on_click=lambda e, idx=index: on_pin_block(idx),
                    disabled=is_pinned,
                    style=ft.ButtonStyle(color=theme.SUCCESS if is_pinned else theme.PRIMARY)
                )
            ], alignment=ft.MainAxisAlignment.END)
        )

        # 6. Suggestions
        sug = block.get("suggestions", [])
        if sug:
            controls.append(ft.Divider(height=1, thickness=0.5, color=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)))
            controls.append(build_suggestion_chips(sug, lambda p: page.run_task(on_suggestion_selected, p), state.is_analyzing))

        return ft.Container(
            content=ft.Column(controls, spacing=10),
            padding=16, margin=ft.Margin(tokens.SPACE_LG, 8, tokens.SPACE_LG, 8),
            border_radius=16, bgcolor=theme.GLASS_BG, border=ft.Border.all(1, theme.GLASS_BORDER_COLOR)
        )

    # ── Main UI ──────────────────────────────────────────────────────

    def _build_content() -> list[ft.Control]:
        res = []
        if state.current_df is None:
            res.append(ft.Container(
                content=ft.Column([
                    ft.Container(height=100),
                    ft.Image("logo.png", width=200, height=80, fit="contain"),
                    ft.Text("Autonomous Data Intelligence", color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Container(height=40),
                    build_file_import_card(on_pick_file, state.is_loading),
                    ft.Container(height=20),
                    ft.Row([
                        ft.Icon(ft.Icons.ROCKET_LAUNCH_ROUNDED, color=theme.ACCENT),
                        ft.Text("Autopilot Mode", weight="w500"),
                        ft.Switch(ref=autopilot_enabled, value=True, active_color=theme.PRIMARY)
                    ], alignment="center", spacing=10)
                ], horizontal_alignment="center"), padding=20
            ))
        else:
            # File Info
            res.append(ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.DESCRIPTION_ROUNDED, color=theme.ACCENT),
                    ft.Column([
                        ft.Text(state.current_df_name, weight="bold", size=16),
                        ft.Text(f"{state.current_df_rows:,} rows | {len(state.current_df_columns)} cols", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
                    ], spacing=2, expand=True),
                    ft.IconButton(ft.Icons.CLOSE_ROUNDED, on_click=on_clear_data)
                ]), padding=ft.Padding(20, 10, 20, 10)
            ))
            
            # Stats
            res.append(ft.Container(ft.Row([
                build_stat_card("Rows", f"{state.current_df_rows:,}", ft.Icons.TABLE_ROWS_ROUNDED, theme.ACCENT),
                build_stat_card("Cols", str(len(state.current_df_columns)), ft.Icons.VIEW_COLUMN_ROUNDED, theme.PRIMARY),
                build_stat_card("Credits", str(state.credits_remaining), ft.Icons.BOLT_ROUNDED, theme.SUCCESS),
            ], spacing=10), padding=ft.Padding(20, 0, 20, 10)))

            # Table Preview
            res.append(ft.Container(build_data_preview(state.current_df), padding=ft.Padding(20, 0, 20, 10)))

            # Loading
            if state.is_analyzing:
                res.append(ft.Row([ft.ProgressRing(width=16, height=16), ft.Text("AI thinking...", size=13)], alignment="center", spacing=10))

            # Blocks
            for i, b in enumerate(blocks):
                res.append(_build_block_card(b, i))

            # Prompt Input
            if not state.is_analyzing:
                res.append(ft.Container(
                    content=ft.Row([
                        ft.TextField(ref=custom_prompt_field, hint_text="Describe an analysis...", expand=True, border_radius=12, on_submit=lambda e: page.run_task(on_custom_prompt, e)),
                        ft.IconButton(ft.Icons.SEND_ROUNDED, icon_color=theme.PRIMARY, on_click=lambda e: page.run_task(on_custom_prompt, e))
                    ]), padding=ft.Padding(20, 10, 10, 10)
                ))
            
            res.append(ft.Container(height=100))

        return res

    def _rebuild(p: ft.Page):
        if content_column.current:
            content_column.current.controls = _build_content()
            # Scroll to bottom if new blocks added
            async def do_scroll():
                try:
                    await content_column.current.scroll_to(offset=-1, duration=500)
                except Exception: pass
            p.run_task(do_scroll)
            p.update()

    # Initial check
    if state.trigger_file_picker:
        state.trigger_file_picker = False
        page.run_task(lambda: file_picker_svc.pick_data_file())

    return ft.View(
        route="/analysis",
        appbar=ft.AppBar(
            title=ft.Text("Analysis Engine", weight="bold"),
            actions=[ft.Container(build_credit_badge(state.credits_remaining), margin=ft.Margin(0,0,20,0))]
        ),
        controls=[ft.Column(ref=content_column, controls=_build_content(), scroll="auto", expand=True)],
        padding=0
    )
