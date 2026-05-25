import asyncio
import logging
import flet as ft

from core.state import state
from core import theme
from services import file_service
from .base import show_error

logger = logging.getLogger(__name__)


def on_clear_data(view_state, e):
    import matplotlib.pyplot as plt

    plt.close("all")
    state.clear_data()
    state.analysis_blocks.clear()
    view_state.rebuild()


async def on_export_data(view_state):
    if state.current_df is None:
        show_error(view_state, "No active dataset to export.")
        return

    view_state.page.snack_bar = ft.SnackBar(
        ft.Text("Preparing dataset export..."), duration=2000
    )
    view_state.page.snack_bar.open = True
    view_state.page.update()

    try:
        if view_state.page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS):
            try:
                import flet_ads as fta

                async def _show_ad(e):
                    await e.control.show()

                # Instantiate service in-memory. DO NOT append to page.overlay.
                fta.InterstitialAd(
                    unit_id="ca-app-pub-5679949845754640/6965536622",
                    on_load=lambda e: view_state.page.run_task(_show_ad, e),
                    on_error=lambda e: logger.error(
                        "Export Interstitial error: %s", e.data
                    ),
                )
            except Exception as ad_err:
                logger.error("Export Interstitial trigger failed: %s", ad_err)

        csv_bytes = await asyncio.to_thread(
            file_service.df_to_csv_bytes, state.current_df
        )

        base_name = state.current_df_name or "cleaned_dataset"
        if base_name.lower().endswith(".csv"):
            suggested_name = base_name.replace(".csv", "_cleaned.csv")
        elif base_name.lower().endswith(".xlsx"):
            suggested_name = base_name.replace(".xlsx", "_cleaned.csv")
        elif base_name.lower().endswith(".json"):
            suggested_name = base_name.replace(".json", "_cleaned.csv")
        else:
            suggested_name = f"{base_name}_cleaned.csv"

        res = await view_state.file_picker_svc.save_file_async(
            file_name=suggested_name,
            allowed_extensions=["csv"],
            src_bytes=csv_bytes,
        )

        if res:
            view_state.page.snack_bar = ft.SnackBar(
                ft.Text("✓ Cleaned dataset saved successfully!"),
                bgcolor=theme.SUCCESS,
                duration=3000,
            )
        else:
            view_state.page.snack_bar = ft.SnackBar(
                ft.Text("Save cancelled by user."),
                duration=2000,
            )
        view_state.page.snack_bar.open = True
        view_state.page.update()

    except Exception as e:
        logger.error("Failed to export dataset: %s", e)
        show_error(view_state, f"Export failed: {e}")
