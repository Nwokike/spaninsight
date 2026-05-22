"""Reports view state management."""

from __future__ import annotations
import flet as ft


class ReportsState:
    def __init__(self, page: ft.Page):
        self.user_reports: list[dict] = []
        self.active_report = {"data": None}
        self.editor_blocks: list[dict] = []
        self.draft_title = {"value": ""}
        self.draft_desc = {"value": ""}
        self.is_loading = {"value": True}
        self.is_saving = {"value": False}
        self.is_sharing = {"value": False}
        self.is_arranging = {"value": False}
        self.is_ai_editing = {"value": False}
        self.is_recording = {"value": False}
        self.is_transcribing = {"value": False}
        self.ai_prompt_text = {"value": ""}
        self.recording_time = {"value": 0}
        self.editor_active = {"value": False}

        self.recording_timer_ref = ft.Ref[ft.Text]()
        self.content_column = ft.Ref[ft.Column]()
        self.rebuild_fn = None

        from services.audio_service import AudioService

        self.audio_svc = AudioService(page)

    def rebuild(self):
        if self.rebuild_fn:
            self.rebuild_fn()
