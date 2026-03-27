"""DWM Thumbnail Backend - abstract interface and Windows DWM implementation.

Provides hardware-accelerated, OS-composited live window previews via the
Desktop Window Manager (DWM) Thumbnail API.
"""

import ctypes
import ctypes.wintypes
import logging
from abc import ABC, abstractmethod
from typing import Any, Tuple

logger = logging.getLogger(__name__)

# ── DWM constants ────────────────────────────────────────────────────────

DWM_TNP_RECTDESTINATION = 0x00000001
DWM_TNP_RECTSOURCE = 0x00000002
DWM_TNP_OPACITY = 0x00000004
DWM_TNP_VISIBLE = 0x00000008
DWM_TNP_SOURCECLIENTAREAONLY = 0x00000010

# ── ctypes structures ────────────────────────────────────────────────────

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class SIZE(ctypes.Structure):
    _fields_ = [
        ("cx", ctypes.c_long),
        ("cy", ctypes.c_long),
    ]


class DWM_THUMBNAIL_PROPERTIES(ctypes.Structure):
    _fields_ = [
        ("dwFlags", ctypes.c_ulong),
        ("rcDestination", RECT),
        ("rcSource", RECT),
        ("opacity", ctypes.c_ubyte),
        ("fVisible", ctypes.c_bool),
        ("fSourceClientAreaOnly", ctypes.c_bool),
    ]


# ── Abstract interface ───────────────────────────────────────────────────

class ThumbnailBackend(ABC):
    """Abstract interface for thumbnail compositing backends."""

    @abstractmethod
    def register(self, dest_hwnd: int, source_hwnd: int) -> Any:
        """Create a live thumbnail link. Returns backend-specific handle."""

    @abstractmethod
    def unregister(self, handle: Any) -> None:
        """Destroy a thumbnail link."""

    @abstractmethod
    def update_properties(
        self,
        handle: Any,
        *,
        dest_rect: Tuple[int, int, int, int],
        opacity: int = 255,
        visible: bool = True,
        source_client_only: bool = True,
    ) -> None:
        """Update thumbnail display properties.

        Args:
            handle: Backend-specific thumbnail handle.
            dest_rect: (left, top, right, bottom) in dest window coordinates.
            opacity: 0-255.
            visible: Show/hide the thumbnail.
            source_client_only: If True, show only the client area (no title bar).
        """

    @abstractmethod
    def query_source_size(self, handle: Any) -> Tuple[int, int]:
        """Return (width, height) of the source window."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is functional on the current system."""


# ── DWM implementation ───────────────────────────────────────────────────

