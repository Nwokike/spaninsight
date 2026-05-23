import asyncio
import logging
import os
import flet as ft

from core.state import state
from core.constants import COST_SUGGEST, COST_CUSTOM_PROMPT, COST_AUTOPILOT
from core import theme
from core.utils import figure_to_png_bytes
from services import ai as ai_service, file_service, sandbox
from services.file_service import FileValidationError
from views.analysis.state import AnalysisState

logger = logging.getLogger(__name__)


def show_error(view_state: AnalysisState, msg: str):
    view_state.page.snack_bar = ft.SnackBar(
        ft.Text(msg, color=ft.Colors.WHITE), bgcolor=theme.ERROR, duration=4000
    )
    view_state.page.snack_bar.open = True
    view_state.page.update()


def show_success(view_state: AnalysisState, msg: str):
    view_state.page.snack_bar = ft.SnackBar(ft.Text(msg), duration=2000)
    view_state.page.snack_bar.open = True
    view_state.page.update()


def build_analysis_context() -> str:
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


async def process_file(view_state: AnalysisState, file):
    if not file.path:
        show_error(view_state, "Could not access the selected file.")
        return

    state.is_loading = True
    try:
        fsize = os.path.getsize(file.path)
    except OSError:
        fsize = 0
    view_state.loading_file_name["value"] = file.name
    view_state.loading_file_size["value"] = fsize
    view_state.rebuild()

    await asyncio.sleep(0.1)

    try:
        import matplotlib.pyplot as plt

        plt.close("all")
        df = await asyncio.to_thread(file_service.load_dataframe, file.path)
        state.set_dataframe(df, file.name)
        state.current_file_path = file.path

        state.current_df_summary = await asyncio.to_thread(
            file_service.get_data_summary, df
        )

        try:
            describe_data = df.describe(include="all").round(2).fillna("")
        except Exception:
            describe_data = None

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
        view_state.rebuild()

        async def load_initial_ai():
            try:
                success, _ = await view_state.credit_service.spend(COST_SUGGEST)
                if not success:
                    state.analysis_blocks[0]["description"] = (
                        "Dataset loaded. AI description unavailable (no credits)."
                    )
                    state.analysis_blocks[0]["suggestions"] = (
                        ai_service.fallback_suggestions()
                    )
                else:
                    # Sequence strictly to ensure context isn't stale
                    description = await ai_service.describe_dataset(
                        state.current_df_summary
                    )
                    state.analysis_blocks[0]["description"] = description
                    view_state.rebuild()

                    suggestions = await ai_service.suggest(state.current_df_summary)
                    state.analysis_blocks[0]["suggestions"] = suggestions
                    state.suggestions = suggestions

                state.credits_remaining = await view_state.credit_service.get_balance()
                view_state.rebuild()

                if getattr(state, "autopilot_enabled", False):
                    await run_autopilot(view_state)

            except Exception as e:
                logger.error("Initial AI load failed: %s", e)
                state.analysis_blocks[0]["description"] = (
                    f"Dataset loaded ({state.current_df_rows:,} rows, "
                    f"{len(state.current_df_columns)} columns). "
                    f"AI is offline — use custom prompts to analyze."
                )
                state.analysis_blocks[0]["suggestions"] = (
                    ai_service.fallback_suggestions()
                )
                state.suggestions = state.analysis_blocks[0]["suggestions"]
                view_state.rebuild()

        view_state.page.run_task(load_initial_ai)

    except FileValidationError as err:
        show_error(view_state, str(err))
        state.clear_data()
    except Exception as err:
        show_error(view_state, f"Failed to load file: {err}")
        state.clear_data()
        logger.exception("File load error")
    finally:
        state.is_loading = False
        view_state.rebuild()


