"""Analysis view — the main data analysis workspace.

Flow: Import data → AI suggests → Generate code → Execute → Render chart → Interpret
Uses FilePickerService (Service-based, NOT overlay Control) for Flet 0.85.0 compatibility.
"""

from __future__ import annotations

import logging

import flet as ft

from core import theme, tokens
from core.state import state
from core.constants import COST_SUGGEST, COST_CUSTOM_PROMPT
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

    # ── Refs for dynamic content ────────────────────────────────────
    content_column = ft.Ref[ft.Column]()
    chart_container = ft.Ref[ft.Container]()
    insight_text = ft.Ref[ft.Text]()
    custom_prompt_field = ft.Ref[ft.TextField]()

    # Autopilot state (local to view)
    autopilot_enabled = ft.Ref[ft.Switch]()

    # ── File Picker Service (NOT overlay — Service pattern) ─────────
    def _on_file_result(file):
        """Callback when FilePickerService picks a data file."""
        page.run_task(_process_file, file)

    file_picker_svc = FilePickerService(page, on_result=_on_file_result)

    # ── Handlers ────────────────────────────────────────────────────

    def on_pick_file(e):
        """Open file picker dialog."""
        file_picker_svc.pick_data_file()

    async def _process_file(file):
        """Handle file selection result."""
        file_path = file.path

        if not file_path:
            _show_error("Could not access the selected file.")
            return

        state.is_loading = True
        _rebuild(page)

        try:
            df = file_service.load_dataframe(file_path)
            state.set_dataframe(df, file.name)
            state.current_df_summary = file_service.get_data_summary(df)

            # Auto-suggest after loading
            state.is_analyzing = True
            _rebuild(page)

            success, _ = await credit_service.spend(COST_SUGGEST)
            if success:
                suggestions = await ai_service.suggest(state.current_df_summary)
                state.suggestions = suggestions
            else:
                state.suggestions = ai_service._fallback_suggestions()

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
            # Update credits display
            state.credits_remaining = await credit_service.get_balance()
            _rebuild(page)

            # --- Autopilot Trigger ---
            if (
                state.current_df is not None
                and autopilot_enabled.current
                and autopilot_enabled.current.value
            ):
                await run_autopilot()

    async def on_suggestion_selected(prompt: str, is_autopilot: bool = False):
        """Handle AI suggestion chip tap — generate code, execute, interpret."""
        if state.current_df is None or state.is_analyzing:
            return

        state.is_analyzing = True
        state.current_code = ""
        state.current_insight = ""
        _rebuild(page)

        try:
            # 1. Generate code
            success, _ = await credit_service.spend(COST_SUGGEST)
            if not success:
                _show_error("Not enough credits. Credits reset daily!")
                state.is_analyzing = False
                _rebuild(page)
                return

            code = await ai_service.generate_code(prompt, state.current_df_summary)
            if not code:
                _show_error("AI could not generate analysis code. Try again.")
                state.is_analyzing = False
                _rebuild(page)
                return

            state.current_code = code

            # 2. Execute in sandbox
            result = sandbox.execute_code(code, state.current_df)

            if not result["success"]:
                _show_error(f"Execution error: {result['error']}")
                state.is_analyzing = False
                _rebuild(page)
                return

            # 3. Render chart if figure exists
            if result["figure"]:
                import flet_charts as fch

                chart_widget = fch.MatplotlibChart(
                    figure=result["figure"],
                    expand=True,
                )
                if chart_container.current:
                    chart_container.current.content = chart_widget
                    chart_container.current.visible = True

            # 4. Interpret results
            interpret_data = {
                "code": code,
                "stdout": result.get("stdout", ""),
                "result": str(result.get("result", "")),
                "prompt": prompt,
            }
            insight = await ai_service.interpret(interpret_data)
            state.current_insight = insight

            if insight_text.current:
                insight_text.current.value = insight
                insight_text.current.visible = True

            # Save to chart history
            state.charts.append({
                "prompt": prompt,
                "code": code,
                "insight": insight,
                "figure": result["figure"],
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
        """Automatically run all suggestions and go to report."""
        if not state.suggestions:
            return

        state.is_analyzing = True
        state.charts.clear()  # Reset report for new autopilot run
        _rebuild(page)

        try:
            for i, sug in enumerate(state.suggestions):
                logger.info(f"Autopilot: running step {i+1}/{len(state.suggestions)}")
                await on_suggestion_selected(sug["prompt"], is_autopilot=True)

            # Navigate to report after autopilot finishes
            page.route = "/report"
            page.update()
        except Exception as e:
            _show_error(f"Autopilot failed: {e}")
        finally:
            state.is_analyzing = False
            _rebuild(page)

    async def on_custom_prompt(e):
        """Handle custom prompt submission."""
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
        """Clear loaded data and reset view."""
        import matplotlib.pyplot as plt
        plt.close("all")
        state.clear_data()
        _rebuild(page)

    # ── Error display helper ────────────────────────────────────────

    def _show_error(message: str):
        page.snack_bar = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.WHITE),
            bgcolor=theme.ERROR,
            duration=4000,
        )
        page.snack_bar.open = True
        page.update()

    # ── Build view content ──────────────────────────────────────────

    def _build_content() -> list[ft.Control]:
        """Build the scrollable content based on current state."""
        controls: list[ft.Control] = []

        if state.current_df is None:
            # No data loaded — show import card
            controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Container(height=tokens.SPACE_XXXL),
                            ft.Image(
                                src="logo.png",
                                width=180,
                                height=60,
                                fit=ft.BoxFit.CONTAIN,
                            ),
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
                                        ft.Icon(
                                            ft.Icons.ROCKET_LAUNCH_ROUNDED,
                                            size=tokens.ICON_MD,
                                            color=theme.ACCENT,
                                        ),
                                        ft.Text(
                                            "Autopilot Mode",
                                            size=tokens.FONT_SM,
                                            weight=ft.FontWeight.W_500,
                                        ),
                                        ft.Switch(
                                            ref=autopilot_enabled,
                                            value=True,
                                            active_color=theme.PRIMARY,
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    spacing=tokens.SPACE_MD,
                                ),
                                tooltip="Automatically generates a full report after upload",
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=0,
                    ),
                    padding=ft.Padding(
                        left=tokens.SPACE_LG,
                        right=tokens.SPACE_LG,
                        top=0,
                        bottom=tokens.SPACE_XXL,
                    ),
                )
            )
        else:
            # Data loaded — show stats, preview, suggestions, chart
            # File info + clear button
            controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.DESCRIPTION_ROUNDED, size=tokens.ICON_MD, color=theme.ACCENT),
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
                                        f"{state.current_df_rows:,} rows × {len(state.current_df_columns)} columns",
                                        size=tokens.FONT_XS,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                ],
                                spacing=tokens.SPACE_XXS,
                                expand=True,
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
                        left=tokens.SPACE_LG,
                        right=tokens.SPACE_SM,
                        top=tokens.SPACE_SM,
                        bottom=tokens.SPACE_SM,
                    ),
                )
            )

            # Stat cards row
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
                                label="Columns",
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
                        left=tokens.SPACE_LG,
                        right=tokens.SPACE_LG,
                        top=tokens.SPACE_SM,
                        bottom=tokens.SPACE_SM,
                    ),
                )
            )

            # Data table preview
            controls.append(
                ft.Container(
                    content=build_data_preview(state.current_df),
                    padding=ft.Padding(
                        left=tokens.SPACE_LG,
                        right=tokens.SPACE_LG,
                        top=tokens.SPACE_SM,
                        bottom=tokens.SPACE_SM,
                    ),
                )
            )

            # AI suggestions
            if state.is_analyzing:
                controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.ProgressRing(width=20, height=20, stroke_width=2),
                                ft.Text(
                                    "AI is analyzing...",
                                    size=tokens.FONT_SM,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
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
                )
            elif state.suggestions:
                controls.append(
                    ft.Container(
                        content=build_suggestion_chips(
                            suggestions=state.suggestions,
                            on_select=lambda p: page.run_task(on_suggestion_selected, p),
                            is_loading=state.is_analyzing,
                        ),
                        padding=ft.Padding(
                            left=tokens.SPACE_LG,
                            right=tokens.SPACE_LG,
                            top=tokens.SPACE_LG,
                            bottom=tokens.SPACE_SM,
                        ),
                    )
                )

            # Custom prompt input
            if state.current_df is not None and not state.is_analyzing:
                controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.TextField(
                                    ref=custom_prompt_field,
                                    hint_text="Ask a custom question about your data...",
                                    hint_style=ft.TextStyle(size=tokens.FONT_SM),
                                    text_size=tokens.FONT_SM,
                                    border_radius=tokens.RADIUS_LG,
                                    expand=True,
                                    max_lines=2,
                                    on_submit=lambda e: page.run_task(on_custom_prompt, e),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.SEND_ROUNDED,
                                    icon_color=theme.PRIMARY,
                                    tooltip="Send (3 credits)",
                                    on_click=lambda e: page.run_task(on_custom_prompt, e),
                                ),
                            ],
                            spacing=tokens.SPACE_SM,
                            vertical_alignment=ft.CrossAxisAlignment.END,
                        ),
                        padding=ft.Padding(
                            left=tokens.SPACE_LG,
                            right=tokens.SPACE_SM,
                            top=tokens.SPACE_SM,
                            bottom=tokens.SPACE_SM,
                        ),
                    )
                )

            # Chart display area
            controls.append(
                ft.Container(
                    ref=chart_container,
                    height=300,
                    visible=False,
                    padding=ft.Padding(
                        left=tokens.SPACE_LG,
                        right=tokens.SPACE_LG,
                        top=tokens.SPACE_SM,
                        bottom=tokens.SPACE_SM,
                    ),
                    border_radius=tokens.RADIUS_LG,
                )
            )

            # AI interpretation text
            controls.append(
                ft.Container(
                    content=ft.Text(
                        ref=insight_text,
                        value="",
                        size=tokens.FONT_SM,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        visible=False,
                    ),
                    padding=ft.Padding(
                        left=tokens.SPACE_LG,
                        right=tokens.SPACE_LG,
                        top=0,
                        bottom=tokens.SPACE_XXL,
                    ),
                )
            )

        return controls

    def _rebuild(p: ft.Page):
        """Rebuild the view content."""
        if content_column.current:
            content_column.current.controls = _build_content()
            p.update()

    # ── Auto-trigger file picker if coming from Home ────────────────
    if state.trigger_file_picker:
        state.trigger_file_picker = False
        page.run_task(lambda: file_picker_svc.pick_data_file())

    # ── AppBar ──────────────────────────────────────────────────────
    appbar = ft.AppBar(
        title=ft.Text(
            "Analysis",
            weight=ft.FontWeight.W_600,
            size=tokens.FONT_XL,
        ),
        center_title=False,
        bgcolor=ft.Colors.TRANSPARENT,
        actions=[
            ft.Container(
                content=build_credit_badge(state.credits_remaining),
                margin=ft.Margin(0, 0, tokens.SPACE_LG, 0),
            ),
        ],
    )

    # ── View ────────────────────────────────────────────────────────
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
