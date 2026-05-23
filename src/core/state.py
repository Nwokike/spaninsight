"""Observable application state — single source of truth.

Uses ``@ft.observable`` (KTV Player pattern) so Flet can auto-react
to property changes without manual page.update() calls.
"""

from __future__ import annotations

import logging
from typing import Any
import flet as ft

logger = logging.getLogger(__name__)


@ft.observable
class AppState:
    """Global mutable state for Spaninsight."""

    # ── Identity ────────────────────────────────────────────────────
    user_uuid: str = ""

    # ── Projects Workspace ──────────────────────────────────────────
    active_project_id: str = ""
    user_projects: dict[str, dict] = None  # Keyed by 6-digit project ID

    # ── Credits ─────────────────────────────────────────────────────
    credits_remaining: int = 50
    bonus_credits: int = 0
    last_credit_reset: str = ""

    # ── Active Project State (Properties mapped to active project) ──
    @property
    def active_project(self) -> dict:
        if not self.user_projects:
            self.user_projects = {}
        if (
            not self.active_project_id
            or self.active_project_id not in self.user_projects
        ):
            # Fallback to first project or return an empty dict
            if self.user_projects:
                self.active_project_id = next(iter(self.user_projects.keys()))
            else:
                return {}
        return self.user_projects[self.active_project_id]

    @property
    def current_df_name(self) -> str:
        return self.active_project.get("current_df_name", "")

    @current_df_name.setter
    def current_df_name(self, value: str):
        self.active_project["current_df_name"] = value

    @property
    def current_file_path(self) -> str:
        return self.active_project.get("current_file_path", "")

    @current_file_path.setter
    def current_file_path(self, value: str):
        self.active_project["current_file_path"] = value

    @property
    def analysis_blocks(self) -> list[dict]:
        return self.active_project.setdefault("analysis_blocks", [])

    @analysis_blocks.setter
    def analysis_blocks(self, value: list[dict]):
        self.active_project["analysis_blocks"] = value

    @property
    def user_reports(self) -> list[dict]:
        return self.active_project.setdefault("user_reports", [])

    @user_reports.setter
    def user_reports(self, value: list[dict]):
        self.active_project["user_reports"] = value

    @property
    def forms(self) -> list[dict]:
        return self.active_project.setdefault("forms", [])

    @forms.setter
    def forms(self, value: list[dict]):
        self.active_project["forms"] = value

    # ── Temporary / In-Memory Session State ─────────────────────────
    current_df: Any = None  # Active pandas DataFrame instance (in-memory only)
    current_df_columns: list[str] = None  # Column names cache
    current_df_rows: int = 0  # Total row count
    current_df_summary: dict = None  # df.describe() summary dict
    dataset_modified: bool = False  # Tracks if the dataset has been cleaned or modified
    suggestions: list[dict] = None  # AI suggestion buttons [{label, icon, prompt}]
    charts: list[dict] = None  # Generated chart history
    current_code: str = ""  # Last generated code
    current_insight: str = ""  # Last AI interpretation
    is_analyzing: bool = False  # Loading state for AI calls
    autopilot_enabled: bool = True  # Autopilot toggle state
    autopilot_cancelled: bool = False  # Flag to stop running autopilot loop
    autopilot_progress: str = ""  # Current autopilot step description for UI
    active_report: dict = None

    # ── Navigation & UI ─────────────────────────────────────────────
    current_tab: int = 0  # 0=Home, 1=Forms, 2=Analysis, 3=Reports, 4=Settings
    is_loading: bool = False
    gateway_online: bool = True
    trigger_file_picker: bool = False
    theme_mode: Any = None  # ft.ThemeMode value
    session_to_restore: dict = None

    def __init__(self):
        self.user_projects = {}
        self.suggestions = []
        self.charts = []
        self.current_df_columns = []
        self.current_df_summary = {}
        self.session_to_restore = None
        self.dataset_modified = False

    def clear_data(self):
        """Reset all data-related state for the active project."""
        self.current_df = None
        self.current_df_columns = []
        self.current_df_rows = 0
        self.current_df_summary = {}
        self.suggestions = []
        self.charts = []
        self.current_code = ""
        self.current_insight = ""
        self.dataset_modified = False

        # Wipe project-specific persistent fields
        self.current_df_name = ""
        self.current_file_path = ""
        self.analysis_blocks.clear()

    def set_dataframe(self, df: Any, filename: str):
        """Load a new DataFrame into state."""
        self.current_df = df
        self.current_df_name = filename
        self.current_df_columns = list(df.columns)
        self.current_df_rows = len(df)
        self.dataset_modified = False


# Module-level singleton
state = AppState()
