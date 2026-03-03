"""Window selector dialog for choosing monitored windows"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from typing import Optional, List, Dict

from screenalert_core.core.window_manager import WindowManager
from screenalert_core.core.config_manager import ConfigManager
from screenalert_core.ui.auto_hide_scrollbar import AutoHideScrollbar

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
        self.selected_windows: List[Dict] = []
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
        self.size_op_menu = tk.OptionMenu(
            size_filter_frame,
            self.size_op_var,
            "==",
            "<=",
            ">=",
            command=self._on_size_op_change,
        )
        self.size_op_menu.pack(side=tk.LEFT, padx=(5, 4))
        self.size_value_var = tk.StringVar(value=initial_size_value)
        size_entry = ttk.Entry(size_filter_frame, textvariable=self.size_value_var, width=14)
        size_entry.pack(side=tk.LEFT)
        size_entry.bind('<KeyRelease>', self._on_filter_change)
        ttk.Label(size_filter_frame, text="(e.g., 1920x1080 or 1920; width-only is supported)").pack(side=tk.LEFT, padx=(6, 0))

        # Window list frame
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Scrollbar
        self.list_scrollbar = AutoHideScrollbar(list_frame, orient=tk.VERTICAL)
        self.list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Listbox
        self.listbox = tk.Listbox(list_frame, yscrollcommand=self.list_scrollbar.set,
                     font=("Segoe UI", 10), height=15, selectmode=tk.EXTENDED)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind("<Double-Button-1>", lambda e: self._on_select())
        self.list_scrollbar.config(command=self.listbox.yview)
        self.dialog.after_idle(lambda: self.list_scrollbar.set(*self.listbox.yview()))
        
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
            size = window.get("size")
            if isinstance(size, (list, tuple)) and len(size) == 2:
                self.listbox.insert(tk.END, f"{display_title} ({size[0]}x{size[1]})")
            else:
                self.listbox.insert(tk.END, display_title)
            self._filtered_rows.append(window)
        self.list_scrollbar.set(*self.listbox.yview())
        if self._filtered_rows:
            self.listbox.selection_set(0)
            self._on_selection_changed(None)
        else:
            self.selected_window = None
            self.selected_windows = []

    def _on_filter_change(self, event):
        self._save_filter_state()
        self._update_listbox()

    def _on_size_op_change(self, _selected: str) -> None:
        self._on_filter_change(None)

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
        """Parse size filter text into (width, height|None).

        Supported formats:
        - WIDTHxHEIGHT (e.g. 1920x1080)
        - WIDTH only (e.g. 1920)
        """
        raw = self.size_value_var.get().strip() if hasattr(self, 'size_value_var') else ""
        if not raw:
            return None
        normalized = raw.lower().replace(" ", "").replace("*", "x")
        if "x" not in normalized:
            try:
                width_only = int(normalized)
                if width_only <= 0:
                    return None
                return (width_only, None)
            except (TypeError, ValueError):
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

        # Width-only filtering (input like "1920")
        if th is None:
            if op == "<=":
                return w <= tw
            if op == ">=":
                return w >= tw
            return w == tw

        if op == "<=":
            return w <= tw and h <= th
        if op == ">=":
            return w >= tw and h >= th
        return w == tw and h == th
    
    def _on_selection_changed(self, event) -> None:
        """Handle window selection change"""
        selection = self.listbox.curselection()
        if not selection or not hasattr(self, '_filtered_rows') or not self._filtered_rows:
            self.selected_window = None
            self.selected_windows = []
            return
        selected: List[Dict] = []
        seen_ids = set()
        for idx in selection:
            if idx < 0 or idx >= len(self._filtered_rows):
                continue
            window = self._filtered_rows[idx]
            window_id = window.get("hwnd")
            if window_id in seen_ids:
                continue
            seen_ids.add(window_id)
            selected.append(window)

        self.selected_windows = selected
        self.selected_window = selected[0] if selected else None
    
    def _on_select(self) -> None:
        """Handle select button"""
        selection = self.listbox.curselection()
        if selection and hasattr(self, '_filtered_rows') and self._filtered_rows:
            self._on_selection_changed(None)

        if not self.selected_windows:
            messagebox.showwarning("Select Window", "Please select one or more windows first")
            return
        
        self._save_filter_state()
        self.result = self.selected_windows
        self.dialog.destroy()
    
    def show(self) -> Optional[List[Dict]]:
        """Show dialog and return selected windows
        
        Returns:
            Selected windows list or None if cancelled
        """
        self.dialog.wait_window()
        return self.result
