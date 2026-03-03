"""Settings dialog for ScreenAlert configuration"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
from typing import Optional, Dict

from screenalert_core.core.config_manager import ConfigManager
from screenalert_core.utils.constants import (
    DEFAULT_REFRESH_RATE_MS, DEFAULT_OPACITY
)

logger = logging.getLogger(__name__)


class SettingsDialog:
    """Dialog for application settings"""
    
    def __init__(self, parent: tk.Widget, config: ConfigManager):
        """Initialize settings dialog
        
        Args:
            parent: Parent window
            config: ConfigManager instance
        """
        self.config = config
        self.result: Optional[Dict] = None
        
        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("ScreenAlert Settings")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._build_ui()
        self._load_settings()
    
    def _build_ui(self) -> None:
        """Build dialog UI"""
        main_frame = ttk.Frame(self.dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        monitor_tab = ttk.Frame(notebook, padding=10)
        appearance_tab = ttk.Frame(notebook, padding=10)
        alert_tab = ttk.Frame(notebook, padding=10)
        diagnostics_tab = ttk.Frame(notebook, padding=10)

        notebook.add(monitor_tab, text="Monitoring")
        notebook.add(appearance_tab, text="Appearance")
        notebook.add(alert_tab, text="Alerts")
        notebook.add(diagnostics_tab, text="Advanced")
        
        # Monitoring
        refresh_frame = ttk.LabelFrame(monitor_tab, text="Monitoring", padding=10)
        refresh_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(refresh_frame, text="Refresh Rate (ms):").grid(row=0, column=0, sticky="w")
        self.refresh_var = tk.IntVar(value=DEFAULT_REFRESH_RATE_MS)
        refresh_spin = ttk.Spinbox(refresh_frame, from_=300, to=5000, increment=100,
                                   textvariable=self.refresh_var, width=10)
        refresh_spin.grid(row=0, column=1, sticky="w", padx=10)
        ttk.Label(refresh_frame, text="(300-5000ms)").grid(row=0, column=2, sticky="w")

        ttk.Label(refresh_frame, text="Default Alert Threshold:").grid(row=1, column=0, sticky="w")
        self.alert_threshold_var = tk.DoubleVar(value=0.99)
        ttk.Spinbox(refresh_frame, from_=0.10, to=1.0, increment=0.01,
                textvariable=self.alert_threshold_var, width=10).grid(row=1, column=1, sticky="w", padx=10)

        ttk.Label(refresh_frame, text="Change Detection:").grid(row=2, column=0, sticky="w")
        self.change_method_var = tk.StringVar(value="ssim")
        ttk.Combobox(refresh_frame, textvariable=self.change_method_var,
                 values=["ssim", "phash"], state="readonly", width=12).grid(row=2, column=1, sticky="w", padx=10)

        ttk.Label(refresh_frame, text="Pause Reminder (sec):").grid(row=3, column=0, sticky="w")
        self.pause_reminder_var = tk.IntVar(value=60)
        ttk.Spinbox(refresh_frame, from_=10, to=3600, increment=10,
                textvariable=self.pause_reminder_var, width=10).grid(row=3, column=1, sticky="w", padx=10)
        
        # Appearance
        appearance_frame = ttk.LabelFrame(appearance_tab, text="Appearance", padding=10)

        appearance_frame.pack(fill=tk.X, pady=(0, 10))

        # High-contrast mode toggle
        ttk.Label(appearance_frame, text="High-Contrast Mode:").grid(row=3, column=0, sticky="w")
        self.high_contrast_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(appearance_frame, variable=self.high_contrast_var).grid(
            row=3, column=1, sticky="w", padx=10)

        appearance_frame.columnconfigure(1, weight=1)
        
        ttk.Label(appearance_frame, text="Thumbnail Opacity:").grid(row=0, column=0, sticky="w")
        self.opacity_var = tk.DoubleVar(value=DEFAULT_OPACITY)
        opacity_scale = ttk.Scale(appearance_frame, from_=0.2, to=1.0,
                                 variable=self.opacity_var, orient=tk.HORIZONTAL)
        opacity_scale.grid(row=0, column=1, sticky="ew", padx=10)
        
        self.opacity_label = ttk.Label(appearance_frame, text="0.8")
        self.opacity_label.grid(row=0, column=2, sticky="w")
        opacity_scale.config(command=lambda x: self.opacity_label.config(
            text=f"{float(x):.2f}"))
        
        ttk.Label(appearance_frame, text="Always on Top:").grid(row=1, column=0, sticky="w")
        self.always_on_top_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(appearance_frame, variable=self.always_on_top_var).grid(
            row=1, column=1, sticky="w", padx=10)
        
        ttk.Label(appearance_frame, text="Show Borders:").grid(row=2, column=0, sticky="w")
        self.show_borders_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(appearance_frame, variable=self.show_borders_var).grid(
            row=2, column=1, sticky="w", padx=10)

        ttk.Label(appearance_frame, text="Show Overlay if Unavailable:").grid(row=4, column=0, sticky="w")
        self.show_overlay_unavailable_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(appearance_frame, variable=self.show_overlay_unavailable_var).grid(
            row=4, column=1, sticky="w", padx=10)
        
        appearance_frame.columnconfigure(1, weight=1)
        
        # Alerts
        alert_frame = ttk.LabelFrame(alert_tab, text="Alerts", padding=10)
        alert_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(alert_frame, text="Enable Sound:").grid(row=0, column=0, sticky="w")
        self.enable_sound_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(alert_frame, variable=self.enable_sound_var).grid(row=0, column=1, sticky="w", padx=10)

        ttk.Label(alert_frame, text="Enable TTS:").grid(row=1, column=0, sticky="w")
        self.enable_tts_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(alert_frame, variable=self.enable_tts_var).grid(row=1, column=1, sticky="w", padx=10)
        
        ttk.Label(alert_frame, text="Default Sound:").grid(row=2, column=0, sticky="w")
        self.sound_var = tk.StringVar(value="")
        sound_entry = ttk.Entry(alert_frame, textvariable=self.sound_var)
        sound_entry.grid(row=2, column=1, sticky="ew", padx=10)
        ttk.Button(alert_frame, text="Browse", command=self._browse_sound).grid(row=2, column=2)
        
        ttk.Label(alert_frame, text="Default TTS Message:").grid(row=3, column=0, sticky="w")
        self.tts_var = tk.StringVar(value="Alert {window} {region_name}")
        tts_entry = ttk.Entry(alert_frame, textvariable=self.tts_var)
        tts_entry.grid(row=3, column=1, columnspan=2, sticky="ew", padx=10)

        ttk.Label(alert_frame, text="Capture on Alert:").grid(row=4, column=0, sticky="w")
        self.capture_on_alert_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(alert_frame, variable=self.capture_on_alert_var).grid(row=4, column=1, sticky="w", padx=10)

        ttk.Label(alert_frame, text="Alert Hold Time (sec):").grid(row=5, column=0, sticky="w")
        self.alert_hold_var = tk.IntVar(value=10)
        ttk.Spinbox(alert_frame, from_=1, to=120, increment=1,
                     textvariable=self.alert_hold_var, width=10).grid(row=5, column=1, sticky="w", padx=10)
        ttk.Label(alert_frame, text="(1-120s, Alert & Warning hold)").grid(row=5, column=2, sticky="w")

        ttk.Label(alert_frame, text="Capture on Green:").grid(row=6, column=0, sticky="w")
        self.capture_on_green_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(alert_frame, variable=self.capture_on_green_var).grid(row=6, column=1, sticky="w", padx=10)

        ttk.Label(alert_frame, text="Capture Directory:").grid(row=7, column=0, sticky="w")
        self.capture_dir_var = tk.StringVar(value="")
        ttk.Entry(alert_frame, textvariable=self.capture_dir_var).grid(row=7, column=1, sticky="ew", padx=10)
        ttk.Button(alert_frame, text="Browse", command=self._browse_capture_dir).grid(row=7, column=2)

        ttk.Label(alert_frame, text="Capture Filename:").grid(row=8, column=0, sticky="w")
        self.capture_filename_var = tk.StringVar(value="{timestamp}_{window}_{region}_{status}.png")
        ttk.Entry(alert_frame, textvariable=self.capture_filename_var).grid(row=8, column=1, columnspan=2, sticky="ew", padx=10)
        
        alert_frame.columnconfigure(1, weight=1)
        
        # Advanced
        logging_frame = ttk.LabelFrame(diagnostics_tab, text="Diagnostics & Safety", padding=10)
        logging_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(logging_frame, text="Verbose Logging:").grid(row=0, column=0, sticky="w")
        self.verbose_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(logging_frame, variable=self.verbose_var).grid(
            row=0, column=1, sticky="w", padx=10)
        
        ttk.Label(logging_frame, text="(Enable for debugging)", 
                 foreground="gray").grid(row=0, column=2, sticky="w")

        ttk.Label(logging_frame, text="Anonymize Logs:").grid(row=1, column=0, sticky="w")
        self.anonymize_logs_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(logging_frame, variable=self.anonymize_logs_var).grid(row=1, column=1, sticky="w", padx=10)

        ttk.Label(logging_frame, text="Suppress in Fullscreen:").grid(row=2, column=0, sticky="w")
        self.suppress_fullscreen_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(logging_frame, variable=self.suppress_fullscreen_var).grid(row=2, column=1, sticky="w", padx=10)

        ttk.Label(logging_frame, text="Check for Updates:").grid(row=3, column=0, sticky="w")
        self.update_check_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(logging_frame, variable=self.update_check_var).grid(row=3, column=1, sticky="w", padx=10)

        ttk.Label(logging_frame, text="Diagnostics Mode:").grid(row=4, column=0, sticky="w")
        self.diagnostics_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(logging_frame, variable=self.diagnostics_var).grid(row=4, column=1, sticky="w", padx=10)

        config_ops_frame = ttk.LabelFrame(diagnostics_tab, text="Configuration", padding=10)
        config_ops_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(config_ops_frame, text="Export Config", command=self._export_config).pack(side=tk.LEFT, padx=4)
        ttk.Button(config_ops_frame, text="Import Config", command=self._import_config).pack(side=tk.LEFT, padx=4)
        ttk.Button(config_ops_frame, text="Reset to Defaults", command=self._reset_defaults).pack(side=tk.LEFT, padx=4)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Apply", command=self._on_apply).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def _load_settings(self) -> None:
        """Load settings from config"""
        self.refresh_var.set(self.config.get_refresh_rate())
        self.opacity_var.set(self.config.get_opacity())
        self.always_on_top_var.set(self.config.get_always_on_top())
        self.show_overlay_unavailable_var.set(self.config.get_show_overlay_when_unavailable())
        self.verbose_var.set(self.config.get_verbose_logging())
        self.high_contrast_var.set(self.config.get_high_contrast())
        self.alert_threshold_var.set(self.config.get_default_alert_threshold())
        self.change_method_var.set(self.config.get_change_detection_method())
        self.enable_sound_var.set(self.config.get_enable_sound())
        self.enable_tts_var.set(self.config.get_enable_tts())
        self.sound_var.set(self.config.get_default_sound_file())
        self.tts_var.set(self.config.get_default_tts_message())
        self.pause_reminder_var.set(self.config.get_pause_reminder_interval_sec())
        self.capture_on_alert_var.set(self.config.get_capture_on_alert())
        self.alert_hold_var.set(self.config.get_alert_hold_seconds())
        self.capture_on_green_var.set(self.config.get_capture_on_green())
        self.capture_dir_var.set(self.config.get_capture_dir())
        self.capture_filename_var.set(self.config.get_capture_filename_format())
        self.anonymize_logs_var.set(self.config.get_anonymize_logs())
        self.suppress_fullscreen_var.set(self.config.get_suppress_fullscreen())
        self.update_check_var.set(self.config.get_update_check_enabled())
        self.diagnostics_var.set(self.config.get_diagnostics_enabled())
    
    def _on_apply(self) -> None:
        """Apply settings without closing"""
        self._save_settings()
        logger.info("Settings applied")
    
    def _on_ok(self) -> None:
        """Apply settings and close"""
        self._save_settings()
        self.result = self._get_settings()
        self.dialog.destroy()
    
    def _save_settings(self) -> None:
        """Save settings to config"""
        try:
            self.config.set_refresh_rate(self.refresh_var.get())
            self.config.set_opacity(self.opacity_var.get())
            self.config.set_always_on_top(self.always_on_top_var.get())
            self.config.set_show_overlay_when_unavailable(self.show_overlay_unavailable_var.get())
            self.config.set_verbose_logging(self.verbose_var.get())
            self.config.set_high_contrast(self.high_contrast_var.get())
            self.config.set_default_alert_threshold(self.alert_threshold_var.get())
            self.config.set_change_detection_method(self.change_method_var.get())
            self.config.set_enable_sound(self.enable_sound_var.get())
            self.config.set_enable_tts(self.enable_tts_var.get())
            self.config.set_default_sound_file(self.sound_var.get())
            self.config.set_default_tts_message(self.tts_var.get())
            self.config.set_pause_reminder_interval_sec(self.pause_reminder_var.get())
            self.config.set_capture_on_alert(self.capture_on_alert_var.get())
            self.config.set_alert_hold_seconds(self.alert_hold_var.get())
            self.config.set_capture_on_green(self.capture_on_green_var.get())
            self.config.set_capture_dir(self.capture_dir_var.get())
            self.config.set_capture_filename_format(self.capture_filename_var.get())
            self.config.set_anonymize_logs(self.anonymize_logs_var.get())
            self.config.set_suppress_fullscreen(self.suppress_fullscreen_var.get())
            self.config.set_update_check_enabled(self.update_check_var.get())
            self.config.set_diagnostics_enabled(self.diagnostics_var.get())
            self.config.save()
            logger.info("Settings saved")
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
    
    def _get_settings(self) -> Dict:
        """Get current settings as dict"""
        return {
            "refresh_rate": self.refresh_var.get(),
            "opacity": self.opacity_var.get(),
            "always_on_top": self.always_on_top_var.get(),
            "show_overlay_when_unavailable": self.show_overlay_unavailable_var.get(),
            "verbose_logging": self.verbose_var.get(),
            "high_contrast": self.high_contrast_var.get(),
            "alert_threshold": self.alert_threshold_var.get(),
            "change_detection_method": self.change_method_var.get(),
            "enable_sound": self.enable_sound_var.get(),
            "enable_tts": self.enable_tts_var.get(),
            "pause_reminder_interval_sec": self.pause_reminder_var.get(),
            "capture_on_alert": self.capture_on_alert_var.get(),
            "alert_hold_seconds": self.alert_hold_var.get(),
            "capture_on_green": self.capture_on_green_var.get(),
            "capture_dir": self.capture_dir_var.get(),
            "capture_filename_format": self.capture_filename_var.get(),
            "anonymize_logs": self.anonymize_logs_var.get(),
            "suppress_fullscreen": self.suppress_fullscreen_var.get(),
            "update_check_enabled": self.update_check_var.get(),
            "diagnostics_enabled": self.diagnostics_var.get(),
        }

    def _browse_sound(self) -> None:
        path = filedialog.askopenfilename(
            title="Select alert sound",
            filetypes=[("Audio files", "*.wav *.mp3 *.ogg"), ("All files", "*.*")]
        )
        if path:
            self.sound_var.set(path)

    def _browse_capture_dir(self) -> None:
        path = filedialog.askdirectory(title="Select capture directory")
        if path:
            self.capture_dir_var.set(path)

    def _export_config(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export configuration",
            defaultextension=".json",
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
                self._load_settings()
                messagebox.showinfo("Import", "Configuration imported successfully")
            else:
                messagebox.showerror("Import", "Failed to import configuration")

    def _reset_defaults(self) -> None:
        if not messagebox.askyesno("Reset", "Reset all settings to defaults?"):
            return
        if self.config.reset_to_defaults():
            self._load_settings()
            messagebox.showinfo("Reset", "Settings reset to defaults")
    
    def show(self) -> Optional[Dict]:
        """Show dialog and return settings
        
        Returns:
            Settings dict or None if cancelled
        """
        self.dialog.wait_window()
        return self.result