class DwmThumbnailBackend(ThumbnailBackend):
    """DWM Thumbnail API backend via ctypes."""

    def __init__(self):
        try:
            self._dwmapi = ctypes.windll.dwmapi

            # DwmRegisterThumbnail(HWND dest, HWND src, PHTHUMBNAIL *phThumb) -> HRESULT
            self._dwmapi.DwmRegisterThumbnail.argtypes = [
                ctypes.wintypes.HWND,
                ctypes.wintypes.HWND,
                ctypes.POINTER(ctypes.c_void_p),
            ]
            self._dwmapi.DwmRegisterThumbnail.restype = ctypes.HRESULT

            # DwmUnregisterThumbnail(HTHUMBNAIL hThumb) -> HRESULT
            self._dwmapi.DwmUnregisterThumbnail.argtypes = [ctypes.c_void_p]
            self._dwmapi.DwmUnregisterThumbnail.restype = ctypes.HRESULT

            # DwmUpdateThumbnailProperties(HTHUMBNAIL, const DWM_THUMBNAIL_PROPERTIES*) -> HRESULT
            self._dwmapi.DwmUpdateThumbnailProperties.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(DWM_THUMBNAIL_PROPERTIES),
            ]
            self._dwmapi.DwmUpdateThumbnailProperties.restype = ctypes.HRESULT

            # DwmQueryThumbnailSourceSize(HTHUMBNAIL, PSIZE) -> HRESULT
            self._dwmapi.DwmQueryThumbnailSourceSize.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(SIZE),
            ]
            self._dwmapi.DwmQueryThumbnailSourceSize.restype = ctypes.HRESULT

            self._available = True
            logger.info("DWM thumbnail backend initialized")
        except Exception as e:
            self._available = False
            logger.error("DWM thumbnail backend unavailable: %s", e, exc_info=True)

    # ── ThumbnailBackend interface ──────────────────────────────────────

    def is_available(self) -> bool:
        return self._available

    def register(self, dest_hwnd: int, source_hwnd: int) -> Any:
        """Register a DWM thumbnail. Returns an opaque handle (c_void_p value)."""
        if not dest_hwnd or not source_hwnd:
            raise ValueError(f"Invalid hwnd: dest={dest_hwnd}, source={source_hwnd}")

        logger.debug("DWM register: dest=%s src=%s", dest_hwnd, source_hwnd)
        thumb_handle = ctypes.c_void_p()
        hr = self._dwmapi.DwmRegisterThumbnail(
            ctypes.wintypes.HWND(dest_hwnd),
            ctypes.wintypes.HWND(source_hwnd),
            ctypes.byref(thumb_handle),
        )
        if hr < 0:
            raise OSError(
                f"DwmRegisterThumbnail failed: HRESULT 0x{hr & 0xFFFFFFFF:08X} "
                f"(dest={dest_hwnd}, src={source_hwnd})"
            )
        logger.debug("DWM thumbnail registered: dest=%s src=%s handle=%s",
                      dest_hwnd, source_hwnd, thumb_handle.value)
        return thumb_handle.value

    def unregister(self, handle: Any) -> None:
        if handle is None:
            return
        try:
            logger.debug("DWM unregister: handle=%s", handle)
            hr = self._dwmapi.DwmUnregisterThumbnail(ctypes.c_void_p(handle))
            if hr < 0:
                logger.warning("DwmUnregisterThumbnail failed: HRESULT 0x%08X (handle=%s)",
                               hr & 0xFFFFFFFF, handle)
            else:
                logger.debug("DWM thumbnail unregistered: handle=%s", handle)
        except Exception as e:
            logger.warning("DwmUnregisterThumbnail exception: %s (handle=%s)", e, handle)

    def update_properties(
        self,
        handle: Any,
        *,
        dest_rect: Tuple[int, int, int, int],
        opacity: int = 255,
        visible: bool = True,
        source_client_only: bool = True,
    ) -> None:
        if handle is None:
            raise ValueError("Cannot update properties: handle is None")

        props = DWM_THUMBNAIL_PROPERTIES()
        props.dwFlags = (
            DWM_TNP_RECTDESTINATION
            | DWM_TNP_OPACITY
            | DWM_TNP_VISIBLE
            | DWM_TNP_SOURCECLIENTAREAONLY
        )
        props.rcDestination.left = dest_rect[0]
        props.rcDestination.top = dest_rect[1]
        props.rcDestination.right = dest_rect[2]
        props.rcDestination.bottom = dest_rect[3]
        props.opacity = max(0, min(255, opacity))
        props.fVisible = visible
        props.fSourceClientAreaOnly = source_client_only

        hr = self._dwmapi.DwmUpdateThumbnailProperties(
            ctypes.c_void_p(handle), ctypes.byref(props)
        )
        if hr < 0:
            raise OSError(
                f"DwmUpdateThumbnailProperties failed: HRESULT 0x{hr & 0xFFFFFFFF:08X} "
                f"(handle={handle}, rect={dest_rect})"
            )
        logger.debug("DWM properties updated: handle=%s rect=%s opacity=%s",
                      handle, dest_rect, opacity)

    def query_source_size(self, handle: Any) -> Tuple[int, int]:
        if handle is None:
            raise ValueError("Cannot query source size: handle is None")

        size = SIZE()
        hr = self._dwmapi.DwmQueryThumbnailSourceSize(
            ctypes.c_void_p(handle), ctypes.byref(size)
        )
        if hr < 0:
            raise OSError(
                f"DwmQueryThumbnailSourceSize failed: HRESULT 0x{hr & 0xFFFFFFFF:08X} "
                f"(handle={handle})"
            )
        logger.debug("DWM source size: handle=%s size=(%s, %s)", handle, size.cx, size.cy)
        return (size.cx, size.cy)
