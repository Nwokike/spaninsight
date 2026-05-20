"""Platform-resilient key-value storage service.

Uses a local JSON file for desktop/mobile persistence, and falls back to
``page.client_storage`` (browser localStorage) when running on the web
(Flet Pyodide/WASM) where the in-memory virtual filesystem is wiped on
tab refresh.

Works identically on:
- Desktop (``flet run``)
- Android dev (``flet run --android``)
- Production APK (``flet build apk``)
- Web/Pyodide (``flet run --web``)
"""

from __future__ import annotations

import json
import logging
import asyncio
import time
from pathlib import Path

import flet as ft

logger = logging.getLogger(__name__)

# Storage location — user home is reliable on desktop/mobile
_STORAGE_DIR = Path.home() / ".spaninsight"
_STORAGE_FILE = _STORAGE_DIR / "storage.json"

# Debounce interval — minimum seconds between disk writes
_WRITE_DEBOUNCE_SEC = 1.0


class StorageService:
    """Platform-resilient async key-value store.

    On desktop/mobile: backed by a local JSON file.
    On web/Pyodide: backed by page.client_storage (browser localStorage).

    Writes are debounced to avoid I/O bottleneck during rapid operations.
    """

    def __init__(self, page: ft.Page):
        self._page = page
        self._data: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._dirty = False
        self._last_write: float = 0.0
        self._pending_write_task: asyncio.Task | None = None

        # Detect web/Pyodide: session_id is only set for web sessions
        self._is_web = bool(getattr(page, "session_id", None))

        if self._is_web:
            logger.info("StorageService: running on web — using client_storage")
            self._load_web()
        else:
            logger.info("StorageService: running on native — using local file")
            self._load()

    # ── Web/Pyodide helpers ──────────────────────────────────────────

    def _load_web(self) -> None:
        """Load data from browser localStorage (synchronous under the hood)."""
        try:
            cs = self._page.client_storage
            raw = cs.get("spaninsight_data")
            if raw:
                self._data = json.loads(raw)
                logger.info(
                    "StorageService (web) loaded %d keys from localStorage",
                    len(self._data),
                )
            else:
                self._data = {}
                logger.info("StorageService (web): no existing data, starting fresh")
        except Exception as e:
            logger.warning("StorageService._load_web failed: %s", e)
            self._data = {}

    def _save_now_web(self) -> None:
        """Persist current data to browser localStorage."""
        try:
            self._page.client_storage.set(
                "spaninsight_data",
                json.dumps(self._data, indent=2, ensure_ascii=False),
            )
            self._last_write = time.monotonic()
            self._dirty = False
        except Exception as e:
            logger.warning("StorageService._save_now_web failed: %s", e)

    # ── Native file helpers ──────────────────────────────────────────

    def _load(self) -> None:
        """Load persisted data from disk with fallback to client_storage."""
        loaded = False
        try:
            _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            if _STORAGE_FILE.exists():
                self._data = json.loads(_STORAGE_FILE.read_text(encoding="utf-8"))
                logger.info(
                    "StorageService loaded %d keys from %s",
                    len(self._data),
                    _STORAGE_FILE,
                )
                loaded = True
            else:
                logger.info(
                    "StorageService: no existing file, checking fallback client_storage"
                )
        except Exception as e:
            logger.warning("StorageService._load filesystem read failed: %s", e)

        if not loaded:
            self._load_web()

    def _save_now(self) -> None:
        """Persist current data to disk immediately with fallback to client_storage."""
        try:
            _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            _STORAGE_FILE.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            self._last_write = time.monotonic()
            self._dirty = False
        except Exception as e:
            logger.warning(
                "StorageService._save failed, falling back to client_storage: %s", e
            )
            try:
                self._save_now_web()
            except Exception as ex:
                logger.error("StorageService fallback save failed: %s", ex)

    def _schedule_write(self) -> None:
        """Schedule a debounced disk write."""
        self._dirty = True
        elapsed = time.monotonic() - self._last_write

        if elapsed >= _WRITE_DEBOUNCE_SEC:
            self._save_now() if not self._is_web else self._save_now_web()
        else:
            if self._pending_write_task is None or self._pending_write_task.done():
                try:
                    loop = asyncio.get_event_loop()
                    self._pending_write_task = loop.create_task(self._deferred_write())
                except RuntimeError:
                    self._save_now() if not self._is_web else self._save_now_web()

    async def _deferred_write(self) -> None:
        """Wait for debounce interval, then write if still dirty."""
        await asyncio.sleep(_WRITE_DEBOUNCE_SEC)
        if self._dirty:
            self._save_now() if not self._is_web else self._save_now_web()

    # ── Public API ───────────────────────────────────────────────────

    async def get(self, key: str) -> str | None:
        """Read a value. Returns ``None`` if the key doesn't exist."""
        async with self._lock:
            return self._data.get(key)

    async def set(self, key: str, value: str) -> None:
        """Write a value."""
        async with self._lock:
            self._data[key] = value
            self._schedule_write()

    async def delete(self, key: str) -> None:
        """Remove a key."""
        async with self._lock:
            self._data.pop(key, None)
            self._schedule_write()

    async def flush(self) -> None:
        """Force an immediate disk write (call on app shutdown)."""
        async with self._lock:
            if self._dirty:
                self._save_now() if not self._is_web else self._save_now_web()
