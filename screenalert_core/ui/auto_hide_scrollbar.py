"""Auto-hiding ttk scrollbar widget."""

import tkinter as tk
from tkinter import ttk


class AutoHideScrollbar(ttk.Scrollbar):
    """Scrollbar that hides itself when content fully fits in view."""

    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self._is_visible = True
        self._layout_manager = None
        self._layout_options = None

    def set(self, first, last):
        """Show scrollbar only when scrolling is needed."""
        try:
            first_float = float(first)
            last_float = float(last)
            needs_scroll = first_float > 0.0 or last_float < 1.0
        except (TypeError, ValueError):
            needs_scroll = True

        if needs_scroll:
            self._show()
        else:
            self._hide()

        super().set(first, last)

    def _hide(self) -> None:
        if not self._is_visible:
            return

        manager = self.winfo_manager()
        if manager == "pack":
            self._layout_manager = "pack"
            self._layout_options = dict(self.pack_info())
            self._layout_options.pop("in", None)
            self.pack_forget()
            self._is_visible = False
        elif manager == "grid":
            self._layout_manager = "grid"
            self._layout_options = dict(self.grid_info())
            self._layout_options.pop("in", None)
            self.grid_remove()
            self._is_visible = False

    def _show(self) -> None:
        if self._is_visible:
            return
        if not self._layout_manager:
            return

        if self._layout_manager == "pack":
            self.pack(**(self._layout_options or {}))
            self._is_visible = True
        elif self._layout_manager == "grid":
            self.grid()
            if self._layout_options:
                self.grid_configure(**self._layout_options)
            self._is_visible = True
