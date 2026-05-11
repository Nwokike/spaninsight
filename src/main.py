"""Spaninsight — Privacy-First Data Intelligence.

Main entry point. Handles page config, NavigationBar, routing,
UUID initialization, and service bootstrapping.

Architecture mirrors Akili flet-rewrite (production) patterns:
- page.route = route (direct assignment, not push_route)
- @ft.observable state singleton
- view builder functions
"""

from __future__ import annotations

import asyncio
import logging
import sys

import flet as ft

from core.theme import AppTheme
from core.state import state
from services.uuid_service import UUIDService
from services.credit_service import CreditService
from services.ad_service import AdService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("spaninsight")

# Fix Windows event loop policy
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main(page: ft.Page):
    """Main Flet application entry point."""

    # ── Page Configuration ──────────────────────────────────────────
    page.title = "Spaninsight"
    page.favicon = "icon.png"

    page.fonts = {
        "Outfit": "https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap"
    }

    page.theme = AppTheme.get_light_theme()
    page.dark_theme = AppTheme.get_dark_theme()
    page.theme.font_family = "Outfit"
    page.dark_theme.font_family = "Outfit"
    page.theme_mode = ft.ThemeMode.LIGHT
    state.theme_mode = page.theme_mode

    # Desktop window sizing
    page.window.width = 420
    page.window.height = 820
    page.window.min_width = 360
    page.window.min_height = 600

    page.padding = 0
    page.spacing = 0

    # ── Error Handler ───────────────────────────────────────────────
    def on_error(e):
        logger.error("Page error: %s", e.data)
        page.snack_bar = ft.SnackBar(
            content=ft.Text("Something went wrong. Please try again.", color=ft.Colors.WHITE),
            bgcolor=ft.Colors.BLACK,
        )
        page.snack_bar.open = True
        page.update()

    page.on_error = on_error

    # ── Initialize Services ─────────────────────────────────────────
    uuid_service = UUIDService(page)
    credit_service = CreditService(page)
    ad_service = AdService(page)

    # Generate or load UUID
    state.user_uuid = await uuid_service.get_or_create_uuid()
    logger.info("User UUID: %s", uuid_service.get_masked_uuid(state.user_uuid))

    # Initialize credits (daily reset)
    state.credits_remaining = await credit_service.initialize()

    # Preload interstitial ad
    page.run_task(ad_service.preload_interstitial)

    # ── Navigation Bar ──────────────────────────────────────────────
    nav_bar = ft.NavigationBar(
        selected_index=0,
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.HOME_OUTLINED,
                selected_icon=ft.Icons.HOME_ROUNDED,
                label="Home",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.ANALYTICS_OUTLINED,
                selected_icon=ft.Icons.ANALYTICS_ROUNDED,
                label="Analysis",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.DYNAMIC_FORM_OUTLINED,
                selected_icon=ft.Icons.DYNAMIC_FORM_ROUNDED,
                label="Forms",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.SETTINGS_OUTLINED,
                selected_icon=ft.Icons.SETTINGS_ROUNDED,
                label="Settings",
            ),
        ],
        bgcolor=ft.Colors.SURFACE,
        indicator_color=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
        label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
    )

    # Tab routes mapping
    TAB_ROUTES = ["/home", "/analysis", "/forms", "/settings"]

    # ── Navigation Helpers ──────────────────────────────────────────
    async def navigate(route: str):
        """Navigate to a route — Akili pattern (direct assignment)."""
        page.route = route
        await route_change()

    def on_import_file(e):
        """Trigger file import — switch to analysis tab."""
        nav_bar.selected_index = 1
        state.current_tab = 1
        state.trigger_file_picker = True
        page.run_task(navigate, "/analysis")

    def on_nav_change(e):
        """Handle NavigationBar tab change."""
        index = e.control.selected_index
        state.current_tab = index
        page.run_task(navigate, TAB_ROUTES[index])

    nav_bar.on_change = on_nav_change

    def nav_to(route: str):
        """Navigation callback for child views."""
        page.run_task(navigate, route)

    # ── Route Change Handler ────────────────────────────────────────
    async def route_change(e=None):
        route = page.route
        logger.info("Route: %s", route)

        page.views.clear()

        if route == "/home" or route == "/":
            from views.home_view import build_home_view

            view = build_home_view(
                page=page,
                on_import_file=on_import_file,
                on_navigate=nav_to,
            )
            page.views.append(view)
            nav_bar.selected_index = 0

        elif route == "/analysis":
            from views.analysis_view import build_analysis_view

            view = build_analysis_view(
                page=page,
                credit_service=credit_service,
            )
            page.views.append(view)
            nav_bar.selected_index = 1

        elif route == "/forms":
            from views.forms_view import build_forms_view

            view = build_forms_view(page=page)
            page.views.append(view)
            nav_bar.selected_index = 2

        elif route == "/settings":
            from views.settings_view import build_settings_view

            view = build_settings_view(
                page=page,
                uuid_service=uuid_service,
                credit_service=credit_service,
            )
            page.views.append(view)
            nav_bar.selected_index = 3

        elif route == "/report":
            from views.report_view import build_report_view

            view = build_report_view(
                page=page,
                on_back=lambda: nav_to("/analysis"),
            )
            page.views.append(view)

        else:
            from views.home_view import build_home_view

            view = build_home_view(
                page=page,
                on_import_file=on_import_file,
                on_navigate=nav_to,
            )
            page.views.append(view)

        # Attach nav bar to the current view (except report)
        if route != "/report" and page.views:
            page.views[-1].navigation_bar = nav_bar

        page.update()

    # ── View Pop Handler ────────────────────────────────────────────
    async def view_pop(e):
        page.views.pop()
        if page.views:
            top = page.views[-1]
            page.route = top.route
        page.update()

    # ── Register Handlers ───────────────────────────────────────────
    page.on_route_change = route_change
    page.on_view_pop = view_pop

    # ── Initial Route ───────────────────────────────────────────────
    await navigate("/home")


# ── Entry Point ─────────────────────────────────────────────────────
if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
