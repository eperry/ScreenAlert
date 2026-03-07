"""Minimal Plugins dialog

Displays configured plugin names and their directories (read-only).
No editing, testing, or enable/disable controls.
"""
import tkinter as tk
from tkinter import ttk
from typing import Any

from screenalert_core.core.config_manager import ConfigManager


class PluginsDialog:
    def __init__(self, parent: tk.Tk, config: ConfigManager):
        self.parent = parent
        self.config = config
        self.top = tk.Toplevel(parent)
        self.top.title("Plugins")
        self.top.transient(parent)
        self.top.grab_set()
        self.top.geometry("480x220")
        self._build()
        self._populate()

    def _build(self) -> None:
        frame = ttk.Frame(self.top, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Configured Plugins", font=(None, 12, 'bold')).pack(anchor=tk.W)

        # Table with two columns: Plugin, Directory
        cols = ('plugin', 'directory')
        self.tree = ttk.Treeview(frame, columns=cols, show='headings', height=8)
        self.tree.heading('plugin', text='Plugin')
        self.tree.heading('directory', text='Directory')
        self.tree.column('plugin', width=160, anchor=tk.W)
        self.tree.column('directory', width=300, anchor=tk.W)
        vsb = ttk.Scrollbar(frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(8, 8))
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)

        close_btn = ttk.Button(btn_frame, text="Close", command=self._close)
        close_btn.pack(side=tk.RIGHT)

    def _populate(self) -> None:
        try:
            plugins = self.config.get_plugins_config() or {}
        except Exception:
            plugins = {}

        # clear
        for i in self.tree.get_children():
            self.tree.delete(i)
        if not plugins:
            self.tree.insert('', 'end', values=('(no plugins configured)', ''))
            return

        for name, cfg in plugins.items():
            path = ''
            if isinstance(cfg, dict):
                path = cfg.get('path', '')
            else:
                path = str(cfg)
            self.tree.insert('', 'end', values=(name, path))

    def _close(self) -> None:
        try:
            self.top.grab_release()
        finally:
            self.top.destroy()
