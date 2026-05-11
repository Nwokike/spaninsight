"""AdMob service — banner and interstitial ads.

Direct port of KTV Player's production AdService pattern.
Uses test Ad IDs until Play Store launch.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

import flet as ft

logger = logging.getLogger(__name__)

# Try importing flet_ads — only available on mobile
try:
    import flet_ads as fta
    _HAS_ADS = True
except ImportError:
    _HAS_ADS = False


class AdService:
    """Manages AdMob banner and interstitial ads."""

    # Test IDs — swap before Play Store submission
    BANNER_ID_ANDROID = "ca-app-pub-3940256099942544/9214589741"
    INTERSTITIAL_ID_ANDROID = "ca-app-pub-3940256099942544/1033173712"

    def __init__(self, page: ft.Page):
        self.page = page
        self.interstitial = None
        self._on_close: Optional[Callable] = None

    def _is_mobile(self) -> bool:
        try:
            return self.page.platform.is_mobile()
        except Exception:
            return False

    def get_banner_ad(self) -> ft.Control:
        """Return a banner ad control, or empty container on desktop."""
        if not _HAS_ADS or not self._is_mobile():
            return ft.Container(width=0, height=0)
        try:
            ad = fta.BannerAd(
                unit_id=self.BANNER_ID_ANDROID,
                width=320,
                height=50,
                on_error=lambda e: None,
            )
            return ft.Container(
                content=ad,
                width=320,
                height=50,
                alignment=ft.Alignment.CENTER,
            )
        except Exception:
            return ft.Container(width=0, height=0)

    async def preload_interstitial(self, on_close: Optional[Callable] = None):
        """Pre-load an interstitial ad for later display."""
        self._on_close = on_close
        if not _HAS_ADS or not self._is_mobile():
            return
        try:
            self.interstitial = fta.InterstitialAd(
                unit_id=self.INTERSTITIAL_ID_ANDROID,
                on_load=lambda e: None,
                on_error=lambda e: None,
                on_close=self._handle_close,
            )
        except Exception:
            self.interstitial = None

    async def _handle_close(self, e):
        if self._on_close:
            if asyncio.iscoroutinefunction(self._on_close):
                await self._on_close()
            else:
                self._on_close()
        await self.preload_interstitial(on_close=self._on_close)

    async def show_interstitial(self) -> bool:
        """Show a preloaded interstitial. Returns True if shown."""
        if self.interstitial:
            try:
                await self.interstitial.show()
                return True
            except Exception:
                return False
        return False
