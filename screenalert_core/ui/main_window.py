"""Main window UI for ScreenAlert v2"""

import logging
import threading
import time
import os
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox as msgbox, filedialog
from typing import Optional, List, Dict
import win32gui
from PIL import Image, ImageTk

from screenalert_core.screening_engine import ScreenAlertEngine
from screenalert_core.ui.window_selector_dialog import WindowSelectorDialog
from screenalert_core.ui.region_selection_overlay import RegionSelectionOverlay
from screenalert_core.ui.settings_dialog import SettingsDialog
from screenalert_core.ui.tooltip import ToolTip
from screenalert_core.ui.auto_hide_scrollbar import AutoHideScrollbar
from screenalert_core.core.image_processor import ImageProcessor
from screenalert_core.utils.update_checker import check_for_updates
from screenalert_core.utils.constants import LOGS_DIR

logger = logging.getLogger(__name__)


class ScreenAlertMainWindow:
    """Main control window for ScreenAlert"""
    
    def __init__(self, engine: ScreenAlertEngine):
        logger.debug("ScreenAlertMainWindow __init__ starting")
        self.engine = engine
        self.config = engine.config
        self.window_manager = engine.window_manager
        self.thumbnail_map = {}  # hwnd -> thumbnail_id mapping
        self.selected_thumbnail_id: Optional[str] = None  # Currently selected window
        self.selected_region_id: Optional[str] = None
        self.region_statuses: Dict[str, Dict[str, str]] = {}  # thumbnail_id -> region_id -> status
        self.region_widgets: Dict[str, Dict[str, tk.Widget]] = {}  # region_id -> widgets
        self.region_photos: Dict[str, ImageTk.PhotoImage] = {}  # region_id -> image
        self.window_preview_photo: Optional[ImageTk.PhotoImage] = None
        self.region_to_thumbnail: Dict[str, str] = {}
        self.show_all_regions = True
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
        logger.debug("Creating Tk root window")
        self.root = tk.Tk()
        self.root.title("ScreenAlert v2.0 - Multibox Monitor")
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
        self._current_theme = 'dark'
        self._apply_theme(self._current_theme)

        # Build UI
        logger.debug("Building UI")
        self._build_ui()
        logger.debug("UI built")

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

        # Auto-start monitoring after a short delay (matches main branch behaviour)
        self.root.after(3000, self._auto_start_monitoring)

    def _add_tooltips(self) -> None:
        # Add tooltips to main window controls
        try:
            # Add tooltips to treeview
            if hasattr(self, 'window_tree'):
                ToolTip(self.window_tree, 'List of monitored windows and regions')
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
        if theme == 'high-contrast':
            self.style.theme_use('clam')
            # High-contrast colors
            self.style.configure('.', background='#000000', foreground='#FFFFFF', font=('Segoe UI', 10, 'bold'))
            self.style.configure('TLabel', background='#000000', foreground='#FFFFFF', font=('Segoe UI', 10, 'bold'))
            self.style.configure('TFrame', background='#000000')
            self.style.configure('TButton', background='#000000', foreground='#FFFF00', font=('Segoe UI', 10, 'bold'))
            self.style.configure('Treeview', background='#000000', foreground='#FFFFFF', fieldbackground='#000000', font=('Segoe UI', 10, 'bold'))
            self.style.configure('TEntry', fieldbackground='#000000', foreground='#FFFFFF', font=('Segoe UI', 10, 'bold'))
        else:
            self.style.theme_use('clam')
            # Modern dark theme colors (gaming style)
            accent = '#00bfff'
            bg = '#181a20'
            fg = '#e0e0e0'
            panel = '#23272e'
            highlight = '#222b3a'
            self.style.configure('.', background=bg, foreground=fg, font=('Segoe UI', 10))
            self.style.configure('TLabel', background=bg, foreground=fg, font=('Segoe UI', 10, 'bold'))
            self.style.configure('TFrame', background=panel)
            self.style.configure('TButton', background=highlight, foreground=accent, font=('Segoe UI', 10, 'bold'))
            self.style.map('TButton', background=[('active', accent)], foreground=[('active', '#181a20')])
            self.style.configure('Treeview', background=panel, foreground=fg, fieldbackground=panel, font=('Segoe UI', 10))
            self.style.configure('TEntry', fieldbackground=highlight, foreground=fg, font=('Segoe UI', 10))

    def set_high_contrast(self, enabled: bool) -> None:
        """Public method to toggle high-contrast mode at runtime"""
        self._current_theme = 'high-contrast' if enabled else 'dark'
        self._apply_theme(self._current_theme)
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
        self.edit_menu.add_command(label="Add Window", command=self._add_window)
        self.edit_menu.add_command(label="Pause All", command=self._toggle_pause)
        self.edit_menu.add_command(label="Reconnect All Windows", command=self._reconnect_all_windows)
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Settings...", command=self._show_settings)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Logs", command=self._open_logs_folder)
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
        content_frame.columnconfigure(1, weight=1)
        content_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # Left: tree of windows/regions
        tree_frame = ttk.LabelFrame(content_frame, text="Windows", padding=8)
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        content_frame.columnconfigure(0, weight=0)
        
        self.window_tree = ttk.Treeview(tree_frame, show="tree")
        self.window_tree.grid(row=0, column=0, sticky="nsew")
        self.tree_scroll = AutoHideScrollbar(tree_frame, orient=tk.VERTICAL, command=self.window_tree.yview)
        self.tree_scroll.grid(row=0, column=1, sticky="ns")
        self.window_tree.configure(yscrollcommand=self.tree_scroll.set)
        self.window_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.window_tree.bind("<Button-3>", self._on_tree_right_click)
        
        # Right: window info + region cards
        self.detail_frame = ttk.Frame(content_frame)
        self.detail_frame.grid(row=0, column=1, sticky="nsew")
        self.detail_frame.rowconfigure(1, weight=1)
        self.detail_frame.columnconfigure(0, weight=1)
        
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
        
        self._preview_placeholder = ImageTk.PhotoImage(Image.new("RGB", (180, 100), "#1a1a1a"))
        self.window_preview_label = tk.Label(self.info_frame, bg="#1a1a1a",
                                             image=self._preview_placeholder)
        self.window_preview_label.grid(row=0, column=2, rowspan=4, sticky="e", padx=(10, 0))
        
        self.regions_frame = ttk.LabelFrame(self.detail_frame, text="Regions", padding=8)
        self.regions_frame.grid(row=1, column=0, sticky="nsew")
        self.regions_frame.rowconfigure(0, weight=1)
        self.regions_frame.columnconfigure(0, weight=1)
        
        self.region_canvas = tk.Canvas(self.regions_frame, bg="#202020", highlightthickness=0)
        self.region_canvas.grid(row=0, column=0, sticky="nsew")
        self.region_scroll = AutoHideScrollbar(self.regions_frame, orient=tk.VERTICAL, command=self.region_canvas.yview)
        self.region_scroll.grid(row=0, column=1, sticky="ns")
        self.region_canvas.configure(yscrollcommand=self.region_scroll.set)
        
        self.regions_inner_frame = tk.Frame(self.region_canvas, bg="#202020")
        self.region_canvas_window = self.region_canvas.create_window(0, 0, window=self.regions_inner_frame, anchor="nw")
        self.region_canvas.bind("<Configure>", self._on_region_canvas_configure)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        self.aggregate_status_var = tk.StringVar(value="Overall: N/A")
        self._update_pause_menu_labels()

        status_bar_frame = tk.Frame(self.root, bd=1, relief=tk.SUNKEN)
        status_bar_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)

        self.status_text_label = ttk.Label(status_bar_frame, textvariable=self.status_var, anchor="w")
        self.status_text_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4), pady=2)

        self.aggregate_status_badge = tk.Label(
            status_bar_frame,
            textvariable=self.aggregate_status_var,
            bg="#2c3e50",
            fg="white",
            padx=10,
            pady=2,
            relief=tk.RIDGE,
            bd=1,
        )
        self.aggregate_status_badge.pack(side=tk.RIGHT, padx=(4, 4), pady=2)

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

    
    def _add_window(self) -> None:
        """Add a new window to monitor"""
        dialog = WindowSelectorDialog(self.root, self.window_manager, self.config)
        window_info = dialog.show()
        
        if window_info:
            hwnd = window_info['hwnd']
            title = window_info['title']
            
            # Check if window already exists
            if hwnd in self.thumbnail_map:
                msgbox.showwarning("Duplicate", f"Window '{title}' is already being monitored")
                return
            
            try:
                # engine.add_thumbnail() handles everything: config + renderer
                thumbnail_id = self.engine.add_thumbnail(
                    window_title=title,
                    window_hwnd=hwnd,
                    window_class=window_info.get('class', ''),
                    window_size=window_info.get('size'),
                    monitor_id=window_info.get('monitor_id')
                )
                if thumbnail_id:
                    self.thumbnail_map[hwnd] = thumbnail_id
                    self._update_thumbnail_list()
                    self.status_var.set(f"Added: {title}")
                    # Auto-start engine if not already running
                    self._ensure_engine_running()
                else:
                    msgbox.showerror("Error", f"Failed to add window {title}")
            except Exception as e:
                logger.error(f"Error adding window '{title}': {str(e)}", exc_info=True)
                msgbox.showerror("Error", f"Failed to add window: {str(e)}")
    
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
        else:
            logger.info("Auto-start skipped: no thumbnails configured")

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
            dialog = SettingsDialog(self.root, self.config)
            result = dialog.show()
            if result:
                self.set_high_contrast(bool(result.get("high_contrast", False)))
                self.status_var.set("Settings updated")
        except Exception as e:
            logger.error(f"Error opening settings dialog: {str(e)}", exc_info=True)
            msgbox.showerror("Error", f"Failed to open settings: {str(e)}")

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
            # Get the window's position on screen to convert coordinates
            rect = win32gui.GetWindowRect(hwnd)
            window_x = rect[0]
            window_y = rect[1]
            window_width = rect[2] - rect[0]
            window_height = rect[3] - rect[1]
            
            logger.info(f"Window position: ({window_x}, {window_y}), size: {window_width}x{window_height}")
            
            # Activate the window (bring to front)
            self.window_manager.activate_window(hwnd)

            # Minimize ScreenAlert window so target app remains visible for selection
            self.root.iconify()
            self.root.update_idletasks()
            time.sleep(0.15)
            
            # Show region selection overlay
            overlay = RegionSelectionOverlay(hwnd, self.root)
            regions_screen = overlay.show()  # Screen coordinates
            
            # Show the ScreenAlert window again
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            
            if regions_screen:
                # Convert screen coordinates to window-relative coordinates
                for i, (x, y, w, h) in enumerate(regions_screen):
                    # Convert screen coords to window-relative
                    region_x = x - window_x
                    region_y = y - window_y
                    
                    # Clamp to window bounds
                    region_x = max(0, min(region_x, window_width - w))
                    region_y = max(0, min(region_y, window_height - h))
                    
                    # Note: engine.add_region() internally calls config.add_region_to_thumbnail()
                    # so we only need to call the engine method
                    self.engine.add_region(thumbnail_id, f"Region_{i+1}", (region_x, region_y, w, h))
                    logger.info(f"Added region {i+1}: window-relative ({region_x}, {region_y}, {w}, {h})")
                
                self.status_var.set(f"Added {len(regions_screen)} region(s) to {title}")
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
                           "ScreenAlert v2.0\n\n"
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

    def _reconnect_all_windows(self) -> None:
        """Manually trigger strict reconnect attempts for all windows."""
        try:
            result = self.engine.reconnect_all_windows()
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
            self.engine.cache_manager.invalidate_all()
            self._update_thumbnail_list()

            if state == "reconnected":
                self.status_var.set(f"Reconnected: {title}")
            elif state == "already_valid":
                self.status_var.set(f"Already connected: {title}")
            elif state == "failed":
                self.status_var.set(f"Reconnect failed: {title}")
            else:
                self.status_var.set(f"Window not found: {title}")
        except Exception as error:
            logger.error(f"Error reconnecting window '{title}': {error}", exc_info=True)
            msgbox.showerror("Reconnect", f"Reconnect failed: {error}")
    
    def _update_thumbnail_list(self) -> None:
        """Update window tree display"""
        for item in self.window_tree.get_children():
            self.window_tree.delete(item)
        self.region_to_thumbnail.clear()
        
        thumbnails = self.config.get_all_thumbnails()
        logger.info(f"Updating window tree: {len(thumbnails)} thumbnails from config")
        
        all_root = self.window_tree.insert("", "end", iid="__all__", text="All")
        for thumbnail in thumbnails:
            thumbnail_id = thumbnail.get("id")
            title = thumbnail.get("window_title", "Unknown")
            regions = thumbnail.get("monitored_regions", [])
            
            if not thumbnail_id:
                continue
            
            self.window_tree.insert(all_root, "end", iid=thumbnail_id, text=title)
            if thumbnail_id not in self.region_statuses:
                self.region_statuses[thumbnail_id] = {}
            
            for region in regions:
                region_id = region.get("id")
                region_name = region.get("name", "Region")
                if not region_id:
                    continue
                self.window_tree.insert(thumbnail_id, "end", iid=region_id, text=region_name)
                self.region_to_thumbnail[region_id] = thumbnail_id
                if region_id not in self.region_statuses[thumbnail_id]:
                    self.region_statuses[thumbnail_id][region_id] = "ok"
        
        if thumbnails and self.show_all_regions:
            self._set_tree_selection("__all__")
            self._show_all_regions()
        elif thumbnails:
            selected_exists = self.selected_thumbnail_id and self.config.get_thumbnail(self.selected_thumbnail_id)
            if not selected_exists:
                first_id = thumbnails[0].get("id")
                if first_id:
                    self._set_tree_selection(first_id)
                    self._select_thumbnail(first_id)
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
            expected_title = thumbnail.get("window_title")
            expected_class = thumbnail.get("window_class") or None
            expected_size = tuple(thumbnail.get("window_size")) if thumbnail.get("window_size") else None
            expected_monitor = thumbnail.get("monitor_id")
            if not self.window_manager.validate_window_identity(
                hwnd,
                expected_title=expected_title,
                expected_class=expected_class,
                expected_monitor_id=expected_monitor,
                expected_size=expected_size,
            ):
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

    def _enqueue_engine_event(self, event_type: str, *args) -> None:
        """Coalesce high-frequency engine events and flush once on UI thread."""
        with self._event_lock:
            if event_type == "alert":
                thumbnail_id, region_id, region_name = args
                self._pending_alert_events[(thumbnail_id, region_id)] = region_name
            elif event_type == "change":
                thumbnail_id, region_id, state = args
                self._pending_region_change_events[(thumbnail_id, region_id)] = state
            elif event_type == "window_lost":
                thumbnail_id, window_title = args
                self._pending_window_lost_events[thumbnail_id] = window_title

            if self._ui_event_flush_scheduled:
                return
            self._ui_event_flush_scheduled = True

        try:
            self.root.after(0, self._flush_engine_events)
        except Exception as error:
            logger.warning(f"Failed scheduling engine event flush: {error}")
            with self._event_lock:
                self._ui_event_flush_scheduled = False

    def _flush_engine_events(self) -> None:
        """Apply coalesced engine events on the Tk UI thread."""
        with self._event_lock:
            alerts = list(self._pending_alert_events.items())
            changes = list(self._pending_region_change_events.items())
            lost_windows = list(self._pending_window_lost_events.items())
            self._pending_alert_events.clear()
            self._pending_region_change_events.clear()
            self._pending_window_lost_events.clear()
            self._ui_event_flush_scheduled = False

        if self.config.get_diagnostics_enabled():
            logger.debug(
                f"[UI EVENT FLUSH] alerts={len(alerts)} changes={len(changes)} window_lost={len(lost_windows)}"
            )

        for (thumbnail_id, region_id), region_name in alerts:
            self._on_alert(thumbnail_id, region_id, region_name)
        for (thumbnail_id, region_id), state in changes:
            self._on_region_change(thumbnail_id, region_id, state)
        for thumbnail_id, window_title in lost_windows:
            self._on_window_lost(thumbnail_id, window_title)
    
    def _on_alert(self, thumbnail_id: str, region_id: str, region_name: str) -> None:
        """Handle alert event with status update and TTS"""
        if threading.current_thread() is not threading.main_thread():
            self._enqueue_engine_event("alert", thumbnail_id, region_id, region_name)
            return

        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if thumbnail:
            title = thumbnail.get('window_title', 'Unknown')
            
            logger.info(f"[ALERT EVENT] {title} - {region_name} (region_id={region_id})")
            
            # Mark region as dirty for BOTH status and thumbnail updates
            self._mark_dirty(thumbnail_id, region_id, status="alert", thumbnail=True)
            
            # Update status bar
            self.status_var.set(f"🚨 ALERT: {title} - {region_name} changed!")
            
            logger.info(f"Alert in {title}: {region_name}")

    
    def _on_region_change(self, thumbnail_id: str, region_id: str, state: str = "ok") -> None:
        """Handle region state change from the monitoring engine."""
        if threading.current_thread() is not threading.main_thread():
            self._enqueue_engine_event("change", thumbnail_id, region_id, state)
            return

        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if thumbnail:
            regions = thumbnail.get('monitored_regions', [])
            region_name = "Unknown"
            for region in regions:
                if region.get('id') == region_id:
                    region_name = region.get('name', 'Unknown')
                    break

            logger.debug(f"[STATE EVENT] {thumbnail.get('window_title', 'Unknown')} - {region_name} -> {state}")

            # Mark region as dirty for BOTH status and thumbnail updates
            self._mark_dirty(thumbnail_id, region_id, status=state, thumbnail=True)

    
    def _on_window_lost(self, thumbnail_id: str, window_title: str) -> None:
        """Handle lost window"""
        if threading.current_thread() is not threading.main_thread():
            self._enqueue_engine_event("window_lost", thumbnail_id, window_title)
            return

        logger.warning(f"Window lost: {window_title}")
        self.status_var.set(f"Window lost: {window_title}")

    def _render_window_detail(self, thumbnail: Optional[Dict]) -> None:
        """Render window info and region cards"""
        for widget in self.regions_inner_frame.winfo_children():
            widget.destroy()
        self.region_widgets.clear()
        self.region_photos.clear()
        
        if self.show_all_regions or not thumbnail:
            self.info_frame.grid_remove()
            self.regions_frame.grid(row=0, column=0, sticky="nsew")
            self.detail_frame.rowconfigure(0, weight=1)
            self.detail_frame.rowconfigure(1, weight=0)
            thumbnails = self.config.get_all_thumbnails()
            total_regions = sum(len(t.get("monitored_regions", [])) for t in thumbnails)
            self.window_title_var.set("All windows")
            self.window_hwnd_var.set("")
            self.window_region_count_var.set(str(total_regions))
            self.window_size_var.set("")

            preview_image = None
            if len(thumbnails) == 1:
                selected_thumb = thumbnails[0]
                preview_hwnd = selected_thumb.get("window_hwnd")
                preview_image = self._get_window_image_for_ui(preview_hwnd, selected_thumb)
            if preview_image:
                preview = preview_image.copy()
                preview.thumbnail((180, 100), Image.Resampling.LANCZOS)
                self.window_preview_photo = ImageTk.PhotoImage(preview)
                self.window_preview_label.config(image=self.window_preview_photo, text="")
            else:
                self.window_preview_label.config(image=self._preview_placeholder, text="No preview", fg="white", compound="center")
            
            row = 0
            for thumb in thumbnails:
                thumb_id = thumb.get("id")
                if not thumb_id:
                    continue
                hwnd = thumb.get("window_hwnd")
                window_image = self._get_window_image_for_ui(hwnd, thumb)
                for region in thumb.get("monitored_regions", []):
                    region_id = region.get("id")
                    if not region_id:
                        continue
                    self._create_region_card(thumb_id, region_id, region, window_image, row,
                                             window_title=thumb.get("window_title", "Unknown"))
                    row += 1
        else:
            self.info_frame.grid()
            self.regions_frame.grid(row=1, column=0, sticky="nsew")
            self.detail_frame.rowconfigure(0, weight=0)
            self.detail_frame.rowconfigure(1, weight=1)
            thumbnail_id = thumbnail.get("id")
            title = thumbnail.get("window_title", "Unknown")
            hwnd = thumbnail.get("window_hwnd")
            regions = thumbnail.get("monitored_regions", [])
            
            self.window_title_var.set(title)
            self.window_hwnd_var.set(str(hwnd) if hwnd else "")
            self.window_region_count_var.set(str(len(regions)))
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
                self.window_preview_label.config(image=self.window_preview_photo, text="")
            else:
                self.window_preview_label.config(image=self._preview_placeholder, text="No preview", fg="white", compound="center")
            
            regions_to_render = regions
            if self.selected_region_id:
                selected = [r for r in regions if r.get("id") == self.selected_region_id]
                if selected:
                    regions_to_render = selected

            for idx, region in enumerate(regions_to_render):
                region_id = region.get("id")
                if not region_id:
                    continue
                self._create_region_card(thumbnail_id, region_id, region, window_image, idx)

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
        self.window_size_var.set("")
        self.window_preview_label.config(image=self._preview_placeholder, text="No window selected", fg="white", compound="center")
        for widget in self.regions_inner_frame.winfo_children():
            widget.destroy()
        self.region_widgets.clear()
        self.region_photos.clear()
        self._schedule_detail_scroll_refresh()

    def _create_region_card(self, thumbnail_id: str, region_id: str, region: Dict,
                             window_image, row: int, window_title: Optional[str] = None) -> None:
        """Create a region card row"""
        card = tk.Frame(self.regions_inner_frame, bg="#202020", bd=1, relief=tk.RIDGE)
        card.grid(row=row, column=0, sticky="ew", pady=2, padx=4)
        card.columnconfigure(2, weight=1)
        
        content_row = 0
        
        # Left status pill
        status_pill = tk.Label(card, text="OK", bg="#2ecc71", fg="black",
                               width=7, height=2)
        status_pill.grid(row=content_row, column=0, rowspan=2, sticky="ns", padx=(4, 0), pady=3)
        
        # Region image
        image_label = tk.Label(card, bg="#1a1a1a")
        image_label.grid(row=content_row, column=1, rowspan=2, sticky="w", padx=6, pady=3)
        
        if window_image:
            try:
                region_image = ImageProcessor.crop_region(window_image, region.get("rect", (0, 0, 0, 0)))
                region_image.thumbnail((220, 96), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(region_image)
                self.region_photos[region_id] = photo
                image_label.config(image=photo)
            except Exception as e:
                logger.error(f"Error creating region image {region_id}: {e}", exc_info=True)
                image_label.config(text="No image", fg="white")
        else:
            image_label.config(text="Not Available", fg="white", bg="#0078D7")
        
        # Region form fields (name + alert text)
        form_frame = tk.Frame(card, bg="#202020")
        form_frame.grid(row=content_row, column=2, rowspan=2, sticky="nsew", padx=(0, 8), pady=(3, 2))

        row_offset = 0
        if window_title:
            tk.Label(form_frame, text="Window:", bg="#202020", fg="#bdbdbd").grid(row=0, column=0, sticky="w", padx=(0, 6))
            tk.Label(form_frame, text=window_title, bg="#202020", fg="#bdbdbd").grid(row=0, column=1, sticky="w")
            row_offset = 1

        tk.Label(form_frame, text="Name:", bg="#202020", fg="#bdbdbd").grid(row=row_offset, column=0, sticky="w", padx=(0, 6), pady=(2 if row_offset else 0, 0))
        name_var = tk.StringVar(value=region.get("name", "Region"))
        name_entry = ttk.Entry(form_frame, textvariable=name_var, width=24)
        name_entry.grid(row=row_offset, column=1, sticky="w", pady=(2 if row_offset else 0, 0))
        name_entry.bind("<Return>", lambda e: self._save_region_name(thumbnail_id, region_id, name_var))
        name_entry.bind("<FocusOut>", lambda e: self._save_region_name(thumbnail_id, region_id, name_var))

        tk.Label(form_frame, text="Alert Text:", bg="#202020", fg="#bdbdbd").grid(row=row_offset + 1, column=0, sticky="w", padx=(0, 6), pady=(3, 0))
        alert_text_var = tk.StringVar(value=region.get("tts_message", self.config.get_default_tts_message()))
        alert_text_entry = ttk.Entry(form_frame, textvariable=alert_text_var, width=24)
        alert_text_entry.grid(row=row_offset + 1, column=1, sticky="w", pady=(3, 0))
        alert_text_entry.bind("<Return>", lambda e: self._save_region_alert_text(thumbnail_id, region_id, alert_text_var))
        alert_text_entry.bind("<FocusOut>", lambda e: self._save_region_alert_text(thumbnail_id, region_id, alert_text_var))
        
        # Right control panel
        controls_panel = tk.Frame(card, bg="#1a1a1a", bd=1, relief=tk.RIDGE)
        controls_panel.grid(row=content_row, column=3, rowspan=2, sticky="e", padx=(0, 6), pady=3)
        
        pause_btn = ttk.Button(controls_panel, text="Pause", width=9, command=lambda: self._toggle_region_pause(region_id))
        pause_btn.pack(padx=6, pady=(4, 2))

        enabled_now = bool(region.get("enabled", True))
        disable_btn = ttk.Button(
            controls_panel,
            text=("Disable" if enabled_now else "Enable"),
            width=9,
            command=lambda: self._toggle_region_enabled(thumbnail_id, region_id)
        )
        disable_btn.pack(padx=6, pady=(0, 3))
        
        self.region_widgets[region_id] = {
            "status_pill": status_pill,
            "pause_btn": pause_btn,
            "disable_btn": disable_btn,
            "name_entry": name_entry,
            "alert_text_entry": alert_text_entry,
            "image_label": image_label,
        }
        
        if not window_image:
            self._set_region_status(thumbnail_id, region_id, "unavailable")
            self._apply_region_status(thumbnail_id, region_id)
        elif not enabled_now:
            self._set_region_status(thumbnail_id, region_id, "disabled")
            self._apply_region_status(thumbnail_id, region_id)
        else:
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

    def _save_region_name(self, thumbnail_id: str, region_id: str, name_var: tk.StringVar) -> None:
        """Persist region name changes"""
        new_name = name_var.get().strip()
        if not new_name:
            return
        if self.config.update_region(thumbnail_id, region_id, {"name": new_name}):
            self.config.save()
            if self.window_tree.exists(region_id):
                self.window_tree.item(region_id, text=new_name)

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
            pill.config(text=status_text, bg="#e74c3c", fg="white")
        elif status == "warning":
            pill.config(text=status_text, bg="#f39c12", fg="black")
        elif status == "paused":
            pill.config(text=status_text, bg="#3498db", fg="white")
        elif status == "unavailable":
            pill.config(text=status_text, bg="#3498db", fg="white")
        elif status == "disabled":
            pill.config(text=status_text, bg="#7f8c8d", fg="white")
        else:
            pill.config(text=status_text, bg="#2ecc71", fg="black")

    def _format_region_status_text(self, region_id: str, status: str) -> str:
        """Build region status text, including countdown for timed states."""
        base_map = {
            "alert": "ALERT",
            "warning": "WARNING",
            "paused": "PAUSED",
            "disabled": "N/A",
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

    def _refresh_dynamic_status_texts(self) -> None:
        """Refresh dynamic text portions (countdown) without changing colors."""
        for region_id, widgets in self.region_widgets.items():
            pill = widgets.get("status_pill")
            if not pill:
                continue
            thumbnail_id = self.region_to_thumbnail.get(region_id)
            status = self.region_statuses.get(thumbnail_id, {}).get(region_id, "ok")
            pill.config(text=self._format_region_status_text(region_id, status))

    def _collect_all_region_states(self) -> List[str]:
        """Collect current states across all configured regions."""
        states: List[str] = []
        for thumbnail in self.config.get_all_thumbnails():
            thumb_enabled = bool(thumbnail.get("enabled", True))
            hwnd = thumbnail.get("window_hwnd")
            title = thumbnail.get("window_title")
            expected_class = thumbnail.get("window_class") or None
            expected_size = tuple(thumbnail["window_size"]) if thumbnail.get("window_size") else None
            expected_monitor = thumbnail.get("monitor_id")
            window_available = (
                bool(hwnd)
                and self.window_manager.validate_window_identity(
                    hwnd,
                    expected_title=title,
                    expected_class=expected_class,
                    expected_monitor_id=expected_monitor,
                    expected_size=expected_size,
                )
            )
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

        if aggregate == "alert":
            self.aggregate_status_var.set("Overall: ALERT")
            self.aggregate_status_badge.config(bg="#e74c3c", fg="white")
        elif aggregate == "warning":
            self.aggregate_status_var.set("Overall: WARNING")
            self.aggregate_status_badge.config(bg="#f39c12", fg="black")
        elif aggregate == "ok":
            self.aggregate_status_var.set("Overall: OK")
            self.aggregate_status_badge.config(bg="#2ecc71", fg="black")
        elif aggregate == "paused":
            self.aggregate_status_var.set("Overall: PAUSED")
            self.aggregate_status_badge.config(bg="#3498db", fg="white")
        else:
            self.aggregate_status_var.set("Overall: N/A")
            self.aggregate_status_badge.config(bg="#3498db", fg="white")

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
            image_label.config(image="", text="Not Available", fg="white", bg="#0078D7")
            self.region_photos.pop(region_id, None)
            self._set_region_status(thumbnail_id, region_id, "unavailable")
            self._apply_region_status(thumbnail_id, region_id)
            return
        try:
            region_image = ImageProcessor.crop_region(window_image, region.get("rect", (0, 0, 0, 0)))
            region_image.thumbnail((220, 96), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(region_image)
            self.region_photos[region_id] = photo
            image_label.config(image=photo, text="", bg="#1a1a1a")
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

    def _force_refresh_all_thumbnails(self) -> None:
        """Force refresh all visible region cards and window preview (every ~5s).

        Invalidates the image cache so the next capture is fresh, then updates
        every region card that currently has widgets on screen plus the window
        preview image.
        """
        try:
            # Invalidate cache so we get a fresh capture
            self.engine.cache_manager.invalidate_all()

            # Refresh each region card that is currently displayed
            for region_id, widgets in list(self.region_widgets.items()):
                thumbnail_id = self.region_to_thumbnail.get(region_id)
                if thumbnail_id:
                    self._update_region_thumbnail(thumbnail_id, region_id)

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
                self.window_preview_label.config(image=self.window_preview_photo, text="")
            else:
                self.window_preview_photo = None
                self.window_preview_label.config(
                    image=self._preview_placeholder,
                    text="Not Available",
                    fg="white",
                    compound="center",
                )
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
        
        if thumbnail:
            self.dirty_regions[region_id]['thumbnail'] = True
            logger.debug(f"[MARK DIRTY] Region {region_id}: thumbnail needs update")

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

            self._refresh_dynamic_status_texts()
            self._refresh_aggregate_status()

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
        # Cancel periodic update timer
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
    
    def run(self) -> None:
        """Run main window"""
        logger.info("Entering Tk mainloop")
        self.root.after(1000, lambda: logger.debug("Tk mainloop heartbeat: still running..."))
        self.root.mainloop()
        logger.info("Exited Tk mainloop")
