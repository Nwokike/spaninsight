"""Audio recording service.

Wraps ``flet-audio-recorder`` to record voice input and return raw bytes
for Whisper transcription via the gateway.

Enforces:
- MAX_VOICE_DURATION_SEC (60s) — auto-stops recording after limit
- MAX_AUDIO_SIZE_BYTES (25MB) — gateway rejects larger files

Based on FletBot + Akili Ear production patterns.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import flet as ft

from core.constants import MAX_VOICE_DURATION_SEC, MAX_AUDIO_SIZE_BYTES

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
    Auto-stops after MAX_VOICE_DURATION_SEC (60s).
    """

    def __init__(self, page: ft.Page):
        self._page = page
        self._recorder: AudioRecorder | None = None
        self._recording = False
        self._output_path: Path | None = None
        self._auto_stop_task: asyncio.Task | None = None

        if _HAS_RECORDER:
            # PERFORMANCE FIX: Store recordings directly in the app's auto-cleaned temp folder to eliminate filesystem directory leaks
            self._output_path = (
                Path.home() / ".spaninsight" / "temp" / f"recording_{id(self)}.wav"
            )
            self._output_path.parent.mkdir(parents=True, exist_ok=True)
            self._recorder = AudioRecorder(
                on_state_change=self._on_state_change,
            )

    @property
    def available(self) -> bool:
        return _HAS_RECORDER and self._recorder is not None

    @property
    def is_recording(self) -> bool:
        return self._recording

    async def start_recording(self, on_auto_stop=None) -> bool:
        """Start recording audio. Returns True if started successfully.

        Args:
            on_auto_stop: Optional callback invoked when recording auto-stops
                          after MAX_VOICE_DURATION_SEC (60s).
        """
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

            # Schedule auto-stop after 60 seconds
            if self._recording:
                self._auto_stop_task = asyncio.create_task(
                    self._auto_stop_timer(on_auto_stop)
                )

            return self._recording
        except Exception as e:
            logger.error("Failed to start recording: %s", e)
            self._page.snack_bar = ft.SnackBar(content=ft.Text(f"Recording error: {e}"))
            self._page.snack_bar.open = True
            self._page.update()
            return False

    async def _auto_stop_timer(self, on_auto_stop=None):
        """Auto-stop recording after MAX_VOICE_DURATION_SEC (60s)."""
        try:
            await asyncio.sleep(MAX_VOICE_DURATION_SEC)
            if self._recording:
                logger.info(
                    "Auto-stopping recording after %ds limit",
                    MAX_VOICE_DURATION_SEC,
                )
                result = await self.stop_recording()

                # Notify the UI that recording was auto-stopped
                self._page.snack_bar = ft.SnackBar(
                    content=ft.Text(
                        f"Voice note auto-stopped ({MAX_VOICE_DURATION_SEC}s limit)"
                    ),
                    duration=3000,
                )
                self._page.snack_bar.open = True
                self._page.update()

                if on_auto_stop and result:
                    # C4 FIX: Check if callback is async and handle appropriately
                    if asyncio.iscoroutinefunction(on_auto_stop):
                        await on_auto_stop(result)
                    else:
                        callback_result = on_auto_stop(result)
                        # If it returned a coroutine (e.g. from page.run_task), await it
                        if asyncio.iscoroutine(callback_result):
                            await callback_result
        except asyncio.CancelledError:
            pass  # Manually stopped before timeout — expected

    async def stop_recording(self) -> tuple[bytes, str] | None:
        """Stop recording and return ``(raw_bytes, mime_type)`` or None."""
        if not self._recorder or not self._recording:
            return None

        # Cancel auto-stop timer if user manually stopped early
        if self._auto_stop_task and not self._auto_stop_task.done():
            self._auto_stop_task.cancel()
            self._auto_stop_task = None

        try:
            saved_path = await self._recorder.stop_recording()
            self._recording = False
            logger.info("Audio recording stopped, saved to: %s", saved_path)

            data = None
            # On Flet Web client-side (Pyodide), stop_recording() returns a browser-local Blob URL.
            # We fetch its content directly within the browser using JS APIs.
            if saved_path and saved_path.startswith("blob:"):
                logger.info(
                    "Detected browser blob URL: %s. Fetching via JS...", saved_path
                )
                try:
                    js = __import__("js")
                    fetch = js.fetch
                    Uint8Array = js.Uint8Array

                    response = await fetch(saved_path)
                    array_buffer = await response.arrayBuffer()
                    uint8_array = Uint8Array.new(array_buffer)
                    try:
                        data = uint8_array.tobytes()
                    except AttributeError:
                        data = bytes(uint8_array)
                    logger.info(
                        "Successfully fetched %d bytes from browser blob URL", len(data)
                    )
                except ImportError:
                    logger.error(
                        "js.fetch not available (not running under Pyodide WASM)"
                    )
                except Exception as js_err:
                    logger.error("Failed to fetch browser blob via Pyodide: %s", js_err)
            else:
                # Native desktop/mobile flow
                file_path = self._output_path
                if saved_path:
                    file_path = Path(saved_path)

                logger.info(
                    "Attempting to read audio data from local path: %s", file_path
                )
                if file_path and file_path.exists():
                    data = file_path.read_bytes()
                    logger.info("Read %d bytes of audio data", len(data))

            if data is not None:
                # Enforce gateway's 25MB limit
                if len(data) > MAX_AUDIO_SIZE_BYTES:
                    logger.warning(
                        "Audio file too large (%d bytes > %d limit)",
                        len(data),
                        MAX_AUDIO_SIZE_BYTES,
                    )
                    if not (saved_path and saved_path.startswith("blob:")):
                        file_path = (
                            Path(saved_path) if saved_path else self._output_path
                        )
                        if file_path and file_path.exists():
                            file_path.unlink(missing_ok=True)
                    self._page.snack_bar = ft.SnackBar(
                        content=ft.Text(
                            "Voice note too large. Please keep it under 25MB."
                        ),
                        bgcolor=ft.Colors.ERROR,
                    )
                    self._page.snack_bar.open = True
                    self._page.update()
                    return None

                # Clean up local file for native platforms
                if not (saved_path and saved_path.startswith("blob:")):
                    file_path = Path(saved_path) if saved_path else self._output_path
                    if file_path and file_path.exists():
                        file_path.unlink(missing_ok=True)
                return (data, "audio/wav")
            else:
                logger.error("Audio data could not be retrieved")
        except Exception as e:
            logger.error("Failed to stop recording: %s", e)
            self._recording = False

        return None

    def _on_state_change(self, e):
        logger.info("AudioRecorder state changed: %s", e)
