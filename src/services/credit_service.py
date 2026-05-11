"""Local credit economy service.

All tracking is local. 50 free credits daily, reset on date change.
Referral bonuses permanently increase the daily cap.
"""

from __future__ import annotations

import logging
from datetime import date

import flet as ft
from flet_secure_storage import SecureStorage

from core.constants import (
    DAILY_FREE_CREDITS,
    REFERRAL_BONUS_DAILY,
    STORAGE_BONUS_CREDITS,
    STORAGE_CREDITS,
    STORAGE_LAST_RESET,
)

logger = logging.getLogger(__name__)


class CreditService:
    """Manages the local credit economy."""

    def __init__(self, page: ft.Page):
        self._page = page
        self._storage = SecureStorage()

    async def initialize(self) -> int:
        """Load credits from storage, reset if new day. Returns current balance."""
        await self._check_daily_reset()
        return await self._get_credits()

    async def spend(self, amount: int) -> tuple[bool, int]:
        """Deduct credits. Returns (success, remaining)."""
        current = await self._get_credits()
        if current < amount:
            return False, current
        new_balance = current - amount
        await self._storage.set(STORAGE_CREDITS, str(new_balance))
        logger.info("Spent %d credits. Remaining: %d", amount, new_balance)
        return True, new_balance

    async def get_balance(self) -> int:
        """Return current credit balance."""
        return await self._get_credits()

    async def get_daily_cap(self) -> int:
        """Return the daily credit cap (base + referral bonuses)."""
        bonus = await self._get_bonus()
        return DAILY_FREE_CREDITS + bonus

    async def add_referral_bonus(self) -> int:
        """Add permanent +10 daily credits. Returns new daily cap."""
        bonus = await self._get_bonus()
        new_bonus = bonus + REFERRAL_BONUS_DAILY
        await self._storage.set(STORAGE_BONUS_CREDITS, str(new_bonus))
        return DAILY_FREE_CREDITS + new_bonus

    async def _check_daily_reset(self) -> None:
        """Reset credits if the date has changed."""
        today = date.today().isoformat()
        last_reset = await self._storage.get(STORAGE_LAST_RESET)
        if last_reset != today:
            daily_cap = await self.get_daily_cap()
            await self._storage.set(STORAGE_CREDITS, str(daily_cap))
            await self._storage.set(STORAGE_LAST_RESET, today)
            logger.info("Daily credit reset: %d credits granted.", daily_cap)

    async def _get_credits(self) -> int:
        val = await self._storage.get(STORAGE_CREDITS)
        try:
            return int(val) if val else DAILY_FREE_CREDITS
        except (TypeError, ValueError):
            return DAILY_FREE_CREDITS

    async def _get_bonus(self) -> int:
        val = await self._storage.get(STORAGE_BONUS_CREDITS)
        try:
            return int(val) if val else 0
        except (TypeError, ValueError):
            return 0
