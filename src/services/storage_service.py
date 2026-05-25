"""Platform-resilient key-value storage service.

Uses a split local JSON file approach for desktop/mobile persistence
(separating heavy history from light settings), and falls back to
``page.client_storage`` when running on the web.
"""

from __future__ import annotations

import logging
import asyncio
import time
import os
import msgspec
from pathlib import Path

import flet as ft

logger = logging.getLogger(__name__)

# Use Flet sandbox data storage path on Android/iOS mobile to avoid Path.home() permission issues
storage_env = os.getenv("FLET_APP_STORAGE_DATA")
if storage_env:
    _STORAGE_DIR = Path(storage_env)
else:
    _STORAGE_DIR = Path.home() / ".spaninsight"

_SETTINGS_FILE = _STORAGE_DIR / "settings.json"
_HISTORY_FILE = _STORAGE_DIR / "history.json"

_WRITE_DEBOUNCE_SEC = 1.0


class StorageService:
    def __init__(self, page: ft.Page):
        self._page = page
        self._settings: dict[str, str] = {}
        self._history: dict[str, str] = {}
        self._lock = asyncio.Lock()

        self._settings_dirty = False
        self._history_dirty = False

        self._last_write: float = 0.0
        self._pending_write_task: asyncio.Task | None = None

        self._is_web = bool(getattr(page, "session_id", None))

        if self._is_web:
            logger.info("StorageService: running on web — using client_storage")
            self._load_web()
        else:
            logger.info("StorageService: running on native — using split local files")
            self._load()

    def _is_history_key(self, key: str) -> bool:
        """Determines if a key contains heavy analytical data vs lightweight settings."""
        return (
            key.startswith("report_")
            or key.startswith("history_")
            or key.startswith("analysis_")
            or key == "spaninsight_projects"
        )

    # ── Web/Pyodide helpers ──────────────────────────────────────────

    def _load_web(self) -> None:
        try:
            cs = self._page.client_storage
            raw_s = cs.get("spaninsight_settings")
            raw_h = cs.get("spaninsight_history")
            self._settings = msgspec.json.decode(raw_s) if raw_s else {}
            self._history = msgspec.json.decode(raw_h) if raw_h else {}
        except Exception as e:
            logger.warning("StorageService._load_web failed: %s", e)
            self._settings, self._history = {}, {}

    def _save_now_web(self) -> None:
        try:
            cs = self._page.client_storage
            if self._settings_dirty:
                cs.set("spaninsight_settings", msgspec.json.encode(self._settings).decode())
                self._settings_dirty = False
            if self._history_dirty:
                cs.set("spaninsight_history", msgspec.json.encode(self._history).decode())
                self._history_dirty = False
            self._last_write = time.monotonic()
        except Exception as e:
            logger.warning("StorageService._save_now_web failed: %s", e)

    # ── Native file helpers ──────────────────────────────────────────

    def _load(self) -> None:
        loaded = False
        try:
            _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            if _SETTINGS_FILE.exists():
                self._settings = msgspec.json.decode(_SETTINGS_FILE.read_bytes())
                loaded = True
            if _HISTORY_FILE.exists():
                self._history = msgspec.json.decode(_HISTORY_FILE.read_bytes())
        except Exception as e:
            logger.warning("StorageService._load filesystem read failed: %s", e)

        if not loaded:
            # No existing data — fresh start
            self._settings, self._history = {}, {}

        if not loaded and self._is_web:
            self._load_web()  # Fallback

    def _write_files_sync(
        self, settings_copy, history_copy, write_settings, write_history
    ) -> None:
        _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        if write_settings:
            _SETTINGS_FILE.write_bytes(
                msgspec.json.encode(settings_copy),
            )
        if write_history:
            _HISTORY_FILE.write_bytes(
                msgspec.json.encode(history_copy),
            )

    async def _save_now_async(self) -> None:
        if self._is_web:
            self._save_now_web()
            return
        try:
            write_settings = self._settings_dirty
            write_history = self._history_dirty

            if write_settings or write_history:
                settings_copy = dict(self._settings) if write_settings else None
                history_copy = dict(self._history) if write_history else None

                await asyncio.to_thread(
                    self._write_files_sync,
                    settings_copy,
                    history_copy,
                    write_settings,
                    write_history,
                )

                if write_settings:
                    self._settings_dirty = False
                if write_history:
                    self._history_dirty = False

            self._last_write = time.monotonic()
        except Exception as e:
            logger.warning(
                "StorageService._save_now_async failed, falling back to web: %s", e
            )
            self._save_now_web()

    def _save_now(self) -> None:
        try:
            _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            if self._settings_dirty:
                _SETTINGS_FILE.write_bytes(
                    msgspec.json.encode(self._settings),
                )
                self._settings_dirty = False
            if self._history_dirty:
                _HISTORY_FILE.write_bytes(
                    msgspec.json.encode(self._history),
                )
                self._history_dirty = False
            self._last_write = time.monotonic()
        except Exception as e:
            logger.warning("StorageService._save failed, falling back to web: %s", e)
            self._save_now_web()

    def _schedule_write(self) -> None:
        elapsed = time.monotonic() - self._last_write
        if elapsed >= _WRITE_DEBOUNCE_SEC:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._save_now_async())
            except RuntimeError:
                self._save_now() if not self._is_web else self._save_now_web()
        else:
            if self._pending_write_task is None or self._pending_write_task.done():
                try:
                    loop = asyncio.get_event_loop()
                    self._pending_write_task = loop.create_task(self._deferred_write())
                except RuntimeError:
                    self._save_now() if not self._is_web else self._save_now_web()

    async def _deferred_write(self) -> None:
        await asyncio.sleep(_WRITE_DEBOUNCE_SEC)
        if self._settings_dirty or self._history_dirty:
            await self._save_now_async()

    # ── Public API ───────────────────────────────────────────────────

    async def get(self, key: str) -> str | None:
        async with self._lock:
            if self._is_history_key(key):
                return self._history.get(key)
            return self._settings.get(key)

    async def set(self, key: str, value: str) -> None:
        async with self._lock:
            if self._is_history_key(key):
                self._history[key] = value
                self._history_dirty = True
            else:
                self._settings[key] = value
                self._settings_dirty = True
            self._schedule_write()

    async def delete(self, key: str) -> None:
        async with self._lock:
            if self._is_history_key(key):
                self._history.pop(key, None)
                self._history_dirty = True
            else:
                self._settings.pop(key, None)
                self._settings_dirty = True
            self._schedule_write()

    async def flush(self) -> None:
        async with self._lock:
            if self._settings_dirty or self._history_dirty:
                await (
                    self._save_now_async()
                ) if not self._is_web else self._save_now_web()
