from __future__ import annotations
import asyncio
import flet as ft
from services.file_picker_service import FilePickerService
from services.audio_service import AudioService

class AnalysisState:
    def __init__(self, page: ft.Page, credit_service):
        self.page = page
        self.credit_service = credit_service
        
        self.content_column = ft.Ref[ft.Column]()
        self.custom_prompt_field = ft.Ref[ft.TextField]()
        self.autopilot_enabled_ref = ft.Ref[ft.Switch]()
        
        self.is_recording = {"value": False}
        self.is_transcribing = {"value": False}
        self.recording_time = {"value": 0}
        self.recording_timer = ft.Ref[ft.Text]()
        
        self.loading_file_name = {"value": ""}
        self.loading_file_size = {"value": 0}
        
        self.analysis_lock = asyncio.Lock()
        
        self.file_picker_svc = None
        self.audio_svc = AudioService(page)
        
        self.rebuild_fn = None
        
    def rebuild(self):
        if self.rebuild_fn:
            self.rebuild_fn()

