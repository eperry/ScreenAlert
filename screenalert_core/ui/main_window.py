"""Main window UI for ScreenAlert v2"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox as msgbox
from typing import Optional, List
import win32gui

from screenalert_core.screening_engine import ScreenAlertEngine
from screenalert_core.ui.window_selector_dialog import WindowSelectorDialog
from screenalert_core.ui.region_selection_overlay import RegionSelectionOverlay
from screenalert_core.ui.settings_dialog import SettingsDialog

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
        
        # Create root window
        self.root = tk.Tk()
        self.root.title("ScreenAlert v2.0 - Multibox Monitor")
        self.root.geometry("1000x700")
        
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
        """Build main UI"""
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
        
        # Control panel
        control_frame = ttk.LabelFrame(main_frame, text="Control Panel", padding=10)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Buttons
        btn_add = ttk.Button(control_frame, text="➕ Add Window", command=self._add_window)
        btn_add.pack(side=tk.LEFT, padx=5)
        
        self.btn_start = ttk.Button(control_frame, text="▶ Start Monitoring", 
                                   command=self._start_monitoring)
        self.btn_start.pack(side=tk.LEFT, padx=5)
        
        self.btn_pause = ttk.Button(control_frame, text="⏸ Pause All", 
                                   command=self._pause_monitoring, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="⚙ Settings", 
                  command=self._show_settings).pack(side=tk.RIGHT, padx=5)
        
        # Thumbnail list
        list_frame = ttk.LabelFrame(main_frame, text="Active Thumbnails (0)", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.list_label = list_frame  # Store reference
        
        # Scrollbar and listbox
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.thumbnail_list = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                        font=("Segoe UI", 10), height=12)
        self.thumbnail_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.thumbnail_list.yview)
        self.thumbnail_list.bind("<Double-Button-1>", self._on_thumbnail_double_click)
        
        # Actions frame
        actions_frame = ttk.Frame(main_frame)
        actions_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(actions_frame, text="Add Region", 
                  command=self._add_region).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="Remove Region", 
                  command=self._remove_region).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="Remove Selected Window", 
                  command=self._remove_thumbnail).pack(side=tk.LEFT, padx=5)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, 
                             relief=tk.SUNKEN, anchor="w")
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)
        
        # Bind window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_exit)
    
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
        if not self.thumbnail_list.curselection():
            self.status_var.set("Select a thumbnail first")
            return
        
        idx = self.thumbnail_list.curselection()[0]
        thumbnails = self.config.get_all_thumbnails()
        if idx >= len(thumbnails):
            return
        
        thumbnail = thumbnails[idx]
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
        if not self.thumbnail_list.curselection():
            self.status_var.set("Select a thumbnail first")
            return
        
        idx = self.thumbnail_list.curselection()[0]
        thumbnails = self.config.get_all_thumbnails()
        if idx >= len(thumbnails):
            return
        
        thumbnail = thumbnails[idx]
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
        if not self.thumbnail_list.curselection():
            self.status_var.set("Select a thumbnail to remove")
            return
        
        idx = self.thumbnail_list.curselection()[0]
        thumbnails = self.config.get_all_thumbnails()
        if idx >= len(thumbnails):
            return
        
        thumbnail = thumbnails[idx]
        thumbnail_id = thumbnail['id']
        hwnd = thumbnail['window_hwnd']
        title = thumbnail.get('window_title', 'Unknown')
        
        try:
            self.engine.remove_thumbnail(thumbnail_id)
            self.config.remove_thumbnail(thumbnail_id)
            if hwnd in self.thumbnail_map:
                del self.thumbnail_map[hwnd]
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
        """Update thumbnail list display"""
        self.thumbnail_list.delete(0, tk.END)
        thumbnails = self.config.get_all_thumbnails()
        logger.info(f"Updating thumbnail list: {len(thumbnails)} thumbnails from config")
        
        for thumbnail in thumbnails:
            title = thumbnail.get('window_title', 'Unknown')
            regions = thumbnail.get('monitored_regions', [])
            text = f"{title} ({len(regions)} regions)"
            self.thumbnail_list.insert(tk.END, text)
            logger.debug(f"  Added to list: {text}")
        
        count = len(thumbnails)
        self.list_label.config(text=f"Active Thumbnails ({count})")
        logger.info(f"Thumbnail list updated: {count} total")
    
    def _on_thumbnail_double_click(self, event) -> None:
        """Handle double-click on thumbnail"""
        if self.thumbnail_list.curselection():
            self._add_region()
    
    def _on_alert(self, thumbnail_id: str, region_id: str, region_name: str) -> None:
        """Handle alert event"""
        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if thumbnail:
            title = thumbnail.get('window_title', 'Unknown')
            self.status_var.set(f"ALERT: {title} - {region_name} changed!")
            logger.info(f"Alert in {title}: {region_name}")
    
    def _on_region_change(self, thumbnail_id: str, region_id: str) -> None:
        """Handle region change"""
        logger.debug(f"Region changed: {region_id}")
    
    def _on_window_lost(self, thumbnail_id: str, window_title: str) -> None:
        """Handle lost window"""
        logger.warning(f"Window lost: {window_title}")
        self.status_var.set(f"Window lost: {window_title}")
    
    def _on_exit(self) -> None:
        """Handle window close"""
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
