"""Per-region detection settings dialog.

Allows the user to choose a detection method for each region and tune
its parameters independently of the global settings.
"""

import tkinter as tk
from tkinter import ttk
import logging
from typing import Dict, Optional, Callable

from screenalert_core.core.change_detectors import VALID_METHODS

logger = logging.getLogger(__name__)

# Sentinel value for the "use global" dropdown entry
_USE_GLOBAL = "__global__"

# Dropdown display values: first entry is the global default, rest are methods
_DROPDOWN_VALUES = [
    "Default (Global Setting)",
    "SSIM (Structural Similarity)",
    "pHash (Perceptual Hash)",
    "Edge Detection (Canny)",
    "Background Subtraction (MOG2)",
]

# Map display label -> config value
_LABEL_TO_METHOD = {
    "Default (Global Setting)": _USE_GLOBAL,
    "SSIM (Structural Similarity)": "ssim",
    "pHash (Perceptual Hash)": "phash",
    "Edge Detection (Canny)": "edge_only",
    "Background Subtraction (MOG2)": "background_subtraction",
}

# Reverse map
_METHOD_TO_LABEL = {v: k for k, v in _LABEL_TO_METHOD.items()}


class RegionDetectionDialog:
    """Dialog for editing detection method and parameters on a single region."""

    def __init__(self, parent: tk.Widget, region_config: Dict,
                 global_config: Optional[Dict] = None,
                 on_apply: Optional[Callable[[Dict], None]] = None):
        self.region_config = region_config
        self.global_config = global_config or {}
        self.on_apply = on_apply
        self.result: Optional[Dict] = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Detection Settings — {region_config.get('name', 'Region')}")
        self.dialog.geometry("540x520")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._build_ui()
        self._load_values()
        self._on_method_changed()  # show/hide param frames

    # ── UI ────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        main = ttk.Frame(self.dialog, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        # Method selector
        method_frame = ttk.LabelFrame(main, text="Detection Method", padding=10)
        method_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(method_frame, text="Method:").grid(row=0, column=0, sticky="w")
        self.method_var = tk.StringVar()
        combo = ttk.Combobox(
            method_frame, textvariable=self.method_var,
            values=_DROPDOWN_VALUES, state="readonly", width=32,
            style="App.TCombobox",
        )
        combo.grid(row=0, column=1, sticky="w", padx=10)
        combo.bind("<<ComboboxSelected>>", lambda _: self._on_method_changed())

        # SSIM / pHash params
        self.ssim_frame = ttk.LabelFrame(main, text="SSIM / pHash Parameters", padding=10)
        self.ssim_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(self.ssim_frame, text="Similarity Threshold:").grid(row=0, column=0, sticky="w")
        self.threshold_var = tk.DoubleVar(value=0.99)
        ttk.Spinbox(self.ssim_frame, from_=0.10, to=1.0, increment=0.01,
                    textvariable=self.threshold_var, width=8).grid(row=0, column=1, sticky="w", padx=10)
        ttk.Label(self.ssim_frame, text="(lower = less sensitive)", foreground="gray").grid(row=0, column=2, sticky="w")
        ttk.Label(self.ssim_frame,
                  text="How similar two frames must be to count as 'no change'.\n"
                       "0.99 = very sensitive (tiny changes trigger). 0.90 = only major changes trigger.",
                  foreground="gray", wraplength=460, justify="left").grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))

        # Edge params
        self.edge_frame = ttk.LabelFrame(main, text="Edge Detection Parameters", padding=10)
        self.edge_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(self.edge_frame, text="Min Edge Change %:").grid(row=0, column=0, sticky="w")
        self.edge_fraction_var = tk.DoubleVar(value=0.3)
        ttk.Spinbox(self.edge_frame, from_=0.0, to=5.0, increment=0.1, format="%.1f",
                    textvariable=self.edge_fraction_var, width=8).grid(row=0, column=1, sticky="w", padx=10)
        ttk.Label(self.edge_frame, text="(0 = any change; higher = less sensitive)",
                  foreground="gray").grid(row=0, column=2, sticky="w")

        ttk.Label(self.edge_frame, text="Canny Low:").grid(row=1, column=0, sticky="w")
        self.canny_low_var = tk.IntVar(value=40)
        ttk.Spinbox(self.edge_frame, from_=1, to=500, increment=5,
                    textvariable=self.canny_low_var, width=8).grid(row=1, column=1, sticky="w", padx=10)
        ttk.Label(self.edge_frame, text="(lower = more edges detected)",
                  foreground="gray").grid(row=1, column=2, sticky="w")

        ttk.Label(self.edge_frame, text="Canny High:").grid(row=2, column=0, sticky="w")
        self.canny_high_var = tk.IntVar(value=120)
        ttk.Spinbox(self.edge_frame, from_=1, to=500, increment=10,
                    textvariable=self.canny_high_var, width=8).grid(row=2, column=1, sticky="w", padx=10)
        ttk.Label(self.edge_frame, text="(higher = fewer, stronger edges only)",
                  foreground="gray").grid(row=2, column=2, sticky="w")

        ttk.Label(self.edge_frame, text="Binarize (B&W):").grid(row=3, column=0, sticky="w")
        self.binarize_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.edge_frame, variable=self.binarize_var, style="App.TCheckbutton").grid(row=3, column=1, sticky="w", padx=10)
        ttk.Label(self.edge_frame, text="(removes gradients; keeps text & UI only)",
                  foreground="gray").grid(row=3, column=2, sticky="w")
        ttk.Label(self.edge_frame,
                  text="Detects changes by comparing edge outlines between frames.\n"
                       "Good for UI-heavy windows where you care about structural changes, not color shifts.",
                  foreground="gray", wraplength=460, justify="left").grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))

        # MOG2 params
        self.bg_frame = ttk.LabelFrame(main, text="Background Subtraction Parameters", padding=10)
        self.bg_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(self.bg_frame, text="History (frames):").grid(row=0, column=0, sticky="w")
        self.bg_history_var = tk.IntVar(value=500)
        ttk.Spinbox(self.bg_frame, from_=10, to=5000, increment=50,
                    textvariable=self.bg_history_var, width=8).grid(row=0, column=1, sticky="w", padx=10)
        ttk.Label(self.bg_frame, text="(how many frames the model remembers)",
                  foreground="gray").grid(row=0, column=2, sticky="w")

        ttk.Label(self.bg_frame, text="Variance Threshold:").grid(row=1, column=0, sticky="w")
        self.bg_var_var = tk.DoubleVar(value=16.0)
        ttk.Spinbox(self.bg_frame, from_=1.0, to=100.0, increment=1.0, format="%.1f",
                    textvariable=self.bg_var_var, width=8).grid(row=1, column=1, sticky="w", padx=10)
        ttk.Label(self.bg_frame, text="(higher = less sensitive to small changes)",
                  foreground="gray").grid(row=1, column=2, sticky="w")

        ttk.Label(self.bg_frame, text="Min FG Change %:").grid(row=2, column=0, sticky="w")
        self.bg_fg_var = tk.DoubleVar(value=0.3)
        ttk.Spinbox(self.bg_frame, from_=0.0, to=20.0, increment=0.1, format="%.1f",
                    textvariable=self.bg_fg_var, width=8).grid(row=2, column=1, sticky="w", padx=10)
        ttk.Label(self.bg_frame, text="(% of foreground pixels to trigger alert)",
                  foreground="gray").grid(row=2, column=2, sticky="w")

        ttk.Label(self.bg_frame, text="Warmup Frames:").grid(row=3, column=0, sticky="w")
        self.bg_warmup_var = tk.IntVar(value=30)
        ttk.Spinbox(self.bg_frame, from_=0, to=500, increment=5,
                    textvariable=self.bg_warmup_var, width=8).grid(row=3, column=1, sticky="w", padx=10)
        ttk.Label(self.bg_frame, text="(frames before detection starts; 0 if warmup file exists)",
                  foreground="gray").grid(row=3, column=2, sticky="w")
        ttk.Label(self.bg_frame,
                  text="Learns what the 'normal' background looks like, then alerts on new foreground activity.\n"
                       "Best for scenes with a stable background where you want to detect new objects or movement.",
                  foreground="gray", wraplength=460, justify="left").grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Apply", command=self._on_apply_btn).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    # ── Load / Save ───────────────────────────────────────────────────

    def _selected_method(self) -> str:
        """Return the raw method string for the current dropdown selection."""
        label = self.method_var.get()
        return _LABEL_TO_METHOD.get(label, _USE_GLOBAL)

    def _load_values(self) -> None:
        """Populate fields from region config, falling back to global."""
        gcfg = self.global_config
        rcfg = self.region_config

        has_override = "detection_method" in rcfg and rcfg["detection_method"]
        if has_override:
            method = rcfg["detection_method"]
            if method not in VALID_METHODS:
                method = _USE_GLOBAL
        else:
            method = _USE_GLOBAL

        label = _METHOD_TO_LABEL.get(method, _DROPDOWN_VALUES[0])
        self.method_var.set(label)

        # SSIM / pHash
        self.threshold_var.set(rcfg.get("alert_threshold",
                                        gcfg.get("default_alert_threshold", 0.99)))

        # Edge
        self.edge_fraction_var.set(round(
            rcfg.get("min_edge_fraction", gcfg.get("min_edge_fraction", 0.003)) * 100, 3
        ))
        self.canny_low_var.set(rcfg.get("canny_low", gcfg.get("canny_low", 40)))
        self.canny_high_var.set(rcfg.get("canny_high", gcfg.get("canny_high", 120)))
        self.binarize_var.set(rcfg.get("edge_binarize", gcfg.get("edge_binarize", False)))

        # MOG2
        self.bg_history_var.set(rcfg.get("bg_history", gcfg.get("bg_history", 500)))
        self.bg_var_var.set(rcfg.get("bg_var_threshold", gcfg.get("bg_var_threshold", 16.0)))
        self.bg_fg_var.set(round(
            rcfg.get("bg_min_fg_fraction", gcfg.get("bg_min_fg_fraction", 0.003)) * 100, 3
        ))
        self.bg_warmup_var.set(rcfg.get("bg_warmup_frames", gcfg.get("bg_warmup_frames", 30)))

    def _collect_updates(self) -> Dict:
        """Gather detection settings from UI into a dict suitable for region config update."""
        updates: Dict = {}
        method = self._selected_method()

        if method == _USE_GLOBAL:
            # Clear region override — detector will fall back to global
            updates["detection_method"] = ""
        else:
            updates["detection_method"] = method

            if method in ("ssim", "phash"):
                updates["alert_threshold"] = self.threshold_var.get()
            elif method == "edge_only":
                updates["min_edge_fraction"] = self.edge_fraction_var.get() / 100.0
                updates["canny_low"] = self.canny_low_var.get()
                updates["canny_high"] = self.canny_high_var.get()
                updates["edge_binarize"] = self.binarize_var.get()
            elif method == "background_subtraction":
                updates["bg_history"] = self.bg_history_var.get()
                updates["bg_var_threshold"] = self.bg_var_var.get()
                updates["bg_min_fg_fraction"] = self.bg_fg_var.get() / 100.0
                updates["bg_warmup_frames"] = self.bg_warmup_var.get()

        return updates

    # ── Visibility ────────────────────────────────────────────────────

    def _on_method_changed(self) -> None:
        method = self._selected_method()
        self._repack_all()

        # Disable param fields when using global default
        is_global = (method == _USE_GLOBAL)
        state = "disabled" if is_global else "normal"
        for frame in (self.ssim_frame, self.edge_frame, self.bg_frame):
            for w in frame.winfo_children():
                try:
                    if isinstance(w, (ttk.Spinbox, ttk.Checkbutton)):
                        w.configure(state=state)
                except tk.TclError:
                    pass

    def _repack_all(self) -> None:
        """Re-pack param frames in order after method change."""
        method = self._selected_method()

        # Forget all param frames
        self.ssim_frame.pack_forget()
        self.edge_frame.pack_forget()
        self.bg_frame.pack_forget()

        # When global is selected, show the frame matching the global method
        # (disabled) so the user can see what they'll get.
        if method == _USE_GLOBAL:
            method = self.global_config.get("change_detection_method", "ssim")

        # Pack the appropriate one
        if method in ("ssim", "phash"):
            self.ssim_frame.pack(fill=tk.X, pady=(0, 8))
        elif method == "edge_only":
            self.edge_frame.pack(fill=tk.X, pady=(0, 8))
        elif method == "background_subtraction":
            self.bg_frame.pack(fill=tk.X, pady=(0, 8))

    # ── Actions ───────────────────────────────────────────────────────

    def _on_apply_btn(self) -> None:
        updates = self._collect_updates()
        self.result = updates
        if self.on_apply:
            self.on_apply(updates)

    def _on_ok(self) -> None:
        self._on_apply_btn()
        self.dialog.destroy()

    def show(self) -> Optional[Dict]:
        self.dialog.wait_window()
        return self.result
