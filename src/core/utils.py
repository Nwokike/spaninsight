"""Shared utilities — snackbar, version comparison, image helpers.

Centralizes patterns that were duplicated 20+ times across views.
"""

from __future__ import annotations

import base64
import io
import logging

import flet as ft

logger = logging.getLogger(__name__)


# ── Snackbar Helper ─────────────────────────────────────────────────


def show_snack(
    page: ft.Page,
    message: str,
    *,
    error: bool = False,
    success: bool = False,
    duration: int = 3000,
) -> None:
    """Show a styled snackbar notification.

    Args:
        page: The Flet page instance.
        message: Text to display.
        error: If True, show with red error styling.
        success: If True, show with green success styling.
        duration: Display duration in milliseconds.
    """
    from core import theme

    bgcolor = None
    text_color = None
    if error:
        bgcolor = theme.ERROR
        text_color = ft.Colors.WHITE
    elif success:
        bgcolor = theme.SUCCESS
        text_color = ft.Colors.WHITE

    page.snack_bar = ft.SnackBar(
        content=ft.Text(message, color=text_color),
        bgcolor=bgcolor,
        duration=duration,
    )
    page.snack_bar.open = True
    page.update()


# ── Version Comparison ──────────────────────────────────────────────


def parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a semver string into a comparable tuple.

    >>> parse_version("1.2.3")
    (1, 2, 3)
    >>> parse_version("10.0.0") > parse_version("9.9.9")
    True
    """
    try:
        return tuple(int(x) for x in version_str.strip().split("."))
    except (ValueError, AttributeError):
        return (0, 0, 0)


# ── Figure to PNG Bytes ─────────────────────────────────────────────


def figure_to_png_bytes(figure, dpi: int = 150) -> bytes:
    """Convert a matplotlib Figure to PNG bytes and close it.

    Closing the figure after conversion prevents the ~2-5MB per-figure
    memory leak that occurs when figures are kept alive in state.
    """
    import matplotlib.pyplot as plt

    buf = io.BytesIO()
    figure.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    buf.seek(0)
    data = buf.read()
    buf.close()
    plt.close(figure)
    return data


def png_bytes_to_base64(png_bytes: bytes) -> str:
    """Encode PNG bytes as a base64 string for ft.Image(src_base64=...)."""
    return base64.b64encode(png_bytes).decode("utf-8")
