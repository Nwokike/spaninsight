"""Onboarding view — first-launch swipe-through explaining the platform.

Shows 3 slides explaining:
  1. Privacy-first data analysis
  2. Smart surveys for students & businesses
  3. Autopilot + export

Dismissed once → STORAGE_ONBOARDING_DONE is set.
"""

from __future__ import annotations

from typing import Callable

import flet as ft

from core import theme
from core.constants import STORAGE_ONBOARDING_DONE


def build_onboarding_view(page: ft.Page, on_done: Callable, storage=None) -> ft.View:
    """Build the onboarding swipe-through."""

    current_page = {"index": 0}
    indicator_row = ft.Ref[ft.Row]()
    slide_container = ft.Ref[ft.Container]()

    async def _launch_privacy(e):
        await ft.UrlLauncher().launch_url("https://spaninsight.com/privacy.html")

    async def _launch_terms(e):
        await ft.UrlLauncher().launch_url("https://spaninsight.com/terms.html")

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
                "complete shareable web report automatically."
            ),
        },
    ]

    def _build_slide(s: dict) -> ft.Column:
        return ft.Column(
            [
                ft.Container(height=80),
                ft.Container(
                    content=ft.Icon(s["icon"], size=64, color=s["color"]),
                    width=120,
                    height=120,
                    border_radius=60,
                    bgcolor=ft.Colors.with_opacity(0.1, s["color"]),
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Container(height=32),
                ft.Text(s["title"], size=24, weight="bold", text_align="center"),
                ft.Container(height=12),
                ft.Text(
                    s["body"],
                    size=14,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    text_align="center",
                ),
            ],
            horizontal_alignment="center",
            spacing=0,
        )

    def _build_indicators() -> list[ft.Control]:
        dots = []
        for i in range(len(slides)):
            dots.append(
                ft.Container(
                    width=10 if i == current_page["index"] else 6,
                    height=6,
                    border_radius=3,
                    bgcolor=theme.PRIMARY
                    if i == current_page["index"]
                    else ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE),
                    animate=ft.Animation(200, "easeOut"),
                )
            )
        return dots

    agree_checkbox_ref = ft.Ref[ft.Checkbox]()
    agree_container_ref = ft.Ref[ft.Container]()

    def on_agree_changed(e):
        if button_ref.current:
            button_ref.current.disabled = not e.control.value
            page.update(button_ref.current)

    button_ref = ft.Ref[ft.FilledButton]()

    def _update():
        is_last = current_page["index"] == len(slides) - 1
        if slide_container.current:
            slide_container.current.content = _build_slide(
                slides[current_page["index"]]
            )
        if indicator_row.current:
            indicator_row.current.controls = _build_indicators()
        if agree_container_ref.current:
            agree_container_ref.current.visible = is_last
        if button_ref.current:
            button_ref.current.content = "Get Started" if is_last else "Next"
            button_ref.current.icon = (
                ft.Icons.CHECK_ROUNDED if is_last else ft.Icons.ARROW_FORWARD_ROUNDED
            )
            # Disable button on last slide if checkbox is unchecked
            button_ref.current.disabled = is_last and not (
                agree_checkbox_ref.current and agree_checkbox_ref.current.value
            )
        page.update()

    def on_next(e):
        is_last = current_page["index"] == len(slides) - 1
        if is_last:
            if agree_checkbox_ref.current and not agree_checkbox_ref.current.value:
                return
            page.run_task(_finish)
        else:
            current_page["index"] += 1
            _update()

    def on_prev(e=None):
        if current_page["index"] > 0:
            current_page["index"] -= 1
            _update()

    # U2 FIX: Swipe gesture handler for mobile UX
    def on_swipe(e: ft.DragEndEvent):
        if e.primary_velocity is not None:
            if e.primary_velocity < -200:  # Swipe left → next
                on_next(e)
            elif e.primary_velocity > 200:  # Swipe right → prev
                on_prev()

    def on_skip(e):
        page.run_task(_finish)

    async def _finish():
        if storage:
            await storage.set(STORAGE_ONBOARDING_DONE, "true")
        on_done()

    is_last = current_page["index"] == len(slides) - 1

    return ft.View(
        route="/onboarding",
        controls=[
            ft.SafeArea(
                content=ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.TextButton(
                                        "Skip",
                                        on_click=on_skip,
                                        style=ft.ButtonStyle(
                                            color=ft.Colors.ON_SURFACE_VARIANT
                                        ),
                                    ),
                                ],
                                alignment="end",
                            ),
                            # U2 FIX: Wrap slide in GestureDetector for swipe navigation
                            ft.GestureDetector(
                                content=ft.Container(
                                    ref=slide_container,
                                    content=_build_slide(slides[0]),
                                    expand=True,
                                    padding=ft.Padding(32, 0, 32, 0),
                                ),
                                on_horizontal_drag_end=on_swipe,
                            ),
                            ft.Row(
                                ref=indicator_row,
                                controls=_build_indicators(),
                                alignment="center",
                                spacing=6,
                            ),
                            ft.Container(height=20),
                            # Agreement check row
                            ft.Container(
                                ref=agree_container_ref,
                                content=ft.Row(
                                    [
                                        ft.Checkbox(
                                            ref=agree_checkbox_ref,
                                            on_change=on_agree_changed,
                                            value=False,
                                        ),
                                        ft.Text("I agree to the ", size=12),
                                        ft.TextButton(
                                            "Privacy Policy",
                                            style=ft.ButtonStyle(color=theme.PRIMARY),
                                            on_click=_launch_privacy,
                                        ),
                                        ft.Text(" & ", size=12),
                                        ft.TextButton(
                                            "Terms of Service",
                                            style=ft.ButtonStyle(color=theme.PRIMARY),
                                            on_click=_launch_terms,
                                        ),
                                    ],
                                    alignment="center",
                                    spacing=0,
                                ),
                                visible=False,
                            ),
                            ft.Container(height=16),
                            ft.Container(
                                content=ft.FilledButton(
                                    "Get Started" if is_last else "Next",
                                    ref=button_ref,
                                    icon=ft.Icons.ARROW_FORWARD_ROUNDED,
                                    on_click=on_next,
                                    width=200,
                                    height=48,
                                    style=ft.ButtonStyle(
                                        bgcolor=theme.ACCENT,
                                        color=ft.Colors.WHITE,
                                        shape=ft.RoundedRectangleBorder(radius=24),
                                    ),
                                ),
                                alignment=ft.Alignment.CENTER,
                            ),
                            ft.Container(height=48),
                        ],
                        expand=True,
                    ),
                    padding=20,
                    expand=True,
                ),
                expand=True,
            )
        ],
        padding=0,
    )
