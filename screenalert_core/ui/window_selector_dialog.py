"""Window selector dialog for choosing monitored windows"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from typing import Optional, List, Dict

from screenalert_core.core.window_manager import WindowManager
from screenalert_core.core.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class WindowSelectorDialog:
    """Dialog for selecting a window to monitor"""
    
    def __init__(self, parent: tk.Widget, window_manager: WindowManager,
                 config_manager: Optional[ConfigManager] = None):
        """Initialize window selector dialog
        
        Args:
            parent: Parent window
            window_manager: WindowManager instance
            config_manager: Config manager for persisting filter state
        """
        self.window_manager = window_manager
        self.config = config_manager
        self.selected_window: Optional[Dict] = None
        self.windows: List[Dict] = []  # Initialize windows list BEFORE UI
        
        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Window to Monitor")
        self.dialog.geometry("700x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
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
        

        # Filter/search entry
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT)
        initial_filter = self.config.get_last_window_filter() if self.config else ""
        initial_size_op = self.config.get_last_window_size_filter_op() if self.config else "=="
        initial_size_value = self.config.get_last_window_size_filter_value() if self.config else ""
        self.filter_var = tk.StringVar(value=initial_filter)
        filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_var)
        filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        filter_entry.bind('<KeyRelease>', self._on_filter_change)

        size_filter_frame = ttk.Frame(main_frame)
        size_filter_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(size_filter_frame, text="Size:").pack(side=tk.LEFT)
        self.size_op_var = tk.StringVar(value=initial_size_op if initial_size_op in ("==", "<=", ">=") else "==")
        self.size_op_combo = ttk.Combobox(
            size_filter_frame,
            textvariable=self.size_op_var,
            values=["==", "<=", ">="],
            width=4,
            state="readonly"
        )
        self.size_op_combo.pack(side=tk.LEFT, padx=(5, 4))
        self.size_op_combo.bind("<<ComboboxSelected>>", self._on_filter_change)
        self.size_value_var = tk.StringVar(value=initial_size_value)
        size_entry = ttk.Entry(size_filter_frame, textvariable=self.size_value_var, width=14)
        size_entry.pack(side=tk.LEFT)
        size_entry.bind('<KeyRelease>', self._on_filter_change)
        ttk.Label(size_filter_frame, text="(e.g., 1920x1080; compares width and height)").pack(side=tk.LEFT, padx=(6, 0))

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
        
        # Button frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)

        button_style = {
            "bg": "#222b3a",
            "fg": "#e0e0e0",
            "activebackground": "#00bfff",
            "activeforeground": "#181a20",
            "relief": tk.RIDGE,
            "bd": 1,
            "padx": 12,
            "pady": 4,
        }

        tk.Button(btn_frame, text="Select", command=self._on_select, **button_style).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Refresh", command=self._load_windows, **button_style).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=self._on_cancel, **button_style).pack(side=tk.RIGHT, padx=5)
        
        # Bind selection change
        self.listbox.bind("<<ListboxSelect>>", self._on_selection_changed)
    
    def _load_windows(self) -> None:
        """Load and display available windows"""
        try:
            windows = self.window_manager.get_window_list(use_cache=False)
            self.windows = windows
            self._update_listbox()
            logger.info(f"Loaded {len(windows)} windows")
        except Exception as e:
            logger.error(f"Error loading windows: {e}")
            messagebox.showerror("Error", f"Failed to load windows: {e}")

    def _update_listbox(self):
        """Update listbox based on filter"""
        filter_text = self.filter_var.get().lower() if hasattr(self, 'filter_var') else ''
        size_target = self._parse_size_filter()
        size_op = self.size_op_var.get() if hasattr(self, 'size_op_var') else "=="
        self.listbox.delete(0, tk.END)
        self._filtered_rows = []
        for window in self.windows:
            title = window["title"]
            if filter_text and filter_text not in title.lower():
                continue
            if not self._matches_size_filter(window.get("size"), size_target, size_op):
                continue

            display_title = title if len(title) <= 80 else title[:77] + "..."
            self.listbox.insert(tk.END, display_title)
            self._filtered_rows.append(("title", window))
            self.listbox.insert(tk.END, f"    Size: {window['size'][0]}x{window['size'][1]}")
            self._filtered_rows.append(("size", window))
        if self._filtered_rows:
            self.listbox.selection_set(0)
            self._on_selection_changed(None)
        else:
            self.selected_window = None

    def _on_filter_change(self, event):
        self._save_filter_state()
        self._update_listbox()

    def _save_filter_state(self) -> None:
        """Persist filter state to config."""
        if not self.config:
            return
        self.config.set_last_window_filter(self.filter_var.get())
        self.config.set_last_window_size_filter_op(self.size_op_var.get())
        self.config.set_last_window_size_filter_value(self.size_value_var.get())
        self.config.save()

    def _on_cancel(self) -> None:
        """Handle cancel/close."""
        self._save_filter_state()
        self.dialog.destroy()

    def _parse_size_filter(self) -> Optional[tuple]:
        """Parse size filter text like 1920x1080 into (width, height)."""
        raw = self.size_value_var.get().strip() if hasattr(self, 'size_value_var') else ""
        if not raw:
            return None
        normalized = raw.lower().replace(" ", "").replace("*", "x")
        if "x" not in normalized:
            return None
        parts = normalized.split("x", 1)
        try:
            width = int(parts[0])
            height = int(parts[1])
            if width <= 0 or height <= 0:
                return None
            return (width, height)
        except (TypeError, ValueError):
            return None

    def _matches_size_filter(self, size: Optional[tuple], target: Optional[tuple], op: str) -> bool:
        """Return True if window size matches size filter criteria."""
        if target is None:
            return True
        if not size or len(size) != 2:
            return False
        w, h = size
        tw, th = target
        if op == "<=":
            return w <= tw and h <= th
        if op == ">=":
            return w >= tw and h >= th
        return w == tw and h == th
    
    def _on_selection_changed(self, event) -> None:
        """Handle window selection change"""
        selection = self.listbox.curselection()
        if not selection or not hasattr(self, '_filtered_rows') or not self._filtered_rows:
            return
        selected_idx = selection[0]
        row_type, window = self._filtered_rows[selected_idx]
        if row_type == "size" and selected_idx > 0:
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(selected_idx - 1)
            self.listbox.activate(selected_idx - 1)
            selected_idx = selected_idx - 1
            _, window = self._filtered_rows[selected_idx]
        self.selected_window = window
    
    def _on_select(self) -> None:
        """Handle select button"""
        selection = self.listbox.curselection()
        if selection and hasattr(self, '_filtered_rows') and self._filtered_rows:
            _, self.selected_window = self._filtered_rows[selection[0]]

        if not self.selected_window:
            messagebox.showwarning("Select Window", "Please select a window first")
            return
        
        self._save_filter_state()
        self.result = self.selected_window
        self.dialog.destroy()
    
    def show(self) -> Optional[Dict]:
        """Show dialog and return selected window
        
        Returns:
            Selected window dict or None if cancelled
        """
        self.dialog.wait_window()
        return self.result
