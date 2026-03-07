"""Adapter that exposes the ThumbnailRenderer API but delegates to the external overlay plugin.

This allows the main application to offload overlays to the `screenalert-plugin-overlay`
package while keeping the existing engine calls unchanged.
"""
import os
import sys
import threading
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Ensure plugin package path is discoverable (assume sibling directory)
HERE = os.path.abspath(os.path.dirname(__file__))
DEFAULT_PLUGIN_DIR = os.path.abspath(os.path.join(HERE, '..', '..', 'screenalert-plugin-overlay'))



class OverlayAdapter:
    """Minimal adapter providing the parts of ThumbnailRenderer used by the engine."""

    def __init__(self, manager_callback=None, parent_root=None, screenalert_root: Optional[str] = None):
        # Attempt to import overlay_plugin from candidate paths.
        self.plugin = None
        candidate_dirs = []
        if screenalert_root:
            candidate_dirs.append(os.path.abspath(screenalert_root))
        # default sibling path
        candidate_dirs.append(DEFAULT_PLUGIN_DIR)

        imported = False
        for candidate in candidate_dirs:
            if not candidate:
                continue
            if os.path.isdir(candidate):
                try:
                    if candidate not in sys.path:
                        sys.path.insert(0, candidate)
                    # import overlay_plugin dynamically
                    import importlib
                    mod = importlib.import_module('overlay_plugin')
                    OverlayPluginClass = getattr(mod, 'OverlayPlugin', None)
                    if OverlayPluginClass:
                        try:
                            # Determine what to pass as screenalert_root to the plugin.
                            # If the candidate path looks like a ScreenAlert repo (contains tools/native_dwm_demo.py),
                            # pass it through. If it's the plugin package directory, let the plugin use its default
                            # (which locates the ScreenAlert repo as a sibling) by passing None.
                            candidate_demo = os.path.join(candidate, 'tools', 'native_dwm_demo.py')
                            inst_root = candidate if os.path.exists(candidate_demo) else None
                            if inst_root:
                                self.plugin = OverlayPluginClass(screenalert_root=inst_root)
                            else:
                                # let plugin pick default ScreenAlert location
                                self.plugin = OverlayPluginClass()
                            imported = True
                            logger.info(f"Overlay plugin loaded from {candidate}")
                            break
                        except Exception as e:
                            logger.exception(f"OverlayPlugin instantiation failed from {candidate}: {e}")
                except Exception:
                    logger.debug(f"overlay_plugin not importable from {candidate}")
                finally:
                    # remove candidate from sys.path if we inserted it
                    try:
                        if sys.path and sys.path[0] == candidate:
                            sys.path.pop(0)
                    except Exception:
                        pass

        if not imported:
            logger.warning('Overlay plugin not available; overlay features will be disabled. Proceeding with no-op adapter.')
        self.manager_callback = manager_callback
        self.parent_root = parent_root
        self._lock = threading.Lock()
        # track simple geometry/config per thumbnail id
        self._thumbnails: Dict[str, Dict] = {}

    # Lifecycle
    def start(self):
        # plugin doesn't need explicit start for subprocess-based overlays
        logger.debug('OverlayAdapter started')

    def stop(self):
        try:
            self.plugin.stop_all()
        except Exception:
            pass

    # Thumbnail management API expected by engine
    def add_thumbnail(self, thumbnail_id: str, config: Dict) -> bool:
        title = config.get('window_title') or config.get('title') or thumbnail_id
        with self._lock:
            self._thumbnails[thumbnail_id] = {
                'x': config.get('position', {}).get('x', 100),
                'y': config.get('position', {}).get('y', 100),
                'width': config.get('size', {}).get('width', 320),
                'height': config.get('size', {}).get('height', 240),
                'config': config,
                'overlay_id': None,
            }

        if self.plugin is None:
            logger.debug(f"Plugin missing: registered thumbnail metadata for {thumbnail_id} but no overlay started")
            return False

        try:
            overlay_id = self.plugin.start_overlay(title=title, name=thumbnail_id)
            with self._lock:
                self._thumbnails[thumbnail_id]['overlay_id'] = overlay_id
            return True
        except Exception as e:
            logger.error(f"Failed to add overlay thumbnail {thumbnail_id}: {e}")
            return False

    def remove_thumbnail(self, thumbnail_id: str) -> bool:
        with self._lock:
            meta = self._thumbnails.get(thumbnail_id)
        if not meta:
            return False
        try:
            if self.plugin is not None:
                oid = meta.get('overlay_id') or thumbnail_id
                try:
                    self.plugin.stop_overlay(oid)
                except Exception:
                    logger.debug(f"Error stopping overlay {thumbnail_id} during remove")
        except Exception:
            pass
        with self._lock:
            self._thumbnails.pop(thumbnail_id, None)
        return True

    def set_thumbnail_user_visibility(self, thumbnail_id: str, visible: bool) -> None:
        # Plugin overlays run in separate processes; visibility control isn't supported yet.
        # As a basic behavior: stop the overlay when hidden, start when shown.
        with self._lock:
            meta = self._thumbnails.get(thumbnail_id)
        if not meta:
            return
        if self.plugin is None:
            logger.debug(f"Plugin missing: visibility change for {thumbnail_id} ignored")
            return
        if visible:
            # ensure running
            if not meta.get('overlay_id'):
                try:
                    oid = self.plugin.start_overlay(title=meta['config'].get('window_title') or thumbnail_id, name=thumbnail_id)
                    with self._lock:
                        meta['overlay_id'] = oid
                except Exception as e:
                    logger.error(f"Failed to start overlay for {thumbnail_id}: {e}")
        else:
            try:
                self.plugin.stop_overlay(thumbnail_id)
            except Exception:
                logger.debug(f"Error stopping overlay {thumbnail_id} when hiding")
            with self._lock:
                meta['overlay_id'] = None

    def update_thumbnail_image(self, thumbnail_id: str, image) -> bool:
        # No-op for native subprocess-based overlays
        return True

    def set_thumbnail_availability(self, thumbnail_id: str, available: bool, show_when_unavailable: bool = False) -> None:
        # Map availability to visibility
        self.set_thumbnail_user_visibility(thumbnail_id, show_when_unavailable or available)

    def set_all_thumbnail_opacity(self, opacity: float) -> None:
        # Not supported for external subprocess overlays
        pass

    def set_all_thumbnail_topmost(self, on_top: bool) -> None:
        # Not supported here
        pass

    def set_all_thumbnail_borders(self, show_borders: bool) -> None:
        # Not supported here
        pass

    def refresh_unavailable_thumbnails(self, show_when_unavailable: bool) -> None:
        # iterate and apply
        with self._lock:
            ids = list(self._thumbnails.keys())
        for tid in ids:
            self.set_thumbnail_availability(tid, True, show_when_unavailable)

    def refresh_thumbnail_titles(self) -> None:
        # Titles are managed by plugin subprocess (native demo uses title arg)
        pass

    def get_all_thumbnail_geometries(self) -> Dict[str, Dict[str, int]]:
        with self._lock:
            return {tid: {'x': meta['x'], 'y': meta['y'], 'width': meta['width'], 'height': meta['height']} for tid, meta in self._thumbnails.items()}
