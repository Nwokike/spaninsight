import asyncio
import logging
import base64
import flet as ft

from core.state import state
from core.constants import COST_AUTOPILOT
from core.utils import figure_to_png_bytes
from services import ai as ai_service, sandbox
from .base import show_error, build_analysis_context

logger = logging.getLogger(__name__)


async def run_autopilot(view_state):
    MAX_ITERATIONS = 8
    # COST_PER_STEP removed to prevent double-charging the user

    if not state.suggestions:
        return

    success, _ = await view_state.credit_service.spend(COST_AUTOPILOT)
    if not success:
        show_error(view_state, "Not enough credits for Autopilot.")
        return

    state.is_analyzing = True
    state.autopilot_running = True
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

            # Proceed directly with code generation and execution under the upfront Autopilot credit payment
            if getattr(state, "autopilot_cancelled", False):
                break

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
                    if result.get("modified"):
                        state.dataset_modified = True
                        if result.get("new_df") is not None:
                            state.current_df = result["new_df"]
                            state.current_df_columns = list(state.current_df.columns)
                            state.current_df_rows = len(state.current_df)
                            from services import file_service

                            state.current_df_summary = file_service.get_data_summary(
                                state.current_df
                            )
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
                import uuid

                block = {
                    "id": "blk_" + str(uuid.uuid4())[:8],
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

            # Step completed successfully

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

            import uuid

            block = {
                "id": "blk_" + str(uuid.uuid4())[:8],
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
                if getattr(state, "autopilot_cancelled", False):
                    return
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

                    if getattr(state, "autopilot_cancelled", False):
                        return

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

            if getattr(state, "autopilot_cancelled", False):
                break

            await load_block_ai(wrapped_block, analysis_history[-1])

        # Compile successfully completed autopilot blocks and save them to a new report
        if view_state.report_service and state.analysis_blocks:
            from .pins import serialize_result_for_report

            report_blocks = []
            for b in state.analysis_blocks:
                if (
                    b.get("type") == "analysis"
                    and b.get("pinned")
                    and not b.get("failed")
                ):
                    png_b64 = ""
                    if b.get("figure_png"):
                        png_b64 = base64.b64encode(b["figure_png"]).decode("utf-8")
                    report_blocks.append(
                        {
                            "source_block_id": b.get("id"),
                            "prompt": b.get("prompt", "Data Overview"),
                            "description": b.get("description", ""),
                            "figure_png_b64": png_b64,
                            "block_type": "chart" if png_b64 else "text",
                            "serialized_result": serialize_result_for_report(
                                b.get("result")
                            ),
                            "stdout": b.get("stdout", ""),
                        }
                    )
            if report_blocks:
                title = f"Autopilot: {state.current_df_name or 'Analysis'} Report"
                await view_state.report_service.create_report(
                    title, state.current_df_name or "", report_blocks
                )
                logger.info("Autopilot compiled and saved report: %s", title)

        state.autopilot_progress = f"Agent loop finished ({iteration} steps)."

        # ── Interstitial Ad (Mobile Only) ────────────────────────────────
        if view_state.page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS):
            try:
                import flet_ads as fta

                async def _show_ad(e):
                    await e.control.show()

                iad = fta.InterstitialAd(
                    unit_id="ca-app-pub-5679949845754640/6965536622",
                    on_load=_show_ad,
                )
                view_state.page.overlay.append(iad)
                view_state.page.update()
            except Exception as ad_err:
                logger.error("Autopilot InterstitialAd trigger failed: %s", ad_err)

    except Exception as e:
        show_error(view_state, f"Autopilot interrupted: {e}")
    finally:
        state.is_analyzing = False
        state.autopilot_running = False
        try:
            state.credits_remaining = await view_state.credit_service.get_balance()
        except Exception:
            pass
        view_state.rebuild()
