"""Reports view — local-first multi-report management with AI editing.

Mirrors the forms_view.py 3-state architecture:
  1. Dashboard — list of reports
  2. Editor — view/edit a single report with block reorder + AI
  3. Import dialog — add blocks from current analysis session
"""

from __future__ import annotations

import base64
import logging

import flet as ft

from core import theme
from core.state import state
from core.utils import figure_to_png_bytes
from components.credit_badge import build_credit_badge
from components.report_editor import build_report_editor
from components.brand_header import build_brand_header

logger = logging.getLogger(__name__)


def build_report_view(
    page: ft.Page,
    report_service=None,
    ad_service=None,
    storage=None,
    credit_service=None,
) -> ft.View:
    """Build the Reports tab — 3-state container architecture."""

    # ── Refs ─────────────────────────────────────────────────────────
    content_column = ft.Ref[ft.Column]()

    # ── Mutable state ────────────────────────────────────────────────
    user_reports: list[dict] = []
    active_report = {"data": None}
    editor_blocks: list[dict] = []
    draft_title = {"value": ""}
    draft_desc = {"value": ""}
    is_loading = {"value": True}
    is_saving = {"value": False}
    is_sharing = {"value": False}
    is_arranging = {"value": False}
    is_ai_editing = {"value": False}
    is_recording = {"value": False}
    is_transcribing = {"value": False}
    ai_prompt_text = {"value": ""}
    recording_time = {"value": 0}
    editor_active = {"value": False}

    recording_timer_ref = ft.Ref[ft.Text]()

    # ── Rebuild ──────────────────────────────────────────────────────

    def _rebuild():
        if not content_column.current:
            return

        if editor_active["value"]:
            content_column.current.controls = _build_editor_content()
        else:
            content_column.current.controls = _build_dashboard_content()

        page.update()

    # ── Dashboard Builder ────────────────────────────────────────────

    def _build_report_card(report: dict) -> ft.Container:
        block_count = len(report.get("blocks", []))
        import datetime
        try:
            dt = datetime.datetime.fromtimestamp(report.get("created_at", 0))
            time_str = dt.strftime("%b %d, %Y")
        except Exception:
            time_str = ""

        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.ASSESSMENT_ROUNDED,
                            color=theme.PRIMARY,
                            size=24,
                        ),
                        width=44,
                        height=44,
                        border_radius=12,
                        bgcolor=ft.Colors.with_opacity(0.1, theme.PRIMARY),
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Column(
                        [
                            ft.Text(
                                report.get("title", "Untitled Report"),
                                weight=ft.FontWeight.W_600,
                                size=14,
                                max_lines=1,
                                overflow="ellipsis",
                            ),
                            ft.Text(
                                f"{block_count} block{'s' if block_count != 1 else ''} · {report.get('dataset_name', '')} · {time_str}",
                                size=11,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                max_lines=1,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Text(
                                    "Shared" if report.get("share_url") else "",
                                    size=10,
                                    color=theme.SUCCESS,
                                ),
                                visible=bool(report.get("share_url")),
                            ),
                            ft.Icon(
                                ft.Icons.CHEVRON_RIGHT_ROUNDED,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=4,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=14,
            border_radius=14,
            bgcolor=theme.GLASS_BG,
            border=ft.Border.all(1, theme.GLASS_BORDER_COLOR),
            on_click=lambda e, r=report: page.run_task(on_open_report, r),
            ink=True,
        )

    def _build_dashboard_content() -> list[ft.Control]:
        controls = []
        controls.append(build_brand_header(show_tagline=True, spacing_below=True))

        # Header
        controls.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Text("Your Reports", size=18, weight=ft.FontWeight.W_700),
                        ft.Container(expand=True),
                        ft.IconButton(
                            ft.Icons.REFRESH_ROUNDED,
                            tooltip="Refresh",
                            on_click=lambda e: page.run_task(load_reports),
                        ),
                    ],
                ),
                padding=ft.Padding(20, 10, 20, 0),
            )
        )

        if is_loading["value"]:
            controls.append(
                ft.Container(
                    content=ft.Column(
                        [ft.ProgressRing(width=30, height=30, stroke_width=3)],
                        horizontal_alignment="center",
                    ),
                    padding=40,
                    alignment=ft.Alignment.CENTER,
                )
            )
        elif not user_reports:
            controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Container(height=40),
                            ft.Icon(
                                ft.Icons.ASSESSMENT_OUTLINED,
                                size=64,
                                color=ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE),
                            ),
                            ft.Text(
                                "No reports yet",
                                size=16,
                                weight="w500",
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            ft.Text(
                                "Pin analysis results or use Autopilot to create your first report.",
                                size=13,
                                color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
                                text_align="center",
                            ),
                            ft.Container(height=16),
                            ft.FilledButton(
                                "Start Analysis",
                                icon=ft.Icons.ANALYTICS_ROUNDED,
                                on_click=lambda _: page.go("/analysis"),
                            ),
                        ],
                        horizontal_alignment="center",
                        spacing=8,
                    ),
                    padding=20,
                    alignment=ft.Alignment.CENTER,
                )
            )
        else:
            for report in user_reports:
                controls.append(
                    ft.Container(
                        content=_build_report_card(report),
                        margin=ft.Margin(20, 4, 20, 4),
                    )
                )

        controls.append(ft.Container(height=100))
        return controls

    # ── Editor Builder ───────────────────────────────────────────────

    def _build_editor_content() -> list[ft.Control]:
        if is_arranging["value"]:
            return [
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Container(height=80),
                            ft.ProgressRing(width=40, height=40, stroke_width=3),
                            ft.Text(
                                "AI is arranging your report...",
                                size=14,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            ft.Text(
                                "Optimizing order, polishing descriptions",
                                size=12,
                                color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
                            ),
                        ],
                        horizontal_alignment="center",
                        spacing=12,
                    ),
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                )
            ]

        return build_report_editor(
            blocks=editor_blocks,
            title=draft_title["value"],
            description=draft_desc["value"],
            on_blocks_changed=_rebuild,
            on_title_changed=lambda v: draft_title.update({"value": v}),
            on_desc_changed=lambda v: draft_desc.update({"value": v}),
            on_save=lambda: page.run_task(on_save),
            on_share=lambda: page.run_task(on_share),
            on_back=on_back,
            on_import=on_import,
            on_ai_edit=lambda action, text: page.run_task(on_ai_edit, action, text),
            on_voice_toggle=lambda e: page.run_task(on_voice_toggle, e),
            is_saving=is_saving["value"],
            is_sharing=is_sharing["value"],
            is_recording=is_recording["value"],
            is_transcribing=is_transcribing["value"],
            is_ai_editing=is_ai_editing["value"],
            recording_time=recording_time["value"],
            ai_prompt_text=ai_prompt_text["value"],
            recording_timer_ref=recording_timer_ref,
        )

    # ── Load Reports ─────────────────────────────────────────────────

    async def load_reports():
        is_loading["value"] = True
        _rebuild()
        try:
            if report_service:
                loaded = await report_service.list_reports()
                user_reports.clear()
                user_reports.extend(loaded)
                state.user_reports = loaded
        except Exception as e:
            logger.error("Failed to load reports: %s", e)
        is_loading["value"] = False
        _rebuild()

    # ── Open Report ──────────────────────────────────────────────────

    async def on_open_report(report: dict):
        active_report["data"] = report
        editor_blocks.clear()
        editor_blocks.extend(report.get("blocks", []))
        draft_title["value"] = report.get("title", "")
        draft_desc["value"] = report.get("description", "")
        editor_active["value"] = True

        # AI auto-arrange on first open
        if not report.get("is_arranged") and len(editor_blocks) > 1:
            is_arranging["value"] = True
            _rebuild()
            try:
                from services.ai_service import arrange_report
                result = await arrange_report(
                    editor_blocks,
                    report.get("dataset_name", ""),
                )
                if result and "blocks" in result:
                    # Reorder blocks based on AI suggestion
                    new_blocks = []
                    for ai_block in result["blocks"]:
                        orig_idx = ai_block.get("original_index", 0)
                        if 0 <= orig_idx < len(editor_blocks):
                            b = editor_blocks[orig_idx].copy()
                            b["prompt"] = ai_block.get("prompt", b.get("prompt", ""))
                            b["description"] = ai_block.get("description", b.get("description", ""))
                            new_blocks.append(b)
                    if len(new_blocks) == len(editor_blocks):
                        editor_blocks.clear()
                        editor_blocks.extend(new_blocks)
                    if result.get("title"):
                        draft_title["value"] = result["title"]
                    if result.get("description"):
                        draft_desc["value"] = result["description"]

                    # Save arranged state
                    if report_service:
                        await report_service.update_report(report["id"], {
                            "is_arranged": True,
                            "title": draft_title["value"],
                            "description": draft_desc["value"],
                            "blocks": editor_blocks,
                        })
            except Exception as e:
                logger.error("AI arrange failed: %s", e)
            is_arranging["value"] = False

        _rebuild()

    # ── Save ─────────────────────────────────────────────────────────

    async def on_save():
        is_saving["value"] = True
        _rebuild()
        try:
            if report_service and active_report["data"]:
                await report_service.update_report(
                    active_report["data"]["id"],
                    {
                        "title": draft_title["value"],
                        "description": draft_desc["value"],
                        "blocks": list(editor_blocks),
                        "is_arranged": True,
                    },
                )
                page.snack_bar = ft.SnackBar(
                    ft.Text("Report saved!", color=ft.Colors.WHITE),
                    bgcolor=theme.SUCCESS,
                    duration=2000,
                )
                page.snack_bar.open = True
        except Exception as e:
            logger.error("Save failed: %s", e)
            page.snack_bar = ft.SnackBar(
                ft.Text(f"Save failed: {e}"),
                duration=3000,
            )
            page.snack_bar.open = True
        is_saving["value"] = False
        _rebuild()

    # ── Share ────────────────────────────────────────────────────────

    async def on_share():
        if not active_report["data"] or is_sharing["value"]:
            return
        is_sharing["value"] = True
        _rebuild()
        try:
            if ad_service:
                await ad_service.show_interstitial()

            if report_service:
                # Make sure blocks are saved first
                active_report["data"]["blocks"] = list(editor_blocks)
                active_report["data"]["title"] = draft_title["value"]
                url = await report_service.share_report(
                    active_report["data"], state.user_uuid
                )
                if url:
                    await page.clipboard.set(url)
                    page.snack_bar = ft.SnackBar(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=theme.SUCCESS, size=20),
                                ft.Column(
                                    [
                                        ft.Text("Link copied!", weight=ft.FontWeight.W_600),
                                        ft.Text(
                                            "Open in browser for PDF/PPTX export. Link expires in 7 days.",
                                            size=12,
                                            color=ft.Colors.ON_SURFACE_VARIANT,
                                        ),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                            ],
                            spacing=12,
                        ),
                        duration=5000,
                    )
                    page.snack_bar.open = True
                else:
                    page.snack_bar = ft.SnackBar(ft.Text("Share failed. Try again."), duration=3000)
                    page.snack_bar.open = True
        except Exception as e:
            logger.error("Share failed: %s", e)
        is_sharing["value"] = False
        _rebuild()

    # ── Back ─────────────────────────────────────────────────────────

    def on_back():
        editor_active["value"] = False
        active_report["data"] = None
        editor_blocks.clear()
        page.run_task(load_reports)

    # ── Import from Analysis ─────────────────────────────────────────

    def on_import():
        if not state.analysis_blocks:
            page.snack_bar = ft.SnackBar(
                ft.Text("No analysis blocks available. Run an analysis first."),
                duration=3000,
            )
            page.snack_bar.open = True
            page.update()
            return

        def on_select_block(idx):
            block = state.analysis_blocks[idx]
            # Build report block from analysis block
            png_b64 = ""
            if block.get("figure_png"):
                png_b64 = base64.b64encode(block["figure_png"]).decode("utf-8")
            elif block.get("figure"):
                try:
                    png_bytes = figure_to_png_bytes(block["figure"], dpi=150)
                    png_b64 = base64.b64encode(png_bytes).decode("utf-8")
                except Exception:
                    pass

            new_block = {
                "prompt": block.get("prompt", "Analysis"),
                "description": block.get("description", ""),
                "figure_png_b64": png_b64,
                "block_type": "chart" if png_b64 else "text",
            }
            editor_blocks.append(new_block)
            page.close(dlg)
            _rebuild()
            page.snack_bar = ft.SnackBar(ft.Text("Block imported!"), duration=2000)
            page.snack_bar.open = True
            page.update()

        items = []
        for i, block in enumerate(state.analysis_blocks):
            if block.get("type") == "initial":
                continue
            items.append(
                ft.ListTile(
                    leading=ft.Icon(
                        ft.Icons.AUTO_AWESOME_ROUNDED if not block.get("failed") else ft.Icons.ERROR_OUTLINE,
                        color=theme.ACCENT if not block.get("failed") else theme.ERROR,
                    ),
                    title=ft.Text(
                        block.get("prompt", "Block")[:60],
                        max_lines=2,
                        size=13,
                    ),
                    subtitle=ft.Text(
                        (block.get("description", "")[:80] + "...") if block.get("description") else "",
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    on_click=lambda e, idx=i: on_select_block(idx),
                    disabled=block.get("failed", False),
                )
            )

        if not items:
            items.append(
                ft.Container(
                    ft.Text("No importable blocks found.", color=ft.Colors.ON_SURFACE_VARIANT),
                    padding=20,
                )
            )

        dlg = ft.AlertDialog(
            title=ft.Text("Import from Analysis"),
            content=ft.Container(
                content=ft.Column(items, scroll="auto", spacing=0),
                width=400,
                height=400,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: page.close(dlg)),
            ],
        )
        page.open(dlg)

    # ── AI Edit ──────────────────────────────────────────────────────

    async def on_ai_edit(action: str, text: str):
        if action == "__set_text__":
            ai_prompt_text["value"] = text
            return

        if action == "__submit__":
            prompt = text.strip()
            if not prompt:
                return

            is_ai_editing["value"] = True
            _rebuild()
            try:
                from services.ai_service import edit_report_with_ai
                result = await edit_report_with_ai(
                    current_blocks=editor_blocks,
                    title=draft_title["value"],
                    description=draft_desc["value"],
                    user_instruction=prompt,
                )
                if result and "blocks" in result:
                    new_blocks = []
                    for ai_block in result["blocks"]:
                        orig_idx = ai_block.get("original_index", 0)
                        if 0 <= orig_idx < len(editor_blocks):
                            b = editor_blocks[orig_idx].copy()
                            b["prompt"] = ai_block.get("prompt", b.get("prompt", ""))
                            b["description"] = ai_block.get("description", b.get("description", ""))
                            new_blocks.append(b)
                    if len(new_blocks) == len(editor_blocks):
                        editor_blocks.clear()
                        editor_blocks.extend(new_blocks)
                    if result.get("title"):
                        draft_title["value"] = result["title"]
                    if result.get("description"):
                        draft_desc["value"] = result["description"]
                    ai_prompt_text["value"] = ""
            except Exception as e:
                logger.error("AI edit failed: %s", e)
                page.snack_bar = ft.SnackBar(ft.Text(f"AI edit failed: {e}"), duration=3000)
                page.snack_bar.open = True
            is_ai_editing["value"] = False
            _rebuild()

    # ── Voice ────────────────────────────────────────────────────────

    async def on_voice_toggle(e):
        if is_recording["value"]:
            is_recording["value"] = False
            is_transcribing["value"] = True
            _rebuild()
            try:
                from services.audio_service import AudioService
                audio_svc = AudioService(page)
                audio_bytes, mime = await audio_svc.stop_and_get_bytes()
                if audio_bytes:
                    from services.ai_service import transcribe_audio
                    transcript = await transcribe_audio(audio_bytes, mime)
                    if transcript and not transcript.startswith("["):
                        ai_prompt_text["value"] = transcript
            except Exception as ex:
                logger.error("Voice transcription failed: %s", ex)
            is_transcribing["value"] = False
            _rebuild()
        else:
            try:
                from services.audio_service import AudioService
                audio_svc = AudioService(page)
                await audio_svc.start_recording()
                is_recording["value"] = True
                recording_time["value"] = 0
                _rebuild()
            except Exception as ex:
                logger.error("Voice recording failed: %s", ex)

    # ── Delete Report ────────────────────────────────────────────────

    async def on_delete_report(report_id: str):
        if report_service:
            await report_service.delete_report(report_id)
        on_back()

    # ── Initial Load ─────────────────────────────────────────────────

    page.run_task(load_reports)

    return ft.View(
        route="/reports",
        appbar=ft.AppBar(
            title=ft.Text("Reports", weight="bold"),
            bgcolor=ft.Colors.TRANSPARENT,
            actions=[
                ft.Container(
                    build_credit_badge(state.credits_remaining),
                    margin=ft.Margin(0, 0, 20, 0),
                ),
            ],
        ),
        controls=[
            ft.Column(
                ref=content_column,
                controls=_build_dashboard_content(),
                scroll="auto",
                expand=True,
            ),
        ],
        padding=0,
    )