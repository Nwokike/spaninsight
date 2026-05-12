"""Onboarding view — first-launch swipe-through explaining the platform.

Shows 3 slides explaining:
  1. Privacy-first data analysis
  2. Smart surveys for students & businesses
  3. Autopilot + export

Dismissed once → STORAGE_ONBOARDING_DONE is set.
"""

from __future__ import annotations

import flet as ft

from core import theme, tokens
from core.constants import STORAGE_ONBOARDING_DONE
from flet_secure_storage import SecureStorage


def build_onboarding_view(page: ft.Page, on_done: callable) -> ft.View:
    """Build the onboarding swipe-through."""

    current_page = {"index": 0}
    indicator_row = ft.Ref[ft.Row]()
    slide_container = ft.Ref[ft.Container]()

    slides = [
        {
            "icon": ft.Icons.SHIELD_ROUNDED,
            "color": theme.SUCCESS,
            "title": "100% Privacy-First",
            "body": (
                "Your data never leaves your device. "
                "All analysis runs locally — only AI prompts "
                "touch the cloud, never your raw data."
            ),
        },
        {
            "icon": ft.Icons.SCHOOL_ROUNDED,
            "color": theme.PRIMARY,
            "title": "Built for Everyone",
            "body": (
                "Whether you're a student writing Chapter 4, a small business "
                "tracking customers, or just exploring data — Spaninsight "
                "makes AI-powered analysis accessible to all."
            ),
        },
        {
            "icon": ft.Icons.ROCKET_LAUNCH_ROUNDED,
            "color": theme.ACCENT,
            "title": "Autopilot Mode",
            "body": (
                "One tap — AI analyzes your data from multiple angles, "
                "generates charts with descriptions, and builds a "
                "complete PDF or PowerPoint report automatically."
            ),
        },
    ]

    def _build_slide(s: dict) -> ft.Column:
        return ft.Column([
            ft.Container(height=80),
            ft.Container(
                content=ft.Icon(s["icon"], size=64, color=s["color"]),
                width=120, height=120, border_radius=60,
                bgcolor=ft.Colors.with_opacity(0.1, s["color"]),
                alignment=ft.Alignment.CENTER,
            ),
            ft.Container(height=32),
            ft.Text(s["title"], size=24, weight="bold", text_align="center"),
            ft.Container(height=12),
            ft.Text(
                s["body"], size=14,
                color=ft.Colors.ON_SURFACE_VARIANT,
                text_align="center",
            ),
        ], horizontal_alignment="center", spacing=0)

    def _build_indicators() -> list[ft.Control]:
        dots = []
        for i in range(len(slides)):
            dots.append(ft.Container(
                width=10 if i == current_page["index"] else 6,
                height=6,
                border_radius=3,
                bgcolor=theme.PRIMARY if i == current_page["index"] else ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE),
                animate=ft.Animation(200, "easeOut"),
            ))
        return dots

    def _update():
        if slide_container.current:
            slide_container.current.content = _build_slide(slides[current_page["index"]])
        if indicator_row.current:
            indicator_row.current.controls = _build_indicators()
        page.update()

    def on_next(e):
        if current_page["index"] < len(slides) - 1:
            current_page["index"] += 1
            _update()
        else:
            page.run_task(_finish)

    def on_skip(e):
        page.run_task(_finish)

    async def _finish():
        storage = SecureStorage()
        await storage.set(STORAGE_ONBOARDING_DONE, "true")
        on_done()

    is_last = current_page["index"] == len(slides) - 1

    return ft.View(
        route="/onboarding",
        controls=[
            ft.Column([
                ft.Row([
                    ft.TextButton("Skip", on_click=on_skip,
                                  style=ft.ButtonStyle(color=ft.Colors.ON_SURFACE_VARIANT)),
                ], alignment="end"),
                ft.Container(
                    ref=slide_container,
                    content=_build_slide(slides[0]),
                    expand=True,
                    padding=ft.Padding(32, 0, 32, 0),
                ),
                ft.Row(ref=indicator_row, controls=_build_indicators(),
                       alignment="center", spacing=6),
                ft.Container(height=24),
                ft.Container(
                    content=ft.Button(
                        "Get Started" if is_last else "Next",
                        icon=ft.Icons.ARROW_FORWARD_ROUNDED,
                        on_click=on_next,
                        width=200, height=48,
                        style=ft.ButtonStyle(
                            bgcolor=theme.PRIMARY,
                            color=ft.Colors.WHITE,
                            shape=ft.RoundedRectangleBorder(radius=24),
                        ),
                    ),
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Container(height=48),
            ], expand=True),
        ],
        padding=0,
    )
