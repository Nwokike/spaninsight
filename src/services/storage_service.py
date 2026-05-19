"""Platform-resilient key-value storage service.

Uses a local JSON file for persistence — pure Python, no Flet plugin
dependencies. This avoids all "Unknown control" and TimeoutException
errors that occur when client-side plugins (SharedPreferences,
SecureStorage) are unavailable in the Flet web runtime
(``flet run --android``).

Works identically on:
- Desktop (``flet run``)
- Android dev (``flet run --android``)
- Production APK (``flet build apk``)

Audit fix H9: Writes are debounced — at most one disk write per second
to avoid I/O bottleneck during rapid credit operations.
"""

from __future__ import annotations

import json
import logging
import asyncio
import time
from pathlib import Path

import flet as ft

logger = logging.getLogger(__name__)

# Storage location — user home is reliable on all platforms
_STORAGE_DIR = Path.home() / ".spaninsight"
_STORAGE_FILE = _STORAGE_DIR / "storage.json"

# Debounce interval — minimum seconds between disk writes
_WRITE_DEBOUNCE_SEC = 1.0


class StorageService:
    """Platform-resilient async key-value store.

    Backed by a local JSON file. All operations are synchronous under
    the hood but exposed as async for API consistency with the rest of
    the codebase.

    Writes are debounced to avoid I/O bottleneck during rapid operations.
    """

    def __init__(self, page: ft.Page):
        self._page = page
        self._data: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._dirty = False
        self._last_write: float = 0.0
        self._pending_write_task: asyncio.Task | None = None
        self._load()

    # ── Private helpers ──────────────────────────────────────────────

    def _load(self) -> None:
        """Load persisted data from disk."""
        try:
            _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            if _STORAGE_FILE.exists():
                self._data = json.loads(_STORAGE_FILE.read_text(encoding="utf-8"))
                logger.info(
                    "StorageService loaded %d keys from %s",
                    len(self._data),
                    _STORAGE_FILE,
                )
            else:
                self._data = {}
                logger.info("StorageService: no existing file, starting fresh")
        except Exception as e:
            logger.warning("StorageService._load failed: %s", e)
            self._data = {}

    def _save_now(self) -> None:
        """Persist current data to disk immediately."""
        try:
            _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            _STORAGE_FILE.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            self._last_write = time.monotonic()
            self._dirty = False
        except Exception as e:
            logger.warning("StorageService._save failed: %s", e)

    def _schedule_write(self) -> None:
        """Schedule a debounced disk write."""
        self._dirty = True
        elapsed = time.monotonic() - self._last_write

        if elapsed >= _WRITE_DEBOUNCE_SEC:
            # Enough time has passed — write immediately
            self._save_now()
        else:
            # Schedule a deferred write if not already pending
            if self._pending_write_task is None or self._pending_write_task.done():
                try:
                    loop = asyncio.get_event_loop()
                    self._pending_write_task = loop.create_task(self._deferred_write())
                except RuntimeError:
                    # No event loop — write immediately
                    self._save_now()

    async def _deferred_write(self) -> None:
        """Wait for debounce interval, then write if still dirty."""
        await asyncio.sleep(_WRITE_DEBOUNCE_SEC)
        if self._dirty:
            self._save_now()

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
                self._save_now()
