"""UUID identity service — generation, backup phrase, and restore.

Privacy-first: no accounts, no servers. Identity is a UUID4 stored
locally in StorageService (works on all platforms).

The backup phrase converts the UUID to a human-readable 12-word
mnemonic using the BIP-39 list so users can recover their identity
after reinstall with zero collision risk.
"""

from __future__ import annotations

import logging
import uuid

import flet as ft

from core.constants import STORAGE_UUID, API_BASE_URL
from services.api_client import request_with_retry
from services.bip39_words import BIP39_WORDS

logger = logging.getLogger(__name__)

# Main 2048-word BIP-39 English word list for secure 12-word recovery
_WORD_LIST = BIP39_WORDS

# Old 256-word list preserved for 100% backward-compatible 6-word restores
_OLD_WORD_LIST = [
    "alpha",
    "atlas",
    "azure",
    "beacon",
    "blaze",
    "bolt",
    "bravo",
    "breeze",
    "cedar",
    "chart",
    "cipher",
    "claim",
    "cloud",
    "coast",
    "comet",
    "coral",
    "craft",
    "crest",
    "crown",
    "curve",
    "dash",
    "dawn",
    "delta",
    "depth",
    "drift",
    "eagle",
    "earth",
    "echo",
    "edge",
    "ember",
    "epoch",
    "fable",
    "falcon",
    "field",
    "flame",
    "flash",
    "flora",
    "forge",
    "frost",
    "gale",
    "gamma",
    "glade",
    "gleam",
    "globe",
    "grace",
    "grain",
    "grove",
    "guard",
    "haven",
    "hawk",
    "heart",
    "helix",
    "heron",
    "honor",
    "hover",
    "ivory",
    "jade",
    "jewel",
    "karma",
    "keen",
    "lance",
    "lark",
    "laser",
    "light",
    "lunar",
    "maple",
    "marsh",
    "mesa",
    "metro",
    "mirth",
    "mist",
    "noble",
    "north",
    "novel",
    "oasis",
    "omega",
    "onyx",
    "orbit",
    "oxide",
    "panda",
    "pearl",
    "peak",
    "phase",
    "pilot",
    "pixel",
    "plume",
    "point",
    "polar",
    "prism",
    "pulse",
    "quake",
    "quest",
    "radar",
    "rapid",
    "raven",
    "realm",
    "reef",
    "ridge",
    "river",
    "robin",
    "rover",
    "royal",
    "ruby",
    "sage",
    "scale",
    "scout",
    "shade",
    "sharp",
    "shell",
    "shore",
    "sigma",
    "silk",
    "slate",
    "slope",
    "solar",
    "sonic",
    "south",
    "spark",
    "spire",
    "spray",
    "stack",
    "star",
    "steel",
    "stone",
    "storm",
    "sugar",
    "surge",
    "swift",
    "table",
    "talon",
    "terra",
    "theta",
    "thorn",
    "tidal",
    "tiger",
    "titan",
    "torch",
    "tower",
    "trace",
    "trail",
    "trend",
    "tulip",
    "ultra",
    "unity",
    "urban",
    "valor",
    "vapor",
    "vault",
    "venom",
    "verse",
    "vigor",
    "vivid",
    "voice",
    "vortex",
    "warden",
    "water",
    "whale",
    "wheat",
    "white",
    "wing",
    "wonder",
    "xenon",
    "yacht",
    "yield",
    "youth",
    "zeal",
    "zenith",
    "zero",
    "amber",
    "anchor",
    "angel",
    "anvil",
    "apple",
    "arrow",
    "badge",
    "basin",
    "berry",
    "birch",
    "bloom",
    "board",
    "bonus",
    "brave",
    "brick",
    "brook",
    "cabin",
    "candy",
    "cargo",
    "chess",
    "chief",
    "cliff",
    "clock",
    "cobra",
    "crane",
    "crisp",
    "cross",
    "dance",
    "denim",
    "diary",
    "dodge",
    "dream",
    "drone",
    "dusk",
    "entry",
    "event",
    "extra",
    "fairy",
    "feast",
    "fiber",
    "finch",
    "flint",
    "focus",
    "frame",
    "fresh",
    "giant",
    "glass",
    "glide",
    "grand",
    "grape",
    "green",
    "guide",
    "happy",
    "hardy",
    "hazel",
    "hobby",
    "honey",
    "hyper",
    "index",
    "input",
    "intro",
    "jelly",
    "jolly",
    "judge",
    "kayak",
    "kiosk",
    "knack",
    "label",
    "layer",
    "lemon",
    "level",
    "lilac",
    "logic",
    "lotus",
    "lucky",
    "magic",
    "major",
    "manor",
    "medal",
    "mercy",
    "micro",
    "model",
    "mocha",
    "motto",
    "music",
    "nerve",
    "nexus",
    "night",
]


