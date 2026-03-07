#!/usr/bin/env python3
"""
Tk GUI window picker for visible top-level windows.
Falls back to DWM thumbnail test after selection.

Usage: python tools/wgc_picker_gui.py
"""
import sys
import os
import json
import subprocess
try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    print('ERROR: tkinter is required to run the picker GUI.', file=sys.stderr)
    sys.exit(1)

try:
    import win32gui
except Exception as e:
    print('ERROR: pywin32 (win32gui) is required for the picker GUI.', file=sys.stderr)
    print('Exception:', e, file=sys.stderr)
    sys.exit(2)


def enum_windows():
    results = []

    def _enum(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and title.strip():
                results.append((hwnd, title))

    win32gui.EnumWindows(_enum, None)
    return results


class PickerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('ScreenAlert - Window Picker')
        self.geometry('640x400')
        self.resizable(True, True)

        self.list = tk.Listbox(self, activestyle='none')
        self.list.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=8, pady=(0,8))

        select_btn = tk.Button(btn_frame, text='Select', command=self.on_select)
        select_btn.pack(side=tk.RIGHT)

        refresh_btn = tk.Button(btn_frame, text='Refresh', command=self.populate)
        refresh_btn.pack(side=tk.RIGHT, padx=(0,8))

        self.populate()
        self.list.bind('<Double-Button-1>', lambda e: self.on_select())

    def populate(self):
        self.list.delete(0, tk.END)
        self.windows = enum_windows()
        for hwnd, title in self.windows:
            try:
                safe = title.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8')
            except Exception:
                safe = title
            self.list.insert(tk.END, safe)

    def on_select(self):
        sel = self.list.curselection()
        if not sel:
            return
        idx = sel[0]
        chosen = self.windows[idx][1]
        try:
            safe_chosen = chosen
        except Exception:
            safe_chosen = chosen

        summary = {'display_name': safe_chosen}
        out_path = os.path.join(os.getcwd(), 'wgc_picker_selection.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        print('Wrote selection to', out_path)
        # launch DWM thumbnail test to show the thumbnail of chosen window
        script = os.path.join(os.getcwd(), 'tools', 'dwm_thumbnail_test.py')
        subprocess.Popen([sys.executable, script, '--title', chosen])
        self.destroy()


if __name__ == '__main__':
    app = PickerApp()
    app.mainloop()
