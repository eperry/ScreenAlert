"""Window selector dialog for choosing monitored windows"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from typing import Optional, List, Dict

from screenalert_core.core.window_manager import WindowManager

logger = logging.getLogger(__name__)


class WindowSelectorDialog:
    """Dialog for selecting a window to monitor"""
    
    def __init__(self, parent: tk.Widget, window_manager: WindowManager):
        """Initialize window selector dialog
        
        Args:
            parent: Parent window
            window_manager: WindowManager instance
        """
        self.window_manager = window_manager
        self.selected_window: Optional[Dict] = None
        self.windows: List[Dict] = []  # Initialize windows list BEFORE UI
        
        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Window to Monitor")
        self.dialog.geometry("700x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Make it modal
        self.result = None
        
        self._build_ui()
        self._load_windows()
    
    def _build_ui(self) -> None:
        """Build dialog UI"""
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main_frame, text="Available Windows:", 
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 10))
        
        # Window list frame
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Listbox
        self.listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, 
                                 font=("Segoe UI", 10), height=15)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind("<Double-Button-1>", lambda e: self._on_select())
        scrollbar.config(command=self.listbox.yview)
        
        # Window details frame
        details_frame = ttk.LabelFrame(main_frame, text="Window Details", padding=10)
        details_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(details_frame, text="Title:").grid(row=0, column=0, sticky="w")
        self.title_var = tk.StringVar(value="")
        ttk.Label(details_frame, textvariable=self.title_var, 
                 relief=tk.SUNKEN).grid(row=0, column=1, sticky="ew", padx=5)
        
        ttk.Label(details_frame, text="Class:").grid(row=1, column=0, sticky="w")
        self.class_var = tk.StringVar(value="")
        ttk.Label(details_frame, textvariable=self.class_var, 
                 relief=tk.SUNKEN).grid(row=1, column=1, sticky="ew", padx=5)
        
        ttk.Label(details_frame, text="Size:").grid(row=2, column=0, sticky="w")
        self.size_var = tk.StringVar(value="")
        ttk.Label(details_frame, textvariable=self.size_var, 
                 relief=tk.SUNKEN).grid(row=2, column=1, sticky="ew", padx=5)
        
        details_frame.columnconfigure(1, weight=1)
        
        # Button frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="Select", command=self._on_select).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_windows).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Bind selection change
        self.listbox.bind("<<ListboxSelect>>", self._on_selection_changed)
    
    def _load_windows(self) -> None:
        """Load and display available windows"""
        try:
            windows = self.window_manager.get_window_list(use_cache=False)
            
            self.listbox.delete(0, tk.END)
            self.windows = windows
            
            for window in windows:
                title = window["title"]
                if len(title) > 80:
                    title = title[:77] + "..."
                self.listbox.insert(tk.END, title)
            
            if windows:
                self.listbox.selection_set(0)
                self._on_selection_changed(None)
            
            logger.info(f"Loaded {len(windows)} windows")
        
        except Exception as e:
            logger.error(f"Error loading windows: {e}")
            messagebox.showerror("Error", f"Failed to load windows: {e}")
    
    def _on_selection_changed(self, event) -> None:
        """Handle window selection change"""
        selection = self.listbox.curselection()
        if not selection:
            return
        
        window = self.windows[selection[0]]
        self.title_var.set(window["title"])
        self.class_var.set(window["class"])
        self.size_var.set(f"{window['size'][0]}x{window['size'][1]}")
        self.selected_window = window
    
    def _on_select(self) -> None:
        """Handle select button"""
        if not self.selected_window:
            messagebox.showwarning("Select Window", "Please select a window first")
            return
        
        self.result = self.selected_window
        self.dialog.destroy()
    
    def show(self) -> Optional[Dict]:
        """Show dialog and return selected window
        
        Returns:
            Selected window dict or None if cancelled
        """
        self.dialog.wait_window()
        return self.result