class UUIDService:
    """Manages the user's local UUID identity."""

    def __init__(self, page: ft.Page, storage):
        self._page = page
        self._storage = storage

    async def get_or_create_uuid(self) -> str:
        """Return existing UUID or generate a new one."""
        existing = await self._storage.get(STORAGE_UUID)
        if existing:
            # Proactively try to sync in background if not already synced
            is_synced = await self._storage.get("spaninsight_uuid_synced")
            if is_synced != "true":
                import asyncio

                asyncio.create_task(self.sync_pending_uuid())
            return existing

        new_uuid = str(uuid.uuid4())
        await self._storage.set(STORAGE_UUID, new_uuid)
        await self._storage.set("spaninsight_uuid_synced", "false")
        logger.info("Generated new UUID: %s...%s", new_uuid[:8], new_uuid[-4:])

        # Store UUID→phrase mapping in D1 for later restore
        phrase = self.uuid_to_phrase(new_uuid)
        try:
            resp = await request_with_retry(
                "POST",
                f"{API_BASE_URL}/uuid/store",
                json={"uuid": new_uuid, "phrase_hash": self._hash_phrase(phrase)},
                timeout=5.0,
            )
            if resp.status_code in (200, 201):
                await self._storage.set("spaninsight_uuid_synced", "true")
                logger.info("UUID stored remotely in D1.")
        except Exception as e:
            logger.warning("Could not store UUID mapping remotely: %s", e)

        return new_uuid

    async def sync_pending_uuid(self) -> bool:
        """Attempt to sync an unsynced local UUID to the gateway D1 database."""
        user_uuid = await self.get_uuid()
        if not user_uuid:
            return False

        is_synced = await self._storage.get("spaninsight_uuid_synced")
        if is_synced == "true":
            return True

        phrase = self.uuid_to_phrase(user_uuid)
        try:
            resp = await request_with_retry(
                "POST",
                f"{API_BASE_URL}/uuid/store",
                json={"uuid": user_uuid, "phrase_hash": self._hash_phrase(phrase)},
                timeout=5.0,
            )
            if resp.status_code in (200, 201):
                await self._storage.set("spaninsight_uuid_synced", "true")
                logger.info("UUID stored remotely in D1 during background sync.")
                return True
        except Exception as e:
            logger.warning("Background UUID sync failed: %s", e)
        return False

    async def is_synced(self) -> bool:
        """Check if the current UUID has been successfully synced to the gateway D1."""
        user_uuid = await self.get_uuid()
        if not user_uuid:
            return True
        val = await self._storage.get("spaninsight_uuid_synced")
        return val == "true"

    async def get_uuid(self) -> str | None:
        """Return stored UUID or None."""
        return await self._storage.get(STORAGE_UUID)

    def uuid_to_phrase(self, user_uuid: str) -> str:
        """Convert a 128-bit UUID integer to a 12-word secure mnemonic using standard BIP-39 words."""
        try:
            u_int = uuid.UUID(user_uuid).int
        except Exception as e:
            logger.error("Invalid UUID format: %s", e)
            return ""

        words = []
        temp_val = u_int
        for _ in range(12):
            idx = temp_val % 2048
            words.append(_WORD_LIST[idx])
            temp_val //= 2048
        return " ".join(words)

    def _phrase_to_uuid(self, phrase: str) -> str | None:
        """Validate a 6-word or 12-word phrase. Returns the phrase if valid, None otherwise."""
        words = phrase.strip().lower().split()
        if len(words) == 6:
            # Backward compatible 6-word phrase
            for w in words:
                if w not in _OLD_WORD_LIST:
                    return None
            return phrase
        elif len(words) == 12:
            # Standard 12-word BIP-39 phrase
            for w in words:
                if w not in _WORD_LIST:
                    return None
            return phrase
        return None

    async def restore_uuid(self, backup_phrase: str) -> bool:
        """Restore UUID from a backup phrase by querying D1."""
        phrase = backup_phrase.strip().lower()
        validated = self._phrase_to_uuid(phrase)
        if not validated:
            return False

        try:
            phrase_hash = self._hash_phrase(phrase)
            resp = await request_with_retry(
                "GET",
                f"{API_BASE_URL}/uuid/restore",
                params={"phrase_hash": phrase_hash},
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                restored_uuid = data.get("uuid")
                if restored_uuid:
                    await self._storage.set(STORAGE_UUID, restored_uuid)
                    logger.info("UUID restored from backup phrase.")
                    return True
            else:
                logger.warning("UUID restore failed: HTTP %d", resp.status_code)
        except Exception as e:
            logger.error("Failed to restore UUID: %s", e)
        return False

    @staticmethod
    def _hash_phrase(phrase: str) -> str:
        """SHA-256 hash of the phrase for D1 lookup."""
        import hashlib

        return hashlib.sha256(phrase.encode()).hexdigest()[:32]

    async def get_backup_phrase(self) -> str:
        """Get the backup phrase for the current UUID."""
        user_uuid = await self.get_uuid()
        if not user_uuid:
            return ""
        return self.uuid_to_phrase(user_uuid)

    def get_masked_uuid(self, user_uuid: str) -> str:
        """Return a masked display version: 'a1b2c3d4-****-****-****-****ef56'."""
        if not user_uuid or len(user_uuid) < 8:
            return "Not generated"
        return f"{user_uuid[:8]}...{user_uuid[-4:]}"
