"""Main window UI for ScreenAlert v2"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox as msgbox
from typing import Optional

from screenalert_core.screening_engine import ScreenAlertEngine

logger = logging.getLogger(__name__)


class ScreenAlertMainWindow:
    """Main control window for ScreenAlert"""
    
    def __init__(self, engine: ScreenAlertEngine):
        """Initialize main window
        
        Args:
            engine: ScreenAlertEngine instance
        """
        self.engine = engine
        
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
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Main content
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Control panel
        control_frame = ttk.LabelFrame(main_frame, text="Control Panel", padding=10)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Buttons
        btn_add = ttk.Button(control_frame, text="Add Window", command=self._add_window)
        btn_add.pack(side=tk.LEFT, padx=5)
        
        btn_start = ttk.Button(control_frame, text="Start Monitoring", command=self._start_monitoring)
        btn_start.pack(side=tk.LEFT, padx=5)
        
        btn_pause = ttk.Button(control_frame, text="Pause All", command=self._pause_monitoring)
        btn_pause.pack(side=tk.LEFT, padx=5)
        
        # Thumbnail list
        list_frame = ttk.LabelFrame(main_frame, text="Active Thumbnails", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Listbox
        self.thumbnail_list = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        self.thumbnail_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.thumbnail_list.yview)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
    
    def _add_window(self) -> None:
        """Add window dialog"""
        msgbox.showinfo("Add Window", "Window selection UI coming soon")
    
    def _start_monitoring(self) -> None:
        """Start monitoring"""
        if self.engine.start():
            self.status_var.set("Monitoring active")
            msgbox.showinfo("Started", "Monitoring has been started")
        else:
            msgbox.showerror("Error", "Failed to start monitoring")
    
    def _pause_monitoring(self) -> None:
        """Pause monitoring"""
        self.engine.set_paused(True)
        self.status_var.set("Monitoring paused")
    
    def _show_settings(self) -> None:
        """Show settings dialog"""
        msgbox.showinfo("Settings", "Settings dialog coming soon")
    
    def _on_alert(self, thumbnail_id: str, region_id: str, region_name: str) -> None:
        """Alert callback"""
        self.status_var.set(f"ALERT: {region_name}")
        logger.info(f"Alert triggered: {region_name}")
    
    def _on_region_change(self, thumbnail_id: str, region_id: str) -> None:
        """Region change callback"""
        logger.debug(f"Region changed: {region_id}")
    
    def _on_window_lost(self, thumbnail_id: str, window_title: str) -> None:
        """Window lost callback"""
        logger.warning(f"Window lost: {window_title}")
        self.status_var.set(f"Window lost: {window_title}")
    
    def run(self) -> None:
        """Run main window"""
        self.root.mainloop()
