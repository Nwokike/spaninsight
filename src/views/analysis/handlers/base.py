import logging
import flet as ft
from core.state import state
from core import theme

logger = logging.getLogger(__name__)


def show_error(view_state, msg: str):
    view_state.page.snack_bar = ft.SnackBar(
        ft.Text(msg, color=ft.Colors.WHITE), bgcolor=theme.ERROR, duration=4000
    )
    view_state.page.snack_bar.open = True
    view_state.page.update()


def show_success(view_state, msg: str):
    view_state.page.snack_bar = ft.SnackBar(ft.Text(msg), duration=2000)
    view_state.page.snack_bar.open = True
    view_state.page.update()


def build_analysis_context() -> str:
    blocks = state.analysis_blocks
    if not blocks:
        return ""
    parts = []
    if blocks[0].get("description"):
        parts.append(f"Dataset: {blocks[0]['description']}")
    recent = [b for b in blocks[1:] if b.get("type") == "analysis"][-2:]
    for b in recent:
        parts.append(f"Done: {b.get('prompt', '')} → {b.get('description', '')}")
    return "\n".join(parts)
