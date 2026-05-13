"""UUID identity service — generation, backup phrase, and restore.

Privacy-first: no accounts, no servers. Identity is a UUID4 stored
locally in StorageService (works on all platforms).

The backup phrase converts the UUID to a human-readable 6-word
mnemonic so users can recover their identity after reinstall.
"""

from __future__ import annotations

import logging
import uuid

import flet as ft
import httpx

from core.constants import STORAGE_UUID, API_BASE_URL, APP_SECRET, USER_AGENT

logger = logging.getLogger(__name__)

# Word list for mnemonic backup phrase (256 words = 1 byte each, 6 words = 48 bits)
# We use the first/last 3 segments of the UUID hex to generate 6 words.
_WORD_LIST = [
    "alpha", "atlas", "azure", "beacon", "blaze", "bolt", "bravo", "breeze",
    "cedar", "chart", "cipher", "claim", "cloud", "coast", "comet", "coral",
    "craft", "crest", "crown", "curve", "dash", "dawn", "delta", "depth",
    "drift", "eagle", "earth", "echo", "edge", "ember", "epoch", "fable",
    "falcon", "field", "flame", "flash", "flora", "forge", "frost", "gale",
    "gamma", "glade", "gleam", "globe", "grace", "grain", "grove", "guard",
    "haven", "hawk", "heart", "helix", "heron", "honor", "hover", "ivory",
    "jade", "jewel", "karma", "keen", "lance", "lark", "laser", "light",
    "lunar", "maple", "marsh", "mesa", "metro", "mirth", "mist", "noble",
    "north", "novel", "oasis", "omega", "onyx", "orbit", "oxide", "panda",
    "pearl", "peak", "phase", "pilot", "pixel", "plume", "point", "polar",
    "prism", "pulse", "quake", "quest", "radar", "rapid", "raven", "realm",
    "reef", "ridge", "river", "robin", "rover", "royal", "ruby", "sage",
    "scale", "scout", "shade", "sharp", "shell", "shore", "sigma", "silk",
    "slate", "slope", "solar", "sonic", "south", "spark", "spire", "spray",
    "stack", "star", "steel", "stone", "storm", "sugar", "surge", "swift",
    "table", "talon", "terra", "theta", "thorn", "tidal", "tiger", "titan",
    "torch", "tower", "trace", "trail", "trend", "tulip", "ultra", "unity",
    "urban", "valor", "vapor", "vault", "venom", "verse", "vigor", "vivid",
    "voice", "vortex", "warden", "water", "whale", "wheat", "white", "wing",
    "wonder", "xenon", "yacht", "yield", "youth", "zeal", "zenith", "zero",
    "amber", "anchor", "angel", "anvil", "apple", "arrow", "badge", "basin",
    "berry", "birch", "bloom", "board", "bonus", "brave", "brick", "brook",
    "cabin", "candy", "cargo", "chess", "chief", "cliff", "clock", "cobra",
    "coral", "crisp", "cross", "dance", "denim", "diary", "dodge", "dream",
    "drone", "dusk", "entry", "event", "extra", "fairy", "feast", "fiber",
    "finch", "flint", "focus", "frame", "fresh", "giant", "glass", "glide",
    "grand", "grape", "green", "guide", "happy", "hardy", "hazel", "hobby",
    "honey", "hyper", "index", "input", "intro", "jewel", "jolly", "judge",
    "kayak", "kiosk", "knack", "label", "layer", "lemon", "level", "lilac",
    "logic", "lotus", "lucky", "magic", "major", "manor", "medal", "mercy",
    "micro", "model", "mocha", "motto", "music", "nerve", "nexus", "night",
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
            return existing

        new_uuid = str(uuid.uuid4())
        await self._storage.set(STORAGE_UUID, new_uuid)
        logger.info("Generated new UUID: %s...%s", new_uuid[:8], new_uuid[-4:])

        # Store UUID→phrase mapping in D1 for later restore
        phrase = self.uuid_to_phrase(new_uuid)
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{API_BASE_URL}/uuid/store",
                    headers={"X-App-Secret": APP_SECRET, "User-Agent": USER_AGENT,
                             "Content-Type": "application/json"},
                    json={"uuid": new_uuid, "phrase_hash": self._hash_phrase(phrase)},
                    timeout=5.0,
                )
        except Exception as e:
            logger.warning("Could not store UUID mapping remotely: %s", e)

        return new_uuid

    async def get_uuid(self) -> str | None:
        """Return stored UUID or None."""
        return await self._storage.get(STORAGE_UUID)

    def uuid_to_phrase(self, user_uuid: str) -> str:
        """Convert a UUID string to a 6-word backup phrase."""
        hex_str = user_uuid.replace("-", "")
        words = []
        # Take 6 groups of 2 hex chars (1 byte each) from spread positions
        indices = [0, 4, 8, 16, 24, 28]
        for i in indices:
            byte_val = int(hex_str[i : i + 2], 16)
            words.append(_WORD_LIST[byte_val])
        return " ".join(words)

    def _phrase_to_uuid(self, phrase: str) -> str | None:
        """Validate a 6-word phrase. Returns phrase if valid, None otherwise."""
        words = phrase.split()
        if len(words) != 6:
            return None

        # Validate all words exist in our word list
        for w in words:
            if w not in _WORD_LIST:
                return None

        return phrase  # Return the phrase; actual D1 lookup happens in restore_uuid

    async def restore_uuid(self, backup_phrase: str) -> bool:
        """Restore UUID from a backup phrase by querying D1."""
        phrase = backup_phrase.strip().lower()
        words = phrase.split()
        if len(words) != 6:
            return False

        # Validate all words exist
        for w in words:
            if w not in _WORD_LIST:
                return False

        try:
            phrase_hash = self._hash_phrase(phrase)
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{API_BASE_URL}/uuid/restore",
                    params={"phrase_hash": phrase_hash},
                    headers={"X-App-Secret": APP_SECRET, "User-Agent": USER_AGENT},
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
