"""Overlay Manager - manages multiple DWM overlay windows.

Drop-in replacement for ThumbnailRenderer.  Uses a dedicated Win32 message
pump thread for all overlay windows and DWM operations.
"""

import ctypes
import ctypes.wintypes
import logging
import queue
import threading
from typing import Callable, Dict, Optional, Tuple
from PIL import Image

from screenalert_core.rendering.dwm_backend import DwmThumbnailBackend
from screenalert_core.rendering.overlay_window import OverlayWindow
from screenalert_core.utils.constants import DEFAULT_OVERLAY_UPDATE_RATE_HZ

logger = logging.getLogger(__name__)

# Win32 message constants
WM_USER = 0x0400
WM_QUIT = 0x0012
WM_APP_COMMAND = WM_USER + 100  # custom message for cross-thread commands


class OverlayManager:
    """Manages DWM-backed overlay windows.  API-compatible with ThumbnailRenderer."""

    def __init__(self, manager_callback: Callable = None, parent_root=None):
        """Initialize overlay manager.

        Args:
            manager_callback: Function to call on user interactions.
            parent_root: Ignored (Tkinter compat). Kept for API compatibility.
        """
        self.manager_callback = manager_callback
        self.parent_root = parent_root  # not used, kept for compat
        self._overlays: Dict[str, OverlayWindow] = {}
        self.running = False
        self.lock = threading.Lock()
        self._active_thumbnail_id: Optional[str] = None
        self._backend = DwmThumbnailBackend()
        self._update_rate_hz = DEFAULT_OVERLAY_UPDATE_RATE_HZ
        self._scaling_mode = "fit"

        # Command queue for cross-thread operations
        self._cmd_queue: queue.Queue = queue.Queue()

        # Message pump thread
        self._pump_thread: Optional[threading.Thread] = None
        self._pump_thread_id: Optional[int] = None
        self._pump_ready = threading.Event()

        logger.info("Overlay manager initialized (DWM backend available=%s)", self._backend.is_available())

    # ── Start / Stop ────────────────────────────────────────────────────

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._pump_thread = threading.Thread(target=self._message_pump, name="overlay-pump", daemon=True)
        self._pump_thread.start()
        self._pump_ready.wait(timeout=5.0)
        logger.info("Overlay manager started")

    def stop(self) -> None:
        self.running = False

        # Clean up all overlays
        with self.lock:
            for tid, overlay in self._overlays.items():
                try:
                    overlay.cleanup()
                except Exception:
                    logger.warning("Error cleaning up overlay %s during stop", tid, exc_info=True)
            self._overlays.clear()

        # Signal message pump to quit
        if self._pump_thread_id is not None:
            try:
                ctypes.windll.user32.PostThreadMessageW(
                    self._pump_thread_id, WM_QUIT, 0, 0
                )
            except Exception:
                logger.warning("Error posting WM_QUIT to pump thread", exc_info=True)

        if self._pump_thread and self._pump_thread.is_alive():
            self._pump_thread.join(timeout=3.0)
            if self._pump_thread.is_alive():
                logger.warning("Overlay pump thread did not exit within timeout")

        logger.info("Overlay manager stopped")

    def is_running(self) -> bool:
        return self.running

    # ── Message pump ────────────────────────────────────────────────────

    def _message_pump(self) -> None:
        """Win32 message pump running on dedicated thread."""
        self._pump_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        # Force message queue creation
        msg = ctypes.wintypes.MSG()
        ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)

        self._pump_ready.set()
        logger.debug("Overlay message pump started (thread_id=%s)", self._pump_thread_id)

        try:
            while self.running:
                # Process pending commands from other threads
                self._drain_command_queue()

                # Pump Win32 messages with timeout (10ms to stay responsive to commands)
                ret = ctypes.windll.user32.MsgWaitForMultipleObjects(
                    0, None, False, 10, 0x04FF  # QS_ALLINPUT
                )
                if ret == 0xFFFFFFFF:  # WAIT_FAILED
                    continue

                while ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                    if msg.message == WM_QUIT:
                        logger.debug("WM_QUIT received in overlay pump")
                        return
                    ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                    ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

        except Exception:
            logger.exception("Overlay message pump error")
        finally:
            self._pump_thread_id = None
            logger.debug("Overlay message pump exited")

    def _post_command(self, func: Callable, *args, **kwargs) -> None:
        """Post a command to execute on the message pump thread."""
        self._cmd_queue.put((func, args, kwargs))

    def _drain_command_queue(self) -> None:
        """Execute all pending commands on the pump thread."""
        while True:
            try:
                func, args, kwargs = self._cmd_queue.get_nowait()
                try:
                    func(*args, **kwargs)
                except Exception:
                    logger.exception("Command execution failed")
            except queue.Empty:
                break

    # ── Thumbnail management (public API) ───────────────────────────────

    def add_thumbnail(self, thumbnail_id: str, config: Dict) -> bool:
        with self.lock:
            if thumbnail_id in self._overlays:
                logger.warning("Overlay %s already exists", thumbnail_id)
                return False

        def _create():
            try:
                overlay = OverlayWindow(
                    thumbnail_id=thumbnail_id,
                    config=config,
                    backend=self._backend,
                    manager_callback=self.manager_callback,
                    owner_manager=self,
                )
                overlay.set_scaling_mode(self._scaling_mode)
                interval_ms = max(16, int(1000 / max(1, self._update_rate_hz)))
                overlay.start_update_timer(interval_ms)
                with self.lock:
                    self._overlays[thumbnail_id] = overlay
                logger.info("Added overlay: %s", thumbnail_id)
            except Exception:
                logger.exception("Error adding overlay %s", thumbnail_id)

        self._post_command(_create)
        return True

    def remove_thumbnail(self, thumbnail_id: str) -> bool:
        with self.lock:
            overlay = self._overlays.pop(thumbnail_id, None)
            if not overlay:
                return False
            if self._active_thumbnail_id == thumbnail_id:
                self._active_thumbnail_id = None

        def _destroy():
            try:
                overlay.cleanup()
            except Exception:
                logger.warning("Error cleaning up overlay %s during removal", thumbnail_id, exc_info=True)

        self._post_command(_destroy)
        logger.info("Removed overlay: %s", thumbnail_id)
        return True

    def set_source_hwnd(self, thumbnail_id: str, hwnd: int) -> None:
        """Update the source window handle for DWM thumbnail registration."""
        with self.lock:
            overlay = self._overlays.get(thumbnail_id)
            if not overlay:
                logger.debug("set_source_hwnd: overlay %s not found", thumbnail_id)
                return

        def _set():
            overlay.set_source_hwnd(hwnd)

        self._post_command(_set)

    def update_thumbnail_image(self, thumbnail_id: str, image: Image.Image) -> bool:
        """No-op for DWM overlay manager. Kept for API compatibility."""
        return thumbnail_id in self._overlays

    # ── Availability / visibility ───────────────────────────────────────

    def set_thumbnail_availability(self, thumbnail_id: str, available: bool,
                                   show_when_unavailable: bool = False) -> bool:
        with self.lock:
            overlay = self._overlays.get(thumbnail_id)
            if not overlay:
                logger.debug("set_thumbnail_availability: overlay %s not found", thumbnail_id)
                return False

        def _set():
            overlay.set_availability(available, show_when_unavailable)

        self._post_command(_set)
        return True

    def set_thumbnail_user_visibility(self, thumbnail_id: str, visible: bool) -> bool:
        with self.lock:
            overlay = self._overlays.get(thumbnail_id)
            if not overlay:
                logger.debug("set_thumbnail_user_visibility: overlay %s not found", thumbnail_id)
                return False

        def _set():
            overlay.set_user_visibility(visible)

        self._post_command(_set)
        return True

    def set_all_thumbnail_user_visibility(self, visible: bool) -> None:
        with self.lock:
            overlays = list(self._overlays.values())

        def _set():
            for o in overlays:
                o.set_user_visibility(bool(visible))

        self._post_command(_set)

    def refresh_unavailable_thumbnails(self, show_when_unavailable: bool) -> None:
        with self.lock:
            unavailable = [o for o in self._overlays.values() if not o._is_available]

        def _set():
            for o in unavailable:
                o.set_availability(False, show_when_unavailable)

        self._post_command(_set)

    # ── Batch settings ──────────────────────────────────────────────────

    def set_all_thumbnail_opacity(self, opacity: float) -> None:
        with self.lock:
            overlays = list(self._overlays.values())

        def _set():
            for o in overlays:
                o.set_opacity(opacity)

        self._post_command(_set)

    def set_all_thumbnail_topmost(self, on_top: bool) -> None:
        with self.lock:
            overlays = list(self._overlays.values())

        def _set():
            for o in overlays:
                o.set_topmost(on_top)

        self._post_command(_set)

    def set_all_thumbnail_borders(self, show_borders: bool) -> None:
        with self.lock:
            overlays = list(self._overlays.values())

        def _set():
            for o in overlays:
                o.set_show_border(show_borders)

        self._post_command(_set)

    def set_all_thumbnail_scaling_mode(self, mode: str) -> None:
        self._scaling_mode = mode
        with self.lock:
            overlays = list(self._overlays.values())

        def _set():
            for o in overlays:
                o.set_scaling_mode(mode)

        self._post_command(_set)

    # ── Active window border ────────────────────────────────────────────

    def set_active_thumbnail(self, thumbnail_id: str, bring_to_front: bool = True) -> None:
        with self.lock:
            if thumbnail_id not in self._overlays:
                logger.debug("set_active_thumbnail: overlay %s not found", thumbnail_id)
                return
            previous_id = self._active_thumbnail_id
            if previous_id == thumbnail_id and not bring_to_front:
                return
            self._active_thumbnail_id = thumbnail_id
            overlays_snapshot = dict(self._overlays)

        def _set():
            if bring_to_front:
                active = overlays_snapshot.get(thumbnail_id)
                if active:
                    active.lift()

            if previous_id == thumbnail_id:
                return

            for tid, overlay in overlays_snapshot.items():
                overlay.set_active_border(tid == thumbnail_id)

        self._post_command(_set)

    def clear_active_thumbnail(self) -> None:
        with self.lock:
            if self._active_thumbnail_id is None:
                return
            self._active_thumbnail_id = None
            overlays_snapshot = list(self._overlays.values())

        def _set():
            for overlay in overlays_snapshot:
                overlay.set_active_border(False)

        self._post_command(_set)

    # ── Title ───────────────────────────────────────────────────────────

    def refresh_thumbnail_titles(self) -> None:
        with self.lock:
            overlays = list(self._overlays.values())

        def _set():
            for o in overlays:
                o.refresh_title()

        self._post_command(_set)

    # ── Info / misc ─────────────────────────────────────────────────────

    def get_all_thumbnail_geometries(self) -> Dict[str, Dict[str, int]]:
        with self.lock:
            return {
                tid: {"x": o.x, "y": o.y, "width": o.width, "height": o.height}
                for tid, o in self._overlays.items()
            }

    def is_thumbnail_visible(self, thumbnail_id: str) -> Optional[bool]:
        with self.lock:
            overlay = self._overlays.get(thumbnail_id)
            if not overlay:
                return None
            return overlay.is_visible()

    def get_thumbnail(self, thumbnail_id: str) -> Optional[OverlayWindow]:
        return self._overlays.get(thumbnail_id)

    # ── Update rate ─────────────────────────────────────────────────────

    def set_update_rate(self, hz: int) -> None:
        """Change the DWM property update rate for all overlays."""
        self._update_rate_hz = max(10, min(60, hz))
        interval_ms = max(16, int(1000 / self._update_rate_hz))

        with self.lock:
            overlays = list(self._overlays.values())

        def _set():
            for o in overlays:
                o.stop_update_timer()
                o.start_update_timer(interval_ms)

        self._post_command(_set)
