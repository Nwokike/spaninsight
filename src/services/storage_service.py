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
"""

from __future__ import annotations

import json
import logging
import asyncio
from pathlib import Path

import flet as ft

logger = logging.getLogger(__name__)

# Storage location — user home is reliable on all platforms
_STORAGE_DIR = Path.home() / ".spaninsight"
_STORAGE_FILE = _STORAGE_DIR / "storage.json"


class StorageService:
    """Platform-resilient async key-value store.

    Backed by a local JSON file. All operations are synchronous under
    the hood but exposed as async for API consistency with the rest of
    the codebase.
    """

    def __init__(self, page: ft.Page):
        self._page = page
        self._data: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._load()

    # ── Private helpers ──────────────────────────────────────────────

    def _load(self) -> None:
        """Load persisted data from disk."""
        try:
            _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            if _STORAGE_FILE.exists():
                self._data = json.loads(_STORAGE_FILE.read_text(encoding="utf-8"))
                logger.info("StorageService loaded %d keys from %s", len(self._data), _STORAGE_FILE)
            else:
                self._data = {}
                logger.info("StorageService: no existing file, starting fresh")
        except Exception as e:
            logger.warning("StorageService._load failed: %s", e)
            self._data = {}

    def _save(self) -> None:
        """Persist current data to disk."""
        try:
            _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            _STORAGE_FILE.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("StorageService._save failed: %s", e)

    # ── Public API ───────────────────────────────────────────────────

    async def get(self, key: str) -> str | None:
        """Read a value. Returns ``None`` if the key doesn't exist."""
        async with self._lock:
            return self._data.get(key)

    async def set(self, key: str, value: str) -> None:
        """Write a value."""
        async with self._lock:
            self._data[key] = value
            self._save()

    async def delete(self, key: str) -> None:
        """Remove a key."""
        async with self._lock:
            self._data.pop(key, None)
            self._save()
