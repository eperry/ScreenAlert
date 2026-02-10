"""Settings dialog for ScreenAlert configuration"""

import tkinter as tk
from tkinter import ttk
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
        
        # Refresh Rate
        refresh_frame = ttk.LabelFrame(main_frame, text="Monitoring", padding=10)
        refresh_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(refresh_frame, text="Refresh Rate (ms):").grid(row=0, column=0, sticky="w")
        self.refresh_var = tk.IntVar(value=DEFAULT_REFRESH_RATE_MS)
        refresh_spin = ttk.Spinbox(refresh_frame, from_=300, to=5000, increment=100,
                                   textvariable=self.refresh_var, width=10)
        refresh_spin.grid(row=0, column=1, sticky="w", padx=10)
        ttk.Label(refresh_frame, text="(300-5000ms)").grid(row=0, column=2, sticky="w")
        
        # Opacity
        appearance_frame = ttk.LabelFrame(main_frame, text="Appearance", padding=10)
        appearance_frame.pack(fill=tk.X, pady=(0, 10))
        
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
        
        appearance_frame.columnconfigure(1, weight=1)
        
        # Alerts
        alert_frame = ttk.LabelFrame(main_frame, text="Alerts", padding=10)
        alert_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(alert_frame, text="Default Sound:").grid(row=0, column=0, sticky="w")
        self.sound_var = tk.StringVar(value="")
        sound_entry = ttk.Entry(alert_frame, textvariable=self.sound_var)
        sound_entry.grid(row=0, column=1, sticky="ew", padx=10)
        ttk.Button(alert_frame, text="Browse").grid(row=0, column=2)
        
        ttk.Label(alert_frame, text="Default TTS Message:").grid(row=1, column=0, sticky="w")
        self.tts_var = tk.StringVar(value="Alert {name}")
        tts_entry = ttk.Entry(alert_frame, textvariable=self.tts_var)
        tts_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=10)
        
        alert_frame.columnconfigure(1, weight=1)
        
        # Logging
        logging_frame = ttk.LabelFrame(main_frame, text="Logging", padding=10)
        logging_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(logging_frame, text="Verbose Logging:").grid(row=0, column=0, sticky="w")
        self.verbose_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(logging_frame, variable=self.verbose_var).grid(
            row=0, column=1, sticky="w", padx=10)
        
        ttk.Label(logging_frame, text="(Enable for debugging)", 
                 foreground="gray").grid(row=0, column=2, sticky="w")
        
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
        self.verbose_var.set(self.config.get_verbose_logging())
    
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
            self.config.set_verbose_logging(self.verbose_var.get())
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
            "verbose_logging": self.verbose_var.get(),
        }
    
    def show(self) -> Optional[Dict]:
        """Show dialog and return settings
        
        Returns:
            Settings dict or None if cancelled
        """
        self.dialog.wait_window()
        return self.result
