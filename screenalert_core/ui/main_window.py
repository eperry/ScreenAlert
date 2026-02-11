"""Main window UI for ScreenAlert v2"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox as msgbox
from typing import Optional, List, Dict
import win32gui
import pyttsx3
from PIL import Image, ImageTk

from screenalert_core.screening_engine import ScreenAlertEngine
from screenalert_core.ui.window_selector_dialog import WindowSelectorDialog
from screenalert_core.ui.region_selection_overlay import RegionSelectionOverlay
from screenalert_core.ui.settings_dialog import SettingsDialog
from screenalert_core.core.image_processor import ImageProcessor

logger = logging.getLogger(__name__)


class ScreenAlertMainWindow:
    """Main control window for ScreenAlert"""
    
    def __init__(self, engine: ScreenAlertEngine):
        """Initialize main window
        
        Args:
            engine: ScreenAlertEngine instance
        """
        self.engine = engine
        self.config = engine.config
        self.window_manager = engine.window_manager
        self.thumbnail_map = {}  # hwnd -> thumbnail_id mapping
        self.selected_thumbnail_id: Optional[str] = None  # Currently selected window
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
        
        # Initialize text-to-speech
        try:
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty('rate', 150)  # Slow down for clarity
        except Exception as e:
            logger.warning(f"Could not initialize TTS: {e}")
            self.tts_engine = None
        
        # Create root window
        self.root = tk.Tk()
        self.root.title("ScreenAlert v2.0 - Multibox Monitor")
        self.root.geometry("1200x800")
        
        # Pass tkinter root to engine for overlay windows
        self.engine.set_tkinter_root(self.root)
        
        # Rebuild thumbnail_map from config (for duplicate checking)
        for thumbnail in self.config.get_all_thumbnails():
            hwnd = thumbnail.get('window_hwnd')
            thumbnail_id = thumbnail.get('id')
            if hwnd and thumbnail_id:
                self.thumbnail_map[hwnd] = thumbnail_id
                logger.debug(f"Restored thumbnail_map: hwnd={hwnd} -> {thumbnail_id}")
        logger.info(f"Restored {len(self.thumbnail_map)} thumbnails in map from config")
        
        # Configure style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Build UI
        self._build_ui()
        
        # Update thumbnail list with any saved thumbnails from config
        self._update_thumbnail_list()
        
        # Setup callbacks
        self.engine.on_alert = self._on_alert
        self.engine.on_region_change = self._on_region_change
        self.engine.on_window_lost = self._on_window_lost
    
    def _build_ui(self) -> None:
        """Build main UI with tree + region detail layout"""
        # Menu
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Settings...", command=self._show_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_exit)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)
        
        # Main content
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Control panel - top
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(control_frame, text="➕ Add Window", command=self._add_window).pack(side=tk.LEFT, padx=5)
        
        self.btn_start = ttk.Button(control_frame, text="▶ Start Monitoring", 
                                   command=self._start_monitoring)
        self.btn_start.pack(side=tk.LEFT, padx=5)
        
        self.btn_pause = ttk.Button(control_frame, text="⏸ Pause All", 
                                   command=self._pause_monitoring, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="🔧 Add Region", 
                  command=self._add_region).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="❌ Remove Region", 
                  command=self._remove_region).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="❌ Remove Window", 
              command=self._remove_thumbnail).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="⚙ Settings", 
                  command=self._show_settings).pack(side=tk.RIGHT, padx=5)
        
        # Content area
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        content_frame.columnconfigure(1, weight=1)
        content_frame.rowconfigure(0, weight=1)
        
        # Left: tree of windows/regions
        tree_frame = ttk.LabelFrame(content_frame, text="Windows", padding=8)
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        
        self.window_tree = ttk.Treeview(tree_frame, show="tree")
        self.window_tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.window_tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.window_tree.configure(yscrollcommand=tree_scroll.set)
        self.window_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        
        # Right: window info + region cards
        detail_frame = ttk.Frame(content_frame)
        detail_frame.grid(row=0, column=1, sticky="nsew")
        detail_frame.rowconfigure(1, weight=1)
        detail_frame.columnconfigure(0, weight=1)
        
        info_frame = ttk.LabelFrame(detail_frame, text="Window Info", padding=8)
        info_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        info_frame.columnconfigure(1, weight=1)
        
        ttk.Label(info_frame, text="Title:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.window_title_var = tk.StringVar(value="")
        ttk.Label(info_frame, textvariable=self.window_title_var).grid(row=0, column=1, sticky="w")
        
        ttk.Label(info_frame, text="HWND:").grid(row=1, column=0, sticky="w", padx=(0, 6))
        self.window_hwnd_var = tk.StringVar(value="")
        ttk.Label(info_frame, textvariable=self.window_hwnd_var).grid(row=1, column=1, sticky="w")
        
        ttk.Label(info_frame, text="Regions:").grid(row=2, column=0, sticky="w", padx=(0, 6))
        self.window_region_count_var = tk.StringVar(value="0")
        ttk.Label(info_frame, textvariable=self.window_region_count_var).grid(row=2, column=1, sticky="w")
        
        self.window_preview_label = tk.Label(info_frame, bg="#1a1a1a", width=30, height=6)
        self.window_preview_label.grid(row=0, column=2, rowspan=3, sticky="e", padx=(10, 0))
        
        regions_frame = ttk.LabelFrame(detail_frame, text="Regions", padding=8)
        regions_frame.grid(row=1, column=0, sticky="nsew")
        regions_frame.rowconfigure(0, weight=1)
        regions_frame.columnconfigure(0, weight=1)
        
        self.region_canvas = tk.Canvas(regions_frame, bg="#202020", highlightthickness=0)
        self.region_canvas.grid(row=0, column=0, sticky="nsew")
        region_scroll = ttk.Scrollbar(regions_frame, orient=tk.VERTICAL, command=self.region_canvas.yview)
        region_scroll.grid(row=0, column=1, sticky="ns")
        self.region_canvas.configure(yscrollcommand=region_scroll.set)
        
        self.regions_inner_frame = tk.Frame(self.region_canvas, bg="#202020")
        self.region_canvas_window = self.region_canvas.create_window(0, 0, window=self.regions_inner_frame, anchor="nw")
        self.region_canvas.bind("<Configure>", self._on_region_canvas_configure)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, 
                             relief=tk.SUNKEN, anchor="w")
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)
        
        # Bind window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_exit)
    
    def _on_region_canvas_configure(self, event) -> None:
        """Handle region canvas resize"""
        self.region_canvas.configure(scrollregion=self.region_canvas.bbox("all"))
        self.region_canvas.itemconfig(self.region_canvas_window, width=event.width)

    
    def _add_window(self) -> None:
        """Add a new window to monitor"""
        dialog = WindowSelectorDialog(self.root, self.window_manager)
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
                thumbnail_id = self.engine.add_thumbnail(window_title=title, window_hwnd=hwnd)
                if thumbnail_id:
                    self.thumbnail_map[hwnd] = thumbnail_id
                    self._update_thumbnail_list()
                    self.status_var.set(f"Added: {title}")
                else:
                    msgbox.showerror("Error", f"Failed to add window {title}")
            except Exception as e:
                logger.error(f"Error adding window '{title}': {str(e)}", exc_info=True)
                msgbox.showerror("Error", f"Failed to add window: {str(e)}")
    
    def _start_monitoring(self) -> None:
        """Start monitoring"""
        thumbnails = self.config.get_all_thumbnails()
        if not thumbnails:
            msgbox.showwarning("Warning", "Add at least one window first")
            return
        
        try:
            self.engine.start()
            self.btn_start.config(state=tk.DISABLED)
            self.btn_pause.config(state=tk.NORMAL)
            self.status_var.set("Monitoring started")
            
            # Start periodic UI update loop
            if self.update_timer_id is None:
                self._periodic_ui_update()
        except Exception as e:
            logger.error(f"Error starting monitoring: {str(e)}", exc_info=True)
            msgbox.showerror("Error", f"Failed to start monitoring: {str(e)}")
    
    def _pause_monitoring(self) -> None:
        """Pause monitoring"""
        try:
            self.engine.set_paused(True)
            self.btn_start.config(state=tk.NORMAL)
            self.btn_pause.config(state=tk.DISABLED)
            self.status_var.set("Monitoring paused")
        except Exception as e:
            logger.error(f"Error pausing monitoring: {str(e)}", exc_info=True)
            msgbox.showerror("Error", f"Failed to pause monitoring: {str(e)}")
    
    def _show_settings(self) -> None:
        """Show settings dialog"""
        try:
            dialog = SettingsDialog(self.root, self.config)
            if dialog.show():
                self.status_var.set("Settings updated")
        except Exception as e:
            logger.error(f"Error opening settings dialog: {str(e)}", exc_info=True)
            msgbox.showerror("Error", f"Failed to open settings: {str(e)}")
    
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
            win32gui.SetForegroundWindow(hwnd)
            
            # Hide the ScreenAlert window
            self.root.withdraw()
            
            # Show region selection overlay
            overlay = RegionSelectionOverlay(hwnd, self.root)
            regions_screen = overlay.show()  # Screen coordinates
            
            # Show the ScreenAlert window again
            self.root.deiconify()
            
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
                self.config.remove_region(thumbnail_id, region_id)
                if thumbnail_id in self.region_statuses:
                    self.region_statuses[thumbnail_id].pop(region_id, None)
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
            self.window_tree.selection_set("__all__")
            self._show_all_regions()
        elif thumbnails:
            selected_exists = self.selected_thumbnail_id and self.config.get_thumbnail(self.selected_thumbnail_id)
            if not selected_exists:
                first_id = thumbnails[0].get("id")
                if first_id:
                    self.window_tree.selection_set(first_id)
                    self._select_thumbnail(first_id)
        elif not thumbnails:
            self.selected_thumbnail_id = None
            self._clear_detail_view()


    
    def _on_tree_select(self, event) -> None:
        """Handle tree selection"""
        selection = self.window_tree.selection()
        if not selection:
            return
        selected_id = selection[0]
        if selected_id == "__all__":
            self._show_all_regions()
            return
        self.show_all_regions = False
        if selected_id in self.region_to_thumbnail:
            thumbnail_id = self.region_to_thumbnail[selected_id]
        else:
            thumbnail_id = selected_id
        self._select_thumbnail(thumbnail_id)

    def _select_thumbnail(self, thumbnail_id: str) -> None:
        """Set selection and refresh detail view"""
        self.selected_thumbnail_id = thumbnail_id
        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if thumbnail:
            title = thumbnail.get("window_title", "Unknown")
            regions = thumbnail.get("monitored_regions", [])
            self.status_var.set(f"Selected: {title} ({len(regions)} regions)")
            self._render_window_detail(thumbnail)
            logger.debug(f"Selected thumbnail: {title}")
    
    def _on_alert(self, thumbnail_id: str, region_id: str, region_name: str) -> None:
        """Handle alert event with status update and TTS"""
        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if thumbnail:
            title = thumbnail.get('window_title', 'Unknown')
            
            logger.info(f"[ALERT EVENT] {title} - {region_name} (region_id={region_id})")
            
            # Mark region as dirty for BOTH status and thumbnail updates
            self._mark_dirty(thumbnail_id, region_id, status="alert", thumbnail=True)
            
            # Update status bar
            self.status_var.set(f"🚨 ALERT: {title} - {region_name} changed!")
            
            # Speak alert via TTS
            if self.tts_engine:
                try:
                    message = f"Alert! {title}, {region_name}"
                    self.tts_engine.say(message)
                    self.tts_engine.runAndWait()
                except Exception as e:
                    logger.warning(f"TTS error: {e}")
            
            logger.info(f"Alert in {title}: {region_name} (region_idx={region_idx})")

    
    def _on_region_change(self, thumbnail_id: str, region_id: str) -> None:
        """Handle region change - update status to WARNING"""
        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if thumbnail:
            regions = thumbnail.get('monitored_regions', [])
            region_name = "Unknown"
            for region in regions:
                if region.get('id') == region_id:
                    region_name = region.get('name', 'Unknown')
                    break
            
            logger.info(f"[CHANGE EVENT] {thumbnail.get('window_title', 'Unknown')} - {region_name} (region_id={region_id})")
            
            # Mark region as dirty for BOTH status and thumbnail updates
            self._mark_dirty(thumbnail_id, region_id, status="warning", thumbnail=True)

    
    def _on_window_lost(self, thumbnail_id: str, window_title: str) -> None:
        """Handle lost window"""
        logger.warning(f"Window lost: {window_title}")
        self.status_var.set(f"Window lost: {window_title}")

    def _render_window_detail(self, thumbnail: Optional[Dict]) -> None:
        """Render window info and region cards"""
        for widget in self.regions_inner_frame.winfo_children():
            widget.destroy()
        self.region_widgets.clear()
        self.region_photos.clear()
        
        if self.show_all_regions or not thumbnail:
            thumbnails = self.config.get_all_thumbnails()
            total_regions = sum(len(t.get("monitored_regions", [])) for t in thumbnails)
            self.window_title_var.set("All windows")
            self.window_hwnd_var.set("")
            self.window_region_count_var.set(str(total_regions))
            self.window_preview_label.config(image="", text="", fg="white")
            
            row = 0
            for thumb in thumbnails:
                thumb_id = thumb.get("id")
                if not thumb_id:
                    continue
                window_image = None
                hwnd = thumb.get("window_hwnd")
                if hwnd:
                    # Use cached image to avoid blocking UI
                    window_image = self.engine.cache_manager.get(hwnd)
                for region in thumb.get("monitored_regions", []):
                    region_id = region.get("id")
                    if not region_id:
                        continue
                    self._create_region_card(thumb_id, region_id, region, window_image, row,
                                             window_title=thumb.get("window_title", "Unknown"))
                    row += 1
        else:
            thumbnail_id = thumbnail.get("id")
            title = thumbnail.get("window_title", "Unknown")
            hwnd = thumbnail.get("window_hwnd")
            regions = thumbnail.get("monitored_regions", [])
            
            self.window_title_var.set(title)
            self.window_hwnd_var.set(str(hwnd) if hwnd else "")
            self.window_region_count_var.set(str(len(regions)))
            
            window_image = None
            if hwnd:
                # Use cached image to avoid blocking UI
                window_image = self.engine.cache_manager.get(hwnd)
            
            if window_image:
                preview = window_image.copy()
                preview.thumbnail((240, 120), Image.Resampling.LANCZOS)
                self.window_preview_photo = ImageTk.PhotoImage(preview)
                self.window_preview_label.config(image=self.window_preview_photo, text="")
            else:
                self.window_preview_label.config(image="", text="No preview", fg="white")
            
            for idx, region in enumerate(regions):
                region_id = region.get("id")
                if not region_id:
                    continue
                self._create_region_card(thumbnail_id, region_id, region, window_image, idx)
        
        self.regions_inner_frame.update_idletasks()
        self.region_canvas.configure(scrollregion=self.region_canvas.bbox("all"))

    def _clear_detail_view(self) -> None:
        """Clear window detail panel"""
        self.window_title_var.set("")
        self.window_hwnd_var.set("")
        self.window_region_count_var.set("0")
        self.window_preview_label.config(image="", text="No window selected", fg="white")
        for widget in self.regions_inner_frame.winfo_children():
            widget.destroy()
        self.region_widgets.clear()
        self.region_photos.clear()

    def _create_region_card(self, thumbnail_id: str, region_id: str, region: Dict,
                             window_image, row: int, window_title: Optional[str] = None) -> None:
        """Create a region card row"""
        card = tk.Frame(self.regions_inner_frame, bg="#202020", bd=1, relief=tk.SOLID)
        card.grid(row=row, column=0, sticky="ew", pady=6, padx=4)
        card.columnconfigure(3, weight=1)
        
        if window_title and self.show_all_regions:
            header = tk.Label(card, text=window_title, bg="#202020", fg="#bdbdbd")
            header.grid(row=0, column=0, columnspan=5, sticky="w", padx=10, pady=(6, 0))
            content_row = 1
        else:
            content_row = 0
        
        # Left status pill
        status_pill = tk.Label(card, text="OK", bg="#2ecc71", fg="black",
                               width=10, height=4)
        status_pill.grid(row=content_row, column=0, rowspan=2, sticky="ns", padx=(6, 0), pady=6)
        
        # Region image
        image_label = tk.Label(card, bg="#1a1a1a")
        image_label.grid(row=content_row, column=1, rowspan=2, sticky="w", padx=8, pady=6)
        
        if window_image:
            try:
                region_image = ImageProcessor.crop_region(window_image, region.get("rect", (0, 0, 0, 0)))
                region_image.thumbnail((360, 180), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(region_image)
                self.region_photos[region_id] = photo
                image_label.config(image=photo)
            except Exception as e:
                logger.error(f"Error creating region image {region_id}: {e}", exc_info=True)
                image_label.config(text="No image", fg="white")
        else:
            image_label.config(text="No image", fg="white")
        
        # Title text
        name_var = tk.StringVar(value=region.get("name", "Region"))
        name_entry = ttk.Entry(card, textvariable=name_var)
        name_entry.grid(row=content_row, column=2, sticky="w", padx=(0, 10), pady=(10, 4))
        name_entry.bind("<Return>", lambda e: self._save_region_name(thumbnail_id, region_id, name_var))
        name_entry.bind("<FocusOut>", lambda e: self._save_region_name(thumbnail_id, region_id, name_var))
        
        # Spacer
        spacer = tk.Frame(card, bg="#202020")
        spacer.grid(row=content_row, column=3, rowspan=2, sticky="nsew")
        
        # Right control panel
        controls_panel = tk.Frame(card, bg="#1a1a1a", bd=1, relief=tk.RIDGE)
        controls_panel.grid(row=content_row, column=4, rowspan=2, sticky="e", padx=(0, 8), pady=6)
        
        pause_btn = ttk.Button(controls_panel, text="Pause", command=lambda: self._toggle_region_pause(region_id))
        pause_btn.pack(padx=8, pady=(8, 4))
        
        status_label = tk.Label(controls_panel, text="OK", width=10, bg="#2ecc71", fg="black")
        status_label.pack(padx=8, pady=(0, 8))
        
        self.region_widgets[region_id] = {
            "status_label": status_label,
            "status_pill": status_pill,
            "pause_btn": pause_btn,
            "name_entry": name_entry,
            "image_label": image_label,
        }
        
        if not window_image:
            self._set_region_status(thumbnail_id, region_id, "unavailable")
        else:
            self._apply_region_status(thumbnail_id, region_id)

    def _save_region_name(self, thumbnail_id: str, region_id: str, name_var: tk.StringVar) -> None:
        """Persist region name changes"""
        new_name = name_var.get().strip()
        if not new_name:
            return
        if self.config.update_region(thumbnail_id, region_id, {"name": new_name}):
            self.config.save()
            if self.window_tree.exists(region_id):
                self.window_tree.item(region_id, text=new_name)

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
        label = widgets.get("status_label")
        pill = widgets.get("status_pill")
        if not label or not pill:
            return
        if status == "alert":
            label.config(text="ALERT", bg="#e74c3c", fg="white")
            pill.config(text="ALERT", bg="#e74c3c", fg="white")
        elif status == "warning":
            label.config(text="WARNING", bg="#f39c12", fg="black")
            pill.config(text="WARNING", bg="#f39c12", fg="black")
        elif status == "paused":
            label.config(text="PAUSED", bg="#3498db", fg="white")
            pill.config(text="PAUSED", bg="#3498db", fg="white")
        elif status == "unavailable":
            label.config(text="UNAVAILABLE", bg="#2c3e50", fg="white")
            pill.config(text="UNAVAILABLE", bg="#2c3e50", fg="white")
        else:
            label.config(text="OK", bg="#2ecc71", fg="black")
            pill.config(text="OK", bg="#2ecc71", fg="black")

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
        window_image = self.engine.cache_manager.get(hwnd)
        if not window_image:
            logger.warning(f"[THUMBNAIL UPDATE] No cached image for hwnd {hwnd}")
            return
        try:
            region_image = ImageProcessor.crop_region(window_image, region.get("rect", (0, 0, 0, 0)))
            region_image.thumbnail((360, 180), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(region_image)
            self.region_photos[region_id] = photo
            image_label.config(image=photo, text="")
            logger.debug(f"[THUMBNAIL UPDATE] Successfully updated image for region {region_id}")
        except Exception as e:
            logger.error(f"Error updating region image {region_id}: {e}", exc_info=True)

    def _show_all_regions(self) -> None:
        """Clear selection filter and show all regions"""
        self.show_all_regions = True
        if self.window_tree.exists("__all__"):
            self.window_tree.selection_set("__all__")
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
                logger.info(f"[MARK DIRTY] Region {region_id}: status {current_status} -> {status}")
        
        if thumbnail:
            self.dirty_regions[region_id]['thumbnail'] = True
            logger.info(f"[MARK DIRTY] Region {region_id}: thumbnail needs update")

    def _periodic_ui_update(self) -> None:
        """Periodic update loop - SINGLE point where UI updates happen every 1000ms"""
        try:
            # Collect all dirty regions
            dirty_count = sum(1 for flags in self.dirty_regions.values() if flags['status'] or flags['thumbnail'])
            
            if dirty_count > 0:
                logger.info(f"[PERIODIC UPDATE] Processing {dirty_count} dirty regions")
                
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
                logger.info(f"[PERIODIC UPDATE] Batch complete")
            else:
                logger.debug(f"[PERIODIC UPDATE] No dirty regions")
                
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
        self.root.mainloop()
