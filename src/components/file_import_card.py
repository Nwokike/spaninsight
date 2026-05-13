"""File import card — dashed upload area with FilePicker integration."""

from __future__ import annotations

import flet as ft

from core import theme, tokens


def build_file_import_card(
    on_pick: callable,
    is_loading: bool = False,
) -> ft.Container:
    """Build the file import upload area.

    Args:
        on_pick: Callback when the upload area is tapped (triggers FilePicker).
        is_loading: Show a loading indicator instead of the upload prompt.
    """
    if is_loading:
        content = ft.Column(
            controls=[
                ft.ProgressRing(width=40, height=40, stroke_width=3),
                ft.Text(
                    "Loading data...",
                    size=tokens.FONT_MD,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_LG,
        )
    else:
        content = ft.Column(
            controls=[
                ft.Container(
                    content=ft.Icon(
                        ft.Icons.UPLOAD_FILE_ROUNDED,
                        size=tokens.ICON_XXL,
                        color=theme.PRIMARY_LIGHT,
                    ),
                    width=80,
                    height=80,
                    border_radius=tokens.RADIUS_XXL,
                    bgcolor=ft.Colors.with_opacity(0.08, theme.PRIMARY),
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Text(
                    "Import CSV or Excel",
                    size=tokens.FONT_LG,
                    weight=ft.FontWeight.W_600,
                ),
                ft.Text(
                    "Tap to select a file (max 100 MB)",
                    size=tokens.FONT_SM,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                ft.Container(height=tokens.SPACE_SM),
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Text(
                                ext,
                                size=tokens.FONT_XXS,
                                color=theme.ACCENT,
                                weight=ft.FontWeight.W_500,
                            ),
                            padding=ft.Padding(
                                left=tokens.SPACE_SM,
                                right=tokens.SPACE_SM,
                                top=tokens.SPACE_XXS,
                                bottom=tokens.SPACE_XXS,
                            ),
                            border_radius=tokens.RADIUS_SM,
                            bgcolor=ft.Colors.with_opacity(0.1, theme.ACCENT),
                        )
                        for ext in [".csv", ".xlsx", ".xls"]
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=tokens.SPACE_SM,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_SM,
        )

    return ft.Container(
        content=content,
        padding=tokens.SPACE_XXXL,
        border_radius=tokens.RADIUS_XL,
        border=ft.Border.all(
            2,
            ft.Colors.with_opacity(0.2, theme.PRIMARY),
        ),
        bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.WHITE),
        alignment=ft.Alignment.CENTER,
        on_click=on_pick if not is_loading else None,
        ink=not is_loading,
        animate=ft.Animation(tokens.ANIM_DEFAULT_MS, ft.AnimationCurve.EASE_OUT),
    )
