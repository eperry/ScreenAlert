"""Main window UI for ScreenAlert v2"""

import logging
import threading
import time
import os
import subprocess
import faulthandler
import traceback
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox as msgbox, filedialog
from typing import Optional, List, Dict
import win32gui
from PIL import Image, ImageTk, ImageDraw, ImageFont

from screenalert_core.screening_engine import ScreenAlertEngine
from screenalert_core.ui.window_selector_dialog import WindowSelectorDialog
from screenalert_core.ui.region_selection_overlay import RegionSelectionOverlay
from screenalert_core.ui.settings_dialog import SettingsDialog
from screenalert_core.ui.region_detection_dialog import RegionDetectionDialog
from screenalert_core.ui.tooltip import ToolTip
from screenalert_core.ui.auto_hide_scrollbar import AutoHideScrollbar
from screenalert_core.core.image_processor import ImageProcessor
from screenalert_core.utils.update_checker import check_for_updates
from screenalert_core.utils.constants import LOGS_DIR
from screenalert_core.ui.window_slot_mixin import WindowSlotMixin
from screenalert_core.ui.engine_event_mixin import EngineEventMixin
from screenalert_core.ui.settings_mixin import SettingsMixin

logger = logging.getLogger(__name__)


class ScreenAlertMainWindow(WindowSlotMixin, EngineEventMixin, SettingsMixin):
    """Main control window for ScreenAlert"""
    
    def __init__(self, engine: ScreenAlertEngine):
        logger.debug("ScreenAlertMainWindow __init__ starting")
        self.engine = engine
        self.config = engine.config
        self.window_manager = engine.window_manager
        self._mcp_server = None  # set later via set_mcp_server()
        self.thumbnail_map = {}  # hwnd -> thumbnail_id mapping
        self.selected_thumbnail_id: Optional[str] = None  # Currently selected window
        self.selected_region_id: Optional[str] = None
        self.region_statuses: Dict[str, Dict[str, str]] = {}  # thumbnail_id -> region_id -> status
        self.region_widgets: Dict[str, Dict[str, tk.Widget]] = {}  # region_id -> widgets
        self.region_photos: Dict[str, ImageTk.PhotoImage] = {}  # region_id -> image
        self.window_preview_photo: Optional[ImageTk.PhotoImage] = None
        self.region_to_thumbnail: Dict[str, str] = {}
        self.show_all_regions = True
        # Region state visibility filters (persisted in config.ui.region_state_filters)
        self.region_state_filters = self.config.get_region_state_filters() if hasattr(self.config, 'get_region_state_filters') else {
            "alert": True,
            "warning": True,
            "paused": True,
            "ok": True,
            "disabled": True,
            "unavailable": True,
        }
        self._region_state_vars: Dict[str, tk.BooleanVar] = {}
        # Dirty flag system - track what needs updating
        self.dirty_regions: Dict[str, Dict[str, bool]] = {}  # region_id -> {'status': bool, 'thumbnail': bool}
        self.pending_status_changes: Dict[str, str] = {}  # region_id -> new_status
        self.update_timer_id = None  # Track scheduled update timer
        self._event_lock = threading.Lock()
        self._ui_event_flush_scheduled = False
        self._pending_alert_events: Dict[tuple, str] = {}
        self._pending_region_change_events: dict[tuple, str] = {}
        self._pending_window_lost_events: Dict[str, str] = {}
        self._ui_cycle_count = 0
        self._ui_cycle_total_ms = 0.0
        self._ui_last_diag_ts = time.time()
        self._suppress_tree_select_event = False
        self._detail_scroll_update_scheduled = False
        self._force_refresh_counter = 0  # counts periodic-update ticks for forced refresh
        self._pending_tree_focus_window_id: Optional[str] = None
        self._pending_tree_focus_region_id: Optional[str] = None
        self.tree_filter_var: Optional[tk.StringVar] = None
        self._left_pane_min_width = 260
        self._splitter_enforce_scheduled = False
        self._add_window_in_progress = False
        self._add_window_queue: List[Dict] = []
        self._add_window_added_count = 0
        self._add_window_duplicate_count = 0
        self._add_window_failed_count = 0
        self._add_window_last_added_thumbnail_id: Optional[str] = None
        self._ui_heartbeat_ts = time.time()
        self._ui_heartbeat_after_id = None
        self._filter_refresh_after_id: Optional[str] = None
        self._watchdog_stop_event = threading.Event()
        self._watchdog_thread: Optional[threading.Thread] = None
        self._watchdog_last_dump_ts = 0.0
        self._last_alert_focus_ts = 0.0
        self._alert_focus_cooldown_seconds = 0.75
        self._tree_icon_tooltip_window: Optional[tk.Toplevel] = None
        self._tree_icon_tooltip_after_id = None
        self._tree_icon_tooltip_target: Optional[tuple] = None
        self._tree_window_icon_meta: Dict[str, List[tuple[str, str]]] = {}
        self._window_tree_icon_strip_cache: Dict[tuple, ImageTk.PhotoImage] = {}
        self._tree_pil_font: Optional[ImageFont.FreeTypeFont] = None
        self._tree_text_font: Optional[tkfont.Font] = None
        logger.debug("Creating Tk root window")
        self.root = tk.Tk()
        self.root.title("ScreenAlert v2.0.2 - Multibox Monitor")
        logger.debug("Tk root window created and titled")
        self.root.geometry("1200x800")
        # Pass tkinter root to engine for overlay windows
        logger.debug("Passing Tk root to engine")
        self.engine.set_tkinter_root(self.root)
        logger.debug("Tk root passed to engine")
        # Rebuild thumbnail_map from config (for duplicate checking)
        for thumbnail in self.config.get_all_thumbnails():
            hwnd = thumbnail.get('window_hwnd')
            thumbnail_id = thumbnail.get('id')
            if hwnd and thumbnail_id:
                self.thumbnail_map[hwnd] = thumbnail_id

        logger.info(f"Restored {len(self.thumbnail_map)} thumbnails in map from config")

        # Configure style/theme
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self._current_theme = 'high-contrast' if self.config.get_high_contrast() else 'dark'
        self._theme_preset = self.config.get_theme_preset()
        self._palette: Dict[str, str] = {}
        self._pending_runtime_settings: Optional[Dict[str, object]] = None
        self._runtime_apply_scheduled = False
        self._last_applied_runtime_settings: Dict[str, object] = {}
        self._apply_theme(self._current_theme)

        # Build UI
        logger.debug("Building UI")
        self._build_ui()
        logger.debug("UI built")

        self._ensure_window_slot_consistency()

        # Update thumbnail list with any saved thumbnails from config
        logger.debug("Updating thumbnail list from config")
        self._update_thumbnail_list()
        logger.debug("Thumbnail list updated")

        # Setup callbacks
        logger.debug("Setting up engine callbacks")
        self.engine.on_alert = self._on_alert
        self.engine.on_region_change = self._on_region_change
        self.engine.on_window_lost = self._on_window_lost

        # Setup keyboard shortcuts
        self._setup_shortcuts()

        # Add tooltips to main controls after UI is built
        self.root.after(100, self._add_tooltips)
        self.root.after(500, self._check_for_updates_async)
        self._schedule_ui_heartbeat()
        self._start_ui_watchdog()

        # Auto-start monitoring after a short delay (matches main branch behaviour)
        self.root.after(3000, self._auto_start_monitoring)

    def _add_tooltips(self) -> None:
        # Add tooltips to main window controls
        try:
            # Add tooltips to region cards
            for region_id, widgets in getattr(self, 'region_widgets', {}).items():
                if 'pause_btn' in widgets:
                    ToolTip(widgets['pause_btn'], 'Pause/resume monitoring for this region')
                if 'status_pill' in widgets:
                    ToolTip(widgets['status_pill'], 'Current status of this region')
                if 'name_entry' in widgets:
                    ToolTip(widgets['name_entry'], 'Edit the name of this region')
                if 'alert_text_entry' in widgets:
                    ToolTip(widgets['alert_text_entry'], 'Edit spoken alert text for this region')
                if 'image_label' in widgets:
                    ToolTip(widgets['image_label'], 'Preview of this region')
        except Exception as e:
            logger.warning(f"Error adding tooltips: {e}")

    def _apply_theme(self, theme: str) -> None:
        """Apply the selected theme (dark or high-contrast)"""
        self._current_theme = theme
        if theme == 'high-contrast':
            self.style.theme_use('clam')
            self._palette = {
                "bg": "#000000",
                "panel": "#000000",
                "surface": "#000000",
                "surface_alt": "#000000",
                "text": "#FFFFFF",
                "text_muted": "#FFFF00",
                "accent": "#FFFF00",
                "entry_bg": "#000000",
                "ok": "#00FF00",
                "info": "#004578",
                "warn": "#FFD800",
                "danger": "#FF3B30",
                "disabled": "#888888",
                "selection_bg": "#FFFF00",
                "selection_fg": "#000000",
            }

            p = self._palette
            self.style.configure('.', background=p["bg"], foreground=p["text"], font=('Segoe UI', 10, 'bold'))
            self.style.configure('TLabel', background=p["bg"], foreground=p["text"], font=('Segoe UI', 10, 'bold'))
            self.style.configure('TFrame', background=p["panel"])
            self.style.configure('TButton', background=p["surface"], foreground=p["accent"], font=('Segoe UI', 10, 'bold'))
            self.style.map('TButton', background=[('active', p["accent"])], foreground=[('active', p["bg"])])
            self.style.configure(
                'Treeview',
                background=p["panel"],
                foreground=p["text"],
                fieldbackground=p["panel"],
                font=('Segoe UI', 10, 'bold'),
            )
            self.style.map('Treeview', background=[('selected', p["selection_bg"])], foreground=[('selected', p["selection_fg"])])
            self.style.configure('Treeview.Heading', background=p["surface"], foreground=p["text"], font=('Segoe UI', 10, 'bold'))
            self.style.configure('TEntry', fieldbackground=p["entry_bg"], foreground=p["text"], font=('Segoe UI', 10, 'bold'))
            self.style.configure('TSpinbox', fieldbackground=p["entry_bg"], foreground=p["text"], background=p["surface"], arrowcolor=p["accent"], insertcolor=p["text"])
            self.style.configure('Horizontal.TScale', background=p["panel"], troughcolor=p["surface"])
            self.style.configure('TNotebook', background=p["panel"], borderwidth=0)
            self.style.configure('TNotebook.Tab', background=p["surface"], foreground=p["text"], padding=(10, 4), font=('Segoe UI', 10, 'bold'))
            self.style.map('TNotebook.Tab', background=[('selected', p["accent"]), ('active', p["surface_alt"])], foreground=[('selected', p["bg"]), ('active', p["text"])])
            self.style.configure('TLabelframe', background=p["panel"], bordercolor=p["surface"], relief=tk.GROOVE)
            self.style.configure('TLabelframe.Label', background=p["panel"], foreground=p["text"], font=('Segoe UI', 10, 'bold'))
            self.style.configure('TCheckbutton', background=p["bg"], foreground=p["text"], indicatorcolor=p["entry_bg"])
            self.style.map('TCheckbutton', background=[('disabled', p["bg"]), ('active', p["bg"])], foreground=[('disabled', p["text"]), ('active', p["text"])], indicatorcolor=[('disabled', p["disabled"]), ('selected', p["accent"]), ('!selected', p["entry_bg"])])
            self.style.configure(
                'App.TCheckbutton',
                background=p["bg"],
                foreground=p["text"],
                indicatorcolor=p["entry_bg"],
            )
            self.style.map(
                'App.TCheckbutton',
                background=[('disabled', p["bg"]), ('active', p["bg"])],
                foreground=[('disabled', p["text"]), ('active', p["text"])],
                indicatorcolor=[('disabled', p["disabled"]), ('selected', p["accent"]), ('!selected', p["entry_bg"])],
            )
            self.style.configure(
                'App.TCombobox',
                fieldbackground=p["entry_bg"],
                background=p["surface"],
                foreground=p["text"],
                arrowcolor=p["accent"],
                selectforeground=p["text"],
                selectbackground=p["entry_bg"],
            )
            self.style.map(
                'App.TCombobox',
                fieldbackground=[('readonly', p["entry_bg"])],
                background=[('readonly', p["surface"])],
                foreground=[('readonly', p["text"])],
            )

            self.style.configure('App.Card.TFrame', background=p["surface"], relief=tk.GROOVE, borderwidth=1)
            self.style.configure('App.CardInner.TFrame', background=p["surface"])
            self.style.configure('App.Controls.TFrame', background=p["surface"], relief=tk.FLAT, borderwidth=0)
            self.style.configure('App.Muted.TLabel', background=p["surface"], foreground=p["text_muted"], font=('Segoe UI', 10))
            self.style.configure('App.Image.TLabel', background=p["surface_alt"], foreground=p["text"], font=('Segoe UI', 10))
            self.style.configure('App.ImageUnavailable.TLabel', background=p["surface_alt"], foreground=p["text_muted"], font=('Segoe UI', 10, 'bold'))
            self.style.configure('App.RegionAction.TButton', background=p["surface_alt"], foreground=p["accent"], font=('Segoe UI', 10, 'bold'))
            self.style.map('App.RegionAction.TButton', background=[('active', p["accent"])], foreground=[('active', p["bg"])])
            self.style.configure('App.Status.Ok.TLabel', background=p["ok"], foreground='#000000', font=('Segoe UI', 9, 'bold'))
            self.style.configure('App.Status.Warning.TLabel', background=p["warn"], foreground='#000000', font=('Segoe UI', 9, 'bold'))
            self.style.configure('App.Status.Alert.TLabel', background=p["danger"], foreground='#FFFFFF', font=('Segoe UI', 9, 'bold'))
            self.style.configure('App.Status.Info.TLabel', background=p["info"], foreground='#FFFFFF', font=('Segoe UI', 9, 'bold'))
            self.style.configure('App.Status.Disabled.TLabel', background=p["disabled"], foreground='#FFFFFF', font=('Segoe UI', 9, 'bold'))
            self.style.configure('App.Preview.TLabel', background=p["surface_alt"], foreground=p["text"])
            self.style.configure('App.PreviewUnavailable.TLabel', background=p["surface_alt"], foreground=p["text_muted"], font=('Segoe UI', 10, 'bold'))
            self.style.configure('App.StatusBar.TFrame', background=p["surface"])
        else:
            self.style.theme_use('clam')
            self._palette = self._get_dark_palette(self._theme_preset)

            p = self._palette
            self.style.configure('.', background=p["bg"], foreground=p["text"], font=('Segoe UI', 10))
            self.style.configure('TLabel', background=p["bg"], foreground=p["text"], font=('Segoe UI', 10, 'bold'))
            self.style.configure('TFrame', background=p["panel"])
            self.style.configure('TButton', background=p["entry_bg"], foreground=p["accent"], font=('Segoe UI', 10, 'bold'))
            self.style.map('TButton', background=[('active', p["accent"])], foreground=[('active', p["bg"])])
            self.style.configure('Treeview', background=p["panel"], foreground=p["text"], fieldbackground=p["panel"], font=('Segoe UI', 10))
            self.style.map('Treeview', background=[('selected', p["selection_bg"])], foreground=[('selected', p["selection_fg"])])
            self.style.configure('Treeview.Heading', background=p["surface"], foreground=p["text"], font=('Segoe UI', 10, 'bold'))
            self.style.configure('TEntry', fieldbackground=p["entry_bg"], foreground=p["text"], font=('Segoe UI', 10))
            self.style.configure('TSpinbox', fieldbackground=p["entry_bg"], foreground=p["text"], background=p["surface"], arrowcolor=p["accent"], insertcolor=p["text"])
            self.style.configure('Horizontal.TScale', background=p["panel"], troughcolor=p["surface"])
            self.style.configure('TNotebook', background=p["panel"], borderwidth=0)
            self.style.configure('TNotebook.Tab', background=p["surface"], foreground=p["text"], padding=(10, 4), font=('Segoe UI', 10, 'bold'))
            self.style.map('TNotebook.Tab', background=[('selected', p["accent"]), ('active', p["surface_alt"])], foreground=[('selected', p["bg"]), ('active', p["text"])])
            self.style.configure('TLabelframe', background=p["panel"], bordercolor=p["surface"], relief=tk.GROOVE)
            self.style.configure('TLabelframe.Label', background=p["panel"], foreground=p["text"], font=('Segoe UI', 10, 'bold'))
            self.style.configure('TCheckbutton', background=p["bg"], foreground=p["text"], indicatorcolor=p["entry_bg"])
            self.style.map('TCheckbutton', background=[('disabled', p["bg"]), ('active', p["bg"])], foreground=[('disabled', p["text"]), ('active', p["text"])], indicatorcolor=[('disabled', p["disabled"]), ('selected', p["accent"]), ('!selected', p["entry_bg"])])
            self.style.configure(
                'App.TCheckbutton',
                background=p["bg"],
                foreground=p["text"],
                indicatorcolor=p["entry_bg"],
            )
            self.style.map(
                'App.TCheckbutton',
                background=[('disabled', p["bg"]), ('active', p["bg"])],
                foreground=[('disabled', p["text"]), ('active', p["text"])],
                indicatorcolor=[('disabled', p["disabled"]), ('selected', p["accent"]), ('!selected', p["entry_bg"])],
            )
            self.style.configure(
                'App.TCombobox',
                fieldbackground=p["entry_bg"],
                background=p["surface"],
                foreground=p["text"],
                arrowcolor=p["accent"],
                selectforeground=p["text"],
                selectbackground=p["entry_bg"],
            )
            self.style.map(
                'App.TCombobox',
                fieldbackground=[('readonly', p["entry_bg"])],
                background=[('readonly', p["surface"])],
                foreground=[('readonly', p["text"])],
            )

            self.style.configure('App.Card.TFrame', background=p["surface"], relief=tk.GROOVE, borderwidth=1)
            self.style.configure('App.CardInner.TFrame', background=p["surface"])
            self.style.configure('App.Controls.TFrame', background=p["surface"], relief=tk.FLAT, borderwidth=0)
            self.style.configure('App.Muted.TLabel', background=p["surface"], foreground=p["text_muted"], font=('Segoe UI', 10))
            self.style.configure('App.Image.TLabel', background=p["surface_alt"], foreground=p["text"], font=('Segoe UI', 10))
            self.style.configure('App.ImageUnavailable.TLabel', background=p["surface_alt"], foreground=p["text_muted"], font=('Segoe UI', 10, 'bold'))
            self.style.configure('App.RegionAction.TButton', background=p["surface_alt"], foreground=p["accent"], font=('Segoe UI', 10, 'bold'))
            self.style.map('App.RegionAction.TButton', background=[('active', p["accent"])], foreground=[('active', p["bg"])])
            self.style.configure('App.Status.Ok.TLabel', background=p["ok"], foreground='#000000', font=('Segoe UI', 9, 'bold'))
            self.style.configure('App.Status.Warning.TLabel', background=p["warn"], foreground='#000000', font=('Segoe UI', 9, 'bold'))
            self.style.configure('App.Status.Alert.TLabel', background=p["danger"], foreground='#FFFFFF', font=('Segoe UI', 9, 'bold'))
            self.style.configure('App.Status.Info.TLabel', background=p["info"], foreground='#FFFFFF', font=('Segoe UI', 9, 'bold'))
            self.style.configure('App.Status.Disabled.TLabel', background=p["disabled"], foreground='#FFFFFF', font=('Segoe UI', 9, 'bold'))
            self.style.configure('App.Preview.TLabel', background=p["surface_alt"], foreground=p["text"])
            self.style.configure('App.PreviewUnavailable.TLabel', background=p["surface_alt"], foreground=p["text_muted"], font=('Segoe UI', 10, 'bold'))
            self.style.configure('App.StatusBar.TFrame', background=p["surface"])

        self._apply_palette_to_runtime_widgets()

    def _rebuild_preview_placeholder(self) -> None:
        """Rebuild preview placeholder image using current palette."""
        self._preview_placeholder = ImageTk.PhotoImage(
            Image.new("RGB", (180, 100), self._palette.get("surface_alt", "#1a1a1a"))
        )

    def _set_preview_placeholder(self, text: str) -> None:
        """Show palette-aware placeholder in the preview area."""
        self.window_preview_photo = None
        if hasattr(self, 'window_preview_label'):
            self.window_preview_label.config(
                image=self._preview_placeholder,
                text=text,
                style='App.PreviewUnavailable.TLabel',
                compound='center',
            )

    def _apply_palette_to_runtime_widgets(self) -> None:
        """Apply palette colors to non-ttk surfaces that are already created."""
        if not getattr(self, '_palette', None):
            return

        self._rebuild_preview_placeholder()

        if hasattr(self, 'region_canvas'):
            self.region_canvas.configure(bg=self._palette["panel"], highlightbackground=self._palette["panel"])
        if hasattr(self, 'regions_inner_frame'):
            self.regions_inner_frame.configure(bg=self._palette["panel"])
        if hasattr(self, 'window_tree'):
            self._configure_tree_tags()
        if hasattr(self, 'aggregate_status_badge'):
            self._refresh_aggregate_status()
        if hasattr(self, 'window_preview_label'):
            current_text = self.window_preview_label.cget('text') or 'Not Available'
            current_image = self.window_preview_label.cget('image')
            preview_image = str(self.window_preview_photo) if self.window_preview_photo else ''
            if preview_image and current_image == preview_image:
                self.window_preview_label.config(style='App.Preview.TLabel')
            else:
                self._set_preview_placeholder(current_text)

    def _configure_tree_tags(self) -> None:
        """Apply tree item tag colors from current palette."""
        self.window_tree.tag_configure("window_connected", foreground=self._palette["ok"])
        self.window_tree.tag_configure("window_alert", foreground=self._palette["danger"])
        self.window_tree.tag_configure("window_warning", foreground=self._palette["warn"])
        self.window_tree.tag_configure("window_paused", foreground=self._palette["info"])
        self.window_tree.tag_configure("window_unavailable", foreground=self._palette["info"])
        self.window_tree.tag_configure("window_disabled", foreground=self._palette["disabled"])
        self.window_tree.tag_configure("region_alert", foreground=self._palette["danger"])
        self.window_tree.tag_configure("region_warning", foreground=self._palette["warn"])
        self.window_tree.tag_configure("region_ok", foreground=self._palette["ok"])
        self.window_tree.tag_configure("region_paused", foreground=self._palette["info"])
        self.window_tree.tag_configure("region_unavailable", foreground=self._palette["info"])
        self.window_tree.tag_configure("region_disabled", foreground=self._palette["disabled"])

    def set_high_contrast(self, enabled: bool) -> None:
        """Public method to toggle high-contrast mode at runtime"""
        self._current_theme = 'high-contrast' if enabled else 'dark'
        self._apply_theme(self._current_theme)
        self.root.update_idletasks()

    def _get_dark_palette(self, preset: str) -> Dict[str, str]:
        """Return dark palette token set for a preset name."""
        normalized = (preset or "default").strip().lower()
        palettes = {
            "default": {
                "bg": "#181a20",
                "panel": "#23272e",
                "surface": "#1f2430",
                "surface_alt": "#141821",
                "text": "#E6EDF3",
                "text_muted": "#A7B3C2",
                "accent": "#33B1FF",
                "entry_bg": "#222b3a",
                "ok": "#2ECC71",
                "info": "#3B82F6",
                "warn": "#F59E0B",
                "danger": "#EF4444",
                "disabled": "#64748B",
                "selection_bg": "#23476C",
                "selection_fg": "#F2F8FF",
            },
            "slate": {
                "bg": "#141922",
                "panel": "#1C2430",
                "surface": "#202B38",
                "surface_alt": "#111827",
                "text": "#E5EEF8",
                "text_muted": "#97A6B8",
                "accent": "#4CC9F0",
                "entry_bg": "#263445",
                "ok": "#34D399",
                "info": "#60A5FA",
                "warn": "#FBBF24",
                "danger": "#F87171",
                "disabled": "#718096",
                "selection_bg": "#2D4F74",
                "selection_fg": "#F2F8FF",
            },
            "midnight": {
                "bg": "#10131A",
                "panel": "#1A1F2B",
                "surface": "#21283A",
                "surface_alt": "#0D111A",
                "text": "#EAF0FF",
                "text_muted": "#94A3B8",
                "accent": "#7C9BFF",
                "entry_bg": "#27324A",
                "ok": "#4ADE80",
                "info": "#60A5FA",
                "warn": "#F59E0B",
                "danger": "#FB7185",
                "disabled": "#6B7280",
                "selection_bg": "#334E80",
                "selection_fg": "#F3F7FF",
            },
        }
        return palettes.get(normalized, palettes["default"])

    def set_theme_preset(self, preset: str) -> None:
        """Set theme preset and apply immediately."""
        normalized = (preset or "default").strip().lower()
        if normalized not in ("default", "slate", "midnight", "high-contrast"):
            normalized = "default"

        if normalized == "high-contrast":
            self._current_theme = 'high-contrast'
            self._apply_theme('high-contrast')
            self.root.update_idletasks()
            return

        self._theme_preset = normalized
        self._current_theme = 'dark'
        self._apply_theme('dark')
        self.root.update_idletasks()

    def _check_for_updates_async(self) -> None:
        """Check for updates on a background thread and notify when available."""
        if not self.config.get_update_check_enabled():
            return

        def worker() -> None:
            info = check_for_updates()
            if not info or not info.is_update_available:
                return

            def show_prompt() -> None:
                try:
                    self.status_var.set(f"Update available: {info.latest_version}")
                    msgbox.showinfo(
                        "Update Available",
                        f"A newer version is available.\n\n"
                        f"Current: {info.current_version}\n"
                        f"Latest: {info.latest_version}\n\n"
                        f"Download: {info.release_url}"
                    )
                except Exception as error:
                    logger.warning(f"Unable to show update prompt: {error}")

            try:
                self.root.after(0, show_prompt)
            except Exception as error:
                logger.warning(f"Unable to schedule update prompt: {error}")

        threading.Thread(target=worker, daemon=True).start()

    def _setup_shortcuts(self) -> None:
        """Bind keyboard shortcuts for major actions"""
        self.root.bind('<Control-n>', lambda e: self._add_window())
        self.root.bind('<Control-r>', lambda e: self._add_region())
        self.root.bind('<Control-Shift-R>', lambda e: self._remove_region())
        self.root.bind('<Control-Delete>', lambda e: self._remove_thumbnail())
        self.root.bind('<Control-s>', lambda e: self._save_config())
        self.root.bind('<Control-Shift-S>', lambda e: self._save_config_as())
        self.root.bind('<F6>', lambda e: self._toggle_pause())
        self.root.bind('<Control-q>', lambda e: self._on_exit())
        for slot in range(1, 10):
            self.root.bind(f'<Alt-KeyPress-{slot}>', lambda _e, s=slot: self._activate_window_by_slot(s))
        self.root.bind('<Alt-KeyPress-0>', lambda _e: self._activate_window_by_slot(10))

    def _build_ui(self) -> None:
        """Build main UI with tree + region detail layout"""
        # Menu
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Save", command=self._save_config)
        file_menu.add_command(label="Save As...", command=self._save_config_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_exit)

        self.edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=self.edit_menu)
        self.edit_menu.add_command(label="Pause All", command=self._toggle_pause)
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Settings...", command=self._show_settings)

        self.windows_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Windows", menu=self.windows_menu)
        self.windows_menu.add_command(label="Add Window", command=self._add_window)
        self.windows_menu.add_command(label="Reconnect All Windows", command=self._reconnect_all_windows)
        self.windows_menu.add_command(label="Enable All Overlays", command=self._enable_all_overlays)
        self.windows_menu.add_command(label="Close All Overlays", command=self._close_all_overlays)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Logs", command=self._open_logs_folder)
        help_menu.add_command(label="Dump Threads Now", command=self._dump_threads_now)
        help_menu.add_separator()
        help_menu.add_command(label="Keyboard Shortcuts", command=self._show_shortcuts)
        help_menu.add_command(label="About", command=self._show_about)
        
        # Main content
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # Content area
        content_frame = ttk.Frame(main_frame)
        content_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        content_frame.rowconfigure(0, weight=1)
        content_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # Horizontal splitter: left windows tree <-> right detail panel
        self.main_splitter = ttk.Panedwindow(content_frame, orient=tk.HORIZONTAL)
        self.main_splitter.grid(row=0, column=0, sticky="nsew")
        
        # Left: tree of windows/regions
        tree_frame = ttk.LabelFrame(self.main_splitter, text="Windows", padding=8)
        tree_frame.rowconfigure(1, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        # Row for text filter
        filter_row = ttk.Frame(tree_frame)
        filter_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        filter_row.columnconfigure(1, weight=1)
        ttk.Label(filter_row, text="Filter:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.tree_filter_var = tk.StringVar(value="")
        tree_filter_entry = ttk.Entry(filter_row, textvariable=self.tree_filter_var)
        tree_filter_entry.grid(row=0, column=1, sticky="ew")
        self.tree_filter_var.trace_add("write", self._on_tree_filter_change)
        
        self.window_tree = ttk.Treeview(tree_frame, show="tree")
        self.window_tree.grid(row=1, column=0, sticky="nsew")
        self._configure_tree_tags()
        self.tree_scroll = AutoHideScrollbar(tree_frame, orient=tk.VERTICAL, command=self.window_tree.yview)
        self.tree_scroll.grid(row=1, column=1, sticky="ns")
        self.window_tree.configure(yscrollcommand=self.tree_scroll.set)
        self.window_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.window_tree.bind("<Button-3>", self._on_tree_right_click)
        
        # Right: window info + region cards
        self.detail_frame = ttk.Frame(self.main_splitter)
        self.detail_frame.rowconfigure(1, weight=1)
        self.detail_frame.columnconfigure(0, weight=1)

        self.main_splitter.add(tree_frame, weight=0)
        self.main_splitter.add(self.detail_frame, weight=1)
        self.main_splitter.bind("<B1-Motion>", lambda _e: self._schedule_splitter_enforce())
        self.main_splitter.bind("<ButtonRelease-1>", lambda _e: self._schedule_splitter_enforce())
        self.root.bind("<Configure>", self._on_root_configure)
        self.root.after_idle(self._enforce_splitter_limits)
        
        self.info_frame = ttk.LabelFrame(self.detail_frame, text="Window Info", padding=6)
        self.info_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.info_frame.columnconfigure(1, weight=1)
        
        ttk.Label(self.info_frame, text="Title:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.window_title_var = tk.StringVar(value="")
        ttk.Label(self.info_frame, textvariable=self.window_title_var).grid(row=0, column=1, sticky="w")
        
        ttk.Label(self.info_frame, text="HWND:").grid(row=1, column=0, sticky="w", padx=(0, 6))
        self.window_hwnd_var = tk.StringVar(value="")
        ttk.Label(self.info_frame, textvariable=self.window_hwnd_var).grid(row=1, column=1, sticky="w")
        
        ttk.Label(self.info_frame, text="Regions:").grid(row=2, column=0, sticky="w", padx=(0, 6))
        self.window_region_count_var = tk.StringVar(value="0")
        ttk.Label(self.info_frame, textvariable=self.window_region_count_var).grid(row=2, column=1, sticky="w")

        ttk.Label(self.info_frame, text="Size:").grid(row=3, column=0, sticky="w", padx=(0, 6))
        self.window_size_var = tk.StringVar(value="")
        ttk.Label(self.info_frame, textvariable=self.window_size_var).grid(row=3, column=1, sticky="w")

        ttk.Label(self.info_frame, text="Alt Slot:").grid(row=4, column=0, sticky="w", padx=(0, 6))
        self.window_slot_var = tk.StringVar(value="")
        self.window_slot_combo = ttk.Combobox(
            self.info_frame,
            style="App.TCombobox",
            textvariable=self.window_slot_var,
            values=[str(i) for i in range(1, 11)],
            width=6,
            state="disabled",
        )
        self.window_slot_combo.grid(row=4, column=1, sticky="w")
        self.window_slot_combo.bind('<<ComboboxSelected>>', self._on_window_slot_changed)
        self.window_slot_combo.bind('<FocusIn>', lambda _e: self._schedule_clear_window_slot_selection())
        self.window_slot_combo.bind('<ButtonRelease-1>', lambda _e: self._schedule_clear_window_slot_selection())

        self.window_primary_var = tk.BooleanVar(value=False)
        self.window_primary_checkbox = ttk.Checkbutton(
            self.info_frame,
            style="App.TCheckbutton",
            text="Primary (bring to front on startup)",
            variable=self.window_primary_var,
            command=self._toggle_primary_window,
        )
        self.window_primary_checkbox.grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.window_primary_checkbox.state(["disabled"])

        self.window_alert_focus_var = tk.BooleanVar(value=False)
        self.window_alert_focus_checkbox = ttk.Checkbutton(
            self.info_frame,
            style="App.TCheckbutton",
            text="Alert Focus (bring to front on alert)",
            variable=self.window_alert_focus_var,
            command=self._toggle_alert_focus_window,
        )
        self.window_alert_focus_checkbox.grid(row=6, column=0, columnspan=2, sticky="w", pady=(2, 0))
        self.window_alert_focus_checkbox.state(["disabled"])
        
        self._rebuild_preview_placeholder()
        self.window_preview_label = ttk.Label(
            self.info_frame,
            style='App.PreviewUnavailable.TLabel',
            image=self._preview_placeholder,
            anchor='center',
        )
        self.window_preview_label.grid(row=0, column=2, rowspan=7, sticky="e", padx=(10, 0))
        
        self.regions_frame = ttk.LabelFrame(self.detail_frame, text="Regions (0/0)", padding=8)
        self.regions_frame.grid(row=1, column=0, sticky="nsew")
        # Row 0: controls, Row 1: canvas (scrollable)
        self.regions_frame.rowconfigure(1, weight=1)
        self.regions_frame.columnconfigure(0, weight=1)

        # Region-state filter controls moved here
        state_controls = ttk.Frame(self.regions_frame)
        state_controls.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        states = [("Warning", "warning"), ("Paused", "paused"), ("OK", "ok"), ("Disabled", "disabled"), ("N/A", "unavailable"), ("Alert", "alert")]
        # keep a compact left-to-right ordering; use stored filter values
        col = 0
        for label_text, state_key in states:
            var = tk.BooleanVar(value=bool(self.region_state_filters.get(state_key, True)))
            cb = ttk.Checkbutton(state_controls, text=label_text, style="App.TCheckbutton", variable=var, command=self._on_region_state_filter_changed)
            cb.grid(row=0, column=col, sticky="w", padx=(0, 6))
            self._region_state_vars[state_key] = var
            col += 1

        self.region_canvas = tk.Canvas(self.regions_frame, bg=self._palette["panel"], highlightthickness=0)
        self.region_canvas.grid(row=1, column=0, sticky="nsew")
        self.region_scroll = AutoHideScrollbar(self.regions_frame, orient=tk.VERTICAL, command=self.region_canvas.yview)
        self.region_scroll.grid(row=0, column=1, sticky="ns")
        self.region_canvas.configure(yscrollcommand=self.region_scroll.set)
        
        self.regions_inner_frame = tk.Frame(self.region_canvas, bg=self._palette["panel"])
        self.region_canvas_window = self.region_canvas.create_window(0, 0, window=self.regions_inner_frame, anchor="nw")
        self.region_canvas.bind("<Configure>", self._on_region_canvas_configure)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        self.aggregate_status_var = tk.StringVar(value="Overall: N/A")
        self._update_pause_menu_labels()

        self.status_bar_frame = ttk.Frame(self.root, style='App.StatusBar.TFrame')
        self.status_bar_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)

        self.status_text_label = ttk.Label(self.status_bar_frame, textvariable=self.status_var, anchor="w")
        self.status_text_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4), pady=2)

        self.aggregate_status_badge = tk.Label(
            self.status_bar_frame,
            textvariable=self.aggregate_status_var,
            bg=self._palette["surface"],
            fg=self._palette["text"],
            padx=10,
            pady=2,
            relief=tk.RIDGE,
            bd=1,
        )
        self.aggregate_status_badge.pack(side=tk.RIGHT, padx=(4, 4), pady=2)

        # MCP toggle button (shown only when MCP server is wired in)
        self._mcp_btn = ttk.Button(
            self.status_bar_frame,
            text="MCP: Off",
            command=self._toggle_mcp,
            width=10,
        )
        self._mcp_btn.pack(side=tk.RIGHT, padx=(4, 0), pady=2)
        self._mcp_btn.pack_forget()  # hidden until set_mcp_server() is called

        # DPI awareness (Windows only)
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
        except Exception:
            pass
        
        # Bind window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_exit)
    
    def _on_region_canvas_configure(self, event) -> None:
        """Handle region canvas resize"""
        self.region_canvas.configure(scrollregion=self.region_canvas.bbox("all"))
        self.region_canvas.itemconfig(self.region_canvas_window, width=event.width)
        self.region_scroll.set(*self.region_canvas.yview())

    def _on_root_configure(self, _event) -> None:
        """Handle root resize events and enforce splitter min width."""
        self._schedule_splitter_enforce()

    def _schedule_splitter_enforce(self) -> None:
        """Coalesce splitter constraint enforcement to idle time."""
        if self._splitter_enforce_scheduled:
            return
        self._splitter_enforce_scheduled = True
        self.root.after_idle(self._enforce_splitter_limits)

    def _enforce_splitter_limits(self) -> None:
        """Ensure left windows pane width does not shrink below minimum."""
        self._splitter_enforce_scheduled = False
        try:
            current = self.main_splitter.sashpos(0)
            if current < self._left_pane_min_width:
                self.main_splitter.sashpos(0, self._left_pane_min_width)
        except Exception:
            # Ignore while splitter not fully realized or during shutdown
            pass

    def _on_tree_filter_change(self, *_args) -> None:
        """Rebuild tree when filter query changes."""
        self._update_thumbnail_list()

    def _get_tree_filter_query(self) -> str:
        """Return normalized tree filter query."""
        if not self.tree_filter_var:
            return ""
        return (self.tree_filter_var.get() or "").strip().casefold()

    def _on_region_state_filter_changed(self) -> None:
        """Persist region state filter changes and refresh the tree."""
        try:
            for state, var in self._region_state_vars.items():
                self.region_state_filters[state] = bool(var.get())
            if hasattr(self.config, 'set_region_state_filters'):
                try:
                    self.config.set_region_state_filters(self.region_state_filters)
                    # Persist immediately
                    self.config.save()
                except Exception:
                    # Fallback to using _save_config which shows status
                    try:
                        self._save_config()
                    except Exception:
                        pass
            # Update visible tree
            self._update_thumbnail_list()
        except Exception as e:
            logger.debug(f"Error updating region state filters: {e}")

    def _region_status_visible(self, status: str) -> bool:
        """Return whether regions with the given status should be visible per current filters."""
        if not status:
            return True
        return bool(self.region_state_filters.get(status, True))

    def _schedule_ui_heartbeat(self) -> None:
        """Update heartbeat timestamp from Tk thread to detect UI stalls."""
        self._ui_heartbeat_ts = time.time()
        if self.root:
            self._ui_heartbeat_after_id = self.root.after(1000, self._schedule_ui_heartbeat)

    def _start_ui_watchdog(self) -> None:
        """Start background watchdog that emits thread dumps if UI heartbeat stalls."""
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            return

        def _watchdog() -> None:
            while not self._watchdog_stop_event.wait(2.0):
                now = time.time()
                stall_seconds = now - self._ui_heartbeat_ts
                if stall_seconds < 8.0:
                    continue
                if (now - self._watchdog_last_dump_ts) < 30.0:
                    continue

                self._watchdog_last_dump_ts = now
                reason = f"UI heartbeat stalled for {stall_seconds:.1f}s"
                logger.warning(f"[UI WATCHDOG] {reason}")
                self._write_thread_dump(reason)

        self._watchdog_thread = threading.Thread(target=_watchdog, name="ui-watchdog", daemon=True)
        self._watchdog_thread.start()

    def _write_thread_dump(self, reason: str) -> None:
        """Write a full Python thread dump for hang debugging."""
        try:
            os.makedirs(LOGS_DIR, exist_ok=True)
            dump_path = os.path.join(LOGS_DIR, "ui_hang_thread_dumps.log")
            with open(dump_path, "a", encoding="utf-8") as dump_file:
                dump_file.write("\n" + "=" * 80 + "\n")
                dump_file.write(f"Thread dump @ {time.strftime('%Y-%m-%d %H:%M:%S')} | reason={reason}\n")
                dump_file.write("=" * 80 + "\n")
                try:
                    faulthandler.dump_traceback(file=dump_file, all_threads=True)
                except Exception:
                    frames = sys._current_frames()
                    for thread in threading.enumerate():
                        frame = frames.get(thread.ident)
                        dump_file.write(f"\n--- Thread: {thread.name} ({thread.ident}) ---\n")
                        if frame is not None:
                            dump_file.write("".join(traceback.format_stack(frame)))
                        else:
                            dump_file.write("No stack available\n")
                dump_file.flush()
            logger.info(f"Thread dump captured: {dump_path}")
        except Exception as error:
            logger.error(f"Failed to write thread dump: {error}", exc_info=True)

    def _dump_threads_now(self) -> None:
        """Manually trigger thread dump from Help menu."""
        self._write_thread_dump("manual menu trigger")
        self.status_var.set("Thread dump captured (see logs folder)")

    
    def _add_window(self) -> None:
        """Add a new window to monitor"""
        if self._add_window_in_progress:
            self.status_var.set("Add windows already in progress...")
            return

        attached_hwnds = self.engine.get_attached_hwnds()
        dialog = WindowSelectorDialog(self.root, self.window_manager, self.config,
                                      attached_hwnds=attached_hwnds)
        windows_info = dialog.show()

        if windows_info:
            self._add_window_in_progress = True
            self._add_window_queue = list(windows_info)
            self._add_window_added_count = 0
            self._add_window_duplicate_count = 0
            self._add_window_failed_count = 0
            self._add_window_last_added_thumbnail_id = None
            self.status_var.set(f"Adding {len(self._add_window_queue)} window(s)...")
            logger.info(f"[ADD WINDOW] Queued {len(self._add_window_queue)} window(s)")
            self.root.after(0, self._process_add_window_queue)

    def _process_add_window_queue(self) -> None:
        """Process one queued window-add operation at a time to keep UI responsive."""
        if not self._add_window_in_progress:
            return

        if not self._add_window_queue:
            self._finalize_add_window_queue()
            return

        window_info = self._add_window_queue.pop(0)
        hwnd = window_info.get('hwnd')
        title = window_info.get('title', 'Unknown')

        if not hwnd:
            self._add_window_failed_count += 1
            logger.warning(f"[ADD WINDOW] Missing HWND for selected item '{title}'")
            self.root.after(1, self._process_add_window_queue)
            return

        if hwnd in self.thumbnail_map:
            self._add_window_duplicate_count += 1
            logger.info(f"[ADD WINDOW] Skipping duplicate '{title}' hwnd={hwnd}")
            self.root.after(1, self._process_add_window_queue)
            return

        started = time.perf_counter()
        try:
            thumbnail_id = self.engine.add_thumbnail(
                window_title=title,
                window_hwnd=hwnd,
                window_class=window_info.get('class', ''),
                window_size=window_info.get('size'),
                monitor_id=window_info.get('monitor_id')
            )
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            logger.info(f"[ADD WINDOW] title='{title}' hwnd={hwnd} elapsed_ms={elapsed_ms:.1f} result={bool(thumbnail_id)}")

            if elapsed_ms > 2000:
                self._write_thread_dump(f"slow add window operation ({elapsed_ms:.1f} ms) title={title}")

            if thumbnail_id:
                self.thumbnail_map[hwnd] = thumbnail_id
                self._assign_default_slot_if_missing(thumbnail_id)
                self._add_window_last_added_thumbnail_id = thumbnail_id
                self._add_window_added_count += 1
            else:
                self._add_window_failed_count += 1
                logger.error(f"Failed to add window '{title}'")
        except Exception as error:
            self._add_window_failed_count += 1
            logger.error(f"Error adding window '{title}': {error}", exc_info=True)

        self.root.after(1, self._process_add_window_queue)

    def _finalize_add_window_queue(self) -> None:
        """Finalize queued add-window operation and update UI once."""
        added_count = self._add_window_added_count
        duplicate_count = self._add_window_duplicate_count
        failed_count = self._add_window_failed_count
        last_added_thumbnail_id = self._add_window_last_added_thumbnail_id

        self._add_window_in_progress = False
        self._add_window_queue = []

        if added_count > 0:
            self._pending_tree_focus_window_id = last_added_thumbnail_id
            self._pending_tree_focus_region_id = None
            if self.tree_filter_var:
                self.tree_filter_var.set("")
            self.show_all_regions = False
            self.selected_region_id = None
            self._update_thumbnail_list()
            self._ensure_engine_running()

        summary_parts = []
        if added_count:
            summary_parts.append(f"added {added_count}")
        if duplicate_count:
            summary_parts.append(f"skipped {duplicate_count} duplicate")
        if failed_count:
            summary_parts.append(f"failed {failed_count}")

        if summary_parts:
            self.status_var.set("Add windows: " + ", ".join(summary_parts))

        if failed_count > 0 and added_count == 0:
            msgbox.showerror("Add Windows", "Unable to add selected windows. Check logs for details.")
    
    def _ensure_engine_running(self) -> bool:
        """Ensure the engine is started. Returns True if engine is running."""
        if self.engine.is_running():
            return True
        thumbnails = self.config.get_all_thumbnails()
        if not thumbnails:
            return False
        try:
            self.engine.start()
            logger.info("Engine started with %d thumbnails", len(thumbnails))
            if self.update_timer_id is None:
                self._periodic_ui_update()
            return True
        except Exception as e:
            logger.error(f"Failed to start engine: {e}", exc_info=True)
            return False

    def _auto_start_monitoring(self) -> None:
        """Automatically start monitoring if thumbnails exist (like main branch)."""
        if self._ensure_engine_running():
            self.engine.set_paused(False)
            self.status_var.set("Monitoring auto-started")
            logger.info("Monitoring auto-started")
            self.root.after(500, self._activate_primary_windows_on_startup)
        else:
            logger.info("Auto-start skipped: no thumbnails configured")

    def _activate_primary_windows_on_startup(self) -> None:
        """Bring configured primary window(s) to foreground on app startup if available."""
        try:
            primary_thumbnails = [
                thumbnail for thumbnail in self.config.get_all_thumbnails()
                if bool(thumbnail.get("is_primary", False)) and thumbnail.get("enabled", True)
            ]
            if not primary_thumbnails:
                return

            activated = 0
            for thumbnail in primary_thumbnails:
                thumbnail_id = thumbnail.get("id")
                hwnd = thumbnail.get("window_hwnd")
                if not thumbnail_id:
                    continue

                if not hwnd or not self.window_manager.is_window_valid(hwnd):
                    reconnect_state = self.engine.reconnect_window(thumbnail_id)
                    if reconnect_state not in ("already_valid", "reconnected"):
                        continue
                    refreshed = self.config.get_thumbnail(thumbnail_id)
                    hwnd = refreshed.get("window_hwnd") if refreshed else None

                if hwnd and self.window_manager.activate_window(hwnd):
                    activated += 1

            if activated:
                self.status_var.set(f"Primary window activated ({activated})")
        except Exception as error:
            logger.error(f"Failed primary-window startup activation: {error}", exc_info=True)

    def _toggle_primary_window(self) -> None:
        """Persist Primary flag for selected window (single-primary semantics)."""
        if not self.selected_thumbnail_id:
            return

        is_primary = bool(self.window_primary_var.get())
        updated = False

        if is_primary:
            selected_thumbnail = self.config.get_thumbnail(self.selected_thumbnail_id)
            if not selected_thumbnail:
                self.window_primary_var.set(False)
                return

            if not self._is_thumbnail_connected(selected_thumbnail):
                self.window_primary_var.set(False)
                self.status_var.set("Primary requires an attached/connected window")
                self._refresh_selected_window_info_panel()
                self._refresh_tree_node_statuses()
                return

            selected_slot = self._get_window_slot(selected_thumbnail)
            slot_one_owner_id = self._get_slot_owner_id(1)

            if slot_one_owner_id and slot_one_owner_id != self.selected_thumbnail_id:
                fallback_slot = selected_slot if selected_slot and selected_slot != 1 else self._get_first_available_slot()
                slot_one_owner = self.config.get_thumbnail(slot_one_owner_id)
                if slot_one_owner:
                    current_owner_slot = self._get_window_slot(slot_one_owner)
                    if fallback_slot is not None and current_owner_slot != fallback_slot:
                        self.config.update_thumbnail(slot_one_owner_id, {"window_slot": fallback_slot})
                        updated = True
                    elif fallback_slot is None and current_owner_slot is not None:
                        self.config.update_thumbnail(slot_one_owner_id, {"window_slot": None})
                        updated = True

            if selected_slot != 1:
                self.config.update_thumbnail(self.selected_thumbnail_id, {"window_slot": 1})
                updated = True

        for thumbnail in self.config.get_all_thumbnails():
            thumbnail_id = thumbnail.get("id")
            if not thumbnail_id:
                continue
            should_be_primary = is_primary and thumbnail_id == self.selected_thumbnail_id
            current = bool(thumbnail.get("is_primary", False))
            if current != should_be_primary:
                self.config.update_thumbnail(thumbnail_id, {"is_primary": should_be_primary})
                updated = True

        if is_primary:
            updated = self._swap_or_assign_window_slot(self.selected_thumbnail_id, 1) or updated

        if updated:
            self.config.save()
            self.engine.refresh_thumbnail_titles()

        self._refresh_selected_window_info_panel()
        self._refresh_tree_node_statuses()

        self.status_var.set("Primary window set" if is_primary else "Primary window cleared")

    def _is_overlay_visible_live(self, thumbnail_id: str, thumbnail: Optional[Dict] = None) -> bool:
        """Return overlay visibility from config state."""
        source = thumbnail if thumbnail is not None else self.config.get_thumbnail(thumbnail_id)
        if not source:
            return True
        return bool(source.get("overlay_visible", source.get("overview_visible", True)))

    # Window slot methods are in WindowSlotMixin (window_slot_mixin.py)

    def _toggle_alert_focus_window(self) -> None:
        """Persist Alert Focus flag for selected window (single-alert-focus semantics)."""
        if not self.selected_thumbnail_id:
            return

        is_alert_focus = bool(self.window_alert_focus_var.get())
        updated = False

        for thumbnail in self.config.get_all_thumbnails():
            thumbnail_id = thumbnail.get("id")
            if not thumbnail_id:
                continue
            should_be_alert_focus = is_alert_focus and thumbnail_id == self.selected_thumbnail_id
            current = bool(thumbnail.get("is_alert_focus", False))
            if current != should_be_alert_focus:
                self.config.update_thumbnail(thumbnail_id, {"is_alert_focus": should_be_alert_focus})
                updated = True

        if updated:
            self.config.save()

        self._refresh_selected_window_info_panel()
        self._refresh_tree_node_statuses()

        self.status_var.set("Alert Focus window set" if is_alert_focus else "Alert Focus window cleared")

    def _get_focus_owner_ids(self) -> tuple[Optional[str], Optional[str]]:
        """Return (primary_owner_id, alert_focus_owner_id)."""
        primary_owner_id: Optional[str] = None
        alert_focus_owner_id: Optional[str] = None
        for thumbnail in self.config.get_all_thumbnails():
            thumbnail_id = thumbnail.get("id")
            if not thumbnail_id:
                continue
            if primary_owner_id is None and bool(thumbnail.get("is_primary", False)):
                primary_owner_id = thumbnail_id
            if alert_focus_owner_id is None and bool(thumbnail.get("is_alert_focus", False)):
                alert_focus_owner_id = thumbnail_id
            if primary_owner_id and alert_focus_owner_id:
                break
        return primary_owner_id, alert_focus_owner_id

    def _refresh_focus_option_states(self) -> None:
        """Refresh enabled/disabled state of Primary and Alert Focus checkboxes."""
        selected_id = self.selected_thumbnail_id
        if not selected_id:
            self.window_primary_var.set(False)
            self.window_primary_checkbox.state(["disabled"])
            self.window_alert_focus_var.set(False)
            self.window_alert_focus_checkbox.state(["disabled"])
            return

        thumbnail = self.config.get_thumbnail(selected_id)
        if not thumbnail:
            self.window_primary_var.set(False)
            self.window_primary_checkbox.state(["disabled"])
            self.window_alert_focus_var.set(False)
            self.window_alert_focus_checkbox.state(["disabled"])
            return

        is_selected_primary = bool(thumbnail.get("is_primary", False))
        is_selected_alert_focus = bool(thumbnail.get("is_alert_focus", False))
        self.window_primary_var.set(is_selected_primary)
        self.window_alert_focus_var.set(is_selected_alert_focus)

        self.window_primary_checkbox.state(["!disabled"])
        self.window_alert_focus_checkbox.state(["!disabled"])

    def _refresh_selected_window_info_panel(self) -> None:
        """Refresh right-side window info fields for the current selection."""
        selected_id = self.selected_thumbnail_id
        if not selected_id or self.show_all_regions:
            return

        thumbnail = self.config.get_thumbnail(selected_id)
        if not thumbnail:
            return

        self.window_title_var.set(thumbnail.get("window_title", "Unknown"))
        hwnd = thumbnail.get("window_hwnd")
        self.window_hwnd_var.set(str(hwnd) if hwnd else "")
        regions = thumbnail.get("monitored_regions", [])
        self.window_region_count_var.set(str(len(regions)))

        slot = self._get_window_slot(thumbnail)
        self.window_slot_var.set(str(slot) if slot else "-")
        self._schedule_clear_window_slot_selection()

        size = thumbnail.get("window_size")
        if isinstance(size, (list, tuple)) and len(size) == 2:
            self.window_size_var.set(f"{size[0]}x{size[1]}")
        else:
            self.window_size_var.set("")

        self._refresh_focus_option_states()

    def _activate_alert_focus_window(self) -> None:
        """Bring configured alert-focus window to foreground, throttled."""
        now = time.time()
        if (now - self._last_alert_focus_ts) < self._alert_focus_cooldown_seconds:
            return

        alert_focus_thumbnail = None
        for thumbnail in self.config.get_all_thumbnails():
            if bool(thumbnail.get("is_alert_focus", False)) and thumbnail.get("enabled", True):
                alert_focus_thumbnail = thumbnail
                break

        if not alert_focus_thumbnail:
            return

        thumbnail_id = alert_focus_thumbnail.get("id")
        hwnd = alert_focus_thumbnail.get("window_hwnd")
        if not thumbnail_id:
            return

        if not hwnd or not self.window_manager.is_window_valid(hwnd):
            reconnect_state = self.engine.reconnect_window(thumbnail_id)
            if reconnect_state not in ("already_valid", "reconnected"):
                return
            refreshed = self.config.get_thumbnail(thumbnail_id)
            hwnd = refreshed.get("window_hwnd") if refreshed else None

        if hwnd and self.window_manager.activate_window(hwnd):
            self._last_alert_focus_ts = now

    def _toggle_pause(self) -> None:
        """Toggle between paused and monitoring states."""
        try:
            if self.engine.paused:
                # Resume
                self._ensure_engine_running()
                self.engine.set_paused(False)
                self.status_var.set("Monitoring resumed")
            else:
                # Pause
                self.engine.set_paused(True)
                self.status_var.set("Monitoring paused")
            self._update_pause_menu_labels()
        except Exception as e:
            logger.error(f"Error toggling pause: {e}", exc_info=True)

    def _update_pause_menu_labels(self) -> None:
        """Update pause/resume label in menu items based on engine state."""
        label = "Resume All" if self.engine.paused else "Pause All"
        try:
            self.edit_menu.entryconfig(1, label=label)
        except Exception:
            pass

    def _show_settings(self) -> None:
        """Show settings dialog"""
        try:
            dialog = SettingsDialog(self.root, self.config, on_apply_callback=self._apply_settings_realtime)
            result = dialog.show()
            if result:
                self.status_var.set("Settings updated")
        except Exception as e:
            logger.error(f"Error opening settings dialog: {str(e)}", exc_info=True)
            msgbox.showerror("Error", f"Failed to open settings: {str(e)}")

    # Runtime settings methods are in SettingsMixin (settings_mixin.py)

    def _show_shortcuts(self) -> None:
        """Display keyboard shortcuts help popup."""
        msgbox.showinfo(
            "Keyboard Shortcuts",
            "Ctrl+N: Add Window\n"
            "Ctrl+R: Add Region\n"
            "Ctrl+Shift+R: Remove Region\n"
            "Ctrl+Delete: Remove Window\n"
            "Ctrl+S: Save Config\n"
            "Ctrl+Shift+S: Save Config As\n"
            "Alt+1..9, Alt+0: Focus assigned window slots 1..10\n"
            "F6: Pause / Resume\n"
            "Ctrl+Q: Exit"
        )
    
    def _add_region(self) -> None:
        """Add region to selected thumbnail using screen overlay"""
        if not self.selected_thumbnail_id:
            self.status_var.set("Select a thumbnail first by clicking on it")
            return
        
        thumbnail = self.config.get_thumbnail(self.selected_thumbnail_id)
        if not thumbnail:
            self.status_var.set("Thumbnail not found")
            return
        
        thumbnail_id = thumbnail['id']
        hwnd = thumbnail['window_hwnd']
        title = thumbnail.get('window_title', 'Unknown')
        
        logger.info(f"Starting region selection for: {title} (id={thumbnail_id}, hwnd={hwnd})")
        
        try:
            def _get_client_rect_screen(target_hwnd: int) -> tuple[int, int, int, int]:
                """Return client-area rect as (x, y, width, height) in screen coordinates."""
                try:
                    client = win32gui.GetClientRect(target_hwnd)
                    if not client:
                        raise RuntimeError("GetClientRect returned empty")
                    top_left = win32gui.ClientToScreen(target_hwnd, (0, 0))
                    bottom_right = win32gui.ClientToScreen(target_hwnd, (client[2], client[3]))
                    x = int(top_left[0])
                    y = int(top_left[1])
                    width = max(1, int(bottom_right[0] - top_left[0]))
                    height = max(1, int(bottom_right[1] - top_left[1]))
                    return x, y, width, height
                except Exception as error:
                    logger.warning("Falling back to window rect for region conversion: %s", error)
                    rect = win32gui.GetWindowRect(target_hwnd)
                    x = int(rect[0])
                    y = int(rect[1])
                    width = max(1, int(rect[2] - rect[0]))
                    height = max(1, int(rect[3] - rect[1]))
                    return x, y, width, height

            # Activate the window (bring to front)
            self.window_manager.activate_window(hwnd)

            # Minimize ScreenAlert window so target app remains visible for selection
            self.root.iconify()
            self.root.update_idletasks()
            time.sleep(0.15)

            # Get latest client-area position after activation for accurate conversion.
            window_x, window_y, window_width, window_height = _get_client_rect_screen(hwnd)
            logger.info(f"Window position: ({window_x}, {window_y}), size: {window_width}x{window_height}")
            
            # Show region selection overlay
            overlay = RegionSelectionOverlay(hwnd, self.root)
            regions_screen = overlay.show()  # Screen coordinates
            
            # Show the ScreenAlert window again
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            
            if regions_screen:
                # Position can shift during selection (focus/move), refresh once more.
                window_x, window_y, window_width, window_height = _get_client_rect_screen(hwnd)

                # Convert screen coordinates to window-relative coordinates
                last_added_region_id = None
                for i, (x, y, w, h) in enumerate(regions_screen):
                    # Convert screen coords to window-relative
                    region_x = x - window_x
                    region_y = y - window_y
                    
                    # Clamp to window bounds
                    region_x = max(0, min(region_x, window_width - w))
                    region_y = max(0, min(region_y, window_height - h))
                    
                    # Note: engine.add_region() internally calls config.add_region_to_thumbnail()
                    # so we only need to call the engine method
                    last_added_region_id = self.engine.add_region(thumbnail_id, f"Region_{i+1}", (region_x, region_y, w, h))
                    logger.info(f"Added region {i+1}: window-relative ({region_x}, {region_y}, {w}, {h})")
                
                self.status_var.set(f"Added {len(regions_screen)} region(s) to {title}")
                self._pending_tree_focus_window_id = thumbnail_id
                self._pending_tree_focus_region_id = last_added_region_id
                if self.tree_filter_var:
                    self.tree_filter_var.set("")
                self.show_all_regions = False
                self._update_thumbnail_list()
            else:
                self.status_var.set("Region selection cancelled")
                
        except Exception as e:
            self.root.deiconify()  # Ensure window is visible even on error
            self.root.lift()
            logger.error(f"Error adding region to '{title}': {str(e)}", exc_info=True)
            msgbox.showerror("Error", f"Failed to add region: {str(e)}")

    
    def _remove_region(self) -> None:
        """Remove region from selected thumbnail"""
        if not self.selected_thumbnail_id:
            self.status_var.set("Select a thumbnail first by clicking on it")
            return
        
        thumbnail = self.config.get_thumbnail(self.selected_thumbnail_id)
        if not thumbnail:
            self.status_var.set("Thumbnail not found")
            return
        
        thumbnail_id = thumbnail['id']
        title = thumbnail.get('window_title', 'Unknown')
        regions = thumbnail.get('monitored_regions', [])
        
        if not regions:
            msgbox.showinfo("No Regions", f"'{title}' has no regions to remove")
            return
        
        # Create a simple list for user to select which region to remove
        region_choices = [f"{r.get('name', 'Unknown')} - {r['rect']}" for r in regions]
        
        # Create a simple dialog to select region
        dialog = tk.Toplevel(self.root)
        dialog.title("Remove Region")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text=f"Select region to remove from '{title}':").pack(padx=10, pady=10)
        
        # Listbox for regions
        listbox = tk.Listbox(dialog, height=10, font=("Segoe UI", 10))
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        for choice in region_choices:
            listbox.insert(tk.END, choice)
        
        if listbox.size() > 0:
            listbox.selection_set(0)
        
        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        def remove_selected():
            selection = listbox.curselection()
            if not selection:
                msgbox.showwarning("Warning", "Please select a region")
                return
            
            region_idx = selection[0]
            region = regions[region_idx]
            region_id = region.get('id')
            region_name = region.get('name', 'Unknown')
            
            try:
                self.engine.monitoring_engine.remove_region(region_id)
                self.config.remove_region(thumbnail_id, region_id)
                self.config.save()
                if thumbnail_id in self.region_statuses:
                    self.region_statuses[thumbnail_id].pop(region_id, None)
                self.region_to_thumbnail.pop(region_id, None)
                self.pending_status_changes.pop(region_id, None)
                self.dirty_regions.pop(region_id, None)
                if self.selected_region_id == region_id:
                    self.selected_region_id = None
                self.status_var.set(f"Removed region '{region_name}' from {title}")
                self._update_thumbnail_list()
                dialog.destroy()
            except Exception as e:
                logger.error(f"Error removing region: {str(e)}", exc_info=True)
                msgbox.showerror("Error", f"Failed to remove region: {str(e)}")
        
        ttk.Button(btn_frame, text="Remove", command=remove_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def _remove_thumbnail(self) -> None:
        """Remove selected thumbnail"""
        if not self.selected_thumbnail_id:
            self.status_var.set("Select a thumbnail to remove by clicking on it")
            return
        
        thumbnail = self.config.get_thumbnail(self.selected_thumbnail_id)
        if not thumbnail:
            self.status_var.set("Thumbnail not found")
            return
        
        thumbnail_id = thumbnail['id']
        hwnd = thumbnail['window_hwnd']
        title = thumbnail.get('window_title', 'Unknown')
        
        # Confirm deletion
        if not msgbox.askyesno("Confirm", f"Remove '{title}' and all its regions?"):
            return
        
        try:
            self.engine.remove_thumbnail(thumbnail_id)
            self.config.remove_thumbnail(thumbnail_id)
            self.region_statuses.pop(thumbnail_id, None)
            if hwnd in self.thumbnail_map:
                del self.thumbnail_map[hwnd]
            self.selected_thumbnail_id = None
            self._update_thumbnail_list()
            self.status_var.set(f"Removed: {title}")
        except Exception as e:
            logger.error(f"Error removing window '{title}': {str(e)}", exc_info=True)
            msgbox.showerror("Error", f"Failed to remove window: {str(e)}")
    
    def _show_about(self) -> None:
        """Show about dialog"""
        try:
            msgbox.showinfo("About ScreenAlert", 
                           "ScreenAlert v2.0.2\n\n"
                           "Advanced multi-window change detection\n"
                           "with Pygame-based overlays")
        except Exception as e:
            logger.error(f"Error showing about dialog: {str(e)}", exc_info=True)

    def _save_config(self) -> None:
        """Save current configuration to active config file."""
        if self.config.save():
            self.status_var.set("Configuration saved")
        else:
            msgbox.showerror("Save Failed", "Failed to save configuration")

    def _save_config_as(self) -> None:
        """Save current configuration snapshot to a user-selected file."""
        path = filedialog.asksaveasfilename(
            title="Save configuration as",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        if self.config.export_config(path):
            self.status_var.set(f"Configuration exported: {path}")
        else:
            msgbox.showerror("Save As Failed", "Failed to export configuration")

    def _open_logs_folder(self) -> None:
        """Open application logs directory in Windows File Explorer."""
        try:
            os.makedirs(LOGS_DIR, exist_ok=True)
            os.startfile(LOGS_DIR)
        except Exception:
            try:
                subprocess.Popen(["explorer", LOGS_DIR])
            except Exception as error:
                logger.error(f"Failed to open logs folder: {error}")
                msgbox.showerror("Logs", f"Unable to open logs folder:\n{LOGS_DIR}")

    def _on_tree_right_click(self, event) -> None:
        """Show context menu based on tree node type (all/window/region)."""
        item_id = self.window_tree.identify_row(event.y)
        if not item_id:
            return

        self._set_tree_selection(item_id)
        kind = self._tree_item_kind(item_id)

        if kind == "window":
            self.show_all_regions = False
            self.selected_thumbnail_id = item_id
        elif kind == "region":
            self.show_all_regions = False
            self.selected_thumbnail_id = self.region_to_thumbnail.get(item_id)
        else:
            self.show_all_regions = True

        menu = tk.Menu(self.root, tearoff=0)
        if kind == "all":
            menu.add_command(label="Add Window", command=self._add_window)
            menu.add_command(
                label="Enable All Overlays",
                command=self._enable_all_overlays,
                state=tk.NORMAL,
            )
            menu.add_command(label=("Resume All" if self.engine.paused else "Pause All"), command=self._toggle_pause)
            menu.add_command(label="Reconnect All Windows", command=self._reconnect_all_windows)
            menu.add_separator()
            can_remove = bool(self.selected_thumbnail_id and self.config.get_thumbnail(self.selected_thumbnail_id))
            menu.add_command(
                label="Remove Window",
                command=self._remove_thumbnail,
                state=(tk.NORMAL if can_remove else tk.DISABLED),
            )
        elif kind == "window":
            menu.add_command(label="Add Region", command=self._add_region)
            menu.add_command(
                label="Enable Overlay",
                command=self._enable_selected_overlay,
                state=tk.NORMAL,
            )
            menu.add_command(label="Reconnect Window", command=self._reconnect_selected_window)
            menu.add_command(label="Remove All Regions", command=self._remove_all_regions)
            menu.add_separator()
            menu.add_command(label="Remove Window", command=self._remove_thumbnail)
        elif kind == "region":
            menu.add_command(label="Remove Region", command=self._remove_region_direct)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _tree_item_kind(self, item_id: str) -> str:
        """Return kind for tree item id: all/window/region."""
        if item_id == "__all__":
            return "all"
        if item_id in self.region_to_thumbnail:
            return "region"
        return "window"

    def _remove_region_direct(self) -> None:
        """Remove currently selected region item directly from tree selection."""
        selection = self.window_tree.selection()
        if not selection:
            return
        region_id = selection[0]
        if region_id not in self.region_to_thumbnail:
            return
        thumbnail_id = self.region_to_thumbnail[region_id]
        region = self.config.get_region(thumbnail_id, region_id)
        if not region:
            return

        region_name = region.get("name", "Region")
        if not msgbox.askyesno("Confirm", f"Remove region '{region_name}'?"):
            return

        self.engine.monitoring_engine.remove_region(region_id)
        self.config.remove_region(thumbnail_id, region_id)
        self.config.save()
        if thumbnail_id in self.region_statuses:
            self.region_statuses[thumbnail_id].pop(region_id, None)
        self.region_to_thumbnail.pop(region_id, None)
        self.pending_status_changes.pop(region_id, None)
        self.dirty_regions.pop(region_id, None)
        if self.selected_region_id == region_id:
            self.selected_region_id = None
        self._update_thumbnail_list()
        self.status_var.set(f"Removed region '{region_name}'")

    def _remove_all_regions(self) -> None:
        """Remove all regions from the selected window."""
        if not self.selected_thumbnail_id:
            return
        thumbnail = self.config.get_thumbnail(self.selected_thumbnail_id)
        if not thumbnail:
            return

        regions = list(thumbnail.get("monitored_regions", []))
        if not regions:
            self.status_var.set("No regions to remove")
            return

        title = thumbnail.get("window_title", "Unknown")
        if not msgbox.askyesno("Confirm", f"Remove all regions from '{title}'?"):
            return

        for region in regions:
            region_id = region.get("id")
            if region_id:
                self.engine.monitoring_engine.remove_region(region_id)
                self.config.remove_region(self.selected_thumbnail_id, region_id)
                self.region_to_thumbnail.pop(region_id, None)
                if self.selected_thumbnail_id in self.region_statuses:
                    self.region_statuses[self.selected_thumbnail_id].pop(region_id, None)

        self.config.save()
        self._update_thumbnail_list()
        self.status_var.set(f"Removed all regions from {title}")

    def _rebuild_thumbnail_map(self) -> None:
        """Rebuild thumbnail_map from config so HWND keys stay in sync."""
        self.thumbnail_map.clear()
        for thumbnail in self.config.get_all_thumbnails():
            hwnd = thumbnail.get('window_hwnd')
            thumbnail_id = thumbnail.get('id')
            if hwnd and thumbnail_id:
                self.thumbnail_map[hwnd] = thumbnail_id

    def _reconnect_all_windows(self) -> None:
        """Manually trigger strict reconnect attempts for all windows."""
        try:
            result = self.engine.reconnect_all_windows()
            self._rebuild_thumbnail_map()
            self.engine.cache_manager.invalidate_all()
            self._update_thumbnail_list()

            self.status_var.set(
                "Reconnect complete: "
                f"{result.get('reconnected', 0)} reconnected, "
                f"{result.get('failed', 0)} failed, "
                f"{result.get('already_valid', 0)} already valid"
            )
        except Exception as error:
            logger.error(f"Error reconnecting windows: {error}", exc_info=True)
            msgbox.showerror("Reconnect", f"Reconnect failed: {error}")

    def _reconnect_selected_window(self) -> None:
        """Manually trigger strict reconnect for currently selected window."""
        thumbnail_id = self.selected_thumbnail_id
        if not thumbnail_id:
            self.status_var.set("Select a window first")
            return

        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if not thumbnail:
            self.status_var.set("Selected window not found")
            return

        title = thumbnail.get("window_title", "Unknown")
        try:
            state = self.engine.reconnect_window(thumbnail_id)
            self._rebuild_thumbnail_map()
            self.engine.cache_manager.invalidate_all()
            self._update_thumbnail_list()

            if state == "reconnected":
                self.status_var.set(f"Reconnected: {title}")
            elif state == "already_valid":
                self.status_var.set(f"Already connected: {title}")
            elif state in ("failed", "missing"):
                self.status_var.set(f"Reconnect failed: {title}")
                if self.config.get_prompt_on_reconnect_fail():
                    self._prompt_reconnect_replacement(thumbnail_id, title)
        except Exception as error:
            logger.error(f"Error reconnecting window '{title}': {error}", exc_info=True)
            msgbox.showerror("Reconnect", f"Reconnect failed: {error}")

    def _prompt_reconnect_replacement(self, thumbnail_id: str, title: str) -> None:
        """After a failed manual reconnect, offer to pick a replacement window."""
        answer = msgbox.askyesno(
            "Reconnect Failed",
            f"Could not reconnect to '{title}'.\n\n"
            "Would you like to select a replacement window?\n"
            "The existing regions and settings will be preserved.",
        )
        if not answer:
            return

        attached_hwnds = self.engine.get_attached_hwnds(exclude_thumbnail_id=thumbnail_id)
        dialog = WindowSelectorDialog(self.root, self.window_manager, self.config,
                                      attached_hwnds=attached_hwnds)
        windows_info = dialog.show()
        if not windows_info or len(windows_info) == 0:
            return

        window_info = windows_info[0]
        new_hwnd = window_info.get('hwnd')
        if not new_hwnd:
            return

        # Capture old size before updating so regions can be scaled
        thumbnail = self.config.get_thumbnail(thumbnail_id)
        old_size = tuple(thumbnail.get("window_size") or []) if thumbnail else ()

        metadata = self.window_manager.get_window_metadata(new_hwnd)
        new_size = window_info.get('size') or (metadata.get('size') if metadata else None)
        updates = {
            "window_hwnd": new_hwnd,
            "window_title": window_info.get('title', title),
            "window_class": window_info.get('class') or (metadata.get('class', '') if metadata else ''),
            "window_size": list(new_size) if new_size else [],
            "monitor_id": window_info.get('monitor_id', metadata.get('monitor_id') if metadata else None),
        }

        self.config.update_thumbnail(thumbnail_id, updates)

        # Scale regions proportionally if window size changed
        if old_size and new_size and len(old_size) == 2 and tuple(new_size) != old_size:
            self.engine.scale_regions_for_new_size(
                thumbnail_id, old_size, tuple(new_size))

        self.config.save()
        self._rebuild_thumbnail_map()

        # Reset engine state so it treats this as a fresh connection
        self.engine._reconnect_attempted_once.discard(thumbnail_id)
        self.engine._window_lost_notified.discard(thumbnail_id)
        self.engine._thumbnail_connected[thumbnail_id] = True
        self.engine.cache_manager.invalidate_all()
        self.engine.renderer.set_source_hwnd(thumbnail_id, new_hwnd)
        self.engine.renderer.set_thumbnail_availability(thumbnail_id, True)

        self._update_thumbnail_list()
        new_title = updates["window_title"]
        self.status_var.set(f"Replaced with: {new_title}")
        logger.info(f"[RECONNECT] Manual replacement for {thumbnail_id}: '{title}' -> '{new_title}' hwnd={new_hwnd}")

    def _set_overlay_enabled(self, thumbnail_id: str, enabled: bool) -> bool:
        """Show/hide a single overlay window without changing monitor state."""
        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if not thumbnail:
            return False

        target_enabled = bool(enabled)
        current_visible = bool(thumbnail.get("overlay_visible",
                                             thumbnail.get("overview_visible", True)))
        if current_visible != target_enabled:
            self.config.update_thumbnail(thumbnail_id, {"overlay_visible": target_enabled})
            self.config.save()

        if target_enabled:
            self.engine.renderer.set_thumbnail_user_visibility(thumbnail_id, True)
            # Re-establish DWM link since it may have been dropped
            window_hwnd = thumbnail.get("window_hwnd")
            if window_hwnd:
                self.engine.renderer.set_source_hwnd(thumbnail_id, window_hwnd)
            self.engine.renderer.set_thumbnail_availability(
                thumbnail_id,
                True,
                self.config.get_show_overlay_when_unavailable(),
            )
        else:
            self.engine.renderer.set_thumbnail_user_visibility(thumbnail_id, False)

        return True

    def _enable_selected_overlay(self) -> None:
        """Enable overlay window for the currently selected thumbnail."""
        if not self.selected_thumbnail_id:
            self.status_var.set("Select a window first")
            return

        thumbnail = self.config.get_thumbnail(self.selected_thumbnail_id)
        if not thumbnail:
            self.status_var.set("Selected window not found")
            return

        title = thumbnail.get("window_title", "Unknown")
        self._set_overlay_enabled(self.selected_thumbnail_id, True)
        self.status_var.set(f"Overlay enabled: {title}")
        self._update_thumbnail_list()

    def _enable_all_overlays(self) -> None:
        """Enable all configured overlay windows."""
        total = 0
        for thumbnail in self.config.get_all_thumbnails():
            thumbnail_id = thumbnail.get("id")
            if not thumbnail_id:
                continue
            self._set_overlay_enabled(thumbnail_id, True)
            total += 1

        self.status_var.set(f"Enabled {total} overlay(s)")
        self._update_thumbnail_list()

    def _close_all_overlays(self) -> None:
        """Close all configured overlay windows visually (keep monitoring active)."""
        total = 0
        for thumbnail in self.config.get_all_thumbnails():
            thumbnail_id = thumbnail.get("id")
            if thumbnail_id:
                self._set_overlay_enabled(thumbnail_id, False)
                total += 1

        self.status_var.set(f"Closed {total} overlay(s)")
        self._update_thumbnail_list()
    
    def _update_thumbnail_list(self) -> None:
        """Update window tree display"""
        for item in self.window_tree.get_children():
            self.window_tree.delete(item)
        self.region_to_thumbnail.clear()
        self._tree_window_icon_meta.clear()
        self._window_tree_icon_strip_cache.clear()
        tree_filter_query = self._get_tree_filter_query()
        
        thumbnails = self.config.get_all_thumbnails()
        active_thumbnails = [thumbnail for thumbnail in thumbnails if self._is_thumbnail_connected(thumbnail)]
        logger.info(
            f"Updating window tree: {len(thumbnails)} configured thumbnails "
            f"({len(active_thumbnails)} active)"
        )
        
        all_root = self.window_tree.insert("", "end", iid="__all__", text="All")
        sorted_thumbnails = sorted(
            thumbnails,
            key=lambda thumbnail: (
                0 if self._is_thumbnail_connected(thumbnail) else 1,
                (thumbnail.get("window_title") or "").casefold(),
            ),
        )

        for thumbnail in sorted_thumbnails:
            thumbnail_id = thumbnail.get("id")
            title = thumbnail.get("window_title", "Unknown")
            regions = list(thumbnail.get("monitored_regions", []))
            
            if not thumbnail_id:
                continue

            title_match = tree_filter_query in title.casefold() if tree_filter_query else True
            if tree_filter_query and not title_match:
                regions_for_tree = [
                    region
                    for region in regions
                    if tree_filter_query in region.get("name", "Region").casefold()
                ]
                if not regions_for_tree:
                    continue
            else:
                regions_for_tree = regions

            window_status = self._get_thumbnail_window_status(thumbnail)
            self._tree_window_icon_meta[thumbnail_id] = self._window_tree_suffix_icons(thumbnail, window_status)
            window_tree_state = self._get_window_tree_state(thumbnail, window_status)
            self.window_tree.insert(
                all_root,
                "end",
                iid=thumbnail_id,
                text="",
                image=self._get_window_tree_icon_image(thumbnail, window_status, window_tree_state),
                tags=(self._window_tree_tag(window_tree_state),),
            )
            if thumbnail_id not in self.region_statuses:
                self.region_statuses[thumbnail_id] = {}
            
            for region in regions_for_tree:
                region_id = region.get("id")
                region_name = region.get("name", "Region")
                if not region_id:
                    continue
                region_status = self._get_region_effective_status(thumbnail, region, window_status)
                # Respect user-selected visibility filters for region states
                if not self._region_status_visible(region_status):
                    continue
                self.window_tree.insert(
                    thumbnail_id,
                    "end",
                    iid=region_id,
                    text=self._format_region_tree_text(region_name, region_status),
                    tags=(self._region_tree_tag(region_status),),
                )
                self.region_to_thumbnail[region_id] = thumbnail_id
                if region_id not in self.region_statuses[thumbnail_id]:
                    self.region_statuses[thumbnail_id][region_id] = "ok"

        self.window_tree.item("__all__", open=True)

        pending_region_id = self._pending_tree_focus_region_id
        pending_window_id = self._pending_tree_focus_window_id
        self._pending_tree_focus_region_id = None
        self._pending_tree_focus_window_id = None

        if pending_region_id and self.window_tree.exists(pending_region_id):
            parent_window_id = self.region_to_thumbnail.get(pending_region_id)
            if parent_window_id and self.window_tree.exists(parent_window_id):
                self.window_tree.item(parent_window_id, open=True)
                self.show_all_regions = False
                self.selected_region_id = pending_region_id
                self._set_tree_selection(pending_region_id)
                self.window_tree.see(pending_region_id)
                self._select_thumbnail(parent_window_id)
                return

        if pending_window_id and self.window_tree.exists(pending_window_id):
            self.window_tree.item(pending_window_id, open=True)
            self.show_all_regions = False
            self.selected_region_id = None
            self._set_tree_selection(pending_window_id)
            self.window_tree.see(pending_window_id)
            self._select_thumbnail(pending_window_id)
            return

        if thumbnails and self.show_all_regions:
            self._set_tree_selection("__all__")
            self.window_tree.see("__all__")
            self._show_all_regions()
        elif thumbnails:
            if self.selected_region_id and self.window_tree.exists(self.selected_region_id):
                parent_window_id = self.region_to_thumbnail.get(self.selected_region_id)
                if parent_window_id and self.window_tree.exists(parent_window_id):
                    self.window_tree.item(parent_window_id, open=True)
                    self._set_tree_selection(self.selected_region_id)
                    self.window_tree.see(self.selected_region_id)
                    self._select_thumbnail(parent_window_id)
                    return

            if self.selected_thumbnail_id and self.window_tree.exists(self.selected_thumbnail_id):
                self._set_tree_selection(self.selected_thumbnail_id)
                self.window_tree.see(self.selected_thumbnail_id)
                self._select_thumbnail(self.selected_thumbnail_id)
                return

            visible_windows = self.window_tree.get_children(all_root)
            if visible_windows:
                first_id = visible_windows[0]
                self._set_tree_selection(first_id)
                self.window_tree.see(first_id)
                self._select_thumbnail(first_id)
            else:
                self.show_all_regions = True
                self._set_tree_selection("__all__")
                self.window_tree.see("__all__")
                self._show_all_regions()
        elif not thumbnails:
            self.selected_thumbnail_id = None
            self._clear_detail_view()


    
    def _on_tree_select(self, event) -> None:
        """Handle tree selection"""
        if self._suppress_tree_select_event:
            return
        selection = self.window_tree.selection()
        if not selection:
            return
        selected_id = selection[0]
        if selected_id == "__all__":
            if self.show_all_regions:
                return
            self._show_all_regions()
            return
        self.show_all_regions = False
        if selected_id in self.region_to_thumbnail:
            thumbnail_id = self.region_to_thumbnail[selected_id]
            self.selected_region_id = selected_id
        else:
            thumbnail_id = selected_id
            self.selected_region_id = None
        if thumbnail_id == self.selected_thumbnail_id and not self.show_all_regions:
            thumbnail = self.config.get_thumbnail(thumbnail_id)
            if thumbnail:
                self._render_window_detail(thumbnail)
            return
        self._select_thumbnail(thumbnail_id)

    def _set_tree_selection(self, item_id: str) -> None:
        """Set tree selection without re-entrant select handling."""
        if not self.window_tree.exists(item_id):
            return
        self._suppress_tree_select_event = True
        try:
            self.window_tree.selection_set(item_id)
        finally:
            self.root.after_idle(self._clear_tree_select_suppression)

    def _clear_tree_select_suppression(self) -> None:
        """Release tree selection suppression after UI settles."""
        self._suppress_tree_select_event = False

    def _select_thumbnail(self, thumbnail_id: str) -> None:
        """Set selection and refresh detail view"""
        self.selected_thumbnail_id = thumbnail_id
        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if thumbnail:
            title = thumbnail.get("window_title", "Unknown")
            regions = thumbnail.get("monitored_regions", [])
            if self.selected_region_id and self.config.get_region(thumbnail_id, self.selected_region_id):
                region_name = self.config.get_region(thumbnail_id, self.selected_region_id).get("name", "Region")
                self.status_var.set(f"Selected: {title} -> {region_name}")
            else:
                self.status_var.set(f"Selected: {title} ({len(regions)} regions)")
            self._render_window_detail(thumbnail)
            logger.debug(f"Selected thumbnail: {title}")

    def _get_window_image_for_ui(self, hwnd: Optional[int], thumbnail: Optional[Dict] = None):
        """Get image for UI previews with strict identity validation."""
        if not hwnd:
            return None

        if thumbnail:
            if not self._is_thumbnail_connected(thumbnail):
                return None

        window_image = self.engine.cache_manager.get(hwnd)
        if window_image is not None:
            return window_image

        try:
            window_image = self.window_manager.capture_window(hwnd)
            if window_image is not None:
                self.engine.cache_manager.set(hwnd, window_image)
            return window_image
        except Exception as error:
            logger.debug(f"UI preview capture failed for hwnd={hwnd}: {error}")
            return None

    def _run_on_ui_thread(self, callback, *args) -> bool:
        """Schedule callback on Tk UI thread when called from worker threads.

        Returns:
            True if callback was scheduled (caller should return early),
            False if already on UI thread and caller can continue immediately.
        """
        if threading.current_thread() is threading.main_thread():
            return False
        try:
            self.root.after(0, lambda: callback(*args))
            return True
        except Exception as error:
            logger.warning(f"Failed to marshal callback to UI thread: {error}")
            return False

    # Engine event methods are in EngineEventMixin (engine_event_mixin.py)

    def _render_window_detail(self, thumbnail: Optional[Dict]) -> None:
        """Render window info and region cards"""
        for widget in self.regions_inner_frame.winfo_children():
            widget.destroy()
        self.region_widgets.clear()
        self.region_photos.clear()
        displayed_regions = 0
        total_regions = 0
        
        if self.show_all_regions or not thumbnail:
            self.info_frame.grid_remove()
            self.regions_frame.grid(row=0, column=0, sticky="nsew")
            self.detail_frame.rowconfigure(0, weight=1)
            self.detail_frame.rowconfigure(1, weight=0)
            thumbnails = self.config.get_all_thumbnails()
            active_thumbnails = [t for t in thumbnails if self._is_thumbnail_connected(t)]
            total_regions = sum(len(t.get("monitored_regions", [])) for t in thumbnails)
            self.window_title_var.set("All windows")
            self.window_hwnd_var.set("")
            self.window_region_count_var.set(str(total_regions))
            self.window_size_var.set("")
            self.window_slot_var.set("-")
            self.window_slot_combo.configure(state="disabled")
            self.window_primary_var.set(False)
            self.window_primary_checkbox.state(["disabled"])
            self.window_alert_focus_var.set(False)
            self.window_alert_focus_checkbox.state(["disabled"])

            preview_image = None
            if len(active_thumbnails) == 1:
                selected_thumb = active_thumbnails[0]
                preview_hwnd = selected_thumb.get("window_hwnd")
                preview_image = self._get_window_image_for_ui(preview_hwnd, selected_thumb)
            if preview_image:
                preview = preview_image.copy()
                preview.thumbnail((180, 100), Image.Resampling.LANCZOS)
                self.window_preview_photo = ImageTk.PhotoImage(preview)
                self.window_preview_label.config(image=self.window_preview_photo, text="", style='App.Preview.TLabel')
            else:
                self._set_preview_placeholder("No connected windows")
            
            row = 0
            for thumb in active_thumbnails:
                thumb_id = thumb.get("id")
                if not thumb_id:
                    continue
                hwnd = thumb.get("window_hwnd")
                window_image = self._get_window_image_for_ui(hwnd, thumb)
                window_status = self._get_thumbnail_window_status(thumb)
                for region in thumb.get("monitored_regions", []):
                    region_id = region.get("id")
                    if not region_id:
                        continue
                    region_status = self._get_region_effective_status(thumb, region, window_status)
                    if not self._region_status_visible(region_status):
                        continue
                    self._create_region_card(thumb_id, region_id, region, window_image, row,
                                             window_title=thumb.get("window_title", "Unknown"))
                    row += 1
            displayed_regions = row
        else:
            self.info_frame.grid()
            self.regions_frame.grid(row=1, column=0, sticky="nsew")
            self.detail_frame.rowconfigure(0, weight=0)
            self.detail_frame.rowconfigure(1, weight=1)
            thumbnail_id = thumbnail.get("id")
            title = thumbnail.get("window_title", "Unknown")
            hwnd = thumbnail.get("window_hwnd")
            regions = thumbnail.get("monitored_regions", [])

            if thumbnail_id:
                self._assign_default_slot_if_missing(thumbnail_id)
                refreshed_thumbnail = self.config.get_thumbnail(thumbnail_id)
                if refreshed_thumbnail:
                    thumbnail = refreshed_thumbnail
                    title = thumbnail.get("window_title", "Unknown")
                    hwnd = thumbnail.get("window_hwnd")
                    regions = thumbnail.get("monitored_regions", [])
            
            self.window_title_var.set(title)
            self.window_hwnd_var.set(str(hwnd) if hwnd else "")
            self.window_region_count_var.set(str(len(regions)))
            self._refresh_focus_option_states()
            slot = self._get_window_slot(thumbnail)
            self.window_slot_var.set(str(slot) if slot else "-")
            self.window_slot_combo.configure(state="readonly")
            size = thumbnail.get("window_size")
            if isinstance(size, (list, tuple)) and len(size) == 2:
                self.window_size_var.set(f"{size[0]}x{size[1]}")
            else:
                self.window_size_var.set("")
            
            window_image = self._get_window_image_for_ui(hwnd, thumbnail)
            
            if window_image:
                preview = window_image.copy()
                preview.thumbnail((180, 100), Image.Resampling.LANCZOS)
                self.window_preview_photo = ImageTk.PhotoImage(preview)
                self.window_preview_label.config(image=self.window_preview_photo, text="", style='App.Preview.TLabel')
            else:
                self._set_preview_placeholder("No preview")
            
            regions_to_render = regions
            if self.selected_region_id:
                selected = [r for r in regions if r.get("id") == self.selected_region_id]
                if selected:
                    regions_to_render = selected

            total_regions = len(regions)

            for idx, region in enumerate(regions_to_render):
                region_id = region.get("id")
                if not region_id:
                    continue
                window_status = self._get_thumbnail_window_status(thumbnail)
                region_status = self._get_region_effective_status(thumbnail, region, window_status)
                if not self._region_status_visible(region_status):
                    continue
                self._create_region_card(thumbnail_id, region_id, region, window_image, idx)
                displayed_regions += 1

        self.regions_frame.configure(text=f"Regions ({displayed_regions}/{total_regions})")

        self._schedule_detail_scroll_refresh()

    def _schedule_detail_scroll_refresh(self) -> None:
        """Coalesce detail panel scrollregion updates to idle time."""
        if self._detail_scroll_update_scheduled:
            return
        self._detail_scroll_update_scheduled = True
        self.root.after_idle(self._refresh_detail_scrollregion)

    def _refresh_detail_scrollregion(self) -> None:
        """Refresh scrollregion once UI geometry has settled."""
        self._detail_scroll_update_scheduled = False
        try:
            bbox = self.region_canvas.bbox("all")
            if bbox:
                self.region_canvas.configure(scrollregion=bbox)
            else:
                self.region_canvas.configure(scrollregion=(0, 0, 0, 0))
            self.region_scroll.set(*self.region_canvas.yview())
        except Exception as error:
            logger.debug(f"Unable to refresh detail scrollregion: {error}")

    def _clear_detail_view(self) -> None:
        """Clear window detail panel"""
        self.window_title_var.set("")
        self.window_hwnd_var.set("")
        self.window_region_count_var.set("0")
        self.regions_frame.configure(text="Regions (0/0)")
        self.window_size_var.set("")
        self.window_slot_var.set("-")
        self.window_slot_combo.configure(state="disabled")
        self.window_primary_var.set(False)
        self.window_primary_checkbox.state(["disabled"])
        self.window_alert_focus_var.set(False)
        self.window_alert_focus_checkbox.state(["disabled"])
        self._set_preview_placeholder("No window selected")
        for widget in self.regions_inner_frame.winfo_children():
            widget.destroy()
        self.region_widgets.clear()
        self.region_photos.clear()
        self._schedule_detail_scroll_refresh()

    def _create_region_card(self, thumbnail_id: str, region_id: str, region: Dict,
                             window_image, row: int, window_title: Optional[str] = None) -> None:
        """Create a region card row"""
        card = ttk.Frame(self.regions_inner_frame, style="App.Card.TFrame")
        card.grid(row=row, column=0, sticky="ew", pady=4, padx=4)
        card.columnconfigure(2, weight=1)
        
        content_row = 0
        
        # Left status pill
        status_pill = ttk.Label(card, text="OK", style="App.Status.Ok.TLabel", width=7, anchor="center")
        status_pill.grid(row=content_row, column=0, rowspan=2, sticky="ns", padx=(4, 0), pady=3)
        
        # Region image
        image_label = ttk.Label(card, style="App.Image.TLabel", anchor="center")
        image_label.grid(row=content_row, column=1, rowspan=2, sticky="w", padx=6, pady=3)
        
        if window_image:
            try:
                region_image = ImageProcessor.crop_region(window_image, region.get("rect", (0, 0, 0, 0)))
                region_image.thumbnail((220, 96), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(region_image)
                self.region_photos[region_id] = photo
                image_label.config(image=photo, text="", style="App.Image.TLabel")
            except Exception as e:
                logger.error(f"Error creating region image {region_id}: {e}", exc_info=True)
                image_label.config(image="", text="No image", style="App.ImageUnavailable.TLabel")
        else:
            image_label.config(image="", text="Not Available", style="App.ImageUnavailable.TLabel")
        
        # Region form fields (name + alert text)
        form_frame = ttk.Frame(card, style="App.CardInner.TFrame")
        form_frame.grid(row=content_row, column=2, rowspan=2, sticky="nsew", padx=(0, 8), pady=(4, 4))

        row_offset = 0
        if window_title:
            ttk.Label(form_frame, text="Window:", style="App.Muted.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 6))
            ttk.Label(form_frame, text=window_title, style="App.Muted.TLabel").grid(row=0, column=1, sticky="w")
            row_offset = 1

        ttk.Label(form_frame, text="Name:", style="App.Muted.TLabel").grid(row=row_offset, column=0, sticky="w", padx=(0, 6), pady=(2 if row_offset else 0, 0))
        name_var = tk.StringVar(value=region.get("name", "Region"))
        name_entry = ttk.Entry(form_frame, textvariable=name_var, width=24)
        name_entry.grid(row=row_offset, column=1, sticky="w", pady=(2 if row_offset else 0, 0))
        name_entry.bind("<Return>", lambda e: self._save_region_name(thumbnail_id, region_id, name_var))
        name_entry.bind("<FocusOut>", lambda e: self._save_region_name(thumbnail_id, region_id, name_var))

        ttk.Label(form_frame, text="Alert Text:", style="App.Muted.TLabel").grid(row=row_offset + 1, column=0, sticky="w", padx=(0, 6), pady=(3, 0))
        alert_text_var = tk.StringVar(value=region.get("tts_message", self.config.get_default_tts_message()))
        alert_text_entry = ttk.Entry(form_frame, textvariable=alert_text_var, width=24)
        alert_text_entry.grid(row=row_offset + 1, column=1, sticky="w", pady=(3, 0))
        alert_text_entry.bind("<Return>", lambda e: self._save_region_alert_text(thumbnail_id, region_id, alert_text_var))
        alert_text_entry.bind("<FocusOut>", lambda e: self._save_region_alert_text(thumbnail_id, region_id, alert_text_var))

        # Live detection metrics (updated each tick)
        detect_info_label = ttk.Label(form_frame, text="", style="App.Muted.TLabel")
        detect_info_label.grid(row=row_offset + 2, column=0, columnspan=2, sticky="w", pady=(2, 0))

        # Right control panel
        controls_panel = ttk.Frame(card, style="App.Controls.TFrame")
        controls_panel.grid(row=content_row, column=3, rowspan=2, sticky="ne", padx=(0, 6), pady=4)
        
        pause_btn = ttk.Button(controls_panel, style="App.RegionAction.TButton", text="Pause", width=8, command=lambda: self._toggle_region_pause(region_id))
        pause_btn.pack(padx=2, pady=(0, 4))

        enabled_now = bool(region.get("enabled", True))
        disable_btn = ttk.Button(
            controls_panel,
            style="App.RegionAction.TButton",
            text=("Disable" if enabled_now else "Enable"),
            width=8,
            command=lambda: self._toggle_region_enabled(thumbnail_id, region_id)
        )
        disable_btn.pack(padx=2, pady=0)

        detect_btn = ttk.Button(
            controls_panel,
            style="App.RegionAction.TButton",
            text="Detect",
            width=8,
            command=lambda tid=thumbnail_id, rid=region_id: self._open_region_detection_dialog(tid, rid),
        )
        detect_btn.pack(padx=2, pady=(4, 0))

        self.region_widgets[region_id] = {
            "status_pill": status_pill,
            "pause_btn": pause_btn,
            "disable_btn": disable_btn,
            "detect_btn": detect_btn,
            "name_entry": name_entry,
            "alert_text_entry": alert_text_entry,
            "detect_info_label": detect_info_label,
            "image_label": image_label,
        }
        
        if not window_image:
            # Do not treat a transient preview/capture miss as the canonical
            # region availability state. Resolve the region status from the
            # monitoring engine and window connectivity instead. Only fall
            # back to 'unavailable' when the thumbnail/window is not connected
            # or no monitor exists for the region.
            thumbnail = self.config.get_thumbnail(thumbnail_id)
            try:
                window_status = self._get_thumbnail_window_status(thumbnail) if thumbnail else None
                region_status = self._get_region_effective_status(thumbnail or {}, region, window_status)
            except Exception:
                region_status = "unavailable"
            # If region is explicitly disabled, prefer that state
            if not enabled_now:
                region_status = "disabled"

            self._set_region_status(thumbnail_id, region_id, region_status)
            self._apply_region_status(thumbnail_id, region_id)
        else:
            # Normal case: a preview image exists; still compute canonical
            # region status via monitoring/window state to avoid brief N/A
            # flicker due to capture failures.
            thumbnail = self.config.get_thumbnail(thumbnail_id)
            try:
                window_status = self._get_thumbnail_window_status(thumbnail) if thumbnail else None
                region_status = self._get_region_effective_status(thumbnail or {}, region, window_status)
            except Exception:
                region_status = "ok"
            if not enabled_now:
                region_status = "disabled"
            self._set_region_status(thumbnail_id, region_id, region_status)
            self._apply_region_status(thumbnail_id, region_id)

    def _toggle_region_enabled(self, thumbnail_id: str, region_id: str) -> None:
        """Enable/disable monitoring for a specific region."""
        region = self.config.get_region(thumbnail_id, region_id)
        if not region:
            return
        enabled = bool(region.get("enabled", True))
        new_enabled = not enabled

        if self.config.update_region(thumbnail_id, region_id, {"enabled": new_enabled}):
            monitor = self.engine.monitoring_engine.get_monitor(region_id)
            if monitor:
                monitor.set_enabled(new_enabled)
            self.config.save()

            widgets = self.region_widgets.get(region_id, {})
            disable_btn = widgets.get("disable_btn")
            if disable_btn:
                disable_btn.config(text=("Disable" if new_enabled else "Enable"))

            if new_enabled:
                self._mark_dirty(thumbnail_id, region_id, status="ok")
                self.status_var.set("Region enabled")
            else:
                self._mark_dirty(thumbnail_id, region_id, status="disabled")
                self.status_var.set("Region disabled")

    def _open_region_detection_dialog(self, thumbnail_id: str, region_id: str) -> None:
        """Open per-region detection settings dialog."""
        region = self.config.get_region(thumbnail_id, region_id)
        if not region:
            return

        # Build a flat global config dict for fallback values
        global_cfg = {
            "change_detection_method": self.config.get_change_detection_method(),
            "default_alert_threshold": self.config.get_default_alert_threshold(),
            "min_edge_fraction": self.config.get_min_edge_fraction(),
            "canny_low": self.config.get_canny_low(),
            "canny_high": self.config.get_canny_high(),
            "edge_binarize": self.config.get_edge_binarize(),
            "bg_history": self.config.get_bg_history(),
            "bg_var_threshold": self.config.get_bg_var_threshold(),
            "bg_min_fg_fraction": self.config.get_bg_min_fg_fraction(),
            "bg_warmup_frames": self.config.get_bg_warmup_frames(),
        }

        def on_apply(updates: Dict) -> None:
            # Persist detection overrides to the region config
            if self.config.update_region(thumbnail_id, region_id, updates):
                self.config.save()

            # Update the live monitor's detector
            monitor = self.engine.monitoring_engine.get_monitor(region_id)
            if monitor:
                method = updates.get("detection_method") or global_cfg.get("change_detection_method", "ssim")
                monitor.set_detector(method, global_config=global_cfg, **updates)

            self.status_var.set(f"Detection settings updated for region")

        RegionDetectionDialog(self.root, region, global_config=global_cfg, on_apply=on_apply)

    def _save_region_name(self, thumbnail_id: str, region_id: str, name_var: tk.StringVar) -> None:
        """Persist region name changes"""
        new_name = name_var.get().strip()
        if not new_name:
            return
        if self.config.update_region(thumbnail_id, region_id, {"name": new_name}):
            self.config.save()
            if self.window_tree.exists(region_id):
                thumbnail = self.config.get_thumbnail(thumbnail_id)
                region = self.config.get_region(thumbnail_id, region_id)
                if thumbnail and region:
                    window_status = self._get_thumbnail_window_status(thumbnail)
                    region_status = self._get_region_effective_status(thumbnail, region, window_status)
                    self.window_tree.item(
                        region_id,
                        text=self._format_region_tree_text(new_name, region_status),
                    )

    def _save_region_alert_text(self, thumbnail_id: str, region_id: str, alert_text_var: tk.StringVar) -> None:
        """Persist region alert TTS template text."""
        value = alert_text_var.get().strip() or self.config.get_default_tts_message()
        if self.config.update_region(thumbnail_id, region_id, {"tts_message": value}):
            self.config.save()

    def _toggle_region_pause(self, region_id: str) -> None:
        """Toggle pause state for a region monitor"""
        monitor = self.engine.monitoring_engine.get_monitor(region_id)
        if not monitor:
            return
        paused = monitor.toggle_pause()
        widget = self.region_widgets.get(region_id, {}).get("pause_btn")
        if widget:
            widget.config(text="Resume" if paused else "Pause")
        
        thumbnail_id = self.region_to_thumbnail.get(region_id)
        if thumbnail_id:
            # Use dirty flag system for status updates
            new_status = "paused" if paused else "ok"
            self._mark_dirty(thumbnail_id, region_id, status=new_status)

    def _set_region_status(self, thumbnail_id: str, region_id: str, status: str) -> None:
        """Set stored status - use _mark_dirty() instead for updates"""
        # This method is now only used internally by _apply_region_status
        if thumbnail_id not in self.region_statuses:
            self.region_statuses[thumbnail_id] = {}
        self.region_statuses[thumbnail_id][region_id] = status

    def _apply_region_status(self, thumbnail_id: str, region_id: str) -> None:
        """Apply status to region UI"""
        status = self.region_statuses.get(thumbnail_id, {}).get(region_id, "ok")
        widgets = self.region_widgets.get(region_id, {})
        pill = widgets.get("status_pill")
        if not pill:
            return
        status_text = self._format_region_status_text(region_id, status)
        if status == "alert":
            pill.config(text=status_text, style="App.Status.Alert.TLabel")
        elif status == "warning":
            pill.config(text=status_text, style="App.Status.Warning.TLabel")
        elif status == "paused":
            pill.config(text=status_text, style="App.Status.Info.TLabel")
        elif status == "unavailable":
            pill.config(text=status_text, style="App.Status.Info.TLabel")
        elif status == "disabled":
            pill.config(text=status_text, style="App.Status.Disabled.TLabel")
        else:
            pill.config(text=status_text, style="App.Status.Ok.TLabel")

        # Update live detection metrics label (only if changed)
        info_label = widgets.get("detect_info_label")
        if info_label:
            info_text = self._format_detect_info(region_id)
            try:
                if str(info_label.cget("text")) != info_text:
                    info_label.config(text=info_text)
            except tk.TclError:
                pass

    def _format_region_status_text(self, region_id: str, status: str) -> str:
        """Build region status text, including countdown for timed states."""
        base_map = {
            "alert": "ALERT",
            "warning": "WARNING",
            "paused": "PAUSED",
            "disabled": "Disabled",
            "unavailable": "N/A",
            "ok": "OK",
        }
        base = base_map.get(status, "OK")

        if status not in ("alert", "warning"):
            return base

        monitor = self.engine.monitoring_engine.get_monitor(region_id)
        if not monitor:
            return base

        remaining = monitor.get_state_remaining_seconds(self.config.get_alert_hold_seconds())
        if remaining is None:
            return base
        return f"{base}\n{remaining:02d}s"

    def _format_detect_info(self, region_id: str) -> str:
        """Build a short string showing live detection metrics for a region."""
        monitor = self.engine.monitoring_engine.get_monitor(region_id)
        if not monitor:
            return ""
        info = monitor.detector.last_detect_info
        if not info:
            return ""
        method = monitor.detector_method
        if method in ("ssim", "phash"):
            sim = info.get("similarity", 0)
            thr = info.get("threshold", 0)
            return f"Similarity: {sim:.4f}  (threshold: {thr})"
        elif method == "edge_only":
            pct = info.get("edge_change_pct", 0)
            mn = info.get("min_edge_pct", 0)
            return f"Edge change: {pct:.3f}%  (min: {mn:.3f}%)"
        elif method == "background_subtraction":
            fg = info.get("fg_pct", 0)
            mn = info.get("min_fg_pct", 0)
            warmup = info.get("warmed_up", False)
            fc = info.get("frame_count", 0)
            if not warmup:
                return f"Warmup: frame {fc}"
            return f"FG: {fg:.3f}%  (min: {mn:.3f}%)"
        return ""

    def _get_thumbnail_window_status(self, thumbnail: Dict) -> str:
        """Return effective window status for thumbnail tree/detail rendering."""
        if not bool(thumbnail.get("enabled", True)):
            return "disabled"
        if self._is_thumbnail_connected(thumbnail):
            return "connected"
        return "unavailable"

    def _is_thumbnail_connected(self, thumbnail: Dict) -> bool:
        """Return True when thumbnail is currently connected to the expected window.

        Uses the engine's cached connection status (updated every main-loop tick)
        to avoid blocking Win32 API calls on the UI thread.
        """
        thumbnail_id = thumbnail.get("id")
        if not thumbnail_id:
            return False
        return self.engine.is_thumbnail_connected(thumbnail_id)

    def _get_region_effective_status(self, thumbnail: Dict, region: Dict, window_status: Optional[str] = None) -> str:
        """Return effective region status used for tree node coloring."""
        thumbnail_id = thumbnail.get("id")
        region_id = region.get("id")
        if not thumbnail_id or not region_id:
            return "unavailable"

        if not bool(thumbnail.get("enabled", True)) or not bool(region.get("enabled", True)):
            return "disabled"

        resolved_window_status = window_status or self._get_thumbnail_window_status(thumbnail)
        if resolved_window_status != "connected":
            return "unavailable"

        monitor = self.engine.monitoring_engine.get_monitor(region_id)
        if monitor and getattr(monitor, "state", None):
            return monitor.state

        return self.region_statuses.get(thumbnail_id, {}).get(region_id, "ok")

    def _window_tree_tag(self, window_state: str) -> str:
        """Map window status to tree tag."""
        if window_state == "alert":
            return "window_alert"
        if window_state == "warning":
            return "window_warning"
        if window_state == "paused":
            return "window_paused"
        if window_state == "connected":
            return "window_connected"
        if window_state == "disabled":
            return "window_disabled"
        return "window_unavailable"

    def _get_window_tree_state(self, thumbnail: Dict, window_status: str) -> str:
        """Return aggregated window state for parent tree-row coloring."""
        if window_status == "disabled":
            return "disabled"
        if window_status != "connected":
            return "unavailable"

        region_states: List[str] = []
        for region in thumbnail.get("monitored_regions", []):
            region_state = self._get_region_effective_status(thumbnail, region, window_status)
            region_states.append(region_state)

        if not region_states:
            return "connected"
        if "alert" in region_states:
            return "alert"
        if "warning" in region_states:
            return "warning"
        if "paused" in region_states:
            return "paused"
        if "ok" in region_states:
            return "connected"
        if all(state == "disabled" for state in region_states):
            return "disabled"
        return "unavailable"

    def _window_status_label(self, window_status: str) -> str:
        """Human-friendly window status suffix text."""
        if window_status == "connected":
            return "Connected"
        if window_status == "disabled":
            return "Disabled"
        return "Unavailable"

    def _window_status_icon(self, window_status: str) -> str:
        """Compact connectivity icon for window status."""
        if window_status == "connected":
            return "✅️"
        return "❌️"

    def _window_tree_suffix_icons(self, thumbnail: Dict, window_status: str) -> List[tuple[str, str]]:
        """Tooltip metadata for logical status icons rendered in window-row image."""
        icons: List[tuple[str, str]] = []
        if window_status == "connected":
            icons.append(("connected", "Window is connected"))
        else:
            icons.append(("disconnected", "Window is disconnected/disabled"))

        thumbnail_id = thumbnail.get("id")
        if self._is_overlay_visible_live(thumbnail_id, thumbnail):
            icons.append(("overlay_open", "Overlay is visible"))
        return icons

    def _format_window_tree_text(self, thumbnail: Dict, window_status: str) -> str:
        """Format window tree text with primary marker at start and other icons at end."""
        title = thumbnail.get("window_title", "Unknown")
        prefix = "• " if bool(thumbnail.get("is_primary", False)) else "  "
        return f"{prefix}{title}"

    def _window_tree_text_color(self, window_tree_state: str) -> str:
        """Resolve text color for image-rendered window rows."""
        if window_tree_state == "alert":
            return self._palette["danger"]
        if window_tree_state == "warning":
            return self._palette["warn"]
        if window_tree_state == "paused":
            return self._palette["info"]
        if window_tree_state == "disabled":
            return self._palette["disabled"]
        if window_tree_state == "unavailable":
            return self._palette["info"]
        return self._palette["ok"]

    def _resolve_tree_pil_font(self) -> ImageFont.ImageFont:
        """Return PIL font matching tree text size as closely as practical."""
        if self._tree_pil_font is not None:
            return self._tree_pil_font

        resolved_tk_font = None
        try:
            configured_font = self.style.lookup('Treeview', 'font') or ('Segoe UI', 10, 'bold')
            resolved_tk_font = tkfont.Font(font=configured_font)
            self._tree_text_font = resolved_tk_font
        except Exception:
            resolved_tk_font = tkfont.Font(family='Segoe UI', size=10, weight='bold')
            self._tree_text_font = resolved_tk_font

        family = str(resolved_tk_font.actual('family') or 'Segoe UI')
        size = abs(int(resolved_tk_font.actual('size') or 10))
        weight = str(resolved_tk_font.actual('weight') or 'normal').lower()

        candidate_paths: List[str] = []
        windir = os.environ.get('WINDIR', 'C:/Windows')
        family_lower = family.casefold()

        if 'segoe ui' in family_lower:
            candidate_paths.append(f"{windir}/Fonts/segoeuib.ttf" if weight == 'bold' else f"{windir}/Fonts/segoeui.ttf")
            candidate_paths.append(f"{windir}/Fonts/segoeui.ttf")
        candidate_paths.append(f"{windir}/Fonts/arialbd.ttf" if weight == 'bold' else f"{windir}/Fonts/arial.ttf")

        loaded = None
        for path in candidate_paths:
            try:
                loaded = ImageFont.truetype(path, size)
                break
            except Exception:
                continue

        if loaded is None:
            try:
                loaded = ImageFont.truetype("segoeui.ttf", size)
            except Exception:
                loaded = ImageFont.load_default()

        self._tree_pil_font = loaded
        return self._tree_pil_font

    def _draw_connection_icon(self, draw: ImageDraw.ImageDraw, x: int, y: int, size: int, connected: bool) -> None:
        """Draw connected/disconnected square icon."""
        x2 = x + size - 1
        y2 = y + size - 1
        pad = max(2, size // 4)
        stroke = max(1, size // 6)
        radius = max(2, size // 6)
        if connected:
            draw.rounded_rectangle((x, y, x2, y2), radius=radius, fill=(0, 170, 0, 255), outline=(0, 255, 0, 255), width=1)
            draw.line((x + pad, y + (size // 2), x + (size // 2) - 1, y + size - pad - 1), fill=(255, 255, 255, 255), width=stroke)
            draw.line((x + (size // 2) - 1, y + size - pad - 1, x + size - pad, y + pad), fill=(255, 255, 255, 255), width=stroke)
        else:
            draw.rounded_rectangle((x, y, x2, y2), radius=radius, fill=(170, 20, 20, 255), outline=(255, 80, 80, 255), width=1)
            draw.line((x + pad, y + pad, x + size - pad, y + size - pad), fill=(255, 255, 255, 255), width=stroke)
            draw.line((x + size - pad, y + pad, x + pad, y + size - pad), fill=(255, 255, 255, 255), width=stroke)

    def _draw_open_eye_icon(self, draw: ImageDraw.ImageDraw, x: int, y: int, size: int) -> None:
        """Draw open-eye icon (with lashes) for visible overlay."""
        outline = (190, 220, 255, 255)
        iris = (140, 190, 255, 255)
        pupil = (40, 70, 110, 255)

        left = x + 1
        top = y + max(1, size // 4)
        right = x + size - 1
        bottom = y + size - max(1, size // 4)
        stroke = max(1, size // 8)

        draw.ellipse((left, top, right, bottom), outline=outline, width=stroke)
        iris_r = max(2, size // 5)
        cx = x + (size // 2)
        cy = y + (size // 2)
        draw.ellipse((cx - iris_r, cy - iris_r, cx + iris_r, cy + iris_r), fill=iris, outline=iris)
        pupil_r = max(1, size // 8)
        draw.ellipse((cx - pupil_r, cy - pupil_r, cx + pupil_r, cy + pupil_r), fill=pupil, outline=pupil)
        lash_y = top - 1
        draw.line((left + 1, top, left, lash_y), fill=outline, width=1)
        draw.line((cx, top, cx, lash_y), fill=outline, width=1)
        draw.line((right - 1, top, right, lash_y), fill=outline, width=1)

    def _get_window_tree_icon_image(self, thumbnail: Dict, window_status: str, window_tree_state: str) -> Optional[ImageTk.PhotoImage]:
        """Return cached full row image in order: bullet/blank, title, connected icon, optional eye icon."""
        title = thumbnail.get("window_title", "Unknown")
        is_primary = bool(thumbnail.get("is_primary", False))
        thumbnail_id = thumbnail.get("id")
        overlay_visible = self._is_overlay_visible_live(thumbnail_id, thumbnail)
        row_text = f"{'• ' if is_primary else '  '}{title}"

        cache_key = (row_text, window_status, overlay_visible, window_tree_state, self._current_theme, self._theme_preset)

        cached = self._window_tree_icon_strip_cache.get(cache_key)
        if cached is not None:
            return cached

        font = self._resolve_tree_pil_font()
        probe = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        probe_draw = ImageDraw.Draw(probe)
        left, top, right, bottom = probe_draw.textbbox((0, 0), row_text, font=font)
        text_width = max(1, right - left)
        text_height = max(1, bottom - top)

        if self._tree_text_font is None:
            try:
                self._tree_text_font = tkfont.Font(font=self.style.lookup('Treeview', 'font') or ('Segoe UI', 10, 'bold'))
            except Exception:
                self._tree_text_font = tkfont.Font(family='Segoe UI', size=10, weight='bold')

        line_space = int(self._tree_text_font.metrics('linespace') or 14)
        icon_size = max(12, line_space - 2)
        spacing = 6
        right_pad = 2
        icon_count = 1 + (1 if overlay_visible else 0)
        icons_width = (icon_count * icon_size) + ((icon_count - 1) * spacing)

        width = 4 + text_width + 10 + icons_width + right_pad
        height = max(text_height, icon_size) + 4
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        text_y = (height - text_height) // 2 - top
        draw.text((2, text_y), row_text, font=font, fill=self._window_tree_text_color(window_tree_state))

        icon_y = (height - icon_size) // 2
        icon_x = 4 + text_width + 10
        self._draw_connection_icon(draw, icon_x, icon_y, icon_size, connected=(window_status == "connected"))
        icon_x += icon_size + spacing

        if overlay_visible:
            self._draw_open_eye_icon(draw, icon_x, icon_y, icon_size)

        tk_image = ImageTk.PhotoImage(image)
        self._window_tree_icon_strip_cache[cache_key] = tk_image
        return tk_image

    def _on_tree_motion(self, event) -> None:
        """Show quick tooltip when hovering a trailing window icon."""
        item_id = self.window_tree.identify_row(event.y)
        if not item_id or self._tree_item_kind(item_id) != "window":
            self._hide_tree_icon_tooltip()
            return

        thumbnail = self.config.get_thumbnail(item_id)
        if not thumbnail:
            self._hide_tree_icon_tooltip()
            return

        suffix_icons = self._tree_window_icon_meta.get(item_id)
        if suffix_icons is None:
            window_status = self._get_thumbnail_window_status(thumbnail)
            suffix_icons = self._window_tree_suffix_icons(thumbnail, window_status)
            self._tree_window_icon_meta[item_id] = suffix_icons
        if not suffix_icons:
            self._hide_tree_icon_tooltip()
            return

        bbox = self.window_tree.bbox(item_id)
        if not bbox:
            self._hide_tree_icon_tooltip()
            return

        if self._tree_text_font is None:
            self._tree_text_font = tkfont.Font(font=self.style.lookup('Treeview', 'font') or ('Segoe UI', 10))
        text_font = self._tree_text_font
        row_x, _row_y, _row_w, _row_h = bbox
        title_prefix = "• " if bool(thumbnail.get("is_primary", False)) else "  "
        title_text = thumbnail.get("window_title", "Unknown")
        suffix_text = " ".join(icon for icon, _tip in suffix_icons)
        start_text = f"{title_prefix}{title_text} "
        start_x = row_x + text_font.measure(start_text)
        end_x = start_x + text_font.measure(suffix_text)

        if event.x < start_x or event.x > end_x:
            self._hide_tree_icon_tooltip()
            return

        current_x = start_x
        hovered_tip: Optional[str] = None
        for index, (icon, tip_text) in enumerate(suffix_icons):
            icon_width = text_font.measure(icon)
            if current_x <= event.x <= (current_x + icon_width):
                hovered_tip = tip_text
                break
            current_x += icon_width
            if index < (len(suffix_icons) - 1):
                current_x += text_font.measure(" ")

        if not hovered_tip:
            self._hide_tree_icon_tooltip()
            return

        target = (item_id, hovered_tip)
        if self._tree_icon_tooltip_target == target and self._tree_icon_tooltip_window:
            self._tree_icon_tooltip_window.wm_geometry(f"+{event.x_root + 16}+{event.y_root + 12}")
            return

        self._schedule_tree_icon_tooltip(hovered_tip, event.x_root + 16, event.y_root + 12, target)

    def _on_tree_leave(self, _event) -> None:
        """Hide icon tooltip when cursor leaves tree."""
        self._hide_tree_icon_tooltip()

    def _schedule_tree_icon_tooltip(self, text: str, x_root: int, y_root: int, target: tuple) -> None:
        """Schedule icon tooltip with short delay for quick hover feedback."""
        self._hide_tree_icon_tooltip()

        def _show() -> None:
            tooltip_window = tk.Toplevel(self.window_tree)
            tooltip_window.wm_overrideredirect(True)
            tooltip_window.wm_geometry(f"+{x_root}+{y_root}")
            label = tk.Label(
                tooltip_window,
                text=text,
                justify=tk.LEFT,
                background=self._palette.get("surface", "#222"),
                foreground=self._palette.get("text", "#fff"),
                relief=tk.SOLID,
                borderwidth=1,
                font=("Segoe UI", 9),
                padx=6,
                pady=3,
            )
            label.pack()
            self._tree_icon_tooltip_window = tooltip_window
            self._tree_icon_tooltip_target = target
            self._tree_icon_tooltip_after_id = None

        self._tree_icon_tooltip_after_id = self.window_tree.after(150, _show)

    def _hide_tree_icon_tooltip(self) -> None:
        """Cancel/hide icon tooltip for tree rows."""
        if self._tree_icon_tooltip_after_id:
            try:
                self.window_tree.after_cancel(self._tree_icon_tooltip_after_id)
            except Exception:
                pass
            self._tree_icon_tooltip_after_id = None

        if self._tree_icon_tooltip_window:
            try:
                self._tree_icon_tooltip_window.destroy()
            except Exception:
                pass
            self._tree_icon_tooltip_window = None

        self._tree_icon_tooltip_target = None

    def _region_tree_tag(self, region_status: str) -> str:
        """Map region status to tree tag."""
        if region_status == "alert":
            return "region_alert"
        if region_status == "warning":
            return "region_warning"
        if region_status == "paused":
            return "region_paused"
        if region_status == "disabled":
            return "region_disabled"
        if region_status == "unavailable":
            return "region_unavailable"
        return "region_ok"

    def _region_status_label(self, region_status: str) -> str:
        """Human-friendly region status suffix text."""
        if region_status == "alert":
            return "ALERT"
        if region_status == "warning":
            return "WARNING"
        if region_status == "paused":
            return "PAUSED"
        if region_status == "disabled":
            return "Disabled"
        if region_status == "unavailable":
            return "Unavailable"
        return "OK"

    def _region_status_icon(self, region_status: str) -> str:
        """Compact icon for region status."""
        if region_status == "alert":
            return "🔴"
        if region_status == "warning":
            return "🟠"
        if region_status == "ok":
            return "🟢"
        if region_status == "paused":
            return "🔵"
        if region_status == "disabled":
            return "⚪"
        return "🔵"

    def _format_region_tree_text(self, region_name: str, region_status: str) -> str:
        """Format region tree text with icon and status suffix."""
        icon = self._region_status_icon(region_status)
        suffix = self._region_status_label(region_status)
        return f"{icon} {region_name} [{suffix}]"

    def _refresh_tree_node_statuses(self) -> None:
        """Refresh tree node tags to reflect live window/region statuses.

        Only updates tree items whose state actually changed to avoid
        unnecessary repaints/flicker.
        """
        if not hasattr(self, '_tree_last_state'):
            self._tree_last_state: Dict[str, str] = {}

        primary_cleared = False
        for thumbnail in self.config.get_all_thumbnails():
            thumbnail_id = thumbnail.get("id")
            if not thumbnail_id or not self.window_tree.exists(thumbnail_id):
                continue

            window_status = self._get_thumbnail_window_status(thumbnail)
            if window_status != "connected" and bool(thumbnail.get("is_primary", False)):
                self.config.update_thumbnail(thumbnail_id, {"is_primary": False})
                thumbnail["is_primary"] = False
                primary_cleared = True
            self._tree_window_icon_meta[thumbnail_id] = self._window_tree_suffix_icons(thumbnail, window_status)
            window_tree_state = self._get_window_tree_state(thumbnail, window_status)

            # Only update tree item if state changed
            state_key = f"win:{thumbnail_id}"
            if self._tree_last_state.get(state_key) != window_tree_state:
                self._tree_last_state[state_key] = window_tree_state
                self.window_tree.item(
                    thumbnail_id,
                    text="",
                    image=self._get_window_tree_icon_image(thumbnail, window_status, window_tree_state),
                    tags=(self._window_tree_tag(window_tree_state),),
                )

            for region in thumbnail.get("monitored_regions", []):
                region_id = region.get("id")
                if not region_id or not self.window_tree.exists(region_id):
                    continue
                region_status = self._get_region_effective_status(thumbnail, region, window_status)
                region_name = region.get("name", "Region")

                state_key = f"reg:{region_id}"
                new_state = f"{region_status}:{region_name}"
                if self._tree_last_state.get(state_key) != new_state:
                    self._tree_last_state[state_key] = new_state
                    self.window_tree.item(
                        region_id,
                        text=self._format_region_tree_text(region_name, region_status),
                        tags=(self._region_tree_tag(region_status),),
                    )

        # Re-sort tree: connected windows first, then alphabetical by title
        # Only move children if the order actually changed
        if self.window_tree.exists("__all__"):
            children = list(self.window_tree.get_children("__all__"))
            thumb_map = {t.get("id"): t for t in self.config.get_all_thumbnails()}
            sorted_children = sorted(children, key=lambda tid: (
                0 if tid in thumb_map and self._is_thumbnail_connected(thumb_map[tid]) else 1,
                (thumb_map.get(tid, {}).get("window_title") or "").casefold(),
            ))
            if sorted_children != children:
                for idx, child_id in enumerate(sorted_children):
                    self.window_tree.move(child_id, "__all__", idx)

        if primary_cleared:
            self.config.save()
            if self.selected_thumbnail_id:
                selected = self.config.get_thumbnail(self.selected_thumbnail_id)
                if selected and not self._is_thumbnail_connected(selected):
                    self.window_primary_var.set(False)

    def _refresh_dynamic_status_texts(self) -> None:
        """Refresh dynamic text portions (countdown) without changing colors.

        Only reconfigures pills whose text actually changed to avoid flicker.
        """
        for region_id, widgets in self.region_widgets.items():
            pill = widgets.get("status_pill")
            if not pill:
                continue
            thumbnail_id = self.region_to_thumbnail.get(region_id)
            status = self.region_statuses.get(thumbnail_id, {}).get(region_id, "ok")
            new_text = self._format_region_status_text(region_id, status)
            try:
                if str(pill.cget("text")) != new_text:
                    pill.config(text=new_text)
            except tk.TclError:
                pass

    def _collect_all_region_states(self) -> List[str]:
        """Collect current states across all configured regions."""
        states: List[str] = []
        for thumbnail in self.config.get_all_thumbnails():
            thumb_enabled = bool(thumbnail.get("enabled", True))
            thumbnail_id = thumbnail.get("id")
            window_available = bool(thumbnail_id) and self._is_thumbnail_connected(thumbnail)
            for region in thumbnail.get("monitored_regions", []):
                region_id = region.get("id")
                if not region_id:
                    continue
                if not thumb_enabled or not bool(region.get("enabled", True)):
                    states.append("disabled")
                    continue
                if not window_available:
                    states.append("unavailable")
                    continue
                monitor = self.engine.monitoring_engine.get_monitor(region_id)
                if monitor:
                    states.append(monitor.state)
                else:
                    states.append("unavailable")
        return states

    def _refresh_aggregate_status(self) -> None:
        """Refresh aggregate status text with priority ordering."""
        states = self._collect_all_region_states()
        if not states:
            aggregate = "unavailable"
        elif any(state == "alert" for state in states):
            aggregate = "alert"
        elif any(state == "warning" for state in states):
            aggregate = "warning"
        elif any(state == "ok" for state in states):
            aggregate = "ok"
        elif any(state == "paused" for state in states):
            aggregate = "paused"
        else:
            aggregate = "unavailable"

        # Only update badge when aggregate state actually changes
        if not hasattr(self, '_last_aggregate'):
            self._last_aggregate = None
        if aggregate == self._last_aggregate:
            return
        self._last_aggregate = aggregate

        if aggregate == "alert":
            self.aggregate_status_var.set("Overall: ALERT")
            self.aggregate_status_badge.config(bg=self._palette["danger"], fg="white")
        elif aggregate == "warning":
            self.aggregate_status_var.set("Overall: WARNING")
            self.aggregate_status_badge.config(bg=self._palette["warn"], fg="black")
        elif aggregate == "ok":
            self.aggregate_status_var.set("Overall: OK")
            self.aggregate_status_badge.config(bg=self._palette["ok"], fg="black")
        elif aggregate == "paused":
            self.aggregate_status_var.set("Overall: PAUSED")
            self.aggregate_status_badge.config(bg=self._palette["info"], fg="white")
        else:
            self.aggregate_status_var.set("Overall: N/A")
            self.aggregate_status_badge.config(bg=self._palette["info"], fg="white")

    def _update_region_thumbnail(self, thumbnail_id: str, region_id: str) -> None:
        """Update a single region thumbnail image"""
        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if not thumbnail:
            logger.warning(f"[THUMBNAIL UPDATE] Thumbnail {thumbnail_id} not found")
            return
        region = self.config.get_region(thumbnail_id, region_id)
        if not region:
            logger.warning(f"[THUMBNAIL UPDATE] Region {region_id} not found")
            return
        widgets = self.region_widgets.get(region_id, {})
        image_label = widgets.get("image_label")
        if not image_label:
            logger.warning(f"[THUMBNAIL UPDATE] Image label for region {region_id} not found")
            return
        hwnd = thumbnail.get("window_hwnd")
        if not hwnd:
            logger.warning(f"[THUMBNAIL UPDATE] HWND not found for thumbnail {thumbnail_id}")
            return
        window_image = self._get_window_image_for_ui(hwnd, thumbnail)
        if not window_image:
            logger.warning(f"[THUMBNAIL UPDATE] No image available for hwnd {hwnd}")
            image_label.config(image="", text="Not Available", style="App.ImageUnavailable.TLabel")
            self.region_photos.pop(region_id, None)
            self._set_region_status(thumbnail_id, region_id, "unavailable")
            self._apply_region_status(thumbnail_id, region_id)
            return
        try:
            region_image = ImageProcessor.crop_region(window_image, region.get("rect", (0, 0, 0, 0)))
            region_image.thumbnail((220, 96), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(region_image)
            self.region_photos[region_id] = photo
            image_label.config(image=photo, text="", style="App.Image.TLabel")
            current_status = self.region_statuses.get(thumbnail_id, {}).get(region_id)
            if current_status == "unavailable":
                monitor = self.engine.monitoring_engine.get_monitor(region_id)
                region_cfg = self.config.get_region(thumbnail_id, region_id) or {}
                if not bool(region_cfg.get("enabled", True)):
                    self._set_region_status(thumbnail_id, region_id, "disabled")
                elif monitor:
                    self._set_region_status(thumbnail_id, region_id, monitor.state)
                else:
                    self._set_region_status(thumbnail_id, region_id, "ok")
                self._apply_region_status(thumbnail_id, region_id)
            logger.debug(f"[THUMBNAIL UPDATE] Successfully updated image for region {region_id}")
        except Exception as e:
            logger.error(f"Error updating region image {region_id}: {e}", exc_info=True)

    def _update_region_thumbnail_soft(self, thumbnail_id: str, region_id: str) -> None:
        """Like _update_region_thumbnail but never flips status to N/A.

        Used by the periodic force-refresh.  If the capture temporarily fails
        (cache just invalidated, PrintWindow blocked, etc.) the previous image
        and status are kept instead of showing a brief N/A flash.
        """
        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if not thumbnail:
            return
        region = self.config.get_region(thumbnail_id, region_id)
        if not region:
            return
        widgets = self.region_widgets.get(region_id, {})
        image_label = widgets.get("image_label")
        if not image_label:
            return
        hwnd = thumbnail.get("window_hwnd")
        if not hwnd:
            return
        window_image = self._get_window_image_for_ui(hwnd, thumbnail)
        if not window_image:
            # Key difference: keep previous image & status instead of N/A
            return
        try:
            region_image = ImageProcessor.crop_region(window_image, region.get("rect", (0, 0, 0, 0)))
            region_image.thumbnail((220, 96), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(region_image)
            self.region_photos[region_id] = photo
            image_label.config(image=photo, text="", style="App.Image.TLabel")
            # If was previously unavailable, recover
            current_status = self.region_statuses.get(thumbnail_id, {}).get(region_id)
            if current_status == "unavailable":
                monitor = self.engine.monitoring_engine.get_monitor(region_id)
                region_cfg = self.config.get_region(thumbnail_id, region_id) or {}
                if not bool(region_cfg.get("enabled", True)):
                    self._set_region_status(thumbnail_id, region_id, "disabled")
                elif monitor:
                    self._set_region_status(thumbnail_id, region_id, monitor.state)
                else:
                    self._set_region_status(thumbnail_id, region_id, "ok")
                self._apply_region_status(thumbnail_id, region_id)
        except Exception as e:
            logger.debug(f"Soft refresh failed for region {region_id}: {e}")

    def _force_refresh_all_thumbnails(self) -> None:
        """Force refresh all visible region cards and window preview (every ~5s).

        Invalidates the image cache so the next capture is fresh, then updates
        every region card that currently has widgets on screen plus the window
        preview image.  If a fresh capture fails, the old image is kept to
        avoid N/A flicker.
        """
        try:
            # Invalidate cache so we get a fresh capture
            self.engine.cache_manager.invalidate_all()

            # Refresh each region card that is currently displayed.
            # Use _update_region_thumbnail_soft which won't set N/A on
            # transient capture failures.
            for region_id, widgets in list(self.region_widgets.items()):
                thumbnail_id = self.region_to_thumbnail.get(region_id)
                if thumbnail_id:
                    self._update_region_thumbnail_soft(thumbnail_id, region_id)

            # Refresh window preview image
            self._refresh_window_preview()

            logger.debug("[FORCE REFRESH] All thumbnails and preview refreshed")
        except Exception as e:
            logger.error(f"Error in force refresh: {e}", exc_info=True)

    def _refresh_window_preview(self) -> None:
        """Refresh the window info preview image with a fresh capture."""
        try:
            if self.show_all_regions:
                thumbnails = self.config.get_all_thumbnails()
                if len(thumbnails) == 1:
                    thumbnail = thumbnails[0]
                    hwnd = thumbnail.get("window_hwnd")
                    window_image = self._get_window_image_for_ui(hwnd, thumbnail)
                else:
                    window_image = None
            elif self.selected_thumbnail_id:
                thumbnail = self.config.get_thumbnail(self.selected_thumbnail_id)
                hwnd = thumbnail.get("window_hwnd") if thumbnail else None
                window_image = self._get_window_image_for_ui(hwnd, thumbnail)
            else:
                window_image = None

            if window_image:
                preview = window_image.copy()
                preview.thumbnail((180, 100), Image.Resampling.LANCZOS)
                self.window_preview_photo = ImageTk.PhotoImage(preview)
                self.window_preview_label.config(image=self.window_preview_photo, text="", style='App.Preview.TLabel')
            else:
                self._set_preview_placeholder("Not Available")
        except Exception as e:
            logger.debug(f"Error refreshing window preview: {e}")

    def _show_all_regions(self) -> None:
        """Clear selection filter and show all regions"""
        self.show_all_regions = True
        self.selected_region_id = None
        if self.window_tree.exists("__all__"):
            self._set_tree_selection("__all__")
        self.selected_thumbnail_id = None
        self._render_window_detail(None)

    def _mark_dirty(self, thumbnail_id: str, region_id: str, status: str = None, thumbnail: bool = False) -> None:
        """Mark a region as needing updates - ONLY way to trigger UI changes"""
        if region_id not in self.dirty_regions:
            self.dirty_regions[region_id] = {'status': False, 'thumbnail': False}
        
        if status:
            # Only mark dirty if status actually changed
            current_status = self.region_statuses.get(thumbnail_id, {}).get(region_id)
            if current_status != status:
                self.dirty_regions[region_id]['status'] = True
                self.pending_status_changes[region_id] = status
                # Update stored status for change detection
                if thumbnail_id not in self.region_statuses:
                    self.region_statuses[thumbnail_id] = {}
                self.region_statuses[thumbnail_id][region_id] = status
                logger.debug(f"[MARK DIRTY] Region {region_id}: status {current_status} -> {status}")
                # Schedule a throttled filter/UI refresh so filters update promptly
                try:
                    self._schedule_filter_refresh()
                except Exception:
                    pass
        
        if thumbnail:
            self.dirty_regions[region_id]['thumbnail'] = True
            logger.debug(f"[MARK DIRTY] Region {region_id}: thumbnail needs update")
            # Thumbnail changes can also affect whether a region is visible
            try:
                self._schedule_filter_refresh()
            except Exception:
                pass

    def _periodic_ui_update(self) -> None:
        """Periodic update loop - SINGLE point where UI updates happen every 1000ms"""
        try:
            cycle_start = time.perf_counter()
            # Collect all dirty regions
            dirty_count = sum(1 for flags in self.dirty_regions.values() if flags['status'] or flags['thumbnail'])
            
            if dirty_count > 0:
                logger.debug(f"[PERIODIC UPDATE] Processing {dirty_count} dirty regions")
                
                # Process all dirty regions in ONE batch
                for region_id, flags in list(self.dirty_regions.items()):
                    if flags['status'] or flags['thumbnail']:
                        # Find thumbnail_id for this region
                        thumbnail_id = self.region_to_thumbnail.get(region_id)
                        if not thumbnail_id:
                            continue
                        
                        # Update status if dirty
                        if flags['status']:
                            new_status = self.pending_status_changes.get(region_id)
                            if new_status:
                                self._apply_region_status(thumbnail_id, region_id)
                                logger.debug(f"[UPDATE] Applied status for region {region_id}: {new_status}")
                        
                        # Update thumbnail if dirty
                        if flags['thumbnail']:
                            self._update_region_thumbnail(thumbnail_id, region_id)
                            logger.debug(f"[UPDATE] Refreshed thumbnail for region {region_id}")
                        
                        # Clear dirty flags for this region
                        self.dirty_regions[region_id] = {'status': False, 'thumbnail': False}
                
                # Clear pending changes
                self.pending_status_changes.clear()
                logger.debug(f"[PERIODIC UPDATE] Batch complete")
            else:
                logger.debug(f"[PERIODIC UPDATE] No dirty regions")

            # Keep thumbnail_map in sync with config (engine may update
            # HWNDs via automatic reconnect on the background thread).
            self._rebuild_thumbnail_map()

            self._refresh_dynamic_status_texts()
            self._refresh_aggregate_status()
            self._refresh_tree_node_statuses()

            # Force full thumbnail + preview refresh every 5 seconds (5 ticks)
            self._force_refresh_counter += 1
            if self._force_refresh_counter >= 5:
                self._force_refresh_counter = 0
                self._force_refresh_all_thumbnails()

            cycle_ms = (time.perf_counter() - cycle_start) * 1000.0
            self._ui_cycle_count += 1
            self._ui_cycle_total_ms += cycle_ms

            if self.config.get_diagnostics_enabled():
                now = time.time()
                if (now - self._ui_last_diag_ts) >= 10.0:
                    avg_ms = self._ui_cycle_total_ms / max(1, self._ui_cycle_count)
                    with self._event_lock:
                        pending_alerts = len(self._pending_alert_events)
                        pending_changes = len(self._pending_region_change_events)
                        pending_lost = len(self._pending_window_lost_events)
                    logger.info(
                        "[UI DIAG] cycles=%s avg_ms=%.2f last_ms=%.2f dirty_regions=%s pending_events(alert=%s,change=%s,lost=%s)",
                        self._ui_cycle_count,
                        avg_ms,
                        cycle_ms,
                        dirty_count,
                        pending_alerts,
                        pending_changes,
                        pending_lost,
                    )
                    self._ui_cycle_count = 0
                    self._ui_cycle_total_ms = 0.0
                    self._ui_last_diag_ts = now
                
        except Exception as e:
            logger.error(f"Error in periodic UI update: {e}", exc_info=True)
        finally:
            # Reschedule for next update cycle
            if self.root:
                self.update_timer_id = self.root.after(1000, self._periodic_ui_update)
    
    def _on_exit(self) -> None:
        """Handle window close"""
        self._watchdog_stop_event.set()

        if self._ui_heartbeat_after_id:
            try:
                self.root.after_cancel(self._ui_heartbeat_after_id)
                self._ui_heartbeat_after_id = None
            except Exception:
                pass

        if self.update_timer_id:
            try:
                self.root.after_cancel(self.update_timer_id)
                self.update_timer_id = None
            except Exception:
                pass

        try:
            self.engine.stop()
        except Exception as e:
            logger.error(f"Error stopping engine: {str(e)}")

        try:
            self.config.save()
        except Exception as e:
            logger.error(f"Error saving config: {str(e)}")

        self.root.quit()

    def _schedule_filter_refresh(self, delay_ms: int = 200) -> None:
        """Schedule a throttled refresh of the tree and regions panel.

        Ensures updates do not occur more frequently than `delay_ms`.
        Subsequent requests while a refresh is pending are coalesced.
        """
        try:
            if getattr(self, '_filter_refresh_after_id', None):
                return
            self._filter_refresh_after_id = self.root.after(delay_ms, self._do_filter_refresh)
        except Exception as e:
            logger.debug(f"Failed scheduling filter refresh: {e}")

    def _do_filter_refresh(self) -> None:
        """Perform the actual refresh of the tree and current region detail view."""
        try:
            self._filter_refresh_after_id = None
            # Update tree first so selection iteration uses up-to-date nodes
            try:
                self._update_thumbnail_list()
            except Exception as e:
                logger.debug(f"Filter refresh: _update_thumbnail_list failed: {e}")

            # Re-render detail panel for currently selected thumbnail (or all)
            try:
                if self.selected_thumbnail_id:
                    thumb = self.config.get_thumbnail(self.selected_thumbnail_id)
                    self._render_window_detail(thumb)
                else:
                    # render all regions view
                    self._render_window_detail(None)
            except Exception as e:
                logger.debug(f"Filter refresh: _render_window_detail failed: {e}")
        except Exception as e:
            logger.debug(f"Error during filter refresh: {e}")
    
    # ── MCP integration ───────────────────────────────────────────────────────

    def set_mcp_server(self, mcp_server) -> None:
        """Wire in the MCPServer instance and show the MCP toggle button."""
        self._mcp_server = mcp_server
        self._mcp_btn.pack(side=tk.RIGHT, padx=(4, 0), pady=2)
        self._update_mcp_button()

    def _toggle_mcp(self) -> None:
        """Toggle the MCP server on/off."""
        if not self._mcp_server:
            return
        if self._mcp_server.is_running():
            self._mcp_server.stop()
            self.config.set_mcp_enabled(False)
            self.config.save()
        else:
            self.config.set_mcp_enabled(True)
            self.config.save()
            self._mcp_server.start()
        self._update_mcp_button()

    def _update_mcp_button(self) -> None:
        """Refresh MCP button text to reflect current server state."""
        if not self._mcp_server:
            return
        if self._mcp_server.is_running():
            self._mcp_btn.config(text="MCP: On")
        else:
            self._mcp_btn.config(text="MCP: Off")

    # ── Tk mainloop ───────────────────────────────────────────────────────────

    def run(self) -> None:
        """Run main window"""
        logger.info("Entering Tk mainloop")
        self.root.after(1000, lambda: logger.debug("Tk mainloop heartbeat: still running..."))
        self.root.mainloop()
        logger.info("Exited Tk mainloop")
