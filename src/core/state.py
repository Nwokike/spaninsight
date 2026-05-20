"""Observable application state — single source of truth.

Uses ``@ft.observable`` (KTV Player pattern) so Flet can auto-react
to property changes without manual page.update() calls.
"""

from __future__ import annotations

from typing import Any

import flet as ft


@ft.observable
class AppState:
    """Global mutable state for Spaninsight."""

    # ── Identity ────────────────────────────────────────────────────
    user_uuid: str = ""

    # ── Credits ─────────────────────────────────────────────────────
    credits_remaining: int = 50
    bonus_credits: int = 0
    last_credit_reset: str = ""

    # ── Data Pipeline ───────────────────────────────────────────────
    current_df: Any = None  # Active pandas DataFrame
    current_df_name: str = ""  # Filename of loaded data
    current_file_path: str = ""  # Path to active CSV/Excel file
    current_df_columns: list = []  # Column names cache
    current_df_rows: int = 0  # Total row count
    current_df_summary: dict = {}  # df.describe() as dict

    # ── Analysis ────────────────────────────────────────────────────
    analysis_blocks: list[dict] = None  # Active interactive blocks in Analysis view
    suggestions: list[dict] = None  # AI suggestion buttons [{label, icon, prompt}]
    charts: list[dict] = (
        None  # Generated chart history [{figure, figure_png, code, insight}]
    )
    current_code: str = ""  # Last generated code
    current_insight: str = ""  # Last AI interpretation
    is_analyzing: bool = False  # Loading state for AI calls
    autopilot_enabled: bool = True  # Autopilot toggle state
    autopilot_cancelled: bool = False  # Flag to stop running autopilot loop
    autopilot_progress: str = ""  # Current autopilot step description for UI

    # ── Forms (Phase 3) ────────────────────────────────────────────
    forms: list[dict] = None

    # ── MCP (Phase 6) ──────────────────────────────────────────────
    mcp_servers: list[dict] = None

    # ── Navigation ──────────────────────────────────────────────────
    current_tab: int = 0  # 0=Home, 1=Analysis, 2=Forms, 3=Settings

    # ── UI ──────────────────────────────────────────────────────────
    is_loading: bool = False
    gateway_online: bool = True
    trigger_file_picker: bool = False
    theme_mode: Any = None  # ft.ThemeMode value
    session_to_restore: dict = None

    def __init__(self):
        self.suggestions = []
        self.charts = []
        self.forms = []
        self.analysis_blocks = []
        self.current_df_columns = []
        self.current_df_summary = {}
        self.session_to_restore = None
        self.mcp_servers = []

    def clear_data(self):
        """Reset all data-related state."""
        self.current_df = None
        self.current_df_name = ""
        self.current_file_path = ""
        self.current_df_columns = []
        self.current_df_rows = 0
        self.current_df_summary = {}
        self.suggestions = []
        self.charts = []
        self.analysis_blocks = []
        self.current_code = ""
        self.current_insight = ""

    def set_dataframe(self, df: Any, filename: str):
        """Load a new DataFrame into state."""
        self.current_df = df
        self.current_df_name = filename
        self.current_df_columns = list(df.columns)
        self.current_df_rows = len(df)


# Module-level singleton
state = AppState()
