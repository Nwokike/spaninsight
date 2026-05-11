"""Audio recording service.

Wraps ``flet-audio-recorder`` to record voice input and return raw bytes
for Whisper transcription via the gateway.

Based on FletBot's production audio pattern.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import flet as ft

logger = logging.getLogger(__name__)

_HAS_RECORDER = False
try:
    from flet_audio_recorder import AudioRecorder

    _HAS_RECORDER = True
except ImportError:
    pass


class AudioService:
    """Voice recording helper.

    Provides start/stop recording and returns audio bytes.
    """

    def __init__(self, page: ft.Page):
        self._page = page
        self._recorder: AudioRecorder | None = None
        self._recording = False
        self._output_path: Path | None = None

        if _HAS_RECORDER:
            self._output_path = Path(tempfile.mkdtemp()) / "recording.wav"
            self._recorder = AudioRecorder(
                on_state_change=self._on_state_change,
            )

    @property
    def available(self) -> bool:
        return _HAS_RECORDER and self._recorder is not None

    @property
    def is_recording(self) -> bool:
        return self._recording

    async def start_recording(self) -> bool:
        """Start recording audio.  Returns True if started successfully."""
        if not self._recorder or not self._output_path:
            self._page.snack_bar = ft.SnackBar(
                content=ft.Text("Audio recording not available on this platform")
            )
            self._page.snack_bar.open = True
            self._page.update()
            return False

        try:
            ok = await self._recorder.start_recording(
                output_path=str(self._output_path)
            )
            self._recording = bool(ok)
            logger.info("Audio recording started → %s (ok=%s)", self._output_path, ok)
            return self._recording
        except Exception as e:
            logger.error("Failed to start recording: %s", e)
            self._page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Recording error: {e}")
            )
            self._page.snack_bar.open = True
            self._page.update()
            return False

    async def stop_recording(self) -> tuple[bytes, str] | None:
        """Stop recording and return ``(raw_bytes, mime_type)`` or None."""
        if not self._recorder or not self._recording:
            return None

        try:
            saved_path = await self._recorder.stop_recording()
            self._recording = False
            logger.info("Audio recording stopped, saved to: %s", saved_path)

            # If saved_path is a blob URL (web), we can't read it from Python.
            # We try to use our local _output_path instead.
            file_path = self._output_path
            if saved_path and not saved_path.startswith("blob:"):
                file_path = Path(saved_path)

            logger.info("Attempting to read audio data from: %s", file_path)
            if file_path and file_path.exists():
                data = file_path.read_bytes()
                logger.info("Read %d bytes of audio data", len(data))
                file_path.unlink(missing_ok=True)
                return (data, "audio/wav")
            else:
                logger.error("Audio file not found at %s", file_path)
        except Exception as e:
            logger.error("Failed to stop recording: %s", e)
            self._recording = False

        return None

    def _on_state_change(self, e):
        logger.info("AudioRecorder state changed: %s", e)