async def process_db_table(view_state: AnalysisState, connection_url: str, table_name: str):
    """Event handler to load a DB table and boot AI data workspace."""
    state.is_loading = True
    view_state.loading_file_name["value"] = f"{table_name} [SQL]"
    view_state.loading_file_size["value"] = 0
    view_state.rebuild()

    await asyncio.sleep(0.1)

    try:
        import matplotlib.pyplot as plt
        from services.db_service import DatabaseService

        plt.close("all")
        # Load the DB table on a background thread to prevent UI freezing
        df = await asyncio.to_thread(DatabaseService.load_table, connection_url, table_name)
        
        state.set_dataframe(df, f"{table_name} (SQL)")
        state.current_file_path = f"sql://{table_name}"

        state.current_df_summary = await asyncio.to_thread(
            file_service.get_data_summary, df
        )

        try:
            describe_data = df.describe(include="all").round(2).fillna("")
        except Exception:
            describe_data = None

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
        view_state.rebuild()

        async def load_initial_ai():
            try:
                success, _ = await view_state.credit_service.spend(COST_SUGGEST)
                if not success:
                    state.analysis_blocks[0]["description"] = (
                        "Dataset loaded. AI description unavailable (no credits)."
                    )
                    state.analysis_blocks[0]["suggestions"] = (
                        ai_service.fallback_suggestions()
                    )
                else:
                    description = await ai_service.describe_dataset(
                        state.current_df_summary
                    )
                    state.analysis_blocks[0]["description"] = description
                    view_state.rebuild()

                    suggestions = await ai_service.suggest(state.current_df_summary)
                    state.analysis_blocks[0]["suggestions"] = suggestions
                    state.suggestions = suggestions

                state.credits_remaining = await view_state.credit_service.get_balance()
                view_state.rebuild()

                if getattr(state, "autopilot_enabled", False):
                    await run_autopilot(view_state)

            except Exception as e:
                logger.error("Initial AI load failed: %s", e)
                state.analysis_blocks[0]["description"] = (
                    f"Dataset loaded ({state.current_df_rows:,} rows, "
                    f"{len(state.current_df_columns)} columns). "
                    f"AI is offline — use custom prompts to analyze."
                )
                state.analysis_blocks[0]["suggestions"] = (
                    ai_service.fallback_suggestions()
                )
                state.suggestions = state.analysis_blocks[0]["suggestions"]
                view_state.rebuild()

        view_state.page.run_task(load_initial_ai)

    except Exception as err:
        show_error(view_state, f"Failed to load table: {err}")
        state.clear_data()
        logger.exception("DB table load error")
    finally:
        state.is_loading = False
        view_state.rebuild()


