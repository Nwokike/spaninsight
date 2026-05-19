"""Splash screen — shown for 2 seconds on startup.

Displays the app icon, name, tagline, and a progress ring.
Follows the same pattern as AnimePahe TV / Nkiri TV splash.
"""

from __future__ import annotations

import flet as ft

from core import theme


def build_splash_view() -> ft.View:
    """Build the splash screen view."""
    return ft.View(
        route="/splash",
        controls=[
            ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                bgcolor=ft.Colors.SURFACE,
                content=ft.Column(
                    [
                        ft.Image(
                            src="icon.png",
                            width=100,
                            height=100,
                            border_radius=20,
                            fit="contain",
                        ),
                        ft.Container(height=16),
                        ft.Text(
                            "Spaninsight",
                            size=32,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.ON_SURFACE,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Text(
                            "Autonomous data intelligence for everyone.",
                            size=14,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Container(height=32),
                        ft.ProgressRing(
                            width=24,
                            height=24,
                            stroke_width=3,
                            color=theme.PRIMARY,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=0,
                ),
            )
        ],
        padding=0,
    )
