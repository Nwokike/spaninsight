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
from components.brand_header import build_brand_header
from services import ai_service, file_service, sandbox
from services.file_service import FileValidationError
from services.file_picker_service import FilePickerService
from services.audio_service import AudioService
from core.utils import figure_to_png_bytes

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
    # Read from global state so history doesn't disappear on tab switch!
    if not hasattr(state, "analysis_blocks"):
        state.analysis_blocks = []

    is_recording = {"value": False}
    is_transcribing = {"value": False}
    recording_time = {"value": 0}
    recording_timer = ft.Ref[ft.Text]()
    loading_file_name = {"value": ""}
    loading_file_size = {"value": 0}
    _analysis_lock = asyncio.Lock()  # Prevent concurrent analysis races

    def _build_analysis_context() -> str:
        """Build compact context: first block desc + last 2 analysis block summaries."""
        blocks = state.analysis_blocks
        if not blocks:
            return ""
        parts = []
        if blocks[0].get("description"):
            parts.append(f"Dataset: {blocks[0]['description']}")
        recent = [b for b in blocks[1:] if b.get("type") == "analysis"][-2:]
        for b in recent:
            parts.append(f"Done: {b.get('prompt', '')} → {b.get('description', '')}")
        return "\n".join(parts)

    # ── File Picker ──────────────────────────────────────────────────
    def _on_file_result(file):
        page.run_task(_process_file, file)

    file_picker_svc = FilePickerService(page, on_result=_on_file_result)
    audio_svc = AudioService(page)

    # ── Handlers ─────────────────────────────────────────────────────

    def on_pick_file(e):
        file_picker_svc.pick_data_file()

    async def _process_file(file):
        """Load file → create Block 0."""
        if not file.path:
            _show_error("Could not access the selected file.")
            return

        state.is_loading = True
        # Track file info for loading message
        import os

        try:
            fsize = os.path.getsize(file.path)
        except OSError:
            fsize = 0
        loading_file_name["value"] = file.name
        loading_file_size["value"] = fsize
        _rebuild(page)

        # Give the UI a frame to render the loading spinner before locking the thread
        await asyncio.sleep(0.1)

        try:
            # Push heavy Pandas CSV parsing to a background thread so UI doesn't freeze
            df = await asyncio.to_thread(file_service.load_dataframe, file.path)
            state.set_dataframe(df, file.name)
            state.current_file_path = file.path

            # Push heavy schema extraction to background thread
            state.current_df_summary = await asyncio.to_thread(
                file_service.get_data_summary, df
            )

            # Build describe DataFrame for Block 0 visual display
            try:
                describe_data = df.describe(include="all").round(2).fillna("")
            except Exception:
                describe_data = None

            # Create Block 0 placeholder
            block0 = {
                "type": "initial",
                "code": "",
                "describe_data": describe_data,
                "description": "Analyzing dataset schema...",
                "suggestions": [],
                "pinned": False,
            }
            state.analysis_blocks.clear()
            state.analysis_blocks.append(block0)
            state.is_loading = False
            _rebuild(page)

            # Background AI tasks
            async def load_initial_ai():
                try:
                    success, _ = await credit_service.spend(COST_SUGGEST)
                    if not success:
                        block0["description"] = (
                            "Dataset loaded. AI description unavailable (no credits)."
                        )
                        block0["suggestions"] = ai_service.fallback_suggestions()
                    else:
                        desc_task = asyncio.create_task(
                            ai_service.describe_dataset(state.current_df_summary)
                        )
                        suggest_task = asyncio.create_task(
                            ai_service.suggest(state.current_df_summary)
                        )

                        description = await desc_task
                        block0["description"] = description
                        _rebuild(page)

                        suggestions = await suggest_task
                        block0["suggestions"] = suggestions
                        state.suggestions = suggestions

                    state.credits_remaining = await credit_service.get_balance()
                    _rebuild(page)

                    if getattr(state, "autopilot_enabled", False):
                        await run_autopilot()

                except Exception as e:
                    logger.error("Initial AI load failed: %s", e)
                    block0["description"] = (
                        f"Dataset loaded ({state.current_df_rows:,} rows, "
                        f"{len(state.current_df_columns)} columns). "
                        f"AI is offline — use custom prompts to analyze."
                    )
                    block0["suggestions"] = ai_service.fallback_suggestions()
                    state.suggestions = block0["suggestions"]
                    _rebuild(page)

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
        if state.current_df is None:
            return

        if _analysis_lock.locked():
            return

        async with _analysis_lock:
            state.is_analyzing = True
            _rebuild(page)

            try:
                # 1. Generate code FIRST (before spending credits)
                ctx = _build_analysis_context()
                code = await ai_service.generate_code(
                    prompt, state.current_df_summary, analysis_context=ctx
                )
                if not code:
                    _show_error("AI failed to generate code. Try a different prompt.")
                    state.is_analyzing = False
                    _rebuild(page)
                    return

                # Reserve credits BEFORE execution
                tx_id = None
                if not is_autopilot:
                    tx_id = await credit_service.reserve(COST_SUGGEST)
                    if not tx_id:
                        _show_error("Not enough credits.")
                        state.is_analyzing = False
                        _rebuild(page)
                        return

                # 2. Execute locally with self-healing (max 2 retries)
                max_retries = 2
                retry_count = 0
                current_code = code
                result = None

                while retry_count <= max_retries:
                    result = await sandbox.execute_code_async(
                        current_code, state.current_df
                    )
                    if result["success"]:
                        break

                    # Self-heal: AI sees the error and generates corrected code
                    retry_count += 1
                    if retry_count <= max_retries:
                        logger.info(
                            "Execution failed (attempt %d/%d), AI self-healing: %s",
                            retry_count,
                            max_retries,
                            result["error"][:120],
                        )
                        corrected = await ai_service.generate_corrected_code(
                            prompt,
                            current_code,
                            result["error"],
                            state.current_df_summary,
                        )
                        if corrected:
                            current_code = corrected
                            continue
                        else:
                            break  # Avoid infinite loop if AI fails to correct

                if not result or not result["success"]:
                    if not is_autopilot and tx_id:
                        await credit_service.rollback(tx_id)
                    block = {
                        "type": "analysis",
                        "prompt": prompt,
                        "code": current_code,
                        "figure": None,
                        "stdout": result.get("stdout", "") if result else "",
                        "result": "",
                        "description": f"Execution failed after {max_retries} self-heal attempts: {result.get('error', 'Unknown Error') if result else 'Code Generation Error'}",
                        "suggestions": [],
                        "pinned": False,
                        "failed": True,
                    }
                    state.analysis_blocks.append(block)
                    state.is_analyzing = False
                    _rebuild(page)
                    return

                # 3. Create block immediately on success
                if not is_autopilot and tx_id:
                    await credit_service.commit(tx_id)

                figure_png = None
                if result.get("figure"):
                    try:
                        figure_png = figure_to_png_bytes(result["figure"])
                    except Exception:
                        pass

                block = {
                    "type": "analysis",
                    "prompt": prompt,
                    "code": current_code,
                    "figure": result["figure"],
                    "figure_png": figure_png,
                    "stdout": result.get("stdout", ""),
                    "result": result.get("result", ""),
                    "description": "Generating insight...",
                    "suggestions": [],
                    "pinned": is_autopilot,
                    "failed": False,
                }
                state.analysis_blocks.append(block)
                state.is_analyzing = False
                _rebuild(page)

                # 4. Background tasks: Interpret insight & Get next suggestions
                async def load_block_ai(b):
                    try:
                        block0_desc = (
                            state.analysis_blocks[0]["description"]
                            if state.analysis_blocks
                            else ""
                        )
                        res_data = {
                            "prompt": b["prompt"],
                            "code": b["code"],
                            "stdout": b["stdout"],
                            "result": str(b["result"]),
                        }

                        desc_task = asyncio.create_task(
                            ai_service.describe_result(block0_desc, res_data)
                        )
                        ctx = _build_analysis_context()
                        suggest_task = asyncio.create_task(
                            ai_service.suggest(
                                state.current_df_summary,
                                initial_description=block0_desc,
                                analysis_context=ctx,
                            )
                        )

                        description = await desc_task
                        b["description"] = description
                        _rebuild(page)

                        suggestions = await suggest_task
                        b["suggestions"] = suggestions
                        state.suggestions = suggestions

                        if is_autopilot:
                            state.charts.append(
                                {
                                    "prompt": b["prompt"],
                                    "figure": b["figure"],
                                    "figure_png": b.get("figure_png"),
                                    "description": description,
                                }
                            )

                        _rebuild(page)
                    except Exception as e:
                        logger.error("Block AI load failed: %s", e)

                page.run_task(load_block_ai, block)

            except Exception as err:
                _show_error(f"Analysis failed: {err}")
                logger.exception("Analysis error")
                state.is_analyzing = False
                _rebuild(page)
            finally:
                try:
                    state.credits_remaining = await credit_service.get_balance()
                except Exception:
                    pass

    async def on_rerun_code(block_index: int, new_code: str):
        """Re-run edited code for an existing block."""
        if block_index < 0 or block_index >= len(state.analysis_blocks):
            return

        block = state.analysis_blocks[block_index]
        result = await sandbox.execute_code_async(new_code, state.current_df)

        block["code"] = new_code
        if result["success"]:
            block["figure"] = result["figure"]
            try:
                block["figure_png"] = (
                    figure_to_png_bytes(result["figure"]) if result["figure"] else None
                )
            except Exception:
                pass
            block["stdout"] = result.get("stdout", "")
            block["result"] = result.get("result", "")
            block["description"] = "Code re-executed successfully."
            block["failed"] = False
            _show_success("✅ Code re-executed successfully!")
        else:
            block["description"] = f"Execution failed: {result['error']}"
            block["failed"] = True
            _show_error(f"Execution Error: {result['error']}")

        _rebuild(page)

    async def run_autopilot():
        """ReAct-style autonomous analysis agent loop."""
        MAX_ITERATIONS = 8
        COST_PER_STEP = 2

        if not state.suggestions:
            return

        success, _ = await credit_service.spend(COST_AUTOPILOT)
        if not success:
            _show_error("Not enough credits for Autopilot.")
            return

        state.is_analyzing = True
        state.charts.clear()
        state.autopilot_cancelled = False
        state.autopilot_progress = "Initializing agent loop..."
        _rebuild(page)

        analysis_history = []
        iteration = 0

        try:
            while iteration < MAX_ITERATIONS:
                if getattr(state, "autopilot_cancelled", False):
                    state.autopilot_progress = "Cancelled by user."
                    _show_error("Autopilot cancelled.")
                    break

                iteration += 1
                state.autopilot_progress = (
                    f"Step {iteration}/{MAX_ITERATIONS}: Planning..."
                )
                _rebuild(page)

                block0_desc = (
                    state.analysis_blocks[0]["description"]
                    if state.analysis_blocks
                    else ""
                )

                plan = await ai_service.plan_next_step(
                    state.current_df_summary,
                    block0_desc,
                    analysis_history,
                )

                if plan.get("is_complete"):
                    state.autopilot_progress = f"Analysis complete after {iteration - 1} steps. {plan.get('reason', '')}"
                    logger.info(
                        "Autopilot complete at step %d: %s",
                        iteration - 1,
                        plan.get("reason", ""),
                    )
                    break

                next_prompt = plan.get("prompt", "").strip()
                if not next_prompt:
                    state.autopilot_progress = (
                        f"Agent decided analysis is complete. {plan.get('reason', '')}"
                    )
                    break

                state.autopilot_progress = f"Step {iteration}/{MAX_ITERATIONS}: {plan.get('label', next_prompt[:60])}"
                _rebuild(page)

                credits_ok, _ = await credit_service.check_balance(COST_PER_STEP)
                if not credits_ok:
                    state.autopilot_progress = "Credits exhausted."
                    _show_error("Not enough credits to continue autopilot.")
                    break

                tx_id = await credit_service.reserve(COST_PER_STEP)

                max_retries = 2
                retry_count = 0
                current_code = await ai_service.generate_code(
                    next_prompt, state.current_df_summary
                )
                result = None

                while retry_count <= max_retries and current_code:
                    result = await sandbox.execute_code_async(
                        current_code, state.current_df
                    )
                    if result["success"]:
                        break

                    retry_count += 1
                    if retry_count <= max_retries:
                        current_code = await ai_service.generate_corrected_code(
                            next_prompt,
                            current_code,
                            result["error"],
                            state.current_df_summary,
                        )
                        if not current_code:
                            break  # Break out if AI fails to supply corrected code

                if not result or not result["success"]:
                    if tx_id:
                        await credit_service.rollback(tx_id)
                    analysis_history.append(
                        {
                            "prompt": next_prompt,
                            "code": current_code or "",
                            "result": "",
                            "description": "",
                            "success": False,
                            "error": result.get("error", "No code generated")
                            if result
                            else "No code generated",
                        }
                    )
                    block = {
                        "type": "analysis",
                        "prompt": next_prompt,
                        "code": current_code or "",
                        "figure": None,
                        "figure_png": None,
                        "stdout": result.get("stdout", "") if result else "",
                        "result": "",
                        "description": f"Autopilot failed after {max_retries} retries: {result.get('error', '') if result else 'No code generated'}",
                        "suggestions": [],
                        "pinned": True,
                        "failed": True,
                    }
                    state.analysis_blocks.append(block)
                    _rebuild(page)
                    continue

                if tx_id:
                    await credit_service.commit(tx_id)

                figure_png = None
                if result.get("figure"):
                    try:
                        figure_png = figure_to_png_bytes(result["figure"])
                    except Exception:
                        pass

                block = {
                    "type": "analysis",
                    "prompt": next_prompt,
                    "code": current_code,
                    "figure": result["figure"],
                    "figure_png": figure_png,
                    "stdout": result.get("stdout", ""),
                    "result": result.get("result", ""),
                    "description": "Generating insight...",
                    "suggestions": [],
                    "pinned": True,
                    "failed": False,
                }
                state.analysis_blocks.append(block)
                _rebuild(page)

                state.charts.append(
                    {
                        "prompt": next_prompt,
                        "figure": result["figure"],
                        "figure_png": figure_png,
                        "description": "",
                    }
                )

                analysis_history.append(
                    {
                        "prompt": next_prompt,
                        "code": current_code,
                        "result": str(result.get("result", "")),
                        "description": "",
                        "success": True,
                        "error": None,
                    }
                )

                async def load_block_ai(b, hist_entry):
                    try:
                        res_data = {
                            "prompt": b["prompt"],
                            "code": b["code"],
                            "stdout": b["stdout"],
                            "result": str(b["result"]),
                        }
                        desc_task = asyncio.create_task(
                            ai_service.describe_result(block0_desc, res_data)
                        )
                        ctx = _build_analysis_context()
                        suggest_task = asyncio.create_task(
                            ai_service.suggest(
                                state.current_df_summary,
                                initial_description=block0_desc,
                                analysis_context=ctx,
                            )
                        )

                        description = await desc_task
                        b["description"] = description
                        hist_entry["description"] = description
                        if state.charts:
                            state.charts[-1]["description"] = description
                        _rebuild(page)

                        suggestions = await suggest_task
                        b["suggestions"] = suggestions
                        state.suggestions = suggestions
                        _rebuild(page)
                    except Exception as e:
                        logger.error("Autopilot block AI failed: %s", e)

                page.run_task(load_block_ai, block, analysis_history[-1])

            state.autopilot_progress = f"Agent loop finished ({iteration} steps)."

        except Exception as e:
            _show_error(f"Autopilot interrupted: {e}")
        finally:
            state.is_analyzing = False
            try:
                state.credits_remaining = await credit_service.get_balance()
            except Exception:
                pass
            _rebuild(page)

    async def on_custom_prompt(e):
        if not custom_prompt_field.current:
            return
        prompt = custom_prompt_field.current.value.strip()
        if not prompt:
            return

        success, _ = await credit_service.spend(COST_CUSTOM_PROMPT)
        if not success:
            _show_error("Not enough credits for custom analysis.")
            return

        custom_prompt_field.current.value = ""
        page.update()
        await on_suggestion_selected(prompt)

    async def on_voice_toggle(e):
        if is_recording["value"]:
            # Stop recording
            result = await audio_svc.stop_recording()
            is_recording["value"] = False
            is_transcribing["value"] = True
            _rebuild(page)
            if result:
                audio_bytes, mime_type = result
                transcript = await ai_service.transcribe_audio(audio_bytes, mime_type)
                if transcript and not transcript.startswith("["):
                    if custom_prompt_field.current:
                        custom_prompt_field.current.value = transcript
                        page.update()
                else:
                    _show_error("Could not transcribe audio. Try again.")
            is_transcribing["value"] = False
            _rebuild(page)
        else:
            # Start recording
            started = await audio_svc.start_recording(
                on_auto_stop=lambda res: page.run_task(_handle_auto_stop, res)
            )
            if started:
                is_recording["value"] = True
                recording_time["value"] = 0
                _rebuild(page)

        # Timer loop — runs while recording, ticks every second
        while is_recording["value"]:
            await asyncio.sleep(1)
            if is_recording["value"]:
                recording_time["value"] += 1
                if recording_timer.current:
                    recording_timer.current.value = (
                        f"00:{recording_time['value']:02d} / 01:00"
                    )
                    page.update(recording_timer.current)
        # Reset timer
        is_recording["value"] = False

    async def _handle_auto_stop(result):
        is_recording["value"] = False
        is_transcribing["value"] = True
        _rebuild(page)
        if result:
            audio_bytes, mime_type = result
            transcript = await ai_service.transcribe_audio(audio_bytes, mime_type)
            if (
                transcript
                and not transcript.startswith("[")
                and custom_prompt_field.current
            ):
                custom_prompt_field.current.value = transcript
                page.update()
        is_transcribing["value"] = False
        _rebuild(page)

    def on_clear_data(e):
        import matplotlib.pyplot as plt

        plt.close("all")
        state.clear_data()
        state.analysis_blocks.clear()
        _rebuild(page)

    def on_pin_block(index: int):
        if index < 0 or index >= len(state.analysis_blocks):
            return
        block = state.analysis_blocks[index]
        if block.get("pinned"):
            page.snack_bar = ft.SnackBar(ft.Text("Already in report."), duration=2000)
            page.snack_bar.open = True
            page.update()
            return

        import base64
        from core.utils import figure_to_png_bytes

        # Build the report block
        png_b64 = ""
        if block.get("figure_png"):
            png_b64 = base64.b64encode(block["figure_png"]).decode("utf-8")
        elif block.get("figure"):
            try:
                png_bytes = figure_to_png_bytes(block["figure"], dpi=150)
                png_b64 = base64.b64encode(png_bytes).decode("utf-8")
            except Exception:
                pass

        report_block = {
            "prompt": block.get("prompt", "Data Overview"),
            "description": block.get("description", ""),
            "figure_png_b64": png_b64,
            "block_type": "chart" if png_b64 else "text",
        }

        # Also keep backward compat with state.charts
        block["pinned"] = True
        state.charts.append(
            {
                "prompt": block.get("prompt", "Data Overview"),
                "figure": block.get("figure"),
                "figure_png": block.get("figure_png"),
                "description": block.get("description", ""),
            }
        )

        async def _pin_to_report(report_id=None):
            from services.report_service import ReportService
            from services.storage_service import StorageService

            # Find storage from page — use the module-level pattern
            storage = None
            for attr in ["_storage", "storage"]:
                if hasattr(page, attr):
                    storage = getattr(page, attr)
                    break
            if storage is None:
                # Create fresh StorageService instance
                storage = StorageService(page)

            svc = ReportService(storage)

            if report_id:
                await svc.add_block_to_report(report_id, report_block)
                page.snack_bar = ft.SnackBar(
                    ft.Text("📌 Added to report!"), duration=2000
                )
            else:
                title = f"{state.current_df_name or 'Analysis'} Report"
                await svc.create_report(
                    title, state.current_df_name or "", [report_block]
                )
                page.snack_bar = ft.SnackBar(
                    ft.Text("📌 New report created!"), duration=2000
                )

            page.snack_bar.open = True
            _rebuild(page)

        async def _show_picker():
            from services.report_service import ReportService
            from services.storage_service import StorageService

            storage = StorageService(page)
            svc = ReportService(storage)
            reports = await svc.list_reports()

            if not reports:
                # No reports exist — auto-create
                await _pin_to_report(None)
                return

            # Show picker dialog
            def _select(rid):
                page.close(dlg)
                page.run_task(_pin_to_report, rid)

            def _create_new():
                page.close(dlg)
                page.run_task(_pin_to_report, None)

            items = []
            for r in reports:
                bc = len(r.get("blocks", []))
                items.append(
                    ft.ListTile(
                        leading=ft.Icon(
                            ft.Icons.ASSESSMENT_ROUNDED, color=theme.PRIMARY
                        ),
                        title=ft.Text(r.get("title", "Untitled"), size=14),
                        subtitle=ft.Text(
                            f"{bc} block{'s' if bc != 1 else ''}", size=11
                        ),
                        on_click=lambda e, rid=r["id"]: _select(rid),
                    )
                )

            items.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.ADD_ROUNDED, color=theme.ACCENT),
                    title=ft.Text(
                        "Create New Report", size=14, weight="w600", color=theme.ACCENT
                    ),
                    on_click=lambda e: _create_new(),
                )
            )

            dlg = ft.AlertDialog(
                title=ft.Text("Pin to Report"),
                content=ft.Container(
                    content=ft.Column(items, scroll="auto", spacing=0),
                    width=350,
                    height=min(len(items) * 65, 350),
                ),
                actions=[ft.TextButton("Cancel", on_click=lambda e: page.close(dlg))],
            )
            page.open(dlg)

        page.run_task(_show_picker)

    # ── UI Construction Helpers ────────────────────────────────────────

    def _show_error(msg: str):
        page.snack_bar = ft.SnackBar(
            ft.Text(msg, color=ft.Colors.WHITE), bgcolor=theme.ERROR, duration=4000
        )
        page.snack_bar.open = True
        page.update()

    def _show_success(msg: str):
        page.snack_bar = ft.SnackBar(ft.Text(msg), duration=2000)
        page.snack_bar.open = True
        page.update()

    def _build_chart_container(block: dict) -> ft.Container | None:
        """Helper to render Matplotlib charts natively using flet_charts."""
        figure = block.get("figure")
        if not figure:
            return None
        try:
            import flet_charts as fch

            return ft.Container(
                # RESTORED: Using the official interactive flet-charts package
                content=fch.MatplotlibChart(figure=figure, expand=True),
                height=280,
            )
        except Exception as e:
            logger.error("Failed to render chart: %s", e)
            return None

    def _build_text_output_container(result_val, stdout_val) -> ft.Container | None:
        """Helper to render textual/dataframe results when no chart is present."""
        import pandas as pd

        # NATIVE PANDAS UPGRADE: Route DataFrames into beautiful native tables
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

        # Clean up fallback string output
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

    def _build_terminal(code: str, block_index: int = -1) -> ft.Container:
        """Terminal-style code viewer with editable text and Run button."""
        code_field = ft.Ref[ft.TextField]()

        def _on_run(e):
            if code_field.current and block_index >= 0:
                new_code = code_field.current.value
                page.run_task(on_rerun_code, block_index, new_code)

        return ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Row(
                                    [
                                        ft.Container(
                                            width=8,
                                            height=8,
                                            border_radius=4,
                                            bgcolor="#FF5F57",
                                        ),
                                        ft.Container(
                                            width=8,
                                            height=8,
                                            border_radius=4,
                                            bgcolor="#FEBC2E",
                                        ),
                                        ft.Container(
                                            width=8,
                                            height=8,
                                            border_radius=4,
                                            bgcolor="#28C840",
                                        ),
                                    ],
                                    spacing=4,
                                ),
                                ft.Text("analysis.py", size=10, color="#888888"),
                                ft.TextButton(
                                    "▶ Run",
                                    icon=ft.Icons.PLAY_ARROW_ROUNDED,
                                    style=ft.ButtonStyle(color="#28C840"),
                                    on_click=_on_run,
                                )
                                if block_index >= 0
                                else ft.Container(),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        padding=ft.Padding(10, 6, 10, 6),
                        bgcolor="#1A1A2E",
                        border_radius=ft.BorderRadius(
                            top_left=8, top_right=8, bottom_left=0, bottom_right=0
                        ),
                    ),
                    ft.Container(
                        content=ft.TextField(
                            ref=code_field,
                            value=code,
                            multiline=True,
                            min_lines=3,
                            max_lines=20,
                            text_size=11,
                            text_style=ft.TextStyle(
                                font_family="RobotoMono", color="#E0E0E0"
                            ),
                            border_color=ft.Colors.TRANSPARENT,
                            bgcolor=ft.Colors.TRANSPARENT,
                            cursor_color="#28C840",
                            filled=False,
                        ),
                        padding=ft.Padding(12, 6, 12, 12),
                        bgcolor="#0D0D1A",
                        border_radius=ft.BorderRadius(
                            top_left=0, top_right=0, bottom_left=8, bottom_right=8
                        ),
                    ),
                ],
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            margin=ft.Margin(0, 4, 0, 8),
        )

    def _build_block_card(block: dict, index: int) -> ft.Container:
        """Main rendering pipeline for an analysis block."""
        is_initial = block["type"] == "initial"
        is_failed = block.get("failed", False)
        controls: list[ft.Control] = []

        # 1. Header
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
                            ft.Icons.ERROR_OUTLINE_ROUNDED
                            if is_failed
                            else ft.Icons.AUTO_AWESOME_ROUNDED,
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
        # 1b. Block 0 enrichment: show df.describe() + column info
        if is_initial:
            describe_data = block.get("describe_data")
            if describe_data is not None:
                try:
                    # Build describe table
                    desc_cols = [
                        ft.DataColumn(
                            ft.Text(
                                "Stat", size=tokens.FONT_XS, weight=ft.FontWeight.W_600
                            )
                        )
                    ] + [
                        ft.DataColumn(
                            ft.Text(
                                str(c)[:15],
                                size=tokens.FONT_XS,
                                weight=ft.FontWeight.W_600,
                            )
                        )
                        for c in describe_data.columns[:20]
                    ]
                    desc_rows = []
                    for stat_name in describe_data.index:
                        cells = [
                            ft.DataCell(
                                ft.Text(
                                    str(stat_name), size=tokens.FONT_XS, weight="w500"
                                )
                            )
                        ]
                        for c in describe_data.columns[:20]:
                            val = describe_data.loc[stat_name, c]
                            display = str(val) if val != "" else "—"
                            if len(display) > 12:
                                display = display[:10] + "…"
                            cells.append(
                                ft.DataCell(ft.Text(display, size=tokens.FONT_XS))
                            )
                        desc_rows.append(ft.DataRow(cells=cells))

                    controls.append(
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Icon(
                                                ft.Icons.QUERY_STATS_ROUNDED,
                                                size=14,
                                                color=theme.PRIMARY,
                                            ),
                                            ft.Text(
                                                "Statistical Summary (df.describe)",
                                                size=12,
                                                weight="w600",
                                            ),
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
                                                    border=ft.Border.all(
                                                        1,
                                                        ft.Colors.with_opacity(
                                                            0.1, ft.Colors.ON_SURFACE
                                                        ),
                                                    ),
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

                    # Column info cards (dtype + nulls)
                    col_chips = []
                    for c in describe_data.columns[:20]:
                        dtype_str = (
                            str(state.current_df[c].dtype)
                            if state.current_df is not None
                            and c in state.current_df.columns
                            else "?"
                        )
                        null_ct = (
                            int(state.current_df[c].isnull().sum())
                            if state.current_df is not None
                            and c in state.current_df.columns
                            else 0
                        )
                        null_color = theme.ERROR if null_ct > 0 else theme.SUCCESS
                        col_chips.append(
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text(
                                            str(c)[:18],
                                            size=11,
                                            weight="w600",
                                            max_lines=1,
                                            overflow="ellipsis",
                                        ),
                                        ft.Text(
                                            dtype_str,
                                            size=10,
                                            color=ft.Colors.ON_SURFACE_VARIANT,
                                        ),
                                        ft.Text(
                                            f"{null_ct} null"
                                            if null_ct > 0
                                            else "0 null",
                                            size=10,
                                            color=null_color,
                                        ),
                                    ],
                                    spacing=2,
                                    horizontal_alignment="center",
                                ),
                                padding=ft.Padding(8, 6, 8, 6),
                                border_radius=8,
                                bgcolor=ft.Colors.with_opacity(
                                    0.05, ft.Colors.ON_SURFACE
                                ),
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
                                                ft.Icon(
                                                    ft.Icons.VIEW_COLUMN_ROUNDED,
                                                    size=14,
                                                    color=theme.ACCENT,
                                                ),
                                                ft.Text(
                                                    "Column Info",
                                                    size=12,
                                                    weight="w600",
                                                ),
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

        # 2. Results Pipeline (Chart or Text)
        if not is_initial:
            has_chart = False
            # Try to build chart first natively with flet-charts
            if block.get("figure"):
                chart_ui = _build_chart_container(block)
                if chart_ui:
                    controls.append(chart_ui)
                    has_chart = True

            # Fallback to Text Output if no chart was rendered
            if not has_chart:
                text_ui = _build_text_output_container(
                    block.get("result"), block.get("stdout")
                )
                if text_ui:
                    controls.append(text_ui)

        # 3. Description (AI Insight)
        desc = block.get("description", "")
        controls.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.LIGHTBULB_OUTLINE_ROUNDED,
                            size=16,
                            color=theme.ACCENT,
                        ),
                        ft.Text(
                            desc,
                            size=tokens.FONT_SM,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            expand=True,
                        ),
                    ],
                    vertical_alignment="start",
                ),
                padding=12,
                bgcolor=ft.Colors.with_opacity(0.05, theme.ACCENT),
                border_radius=8,
            )
        )

        # 4. Code viewer (expandable)
        code = block.get("code", "")
        if code:
            adv = ft.Ref[ft.Container]()

            def toggle(e, ref=adv):
                ref.current.visible = not ref.current.visible
                page.update()

            controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED,
                                size=20,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            ft.Text(
                                "View Code", size=12, color=ft.Colors.ON_SURFACE_VARIANT
                            ),
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
                ft.Container(
                    ref=adv, content=_build_terminal(code, index), visible=False
                )
            )

        # 5. Actions (Pin / Retry)
        if not is_initial:
            action_row = []
            if is_failed:
                action_row.append(
                    ft.TextButton(
                        "Retry with AI",
                        icon=ft.Icons.REFRESH_ROUNDED,
                        on_click=lambda e, p=block["prompt"]: page.run_task(
                            on_suggestion_selected, p
                        ),
                        style=ft.ButtonStyle(color=theme.WARNING),
                    )
                )
            is_pinned = block.get("pinned", False)
            if not is_failed:
                action_row.append(
                    ft.TextButton(
                        "Pinned" if is_pinned else "Pin to Report",
                        icon=ft.Icons.PUSH_PIN_ROUNDED
                        if is_pinned
                        else ft.Icons.PUSH_PIN_OUTLINED,
                        on_click=lambda e, idx=index: on_pin_block(idx),
                        disabled=is_pinned,
                        style=ft.ButtonStyle(
                            color=theme.SUCCESS if is_pinned else theme.PRIMARY
                        ),
                    )
                )
            controls.append(ft.Row(action_row, alignment=ft.MainAxisAlignment.END))

        # 6. Suggestions (Chips)
        sug = block.get("suggestions", [])
        if sug:
            controls.append(
                ft.Divider(
                    height=1,
                    thickness=0.5,
                    color=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE),
                )
            )
            controls.append(
                build_suggestion_chips(
                    sug,
                    lambda p: page.run_task(on_suggestion_selected, p),
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

    # ── Main Content Column Builder ──────────────────────────────────

    def on_autopilot_toggle(e):
        state.autopilot_enabled = e.control.value

    def _build_content() -> list[ft.Control]:
        res = []
        if state.current_df is None:
            # Welcome & File Import Screen
            if state.is_loading:
                # Build loading message with file info
                fname = loading_file_name["value"] or "data"
                fsize = loading_file_size["value"]
                size_mb = fsize / (1024 * 1024) if fsize else 0
                load_msg = f"Loading {fname}..."
                if size_mb > 0:
                    load_msg = f"Loading {fname} ({size_mb:.1f} MB)..."

                loading_controls = [
                    ft.Container(height=150),
                    ft.ProgressRing(width=40, height=40, stroke_width=3),
                    ft.Text(
                        load_msg,
                        size=14,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ]
                # Warn about large Excel files
                if size_mb > 5 and fname.lower().endswith(".xlsx"):
                    loading_controls.append(
                        ft.Text(
                            "Large Excel files may take up to 60 seconds",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            italic=True,
                        )
                    )
                elif size_mb > 10:
                    loading_controls.append(
                        ft.Text(
                            "Large files may take a moment to process",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            italic=True,
                        )
                    )

                res.append(
                    ft.Container(
                        content=ft.Column(
                            loading_controls,
                            horizontal_alignment="center",
                            spacing=16,
                        ),
                        expand=True,
                        alignment=ft.Alignment.CENTER,
                    )
                )
            else:
                res.append(
                    ft.Container(
                        content=ft.Column(
                            [
                                build_brand_header(
                                    show_tagline=True, spacing_below=True
                                ),
                                build_file_import_card(on_pick_file, False),
                                ft.Container(height=20),
                                ft.Row(
                                    [
                                        ft.Icon(
                                            ft.Icons.ROCKET_LAUNCH_ROUNDED,
                                            color=theme.ACCENT,
                                        ),
                                        ft.Text("Autopilot Mode", weight="w500"),
                                        ft.Switch(
                                            ref=autopilot_enabled,
                                            value=getattr(
                                                state, "autopilot_enabled", True
                                            ),
                                            active_color=theme.PRIMARY,
                                            on_change=on_autopilot_toggle,
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
            # 1. Active File Info
            res.append(
                ft.Container(
                    content=ft.Row(
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
                                ft.Icons.CLOSE_ROUNDED, on_click=on_clear_data
                            ),
                        ]
                    ),
                    padding=ft.Padding(20, 10, 20, 10),
                )
            )

            # 2. Stats Deck
            res.append(
                ft.Container(
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
                    padding=ft.Padding(20, 0, 20, 10),
                )
            )

            # 3. Table Preview Component
            res.append(
                ft.Container(
                    build_data_preview(state.current_df),
                    padding=ft.Padding(20, 0, 20, 10),
                )
            )

            # 4. Render All Analysis Blocks from Global State
            for i, b in enumerate(state.analysis_blocks):
                res.append(_build_block_card(b, i))

            # 5. Loading Indicator moved to the BOTTOM
            if state.is_analyzing:
                progress_text = (
                    getattr(state, "autopilot_progress", "") or "AI thinking..."
                )
                loading_controls = [
                    ft.ProgressRing(width=16, height=16),
                    ft.Text(
                        progress_text,
                        size=13,
                        expand=True,
                    ),
                ]
                if getattr(state, "autopilot_progress", ""):
                    loading_controls.append(
                        ft.TextButton(
                            "Stop",
                            icon=ft.Icons.STOP_ROUNDED,
                            icon_color=theme.ERROR,
                            on_click=lambda e: (
                                setattr(state, "autopilot_cancelled", True)
                                or _rebuild(page)
                            ),
                        )
                    )
                res.append(
                    ft.Container(
                        content=ft.Row(
                            loading_controls, alignment="center", spacing=10
                        ),
                        padding=ft.Padding(0, 16, 0, 16),
                    )
                )

            # 6. User Prompt Input
            if not state.is_analyzing:
                res.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.TextField(
                                    ref=custom_prompt_field,
                                    hint_text="Describe an analysis or tap mic...",
                                    expand=True,
                                    border_radius=12,
                                    on_submit=lambda e: page.run_task(
                                        on_custom_prompt, e
                                    ),
                                    disabled=is_recording["value"]
                                    or is_transcribing["value"],
                                ),
                                ft.Row(
                                    [
                                        ft.Text(
                                            ref=recording_timer,
                                            value=f"00:{recording_time['value']:02d} / 01:00",
                                            size=12,
                                            color=theme.ERROR,
                                            weight="bold",
                                            visible=is_recording["value"],
                                        ),
                                        ft.ProgressRing(
                                            width=16,
                                            height=16,
                                            stroke_width=2,
                                            visible=is_transcribing["value"],
                                        ),
                                        ft.IconButton(
                                            ft.Icons.STOP_ROUNDED
                                            if is_recording["value"]
                                            else ft.Icons.MIC_ROUNDED,
                                            icon_color=theme.ERROR
                                            if is_recording["value"]
                                            else ft.Colors.ON_SURFACE_VARIANT,
                                            tooltip="Stop"
                                            if is_recording["value"]
                                            else "Voice",
                                            on_click=lambda e: page.run_task(
                                                on_voice_toggle, e
                                            ),
                                            disabled=is_transcribing["value"],
                                        ),
                                    ],
                                    spacing=4,
                                    vertical_alignment="center",
                                ),
                                ft.IconButton(
                                    ft.Icons.SEND_ROUNDED,
                                    icon_color=theme.PRIMARY,
                                    on_click=lambda e: page.run_task(
                                        on_custom_prompt, e
                                    ),
                                    disabled=is_recording["value"]
                                    or is_transcribing["value"],
                                ),
                            ]
                        ),
                        padding=ft.Padding(20, 10, 10, 10),
                    )
                )

            # Footer buffer
            res.append(ft.Container(height=100))

        return res

    def _rebuild(p: ft.Page):
        """Rebuild view and automatically scroll to the newest block."""
        if content_column.current:
            content_column.current.controls = _build_content()

            async def do_scroll():
                try:
                    await content_column.current.scroll_to(offset=-1, duration=500)
                except Exception:
                    pass

            p.run_task(do_scroll)
            p.update()

    # Initial check if navigating via file picker trigger
    if getattr(state, "trigger_file_picker", False):
        state.trigger_file_picker = False
        file_picker_svc.pick_data_file()

    # Restore session from home "Recent Analyses"
    if getattr(state, "session_to_restore", None):
        session = state.session_to_restore
        state.session_to_restore = None
        file_path = session.get("file_path", "")
        if file_path and state.current_df is None:
            page.run_task(
                _process_file,
                type(
                    "File",
                    (),
                    {"path": file_path, "name": session.get("df_name", "Dataset")},
                )(),
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
                ref=content_column,
                controls=_build_content(),
                scroll="auto",
                expand=True,
            )
        ],
        padding=0,
    )
