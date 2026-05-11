"""Camera capture service.

Wraps ``flet-camera`` to provide a simple capture-photo flow.
Returns raw image bytes for vision AI input.

Based on FletBot's production camera pattern.
On platforms without camera support (desktop) this is a no-op.
"""

from __future__ import annotations

import logging

import flet as ft

logger = logging.getLogger(__name__)

_HAS_CAMERA = False
try:
    from flet_camera import Camera
    from flet_camera.types import ResolutionPreset

    _HAS_CAMERA = True
except ImportError:
    pass


class CameraService:
    """Camera capture helper.

    On platforms without camera support (desktop) this is a no-op that
    returns ``None``.
    """

    def __init__(self, page: ft.Page):
        self._page = page

    @property
    def available(self) -> bool:
        return _HAS_CAMERA

    async def capture_photo(self) -> tuple[bytes, str] | None:
        """Capture a photo and return ``(raw_bytes, mime_type)`` or None.

        Opens the camera, takes a single image, and returns its data.
        """
        if not _HAS_CAMERA:
            logger.info("Camera not available on this platform")
            self._page.snack_bar = ft.SnackBar(
                content=ft.Text("Camera is not available on desktop")
            )
            self._page.snack_bar.open = True
            self._page.update()
            return None

        camera = None
        try:
            camera = Camera()
            self._page.overlay.append(camera)
            self._page.update()

            # Get available cameras and use the first one
            cameras = await camera.get_available_cameras()
            if not cameras:
                self._page.snack_bar = ft.SnackBar(
                    content=ft.Text("No cameras found")
                )
                self._page.snack_bar.open = True
                self._page.update()
                return None

            # Initialize with first camera at medium resolution
            await camera.initialize(
                description=cameras[0],
                resolution_preset=ResolutionPreset.MEDIUM,
                enable_audio=False,
            )

            # Capture — returns bytes directly
            image_bytes = await camera.take_picture()

            if image_bytes:
                logger.info("Camera captured %d bytes", len(image_bytes))
                return (image_bytes, "image/jpeg")

        except Exception as e:
            logger.error("Camera capture failed: %s", e)
            self._page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Camera error: {e}")
            )
            self._page.snack_bar.open = True
            self._page.update()
        finally:
            # Cleanup
            if camera:
                try:
                    if camera in self._page.overlay:
                        self._page.overlay.remove(camera)
                    self._page.update()
                except Exception:
                    pass

        return None
