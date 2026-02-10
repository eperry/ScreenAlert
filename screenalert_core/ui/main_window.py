"""Main window UI for ScreenAlert v2"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox as msgbox
from typing import Optional, List

from screenalert_core.screening_engine import ScreenAlertEngine
from screenalert_core.ui.window_selector_dialog import WindowSelectorDialog
from screenalert_core.ui.region_editor_dialog import RegionEditorDialog
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
        
        # Configure style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Build UI
        self._build_ui()
        
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
        ttk.Button(actions_frame, text="Remove Selected", 
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
            
            try:
                thumbnail_id = self.config.add_thumbnail(window_title=title, window_hwnd=hwnd)
                self.thumbnail_map[hwnd] = thumbnail_id
                self.engine.add_thumbnail(window_title=title, window_hwnd=hwnd)
                self._update_thumbnail_list()
                self.status_var.set(f"Added: {title}")
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
        """Add region to selected thumbnail"""
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
        
        try:
            image = self.window_manager.capture_window(hwnd)
            if not image:
                msgbox.showerror("Error", "Cannot capture window")
                return
            
            dialog = RegionEditorDialog(self.root, image)
            regions = dialog.show()
            
            if regions:
                for i, region in enumerate(regions):
                    x, y, w, h = region
                    region_dict = {
                        "name": f"Region_{i+1}",
                        "rect": [x, y, w, h],
                        "alert_threshold": 0.99,
                        "enabled": True
                    }
                    self.config.add_region_to_thumbnail(thumbnail_id, region_dict)
                    self.engine.add_region(thumbnail_id, f"Region_{i+1}", (x, y, w, h))
                
                self.status_var.set(f"Added {len(regions)} region(s) to {title}")
                self._update_thumbnail_list()
        except Exception as e:
            logger.error(f"Error adding region to '{title}': {str(e)}", exc_info=True)
            msgbox.showerror("Error", f"Failed to add region: {str(e)}")
    
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
        
        for thumbnail in thumbnails:
            title = thumbnail.get('window_title', 'Unknown')
            regions = thumbnail.get('monitored_regions', [])
            text = f"{title} ({len(regions)} regions)"
            self.thumbnail_list.insert(tk.END, text)
        
        count = len(thumbnails)
        self.list_label.config(text=f"Active Thumbnails ({count})")
    
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