async def on_suggestion_selected(
    view_state: AnalysisState, prompt: str, is_autopilot: bool = False
):
    if state.current_df is None:
        return

    if view_state.analysis_lock.locked():
        return

    async with view_state.analysis_lock:
        state.is_analyzing = True
        view_state.rebuild()

        try:
            ctx = build_analysis_context()

            code = await ai_service.generate_code(
                prompt, state.current_df_summary, analysis_context=ctx
            )
            if not code:
                show_error(
                    view_state, "AI failed to generate code. Try a different prompt."
                )
                return

            tx_id = None
            if not is_autopilot:
                tx_id = await view_state.credit_service.reserve(COST_SUGGEST)
                if not tx_id:
                    show_error(view_state, "Not enough credits.")
                    return

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
                        break

            if not result or not result["success"]:
                if not is_autopilot and tx_id:
                    await view_state.credit_service.rollback(tx_id)
                block = {
                    "type": "analysis",
                    "prompt": prompt,
                    "code": current_code,
                    "figure": None,
                    "figure_png": None,
                    "stdout": result.get("stdout", "") if result else "",
                    "result": "",
                    "description": f"Execution failed after {max_retries} self-heal attempts: {result.get('error', 'Unknown Error') if result else 'Code Generation Error'}",
                    "suggestions": [],
                    "pinned": False,
                    "failed": True,
                }
                state.analysis_blocks.append(block)
                view_state.rebuild()
                return

            if not is_autopilot and tx_id:
                await view_state.credit_service.commit(tx_id)

            figure_png = None
            raw_figure = result.get("figure")
            if raw_figure:
                try:
                    figure_png = await asyncio.to_thread(
                        figure_to_png_bytes, raw_figure
                    )
                except Exception:
                    pass
                result["figure"] = None  # Free C++ memory reference
                raw_figure = None

            block = {
                "type": "analysis",
                "prompt": prompt,
                "code": current_code,
                "figure": None,
                "figure_png": figure_png,
                "stdout": result.get("stdout", ""),
                "result": result.get("result", ""),
                "description": "Generating insight...",
                "suggestions": [],
                "pinned": is_autopilot,
                "failed": False,
            }

            # 1. Append block but keep is_analyzing = True
            state.analysis_blocks.append(block)
            wrapped_block = state.analysis_blocks[-1]
            view_state.rebuild()

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

                    # 2. Fetch Description FIRST
                    description = await ai_service.describe_result(
                        block0_desc, res_data
                    )
                    b["description"] = description
                    view_state.rebuild()

                    # 3. Build context AFTER description to avoid stale history
                    ctx = build_analysis_context()

                    # 4. Fetch Suggestions
                    suggestions = await ai_service.suggest(
                        state.current_df_summary,
                        initial_description=block0_desc,
                        analysis_context=ctx,
                    )
                    b["suggestions"] = suggestions
                    state.suggestions = suggestions

                    if is_autopilot:
                        state.charts.append(
                            {
                                "prompt": b["prompt"],
                                "figure": None,  # Never store
                                "figure_png": b.get("figure_png"),
                                "description": description,
                            }
                        )

                    view_state.rebuild()
                except Exception as e:
                    logger.error("Block AI load failed: %s", e)

            # Ensure all AI is finished while lock is held
            await load_block_ai(wrapped_block)

        except Exception as err:
            show_error(view_state, f"Analysis failed: {err}")
            logger.exception("Analysis error")
        finally:
            # 5. NOW release the UI, ensuring no inputs were dropped
            state.is_analyzing = False
            try:
                state.credits_remaining = await view_state.credit_service.get_balance()
            except Exception:
                pass
            view_state.rebuild()


async def on_rerun_code(view_state: AnalysisState, block_index: int, new_code: str):
    if block_index < 0 or block_index >= len(state.analysis_blocks):
        return

    block = state.analysis_blocks[block_index]
    result = await sandbox.execute_code_async(new_code, state.current_df)

    block["code"] = new_code
    if result["success"]:
        raw_figure = result.get("figure")
        figure_png = None
        if raw_figure:
            try:
                figure_png = await asyncio.to_thread(figure_to_png_bytes, raw_figure)
            except Exception:
                pass

        block["figure"] = None
        block["figure_png"] = figure_png
        block["stdout"] = result.get("stdout", "")
        block["result"] = result.get("result", "")
        block["description"] = "Code re-executed successfully."
        block["failed"] = False
        show_success(view_state, "✅ Code re-executed successfully!")
    else:
        block["description"] = f"Execution failed: {result['error']}"
        block["failed"] = True
        show_error(view_state, f"Execution Error: {result['error']}")

    view_state.rebuild()


