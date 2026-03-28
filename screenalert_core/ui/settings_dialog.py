"""Settings dialog for ScreenAlert configuration.

Regedit-style layout:
  - Left pane: tree of setting categories
  - Right pane: table of settings (Name | Value | Description)
  - Double-click a row to edit via a type-appropriate dialog
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
from typing import Optional, Dict, Callable, List, Any, Tuple

from screenalert_core.core.config_manager import ConfigManager
from screenalert_core.utils.constants import (
    DEFAULT_REFRESH_RATE_MS, DEFAULT_OPACITY
)

logger = logging.getLogger(__name__)


# ── Setting metadata ──────────────────────────────────────────────────
# Each setting: (key, display_name, type, description, extra)
#   type: "bool", "int", "float", "string", "choice", "file", "dir"
#   extra: dict with type-specific info (min, max, increment, choices, filetypes)

# Tree structure: (id, label, parent_id_or_None, settings_list)
# parent_id=None means root node.  Nodes with children can also have settings.
_CATEGORIES: List[Tuple[str, str, Optional[str], List[dict]]] = [
    ("monitoring", "Monitoring", None, [
        {
            "key": "refresh_rate", "name": "Refresh Rate (ms)", "type": "int",
            "desc": "How often each window is captured and checked for changes. "
                    "Lower = faster detection but more CPU. 300ms is fastest, 1000ms is a good default.",
            "min": 300, "max": 5000, "increment": 100,
        },
        {
            "key": "pause_reminder_interval_sec", "name": "Pause Reminder (sec)", "type": "int",
            "desc": "When a region is paused, flash a reminder after this many seconds "
                    "so you don't forget to unpause.",
            "min": 10, "max": 3600, "increment": 10,
        },
    ]),
    ("detection", "Detection", None, [
        {
            "key": "change_detection_method", "name": "Detection Method", "type": "choice",
            "desc": "The global default algorithm used to detect changes between frames. "
                    "Individual regions can override this via their Detect button.\n\n"
                    "ssim = Structural Similarity (accurate, compares luminance/contrast/structure)\n"
                    "phash = Perceptual Hash (faster, compares visual fingerprints)\n"
                    "edge_only = Canny Edge diff (compares outlines; ignores color/gradient shifts)\n"
                    "background_subtraction = MOG2 (learns background over time; detects new foreground)",
            "choices": ["ssim", "phash", "edge_only", "background_subtraction"],
        },
        {
            "key": "alert_threshold", "name": "Alert Threshold (SSIM/pHash)", "type": "float",
            "desc": "Used by SSIM and pHash methods. How similar two frames must be to count as "
                    "'no change'. 0.99 = very sensitive (tiny pixel shifts trigger). "
                    "0.90 = only significant visual changes trigger.",
            "min": 0.10, "max": 1.0, "increment": 0.01, "format": "%.2f",
        },
    ]),
    ("detection_edge", "Edge", "detection", [
        {
            "key": "min_edge_fraction", "name": "Min Edge Change %", "type": "float",
            "desc": "Minimum percentage of edge pixels that must differ between frames to trigger an alert. "
                    "0 = any edge change triggers. Higher = less sensitive. "
                    "For windows with animated backgrounds, try 1.5-4.0%.",
            "min": 0.0, "max": 10.0, "increment": 0.1, "format": "%.1f",
            "scale": 100,  # stored as fraction, displayed as %
        },
        {
            "key": "canny_low", "name": "Canny Low Threshold", "type": "int",
            "desc": "Lower boundary for Canny edge detection hysteresis. "
                    "Lower values detect more/weaker edges. Default 40.",
            "min": 1, "max": 500, "increment": 5,
        },
        {
            "key": "canny_high", "name": "Canny High Threshold", "type": "int",
            "desc": "Upper boundary for Canny hysteresis. Only strong gradients above this "
                    "value are kept as definite edges. Default 120.",
            "min": 1, "max": 500, "increment": 10,
        },
        {
            "key": "edge_binarize", "name": "Binarize (B&W)", "type": "bool",
            "desc": "Converts the image to pure black & white using adaptive thresholding before "
                    "edge detection. Strips smooth gradients and animated backgrounds "
                    "while preserving text and UI outlines. Recommended ON for game UIs "
                    "with animated backgrounds.",
        },
    ]),
    ("detection_bg", "Background Sub.", "detection", [
        {
            "key": "bg_history", "name": "History (frames)", "type": "int",
            "desc": "Number of recent frames the background model considers. Higher = slower "
                    "adaptation to gradual changes. Lower = faster adaptation but more false "
                    "positives from slow animations.",
            "min": 10, "max": 5000, "increment": 50,
        },
        {
            "key": "bg_var_threshold", "name": "Variance Threshold", "type": "float",
            "desc": "How much a pixel's brightness can vary before it's classified as 'foreground'. "
                    "Higher = more tolerant of noise/flickering. Default 16. "
                    "Increase to 30-50 for noisy or animated scenes.",
            "min": 1.0, "max": 100.0, "increment": 1.0, "format": "%.1f",
        },
        {
            "key": "bg_min_fg_fraction", "name": "Min FG Change %", "type": "float",
            "desc": "Minimum percentage of pixels that must be classified as foreground to trigger "
                    "an alert. Filters out small scattered noise. 0.3% is sensitive; increase to "
                    "1-5% for noisy scenes.",
            "min": 0.0, "max": 20.0, "increment": 0.1, "format": "%.1f",
            "scale": 100,
        },
        {
            "key": "bg_warmup_frames", "name": "Warmup Frames", "type": "int",
            "desc": "Number of frames to observe silently before detection starts, allowing the "
                    "model to learn the baseline. Set to 0 if a saved warmup file exists from a "
                    "previous session.",
            "min": 0, "max": 500, "increment": 5,
        },
    ]),
    ("appearance", "Appearance", None, [
        {
            "key": "theme_preset", "name": "Theme", "type": "choice",
            "desc": "Color theme for the main window and overlays. Changes apply as a live preview.",
            "choices": ["default", "slate", "midnight", "high-contrast"],
        },
        {
            "key": "opacity", "name": "Thumbnail Opacity", "type": "float",
            "desc": "Transparency of the floating thumbnail overlays. "
                    "0.2 = nearly invisible, 1.0 = fully opaque.",
            "min": 0.2, "max": 1.0, "increment": 0.05, "format": "%.2f",
        },
        {
            "key": "always_on_top", "name": "Always on Top", "type": "bool",
            "desc": "Keep thumbnail overlays above all other windows. "
                    "Disable if they interfere with fullscreen apps.",
        },
        {
            "key": "show_borders", "name": "Show Borders", "type": "bool",
            "desc": "Draw a colored border around each thumbnail overlay. "
                    "The border color reflects the region's alert state (green/red/orange).",
        },
        {
            "key": "show_overlay_when_unavailable", "name": "Show Overlay if Unavailable", "type": "bool",
            "desc": "Keep showing the thumbnail overlay even when the monitored window is closed or not found. "
                    "When off, overlays auto-hide for missing windows.",
        },
        {
            "key": "overlay_update_rate_hz", "name": "Overlay Update Rate (Hz)", "type": "int",
            "desc": "How often overlay properties (size, position, opacity) are synced. "
                    "Does not affect visual smoothness — DWM thumbnails are always composited "
                    "at display refresh rate. Higher values = faster response to changes.",
            "min": 10, "max": 60, "increment": 5,
        },
        {
            "key": "auto_discovery_enabled", "name": "Auto-Discover Windows", "type": "bool",
            "desc": "Periodically scan for disconnected windows and automatically reconnect them. "
                    "Runs on a lightweight background thread, separate from the main monitoring loop.",
        },
        {
            "key": "auto_discovery_interval_sec", "name": "Auto-Discovery Interval (sec)", "type": "int",
            "desc": "How often (in seconds) to search for disconnected windows. "
                    "Lower values find windows faster but use slightly more CPU.",
            "min": 10, "max": 300, "increment": 10,
        },
        {
            "key": "overlay_scaling_mode", "name": "Overlay Scaling", "type": "choice",
            "desc": "How the overlay resizes and displays the source window.\n\n"
                    "Fit = Aspect ratio locked. Resizing adjusts both axes together "
                    "to match the source window proportions. No black bars.\n"
                    "Stretch = Free-form resize. The thumbnail stretches to fill "
                    "whatever shape you drag the overlay to. May distort.\n"
                    "Letterbox = Free-form resize but the thumbnail keeps its "
                    "aspect ratio inside, with black bars filling the gap.",
            "choices": ["fit", "stretch", "letterbox"],
        },
        {
            "key": "show_overlay_on_connect", "name": "Show Overlay on Connect", "type": "bool",
            "desc": "Automatically show the overlay window when a monitored application is "
                    "discovered or reconnected. When off, overlays stay hidden until manually enabled.",
        },
    ]),
    ("alerts", "Alerts", None, [
        {
            "key": "enable_sound", "name": "Enable Sound", "type": "bool",
            "desc": "Play an audio file when a change is detected. "
                    "Requires a sound file to be configured below.",
        },
        {
            "key": "enable_tts", "name": "Enable TTS", "type": "bool",
            "desc": "Speak the alert message aloud using text-to-speech when a change is detected.",
        },
        {
            "key": "default_sound_file", "name": "Default Sound File", "type": "file",
            "desc": "Path to a .wav/.mp3/.ogg file played on alert. Leave empty for no sound.",
            "filetypes": [("Audio files", "*.wav *.mp3 *.ogg"), ("All files", "*.*")],
        },
        {
            "key": "default_tts_message", "name": "Default TTS Message", "type": "string",
            "desc": "Template for the spoken alert. Variables: {window} = window title, "
                    "{region_name} = region name. Each region can override this.",
        },
        {
            "key": "alert_hold_seconds", "name": "Alert Hold Time (sec)", "type": "int",
            "desc": "How long a region stays in ALERT (red) or WARNING (orange) state after a "
                    "change is detected, before returning to OK (green). During this hold, the "
                    "sound won't re-trigger for the same region.",
            "min": 1, "max": 120, "increment": 1,
        },
    ]),
    ("captures", "Captures", None, [
        {
            "key": "capture_on_alert", "name": "Capture on Alert", "type": "bool",
            "desc": "Automatically save a screenshot of the region when an alert triggers.",
        },
        {
            "key": "save_alert_diagnostics", "name": "Save Alert Diagnostics", "type": "bool",
            "desc": "Save detailed diagnostic images on each alert: previous frame, current frame, "
                    "edge maps, and diff. Useful for tuning detection parameters.",
        },
        {
            "key": "capture_on_green", "name": "Capture on Green", "type": "bool",
            "desc": "Save a screenshot when a region returns to OK (green) state after an "
                    "alert/warning cycle.",
        },
        {
            "key": "capture_dir", "name": "Capture Directory", "type": "dir",
            "desc": "Folder where captured screenshots are saved. "
                    "Defaults to AppData/ScreenAlert/captures if empty.",
        },
        {
            "key": "capture_filename_format", "name": "Capture Filename", "type": "string",
            "desc": "Filename template for captures. Variables: {timestamp}, {window}, "
                    "{region}, {status}.",
        },
    ]),
    ("advanced", "Advanced", None, [
        {
            "key": "log_level", "name": "Log Level", "type": "choice",
            "desc": "Controls how much detail is written to the log file.\n\n"
                    "ERROR = only errors (default, recommended).\n"
                    "WARNING = errors and warnings.\n"
                    "INFO = normal operational messages.\n"
                    "DEBUG = detailed troubleshooting output.\n"
                    "TRACE = maximum verbosity — every frame, every check.",
            "choices": ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR"],
        },
        {
            "key": "anonymize_logs", "name": "Anonymize Logs", "type": "bool",
            "desc": "Replace window titles and character names in log output with generic "
                    "placeholders. Use when sharing logs publicly.",
        },
        {
            "key": "suppress_fullscreen", "name": "Suppress in Fullscreen", "type": "bool",
            "desc": "Automatically hide thumbnail overlays when a fullscreen application "
                    "is detected in the foreground.",
        },
        {
            "key": "update_check_enabled", "name": "Check for Updates", "type": "bool",
            "desc": "Check for new versions of ScreenAlert on startup.",
        },
        {
            "key": "diagnostics_enabled", "name": "Diagnostics Mode", "type": "bool",
            "desc": "Enable diagnostics overlay and extra runtime metrics. "
                    "Shows frame timing, detection scores, and thread health.",
        },
    ]),
    ("reconnect", "Reconnect", None, [
        {
            "key": "reconnect_size_tolerance", "name": "Size Tolerance (px)", "type": "int",
            "desc": "How many pixels a window's width or height may differ from the saved size "
                    "before it is considered a different window. 0 = exact match required, "
                    "20 = a few pixels of resize are tolerated. Applies to identity validation "
                    "and automatic reconnection.",
            "min": 0, "max": 500, "increment": 5,
        },
        {
            "key": "prompt_on_reconnect_fail", "name": "Prompt on Reconnect Fail", "type": "bool",
            "desc": "When a manual single-window reconnect fails, show a dialog offering to "
                    "pick a replacement window from the window selector. Does not apply to "
                    "Reconnect All or automatic startup reconnection.",
        },
    ]),
    ("event_log", "Event Log", None, [
        {
            "key": "event_log_enabled", "name": "Enable Event Log", "type": "bool",
            "desc": "Record all alerts, window events, and setting changes to a JSONL file. "
                    "Required for the MCP event log tools and alert image history.",
        },
        {
            "key": "event_log_max_rows", "name": "Max Log Entries", "type": "int",
            "desc": "Maximum number of events kept before oldest entries are pruned. "
                    "5000 is a good default; increase if you need longer history.",
            "min": 100, "max": 100000, "increment": 1000,
        },
    ]),
    ("mcp", "MCP Server", None, [
        {
            "key": "mcp_enabled", "name": "Enable MCP Server", "type": "bool",
            "desc": "Start the embedded HTTPS MCP server so Claude Desktop, Claude Code, "
                    "and other MCP-compatible clients can connect. Requires app restart to take effect.",
        },
        {
            "key": "mcp_port", "name": "HTTPS Port", "type": "int",
            "desc": "Port number the MCP server listens on. Default 8765. "
                    "Update your MCP client config if you change this.",
            "min": 1024, "max": 65535, "increment": 1,
        },
        {
            "key": "mcp_max_connections", "name": "Max Connections", "type": "int",
            "desc": "Maximum number of simultaneous MCP client connections. "
                    "Excess connections receive a 429 response.",
            "min": 1, "max": 20, "increment": 1,
        },
        {
            "key": "mcp_http_redirect", "name": "HTTP Redirect", "type": "bool",
            "desc": "Listen on the HTTP port and redirect all traffic to HTTPS. "
                    "Useful if a client doesn't support HTTPS natively.",
        },
        {
            "key": "mcp_http_port", "name": "HTTP Redirect Port", "type": "int",
            "desc": "Port for the plain-HTTP redirect listener (only used when HTTP Redirect is on). "
                    "Default 8766.",
            "min": 1024, "max": 65535, "increment": 1,
        },
    ]),
]

# Config getter/setter mapping: key -> (getter_name, setter_name)
# Most follow the pattern get_<key> / set_<key>, but some differ.
_CONFIG_MAP = {
    "refresh_rate": ("get_refresh_rate", "set_refresh_rate"),
    "pause_reminder_interval_sec": ("get_pause_reminder_interval_sec", "set_pause_reminder_interval_sec"),
    "change_detection_method": ("get_change_detection_method", "set_change_detection_method"),
    "alert_threshold": ("get_default_alert_threshold", "set_default_alert_threshold"),
    "min_edge_fraction": ("get_min_edge_fraction", "set_min_edge_fraction"),
    "canny_low": ("get_canny_low", "set_canny_low"),
    "canny_high": ("get_canny_high", "set_canny_high"),
    "edge_binarize": ("get_edge_binarize", "set_edge_binarize"),
    "bg_history": ("get_bg_history", "set_bg_history"),
    "bg_var_threshold": ("get_bg_var_threshold", "set_bg_var_threshold"),
    "bg_min_fg_fraction": ("get_bg_min_fg_fraction", "set_bg_min_fg_fraction"),
    "bg_warmup_frames": ("get_bg_warmup_frames", "set_bg_warmup_frames"),
    "theme_preset": ("get_theme_preset", "set_theme_preset"),
    "opacity": ("get_opacity", "set_opacity"),
    "always_on_top": ("get_always_on_top", "set_always_on_top"),
    "show_borders": ("get_show_borders", "set_show_borders"),
    "show_overlay_when_unavailable": ("get_show_overlay_when_unavailable", "set_show_overlay_when_unavailable"),
    "enable_sound": ("get_enable_sound", "set_enable_sound"),
    "enable_tts": ("get_enable_tts", "set_enable_tts"),
    "default_sound_file": ("get_default_sound_file", "set_default_sound_file"),
    "default_tts_message": ("get_default_tts_message", "set_default_tts_message"),
    "alert_hold_seconds": ("get_alert_hold_seconds", "set_alert_hold_seconds"),
    "capture_on_alert": ("get_capture_on_alert", "set_capture_on_alert"),
    "save_alert_diagnostics": ("get_save_alert_diagnostics", "set_save_alert_diagnostics"),
    "capture_on_green": ("get_capture_on_green", "set_capture_on_green"),
    "capture_dir": ("get_capture_dir", "set_capture_dir"),
    "capture_filename_format": ("get_capture_filename_format", "set_capture_filename_format"),
    "log_level": ("get_log_level", "set_log_level"),
    "anonymize_logs": ("get_anonymize_logs", "set_anonymize_logs"),
    "suppress_fullscreen": ("get_suppress_fullscreen", "set_suppress_fullscreen"),
    "update_check_enabled": ("get_update_check_enabled", "set_update_check_enabled"),
    "diagnostics_enabled": ("get_diagnostics_enabled", "set_diagnostics_enabled"),
    "reconnect_size_tolerance": ("get_reconnect_size_tolerance", "set_reconnect_size_tolerance"),
    "prompt_on_reconnect_fail": ("get_prompt_on_reconnect_fail", "set_prompt_on_reconnect_fail"),
    "overlay_update_rate_hz": ("get_overlay_update_rate_hz", "set_overlay_update_rate_hz"),
    "auto_discovery_enabled": ("get_auto_discovery_enabled", "set_auto_discovery_enabled"),
    "auto_discovery_interval_sec": ("get_auto_discovery_interval_sec", "set_auto_discovery_interval_sec"),
    "overlay_scaling_mode": ("get_overlay_scaling_mode", "set_overlay_scaling_mode"),
    "show_overlay_on_connect": ("get_show_overlay_on_connect", "set_show_overlay_on_connect"),
    "event_log_enabled": ("get_event_log_enabled", "set_event_log_enabled"),
    "event_log_max_rows": ("get_event_log_max_rows", "set_event_log_max_rows"),
    "mcp_enabled": ("get_mcp_enabled", "set_mcp_enabled"),
    "mcp_port": ("get_mcp_port", "set_mcp_port"),
    "mcp_max_connections": ("get_mcp_max_connections", "set_mcp_max_connections"),
    "mcp_http_redirect": ("get_mcp_http_redirect", "set_mcp_http_redirect"),
    "mcp_http_port": ("get_mcp_http_port", "set_mcp_http_port"),
}


class SettingsDialog:
    """Regedit-style settings dialog."""

    def __init__(self, parent: tk.Widget, config: ConfigManager,
                 on_apply_callback: Optional[Callable[[Dict], None]] = None):
        self.config = config
        self.on_apply_callback = on_apply_callback
        self.result: Optional[Dict] = None
        self._parent = parent

        # Flat lookup: key -> setting metadata dict
        self._setting_meta: Dict[str, dict] = {}
        for _cid, _clabel, _parent, settings in _CATEGORIES:
            for s in settings:
                self._setting_meta[s["key"]] = s

        # Current values cached for display
        self._values: Dict[str, Any] = {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("ScreenAlert Settings")
        self.dialog.geometry("780x520")
        self.dialog.minsize(680, 400)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._build_ui()
        self._load_all_values()
        # Select first category
        self._cat_tree.selection_set(_CATEGORIES[0][0])
        self._show_category(_CATEGORIES[0][0])

    # ── UI ────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.dialog, padding=8)
        outer.pack(fill=tk.BOTH, expand=True)

        # Paned window: left tree | right table
        pane = ttk.PanedWindow(outer, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        # Left: category tree
        left = ttk.Frame(pane, width=180)
        self._cat_tree = ttk.Treeview(left, show="tree", selectmode="browse",
                                       style="App.Treeview")
        self._cat_tree.pack(fill=tk.BOTH, expand=True)
        for cid, clabel, parent, _settings in _CATEGORIES:
            parent_iid = parent if parent else ""
            self._cat_tree.insert(parent_iid, tk.END, iid=cid, text=clabel, open=True)
        self._cat_tree.bind("<<TreeviewSelect>>", self._on_cat_select)
        pane.add(left, weight=0)

        # Right: value table
        right = ttk.Frame(pane)
        cols = ("value", "description")
        self._val_tree = ttk.Treeview(right, columns=cols, show="headings tree",
                                       selectmode="browse", style="App.Treeview")
        self._val_tree.heading("#0", text="Name", anchor="w")
        self._val_tree.heading("value", text="Value", anchor="w")
        self._val_tree.heading("description", text="Description", anchor="w")
        self._val_tree.column("#0", width=180, minwidth=120)
        self._val_tree.column("value", width=160, minwidth=80)
        self._val_tree.column("description", width=320, minwidth=150)

        vsb = ttk.Scrollbar(right, orient="vertical", command=self._val_tree.yview)
        self._val_tree.configure(yscrollcommand=vsb.set)
        self._val_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self._val_tree.bind("<Double-1>", self._on_double_click)
        self._val_tree.bind("<Return>", self._on_double_click)
        pane.add(right, weight=1)

        # Buttons
        btn_frame = ttk.Frame(outer)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Apply", command=self._on_apply).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Reset to Defaults", command=self._reset_defaults).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Import", command=self._import_config).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Export", command=self._export_config).pack(side=tk.RIGHT, padx=5)

    # ── Category selection ────────────────────────────────────────────

    def _on_cat_select(self, _event=None) -> None:
        sel = self._cat_tree.selection()
        if sel:
            self._show_category(sel[0])

    def _show_category(self, cat_id: str) -> None:
        # Clear table
        for item in self._val_tree.get_children():
            self._val_tree.delete(item)

        # Find category
        for cid, _clabel, _parent, settings in _CATEGORIES:
            if cid == cat_id:
                for s in settings:
                    key = s["key"]
                    val = self._values.get(key, "")
                    disp = self._format_value(s, val)
                    # Truncate description for table (first sentence)
                    desc_short = s.get("desc", "")
                    if ". " in desc_short:
                        desc_short = desc_short[:desc_short.index(". ") + 1]
                    if len(desc_short) > 100:
                        desc_short = desc_short[:97] + "..."
                    self._val_tree.insert("", tk.END, iid=key, text=s["name"],
                                          values=(disp, desc_short))
                break

    def _format_value(self, meta: dict, val: Any) -> str:
        """Format a value for display in the table."""
        vtype = meta.get("type", "string")
        if vtype == "bool":
            return "True" if val else "False"
        if vtype == "float":
            scale = meta.get("scale", 1)
            fmt = meta.get("format", "%.2f")
            return fmt % (val * scale if scale != 1 else val)
        return str(val)

    # ── Load / Save ───────────────────────────────────────────────────

    def _load_all_values(self) -> None:
        """Read all settings from config into self._values."""
        for key, (getter, _setter) in _CONFIG_MAP.items():
            try:
                self._values[key] = getattr(self.config, getter)()
            except Exception:
                self._values[key] = ""

    def _save_all_values(self) -> Optional[Dict]:
        """Write all cached values back to config."""
        try:
            for key, (_getter, setter) in _CONFIG_MAP.items():
                val = self._values.get(key)
                if val is not None:
                    getattr(self.config, setter)(val)
            self.config.save()
            logger.info("Settings saved")
            return self._get_settings_dict()
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return None

    def _get_settings_dict(self) -> Dict:
        """Build a settings dict for the on_apply callback."""
        return dict(self._values)

    # ── Edit dialog ───────────────────────────────────────────────────

    def _on_double_click(self, _event=None) -> None:
        sel = self._val_tree.selection()
        if not sel:
            return
        key = sel[0]
        meta = self._setting_meta.get(key)
        if not meta:
            return
        self._open_edit_dialog(key, meta)

    def _open_edit_dialog(self, key: str, meta: dict) -> None:
        """Open a type-appropriate edit dialog for the setting."""
        vtype = meta.get("type", "string")
        current = self._values.get(key, "")

        dlg = tk.Toplevel(self.dialog)
        dlg.title(f"Edit — {meta['name']}")
        dlg.transient(self.dialog)
        dlg.grab_set()
        dlg.resizable(False, False)

        main = ttk.Frame(dlg, padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        # Name
        ttk.Label(main, text="Setting:", font=("", 9, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(main, text=meta["name"]).grid(row=0, column=1, sticky="w", padx=(8, 0))

        # Description (full text, wrapped)
        ttk.Label(main, text="Description:", font=("", 9, "bold")).grid(row=1, column=0, sticky="nw", pady=(8, 0))
        desc_label = ttk.Label(main, text=meta.get("desc", ""), wraplength=380,
                               justify="left", foreground="gray")
        desc_label.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

        # Value editor
        ttk.Label(main, text="Value:", font=("", 9, "bold")).grid(row=2, column=0, sticky="w", pady=(12, 0))

        result_var = tk.StringVar()
        editor_frame = ttk.Frame(main)
        editor_frame.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(12, 0))

        if vtype == "bool":
            bool_var = tk.BooleanVar(value=bool(current))
            ttk.Checkbutton(editor_frame, variable=bool_var, text="Enabled",
                            style="App.TCheckbutton").pack(anchor="w")
            def get_val():
                return bool_var.get()

        elif vtype == "choice":
            choices = meta.get("choices", [])
            choice_var = tk.StringVar(value=str(current))
            ttk.Combobox(editor_frame, textvariable=choice_var, values=choices,
                         state="readonly", width=30, style="App.TCombobox").pack(anchor="w")
            def get_val():
                return choice_var.get()

        elif vtype == "int":
            int_var = tk.IntVar(value=int(current))
            ttk.Spinbox(editor_frame, from_=meta.get("min", 0), to=meta.get("max", 99999),
                         increment=meta.get("increment", 1),
                         textvariable=int_var, width=12).pack(anchor="w")
            def get_val():
                return int_var.get()

        elif vtype == "float":
            scale = meta.get("scale", 1)
            display_val = current * scale if scale != 1 else current
            float_var = tk.DoubleVar(value=display_val)
            fmt = meta.get("format", "%.2f")
            spinbox_min = meta.get("min", 0.0)
            spinbox_max = meta.get("max", 999.0)
            if scale != 1:
                spinbox_min *= scale
                spinbox_max *= scale
            ttk.Spinbox(editor_frame, from_=spinbox_min, to=spinbox_max,
                         increment=meta.get("increment", 0.01) * (scale if scale != 1 else 1),
                         format=fmt,
                         textvariable=float_var, width=12).pack(anchor="w")
            def get_val():
                v = float_var.get()
                if scale != 1:
                    return v / scale
                return v

        elif vtype == "file":
            file_var = tk.StringVar(value=str(current))
            entry = ttk.Entry(editor_frame, textvariable=file_var, width=36)
            entry.pack(side=tk.LEFT)
            def _browse():
                ft = meta.get("filetypes", [("All files", "*.*")])
                p = filedialog.askopenfilename(title=f"Select {meta['name']}", filetypes=ft)
                if p:
                    file_var.set(p)
            ttk.Button(editor_frame, text="Browse", command=_browse).pack(side=tk.LEFT, padx=4)
            def get_val():
                return file_var.get()

        elif vtype == "dir":
            dir_var = tk.StringVar(value=str(current))
            ttk.Entry(editor_frame, textvariable=dir_var, width=36).pack(side=tk.LEFT)
            def _browse_dir():
                p = filedialog.askdirectory(title=f"Select {meta['name']}")
                if p:
                    dir_var.set(p)
            ttk.Button(editor_frame, text="Browse", command=_browse_dir).pack(side=tk.LEFT, padx=4)
            def get_val():
                return dir_var.get()

        else:  # string
            str_var = tk.StringVar(value=str(current))
            ttk.Entry(editor_frame, textvariable=str_var, width=36).pack(anchor="w")
            def get_val():
                return str_var.get()

        # OK / Cancel
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=(16, 0))

        def _ok():
            new_val = get_val()
            self._values[key] = new_val
            # Update table display
            disp = self._format_value(meta, new_val)
            self._val_tree.set(key, "value", disp)
            # Live preview for theme
            if key == "theme_preset" and self.on_apply_callback:
                try:
                    self.on_apply_callback({"theme_preset": new_val})
                except Exception:
                    pass
            dlg.destroy()

        ttk.Button(btn_frame, text="OK", command=_ok, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dlg.destroy, width=10).pack(side=tk.LEFT, padx=5)

        # Size and center
        dlg.update_idletasks()
        w = max(480, dlg.winfo_reqwidth())
        h = dlg.winfo_reqheight()
        dlg.geometry(f"{w}x{h}")

    # ── Actions ───────────────────────────────────────────────────────

    def _on_apply(self) -> None:
        settings = self._save_all_values()
        if settings and self.on_apply_callback:
            try:
                self.on_apply_callback(settings)
            except Exception as e:
                logger.error(f"Error applying settings: {e}")
        logger.info("Settings applied")

    def _on_ok(self) -> None:
        settings = self._save_all_values()
        if settings and self.on_apply_callback:
            try:
                self.on_apply_callback(settings)
            except Exception as e:
                logger.error(f"Error applying settings: {e}")
        self.result = settings
        self.dialog.destroy()

    def _export_config(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export configuration", defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if path and self.config.export_config(path):
            messagebox.showinfo("Export", "Configuration exported successfully")

    def _import_config(self) -> None:
        path = filedialog.askopenfilename(
            title="Import configuration",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if path:
            if self.config.import_config(path):
                self._load_all_values()
                # Refresh current category view
                sel = self._cat_tree.selection()
                if sel:
                    self._show_category(sel[0])
                messagebox.showinfo("Import", "Configuration imported successfully")
            else:
                messagebox.showerror("Import", "Failed to import configuration")

    def _reset_defaults(self) -> None:
        if not messagebox.askyesno("Reset", "Reset all settings to defaults?"):
            return
        if self.config.reset_to_defaults():
            self._load_all_values()
            sel = self._cat_tree.selection()
            if sel:
                self._show_category(sel[0])
            messagebox.showinfo("Reset", "Settings reset to defaults")

    def show(self) -> Optional[Dict]:
        self.dialog.wait_window()
        return self.result
