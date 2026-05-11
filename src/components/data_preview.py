"""Data preview component — DataTable with 50-row cap."""

from __future__ import annotations

import flet as ft
import pandas as pd

from core import tokens
from core.constants import DATA_PREVIEW_ROWS


def build_data_preview(df: pd.DataFrame) -> ft.Column:
    """Build a scrollable DataTable preview of the first 50 rows.

    Args:
        df: The pandas DataFrame to preview.

    Returns:
        A Column containing the DataTable and a row count footer.
    """
    preview_df = df.head(DATA_PREVIEW_ROWS)
    total_rows = len(df)

    # Build column headers
    columns = [
        ft.DataColumn(
            ft.Text(
                str(col),
                size=tokens.FONT_XS,
                weight=ft.FontWeight.W_600,
            )
        )
        for col in preview_df.columns
    ]

    # Build data rows
    rows = []
    for _, row in preview_df.iterrows():
        cells = [
            ft.DataCell(
                ft.Text(
                    _format_cell(row[col]),
                    size=tokens.FONT_XS,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                )
            )
            for col in preview_df.columns
        ]
        rows.append(ft.DataRow(cells=cells))

    table = ft.DataTable(
        columns=columns,
        rows=rows,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
        border_radius=tokens.RADIUS_MD,
        horizontal_lines=ft.BorderSide(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
        column_spacing=tokens.SPACE_LG,
        heading_row_height=40,
        data_row_max_height=36,
    )

    # Footer showing row count
    showing = min(DATA_PREVIEW_ROWS, total_rows)
    footer_text = (
        f"Showing {showing} of {total_rows:,} rows"
        if total_rows > DATA_PREVIEW_ROWS
        else f"{total_rows:,} rows"
    )

    return ft.Column(
        controls=[
            ft.Container(
                content=ft.Row(
                    controls=[table],
                    scroll=ft.ScrollMode.AUTO,
                ),
                border_radius=tokens.RADIUS_LG,
            ),
            ft.Container(
                content=ft.Text(
                    footer_text,
                    size=tokens.FONT_XS,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    italic=True,
                ),
                padding=ft.Padding(left=tokens.SPACE_SM, top=tokens.SPACE_XS, right=0, bottom=0),
            ),
        ],
        spacing=tokens.SPACE_XS,
    )


def _format_cell(value) -> str:
    """Format a cell value for display."""
    if pd.isna(value):
        return "—"
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return f"{value:.2f}"
    s = str(value)
    return s[:40] + "…" if len(s) > 40 else s