async def run_autopilot(view_state: AnalysisState):
    MAX_ITERATIONS = 8
    COST_PER_STEP = 2

    if not state.suggestions:
        return

    success, _ = await view_state.credit_service.spend(COST_AUTOPILOT)
    if not success:
        show_error(view_state, "Not enough credits for Autopilot.")
        return

    state.is_analyzing = True
    state.charts.clear()
    state.autopilot_cancelled = False
    state.autopilot_progress = "Initializing agent loop..."
    view_state.rebuild()

    analysis_history = []
    iteration = 0

    try:
        while iteration < MAX_ITERATIONS:
            if getattr(state, "autopilot_cancelled", False):
                state.autopilot_progress = "Cancelled by user."
                show_error(view_state, "Autopilot cancelled.")
                break

            iteration += 1
            state.autopilot_progress = f"Step {iteration}/{MAX_ITERATIONS}: Planning..."
            view_state.rebuild()

            block0_desc = (
                state.analysis_blocks[0]["description"] if state.analysis_blocks else ""
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
            view_state.rebuild()

            credits_ok, _ = await view_state.credit_service.check_balance(COST_PER_STEP)
            if not credits_ok:
                state.autopilot_progress = "Credits exhausted."
                show_error(view_state, "Not enough credits to continue autopilot.")
                break

            tx_id = await view_state.credit_service.reserve(COST_PER_STEP)

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
                        break

            if not result or not result["success"]:
                if tx_id:
                    await view_state.credit_service.rollback(tx_id)
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
                view_state.rebuild()
                continue

            if tx_id:
                await view_state.credit_service.commit(tx_id)

            figure_png = None
            raw_figure = result.get("figure")
            if raw_figure:
                try:
                    figure_png = await asyncio.to_thread(
                        figure_to_png_bytes, raw_figure
                    )
                except Exception:
                    pass
                result["figure"] = None

            block = {
                "type": "analysis",
                "prompt": next_prompt,
                "code": current_code,
                "figure": None,
                "figure_png": figure_png,
                "stdout": result.get("stdout", ""),
                "result": result.get("result", ""),
                "description": "Generating insight...",
                "suggestions": [],
                "pinned": True,
                "failed": False,
            }
            state.analysis_blocks.append(block)
            wrapped_block = state.analysis_blocks[-1]
            view_state.rebuild()

            state.charts.append(
                {
                    "prompt": next_prompt,
                    "figure": None,
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

                    description = await ai_service.describe_result(
                        block0_desc, res_data
                    )
                    b["description"] = description
                    hist_entry["description"] = description
                    if state.charts:
                        state.charts[-1]["description"] = description
                    view_state.rebuild()

                    ctx = build_analysis_context()

                    suggestions = await ai_service.suggest(
                        state.current_df_summary,
                        initial_description=block0_desc,
                        analysis_context=ctx,
                    )

                    b["suggestions"] = suggestions
                    state.suggestions = suggestions
                    view_state.rebuild()
                except Exception as e:
                    logger.error("Autopilot block AI failed: %s", e)

            await load_block_ai(wrapped_block, analysis_history[-1])

        state.autopilot_progress = f"Agent loop finished ({iteration} steps)."

    except Exception as e:
        show_error(view_state, f"Autopilot interrupted: {e}")
    finally:
        state.is_analyzing = False
        try:
            state.credits_remaining = await view_state.credit_service.get_balance()
        except Exception:
            pass
        view_state.rebuild()


async def on_custom_prompt(view_state: AnalysisState, e):
    if not view_state.custom_prompt_field.current:
        return
    prompt = view_state.custom_prompt_field.current.value.strip()
    if not prompt:
        return

    success, _ = await view_state.credit_service.spend(COST_CUSTOM_PROMPT)
    if not success:
        show_error(view_state, "Not enough credits for custom analysis.")
        return

    view_state.custom_prompt_field.current.value = ""
    view_state.page.update()
    await on_suggestion_selected(view_state, prompt)


async def _handle_auto_stop(view_state: AnalysisState, result):
    view_state.is_recording["value"] = False
    view_state.is_transcribing["value"] = True
    view_state.rebuild()
    if result:
        audio_bytes, mime_type = result
        transcript = await ai_service.transcribe_audio(audio_bytes, mime_type)
        if (
            transcript
            and not transcript.startswith("[")
            and view_state.custom_prompt_field.current
        ):
            view_state.custom_prompt_field.current.value = transcript
            view_state.page.update()
    view_state.is_transcribing["value"] = False
    view_state.rebuild()


async def on_voice_toggle(view_state: AnalysisState, e):
    if view_state.is_recording["value"]:
        result = await view_state.audio_svc.stop_recording()
        view_state.is_recording["value"] = False
        view_state.is_transcribing["value"] = True
        view_state.rebuild()
        if result:
            audio_bytes, mime_type = result
            transcript = await ai_service.transcribe_audio(audio_bytes, mime_type)
            if transcript and not transcript.startswith("["):
                if view_state.custom_prompt_field.current:
                    view_state.custom_prompt_field.current.value = transcript
                    view_state.page.update()
            else:
                show_error(view_state, "Could not transcribe audio. Try again.")
        view_state.is_transcribing["value"] = False
        view_state.rebuild()
    else:
        started = await view_state.audio_svc.start_recording(
            on_auto_stop=lambda res: view_state.page.run_task(
                _handle_auto_stop, view_state, res
            )
        )
        if started:
            view_state.is_recording["value"] = True
            view_state.recording_time["value"] = 0
            view_state.rebuild()

    while view_state.is_recording["value"]:
        await asyncio.sleep(1)
        if view_state.is_recording["value"]:
            view_state.recording_time["value"] += 1
            if view_state.recording_timer.current:
                view_state.recording_timer.current.value = (
                    f"00:{view_state.recording_time['value']:02d} / 01:00"
                )
                view_state.page.update(view_state.recording_timer.current)
    view_state.is_recording["value"] = False


def on_clear_data(view_state: AnalysisState, e):
    import matplotlib.pyplot as plt

    plt.close("all")
    state.clear_data()
    state.analysis_blocks.clear()
    view_state.rebuild()


def on_pin_block(view_state: AnalysisState, index: int):
    if index < 0 or index >= len(state.analysis_blocks):
        return
    block = state.analysis_blocks[index]
    if block.get("pinned"):
        view_state.page.snack_bar = ft.SnackBar(
            ft.Text("Already in report."), duration=2000
        )
        view_state.page.snack_bar.open = True
        view_state.page.update()
        return

    import base64

    async def _pin_to_report(report_id=None):
        png_b64 = ""
        if block.get("figure_png"):
            png_b64 = base64.b64encode(block["figure_png"]).decode("utf-8")

        report_block = {
            "prompt": block.get("prompt", "Data Overview"),
            "description": block.get("description", ""),
            "figure_png_b64": png_b64,
            "block_type": "chart" if png_b64 else "text",
        }

        block["pinned"] = True
        state.charts.append(
            {
                "prompt": block.get("prompt", "Data Overview"),
                "figure": None,
                "figure_png": block.get("figure_png"),
                "description": block.get("description", ""),
            }
        )

        if not view_state.report_service:
            view_state.page.snack_bar = ft.SnackBar(
                ft.Text("Report service unavailable"), duration=2000
            )
            view_state.page.snack_bar.open = True
            view_state.page.update()
            return

        svc = view_state.report_service

        if report_id:
            await svc.add_block_to_report(report_id, report_block)
            view_state.page.snack_bar = ft.SnackBar(
                ft.Text("📌 Added to report!"), duration=2000
            )
        else:
            title = f"{state.current_df_name or 'Analysis'} Report"
            await svc.create_report(title, state.current_df_name or "", [report_block])
            view_state.page.snack_bar = ft.SnackBar(
                ft.Text("📌 New report created!"), duration=2000
            )

        view_state.page.snack_bar.open = True
        view_state.rebuild()

    async def _show_picker():
        if not view_state.report_service:
            await _pin_to_report(None)
            return

        svc = view_state.report_service
        reports = await svc.list_reports()

        if not reports:
            await _pin_to_report(None)
            return

        # FIX: Securely defining the close handler before attaching it to the dialog
        def _close_dlg(e=None):
            dlg.open = False
            view_state.page.update()

        def _select(rid):
            _close_dlg()
            view_state.page.run_task(_pin_to_report, rid)

        def _create_new():
            _close_dlg()
            view_state.page.run_task(_pin_to_report, None)

        items = []
        for r in reports:
            bc = len(r.get("blocks", []))
            items.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.ASSESSMENT_ROUNDED, color=theme.PRIMARY),
                    title=ft.Text(r.get("title", "Untitled"), size=14),
                    subtitle=ft.Text(f"{bc} block{'s' if bc != 1 else ''}", size=11),
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
            actions=[ft.TextButton("Cancel", on_click=_close_dlg)],
        )

        # FIX: Reverted to the older Flet API mount pattern
        view_state.page.dialog = dlg
        dlg.open = True
        view_state.page.update()

    view_state.page.run_task(_show_picker)
