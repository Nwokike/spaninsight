"""Forms view — Create AI-generated surveys, manage forms, view responses.

User flow:
  1. Describe a form (text or voice) → AI generates JSON schema
  2. Schema sent to D1 → returns a shareable link
  3. Dashboard shows all forms with response counts
  4. Tap a form → view responses, download CSV, or analyze in engine
"""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from core import theme
from core.state import state
from services import ai_service, forms_service
from services.audio_service import AudioService

logger = logging.getLogger(__name__)


def build_forms_view(page: ft.Page) -> ft.View:
    """Build the Forms tab view."""

    content_column = ft.Ref[ft.Column]()
    form_prompt_field = ft.Ref[ft.TextField]()

    user_forms: list[dict] = []
    is_loading = {"value": False}
    is_creating = {"value": False}
    is_recording = {"value": False}
    recording_time = {"value": 0}
    active_form: dict = {"data": None}

    audio_svc = AudioService(page)

    async def load_forms():
        is_loading["value"] = True
        _rebuild()
        try:
            forms = await forms_service.list_forms(state.user_uuid)
            user_forms.clear()
            user_forms.extend(forms)
        except Exception as e:
            logger.error("Failed to load forms: %s", e)
            _show_error("Could not load forms. Check your connection.")
        finally:
            is_loading["value"] = False
            _rebuild()

    async def on_create_form(e):
        if not form_prompt_field.current:
            return
        prompt = form_prompt_field.current.value.strip()
        if not prompt:
            return
        is_creating["value"] = True
        _rebuild()
        try:
            schema = await ai_service.generate_form_schema(prompt)
            if not schema:
                _show_error("AI could not generate a form schema. Try again.")
                is_creating["value"] = False
                _rebuild()
                return
            title = schema.get("title", prompt[:50])
            description = schema.get("description", "")
            fields = schema.get("fields", [])
            result = await forms_service.create_form(
                user_uuid=state.user_uuid, title=title,
                description=description, schema_json=fields,
            )
            if result:
                form_prompt_field.current.value = ""
                page.snack_bar = ft.SnackBar(ft.Text(f"Form created! Share: {result['url']}"), duration=5000)
                page.snack_bar.open = True
                try:
                    await page.clipboard.set(result["url"])
                except Exception:
                    pass
                await load_forms()
            else:
                _show_error("Failed to create form. Check your connection.")
        except Exception as err:
            _show_error(f"Error: {err}")
            logger.exception("Create form error")
        finally:
            is_creating["value"] = False
            _rebuild()

    async def on_voice_toggle(e):
        if is_recording["value"]:
            result = await audio_svc.stop_recording()
            is_recording["value"] = False
            _rebuild()
            if result:
                audio_bytes, mime_type = result
                page.snack_bar = ft.SnackBar(ft.Text("Transcribing..."), duration=2000)
                page.snack_bar.open = True
                page.update()
                transcript = await ai_service.transcribe_audio(audio_bytes, mime_type)
                if transcript and not transcript.startswith("["):
                    if form_prompt_field.current:
                        form_prompt_field.current.value = transcript
                        page.update()
                else:
                    _show_error("Could not transcribe audio. Try again.")
        else:
            started = await audio_svc.start_recording(
                on_auto_stop=lambda res: page.run_task(_handle_auto_stop, res)
            )
            if started:
                is_recording["value"] = True
                recording_time["value"] = 0
                _rebuild()
                page.run_task(_update_timer)

    async def _update_timer():
        while is_recording["value"]:
            await asyncio.sleep(1)
            if is_recording["value"]:
                recording_time["value"] += 1
                _rebuild()

    async def _handle_auto_stop(result):
        is_recording["value"] = False
        _rebuild()
        if result:
            audio_bytes, mime_type = result
            transcript = await ai_service.transcribe_audio(audio_bytes, mime_type)
            if transcript and not transcript.startswith("[") and form_prompt_field.current:
                form_prompt_field.current.value = transcript
                page.update()

    async def on_view_form(form: dict):
        active_form["data"] = form
        resp_data = await forms_service.get_responses(form["id"])
        active_form["data"]["_responses"] = resp_data.get("responses", [])
        active_form["data"]["_count"] = resp_data.get("count", 0)
        _rebuild()

    def on_back_to_list(e):
        active_form["data"] = None
        _rebuild()

    async def on_copy_link(form_id: str):
        url = f"https://f.spaninsight.com/{form_id}"
        await page.clipboard.set(url)
        page.snack_bar = ft.SnackBar(ft.Text("Link copied!"), duration=2000)
        page.snack_bar.open = True
        page.update()

    async def on_renew_form(form_id: str):
        new_exp = await forms_service.renew_form(form_id)
        if new_exp:
            page.snack_bar = ft.SnackBar(ft.Text(f"Extended to {new_exp[:10]}"), duration=3000)
            page.snack_bar.open = True
            await load_forms()
        else:
            _show_error("Failed to renew.")

    async def on_delete_form(form_id: str):
        success = await forms_service.delete_form(form_id)
        if success:
            active_form["data"] = None
            page.snack_bar = ft.SnackBar(ft.Text("Form deleted."), duration=2000)
            page.snack_bar.open = True
            await load_forms()
        else:
            _show_error("Failed to delete.")

    async def on_download_csv(form: dict):
        responses = form.get("_responses", [])
        if not responses:
            _show_error("No responses to download.")
            return
        csv_bytes = forms_service.responses_to_csv_bytes(responses)
        # Flet 0.85.0: FilePicker is a Service, NOT a Control — no overlay
        picker = ft.FilePicker()
        async def _do_save():
            result = await picker.save_file(
                dialog_title="Save Responses CSV",
                file_name=f"{form['title'].replace(' ', '_')}_responses.csv",
                allowed_extensions=["csv"],
            )
            if result:
                try:
                    with open(result, "wb") as f:
                        f.write(csv_bytes)
                    page.snack_bar = ft.SnackBar(ft.Text("Saved!"), duration=3000)
                    page.snack_bar.open = True
                    page.update()
                except Exception as err:
                    _show_error(f"Save failed: {err}")
        page.run_task(_do_save)

    async def on_analyze_responses(form: dict):
        responses = form.get("_responses", [])
        if not responses:
            _show_error("No responses to analyze.")
            return
        import pandas as pd
        rows = [r["data"] for r in responses]
        df = pd.DataFrame(rows)
        from services import file_service
        state.set_dataframe(df, f"{form['title']}_responses")
        state.current_df_summary = file_service.get_data_summary(df)
        page.route = "/analysis"
        page.update()

    def _show_error(msg: str):
        page.snack_bar = ft.SnackBar(
            ft.Text(msg, color=ft.Colors.WHITE), bgcolor=theme.ERROR, duration=4000)
        page.snack_bar.open = True
        page.update()

    def _build_form_card(form: dict) -> ft.Container:
        is_expired = False
        try:
            from datetime import datetime
            exp = datetime.fromisoformat(form["expires_at"].replace("Z", "+00:00"))
            is_expired = exp < datetime.now(exp.tzinfo)
        except Exception:
            pass
        status_color = theme.ERROR if is_expired else theme.SUCCESS
        status_text = "Expired" if is_expired else "Active"
        return ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text(form["title"], weight="bold", size=14, max_lines=1, overflow="ellipsis"),
                    ft.Row([
                        ft.Container(content=ft.Text(status_text, size=9, color=status_color, weight="bold"),
                                     padding=ft.Padding(6, 2, 6, 2), border_radius=4,
                                     bgcolor=ft.Colors.with_opacity(0.1, status_color)),
                        ft.Text(f"{form.get('response_count', 0)} responses", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=8),
                ], spacing=4, expand=True),
                ft.IconButton(ft.Icons.ARROW_FORWARD_IOS_ROUNDED, icon_size=16,
                              on_click=lambda e, f=form: page.run_task(on_view_form, f)),
            ]),
            padding=14, border_radius=12, bgcolor=theme.GLASS_BG,
            border=ft.Border.all(1, theme.GLASS_BORDER_COLOR),
            margin=ft.Margin(20, 0, 20, 8),
            on_click=lambda e, f=form: page.run_task(on_view_form, f), ink=True,
        )

    def _build_form_detail(form: dict) -> list[ft.Control]:
        controls = []
        controls.append(ft.Container(content=ft.Row([
            ft.IconButton(ft.Icons.ARROW_BACK_ROUNDED, on_click=on_back_to_list),
            ft.Text(form["title"], weight="bold", size=16, expand=True),
        ]), padding=ft.Padding(10, 0, 10, 0)))
        resp_count = form.get("_count", form.get("response_count", 0))
        controls.append(ft.Container(content=ft.Column([
            ft.Row([ft.Icon(ft.Icons.PEOPLE_ROUNDED, size=16, color=theme.ACCENT),
                    ft.Text(f"{resp_count} responses", weight="w500")], spacing=8),
            ft.Row([ft.Icon(ft.Icons.TIMER_ROUNDED, size=16, color=theme.WARNING),
                    ft.Text(f"Expires: {form.get('expires_at', '')[:10]}", size=12)], spacing=8),
        ], spacing=8), padding=16, margin=ft.Margin(20, 8, 20, 8),
            border_radius=12, bgcolor=theme.GLASS_BG, border=ft.Border.all(1, theme.GLASS_BORDER_COLOR)))

        # ── Form Fields Preview ──────────────────────────────────────
        schema_json = form.get("schema_json", "")
        fields = []
        if isinstance(schema_json, str) and schema_json:
            try:
                import json
                fields = json.loads(schema_json)
            except Exception:
                pass
        elif isinstance(schema_json, list):
            fields = schema_json

        if fields:
            field_controls = []
            for idx, field in enumerate(fields):
                label = field.get("label", field.get("name", f"Field {idx+1}"))
                ftype = field.get("type", "text")
                required = field.get("required", False)
                options = field.get("options", [])

                type_icons = {
                    "text": ft.Icons.SHORT_TEXT_ROUNDED,
                    "textarea": ft.Icons.NOTES_ROUNDED,
                    "number": ft.Icons.NUMBERS_ROUNDED,
                    "email": ft.Icons.EMAIL_ROUNDED,
                    "select": ft.Icons.LIST_ROUNDED,
                    "radio": ft.Icons.RADIO_BUTTON_CHECKED_ROUNDED,
                    "checkbox": ft.Icons.CHECK_BOX_ROUNDED,
                }

                field_row_controls = [
                    ft.Icon(type_icons.get(ftype, ft.Icons.TEXT_FIELDS_ROUNDED), size=16, color=theme.ACCENT),
                    ft.Column([
                        ft.Row([
                            ft.Text(label, size=13, weight="w500", expand=True),
                            ft.Container(
                                content=ft.Text(ftype.upper(), size=9, color=theme.PRIMARY, weight="bold"),
                                padding=ft.Padding(6, 2, 6, 2), border_radius=4,
                                bgcolor=ft.Colors.with_opacity(0.08, theme.PRIMARY),
                            ),
                            ft.Text("*", size=14, color=theme.ERROR, weight="bold") if required else ft.Container(),
                        ], spacing=6),
                        ft.Text(", ".join(options[:5]), size=10, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow="ellipsis") if options else ft.Container(),
                    ], spacing=2, expand=True),
                ]
                field_controls.append(ft.Container(
                    content=ft.Row(field_row_controls, spacing=10, vertical_alignment="start"),
                    padding=ft.Padding(12, 8, 12, 8),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                ))

            controls.append(ft.Container(content=ft.Column([
                ft.Text(f"Form Fields ({len(fields)})", weight="bold", size=13),
                ft.Column(field_controls, spacing=4),
            ], spacing=8), padding=ft.Padding(20, 8, 20, 8)))

        # ── Action Buttons ───────────────────────────────────────────
        controls.append(ft.Container(content=ft.Column([
            ft.Row([
                ft.Button("Copy Link", icon=ft.Icons.LINK_ROUNDED,
                          on_click=lambda e: page.run_task(on_copy_link, form["id"])),
                ft.Button("Renew +7d", icon=ft.Icons.UPDATE_ROUNDED,
                          on_click=lambda e: page.run_task(on_renew_form, form["id"])),
            ], spacing=8, wrap=True),
            ft.Row([
                ft.Button("Download CSV", icon=ft.Icons.DOWNLOAD_ROUNDED,
                          on_click=lambda e: page.run_task(on_download_csv, form)),
                ft.Button("Analyze", icon=ft.Icons.ANALYTICS_ROUNDED,
                          on_click=lambda e: page.run_task(on_analyze_responses, form)),
            ], spacing=8, wrap=True),
            ft.TextButton("Delete Form", icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                          style=ft.ButtonStyle(color=theme.ERROR),
                          on_click=lambda e: page.run_task(on_delete_form, form["id"])),
        ], spacing=8), padding=ft.Padding(20, 8, 20, 8)))
        responses = form.get("_responses", [])
        if responses:
            import pandas as pd
            rows = [r["data"] for r in responses[:50]]
            df = pd.DataFrame(rows)
            from components.data_preview import build_data_preview
            controls.append(ft.Container(content=ft.Column([
                ft.Text(f"Latest {min(50, len(responses))} Responses", weight="bold", size=13),
                build_data_preview(df),
            ], spacing=8), padding=ft.Padding(20, 8, 20, 8)))
        controls.append(ft.Container(height=100))
        return controls

    def _build_content() -> list[ft.Control]:
        if active_form["data"]:
            return _build_form_detail(active_form["data"])
        controls = []
        controls.append(ft.Container(content=ft.Column([
            ft.Text("Create a Survey", weight="bold", size=16),
            ft.Text("Describe your questionnaire — perfect for research projects, "
                     "customer feedback, or student data collection.",
                     size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Container(height=8),
            ft.Row([
                ft.TextField(ref=form_prompt_field,
                             hint_text="e.g. 'A survey about student study habits...'",
                             expand=True, border_radius=12, max_lines=3, min_lines=1,
                             on_submit=lambda e: page.run_task(on_create_form, e),
                             disabled=is_creating["value"] or is_recording["value"]),
                ft.Row([
                    ft.Text(f"00:{recording_time['value']:02d} / 01:00", size=11, color=theme.ERROR, weight="bold", visible=is_recording["value"]),
                    ft.IconButton(ft.Icons.STOP_ROUNDED if is_recording["value"] else ft.Icons.MIC_ROUNDED,
                                  icon_color=theme.ERROR if is_recording["value"] else theme.ACCENT,
                                  tooltip="Stop recording" if is_recording["value"] else "Describe with voice",
                                  on_click=lambda e: page.run_task(on_voice_toggle, e),
                                  disabled=is_creating["value"]),
                ], spacing=2, vertical_alignment="center"),
                ft.IconButton(ft.Icons.SEND_ROUNDED, icon_color=theme.PRIMARY,
                              on_click=lambda e: page.run_task(on_create_form, e),
                              disabled=is_creating["value"] or is_recording["value"]),
            ], spacing=4, vertical_alignment="center"),
            ft.ProgressBar(visible=is_creating["value"]),
        ], spacing=4), padding=20, margin=ft.Margin(20, 10, 20, 10),
            border_radius=16, bgcolor=theme.GLASS_BG, border=ft.Border.all(1, theme.GLASS_BORDER_COLOR)))
        controls.append(ft.Container(content=ft.Row([
            ft.Text("Your Forms", weight="bold", size=16),
            ft.TextButton("Refresh", icon=ft.Icons.REFRESH_ROUNDED,
                          on_click=lambda e: page.run_task(load_forms)),
        ], alignment="spaceBetween"), padding=ft.Padding(20, 16, 20, 4)))
        if is_loading["value"]:
            controls.append(ft.Container(content=ft.Row([
                ft.ProgressRing(width=16, height=16), ft.Text("Loading forms...")
            ], spacing=10, alignment="center"), padding=20))
        elif not user_forms:
            controls.append(ft.Container(content=ft.Column([
                ft.Icon(ft.Icons.DYNAMIC_FORM_ROUNDED, size=48, color=ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE)),
                ft.Text("No forms yet", color=ft.Colors.ON_SURFACE_VARIANT, size=13),
                ft.Text("Create your first survey above!", color=ft.Colors.ON_SURFACE_VARIANT, size=11),
            ], horizontal_alignment="center", spacing=8), padding=40, alignment=ft.Alignment.CENTER))
        else:
            for form in user_forms:
                controls.append(_build_form_card(form))
        controls.append(ft.Container(height=100))
        return controls

    def _rebuild():
        if content_column.current:
            content_column.current.controls = _build_content()
            page.update()

    page.run_task(load_forms)

    return ft.View(
        route="/forms",
        appbar=ft.AppBar(title=ft.Text("Forms", weight="bold"), bgcolor=ft.Colors.TRANSPARENT),
        controls=[ft.Column(ref=content_column, controls=_build_content(), scroll="auto", expand=True)],
        padding=0,
    )
