"""Application-wide constants — API config, limits, security.

Every magic string and hard limit lives here. Import from
``core.constants`` instead of hard-coding values.
"""

from __future__ import annotations

# ── API Gateway (Cloudflare Worker) ─────────────────────────────────
API_BASE_URL = "https://api.spaninsight.com"
API_HEALTH_ENDPOINT = f"{API_BASE_URL}/health"
API_CHAT_ENDPOINT = f"{API_BASE_URL}/chat"

# Headers required by the gateway's security gate
APP_SECRET = "spaninsight-mobile-v1"
APP_VERSION = "1.0.0"
USER_AGENT = f"SpaninsightApp/{APP_VERSION}"

# ── Task Types (maps to gateway ROUTES) ─────────────────────────────
TASK_SUGGEST = "suggest"
TASK_CODE = "code"
TASK_INTERPRET = "interpret"
TASK_AUDIO = "audio"
TASK_VISION = "vision"

# ── File Limits ─────────────────────────────────────────────────────
# Modern phones have 4GB+ RAM. pandas can handle ~100MB CSVs comfortably.
MAX_FILE_SIZE_MB = 100
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {".csv", ".json",".xlsx", ".xls"}

# ── Data Display ────────────────────────────────────────────────────
DATA_PREVIEW_ROWS = 50

# ── Audio ───────────────────────────────────────────────────────────
MAX_VOICE_DURATION_SEC = 60
MAX_AUDIO_SIZE_BYTES = 25 * 1024 * 1024  # Gateway limit

# ── Credits ─────────────────────────────────────────────────────────
DAILY_FREE_CREDITS = 50
COST_SUGGEST = 1
COST_CUSTOM_PROMPT = 3
COST_AUTOPILOT = 15
REFERRAL_BONUS_DAILY = 10

# ── Sandbox Security ────────────────────────────────────────────────
BLOCKED_TERMS = [
    "import os",
    "import sys",
    "subprocess",
    "open(",
    "shutil",
    "import socket",
    "import http",
    "__import__",
    "eval(",
    "compile(",
    "exec(",
    "import pathlib",
    "import glob",
    "import signal",
    "import ctypes",
    "import multiprocessing",
    "import threading",
    "import asyncio",
    "import requests",
    "import urllib",
    "import webbrowser",
]

SANDBOX_TIMEOUT_SEC = 10

# ── Storage Keys (for SecureStorage) ────────────────────────────────
STORAGE_UUID = "spaninsight_uuid"
STORAGE_THEME = "spaninsight.theme"
STORAGE_CREDITS = "spaninsight_credits"
STORAGE_BONUS_CREDITS = "spaninsight_bonus_credits"
STORAGE_LAST_RESET = "spaninsight_last_reset"
STORAGE_REFERRAL_CODE = "spaninsight_referral_code"
STORAGE_ONBOARDING_DONE = "spaninsight_onboarding_done"
