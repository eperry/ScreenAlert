"""Complete Main window UI for ScreenAlert using Dear PyGui (GPU-accelerated, flicker-free)"""

import logging
import dearpygui.dearpygui as dpg
from typing import Optional, Dict, List
import win32gui
import pyttsx3
from PIL import Image
import numpy as np
import threading

from screenalert_core.screening_engine import ScreenAlertEngine
from screenalert_core.core.image_processor import ImageProcessor

logger = logging.getLogger(__name__)


class ScreenAlertMainWindowDPG:
    """Main control window using Dear PyGui for flicker-free updates"""
    
    def __init__(self, engine: ScreenAlertEngine):
        """Initialize main window"""
        self.engine = engine
        self.config = engine.config
        self.window_manager = engine.window_manager
        self.thumbnail_map = {}  # hwnd -> thumbnail_id mapping
        self.selected_thumbnail_id: Optional[str] = None
        self.region_statuses: Dict[str, Dict[str, str]] = {}
        self.region_to_thumbnail: Dict[str, str] = {}
        self.show_all_regions = True
        self.monitoring_active = False
        
        # Initialize text-to-speech
        try:
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty('rate', 150)
        except Exception as e:
            logger.warning(f"Could not initialize TTS: {e}")
            self.tts_engine = None
        
        # Rebuild thumbnail_map from config
        for thumbnail in self.config.get_all_thumbnails():
            hwnd = thumbnail.get('window_hwnd')
            thumbnail_id = thumbnail.get('id')
            if hwnd and thumbnail_id:
                self.thumbnail_map[hwnd] = thumbnail_id
        
        # Setup callbacks
        self.engine.on_alert = self._on_alert
        self.engine.on_region_change = self._on_region_change
        self.engine.on_window_lost = self._on_window_lost
    
    def _pil_to_dpg_texture(self, pil_image: Image.Image, width: int, height: int) -> np.ndarray:
        """Convert PIL image to Dear PyGui texture format"""
        pil_image = pil_image.resize((width, height), Image.Resampling.LANCZOS)
        if pil_image.mode != 'RGBA':
            pil_image = pil_image.convert('RGBA')
        img_array = np.array(pil_image).astype('float32') / 255.0
        return img_array
    
    def _build_ui(self) -> None:
        """Build main UI"""
        dpg.create_context()
        
        # Setup viewport
        dpg.create_viewport(title="ScreenAlert v2.0 - Multibox Monitor (GPU-Accelerated)", 
                           width=1400, height=900)
        dpg.setup_dearpygui()
        
        # Apply dark theme
        with dpg.theme() as global_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5)
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 5)
                dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 5)
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (32, 32, 32))
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (40, 40, 40))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (50, 50, 50))
                dpg.add_theme_color(dpg.mvThemeCol_Button, (60, 60, 60))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (70, 70, 70))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (80, 80, 80))
        dpg.bind_theme(global_theme)
        
        # Main window
        with dpg.window(label="ScreenAlert", tag="primary_window", no_title_bar=True):
            # Menu bar
            with dpg.menu_bar():
                with dpg.menu(label="File"):
                    dpg.add_menu_item(label="Settings...", callback=self._show_settings)
                    dpg.add_separator()
                    dpg.add_menu_item(label="Exit", callback=self._on_exit)
                with dpg.menu(label="Help"):
                    dpg.add_menu_item(label="About", callback=self._show_about)
            
            # Control panel
            with dpg.group(horizontal=True):
                dpg.add_button(label="➕ Add Window", callback=self._add_window, width=120)
                dpg.add_button(label="▶ Start Monitoring", tag="btn_start",
                             callback=self._start_monitoring, width=140)
                dpg.add_button(label="⏸ Pause All", tag="btn_pause",
                             callback=self._pause_monitoring, width=120, enabled=False)
                dpg.add_button(label="🔧 Add Region", callback=self._add_region, width=120)
                dpg.add_button(label="❌ Remove Region", callback=self._remove_region, width=140)
                dpg.add_button(label="❌ Remove Window", callback=self._remove_window, width=150)
            
            dpg.add_separator()
            
            # Main content area
            with dpg.group(horizontal=True):
                # Left: Window tree
                with dpg.child_window(width=280, tag="tree_panel"):
                    dpg.add_text("Windows", color=(100, 200, 255))
                    dpg.add_separator()
                    dpg.add_text("Loading...", tag="tree_content")
                
                # Right: Region details
                with dpg.child_window(tag="detail_panel"):
                    # Window info header
                    with dpg.child_window(height=150, tag="info_panel"):
                        dpg.add_text("Window Info", color=(100, 200, 255))
                        dpg.add_separator()
                        dpg.add_text("No window selected", tag="window_title")
                        dpg.add_text("", tag="window_hwnd")
                        dpg.add_text("Regions: 0", tag="window_regions")
                    
                    dpg.add_separator()
                    
                    # Regions container with scrolling
                    with dpg.child_window(tag="region_container"):
                        dpg.add_text("Select a window or click 'Add Window' to begin",
                                   tag="no_regions_text", color=(150, 150, 150))
            
            # Status bar
            dpg.add_separator()
            dpg.add_text("Ready - GPU-accelerated rendering active", 
                        tag="status_bar", color=(100, 200, 100))
        
        # Load initial window list
        self._update_window_tree()
    
    def _get_status_color(self, status: str) -> tuple:
        """Get color tuple for status"""
        colors = {
            "alert": (231, 76, 60),      # Red
            "warning": (243, 156, 18),    # Orange/Yellow
            "paused": (52, 152, 219),     # Blue
            "unavailable": (44, 62, 80),  # Dark blue
            "ok": (46, 204, 113)          # Green
        }
        return colors.get(status, (150, 150, 150))
    
    def _update_window_tree(self) -> None:
        """Update window tree display"""
        # Clear existing tree
        if dpg.does_item_exist("tree_content"):
            dpg.delete_item("tree_content")
        
        thumbnails = self.config.get_all_thumbnails()
        
        with dpg.group(parent="tree_panel", tag="tree_content"):
            if not thumbnails:
                dpg.add_text("No windows added yet", color=(150, 150, 150))
                dpg.add_text("Click '➕ Add Window'", color=(150, 150, 150))
                return
            
            # "All" root node
            if dpg.add_button(label="📁 All Windows", tag="tree_all",
                            callback=lambda: self._select_view("all"), width=-1):
                pass
            
            dpg.add_separator()
            
            # Individual windows
            for thumbnail in thumbnails:
                thumbnail_id = thumbnail.get("id")
                title = thumbnail.get("window_title", "Unknown")
                regions = thumbnail.get("monitored_regions", [])
                
                label = f"🪟 {title} ({len(regions)} regions)"
                dpg.add_button(label=label, tag=f"tree_{thumbnail_id}",
                             callback=lambda s, a, u=thumbnail_id: self._select_view(u),
                             width=-1)
    
    def _select_view(self, view_id: str) -> None:
        """Select a window or 'all' view"""
        if view_id == "all":
            self.show_all_regions = True
            self.selected_thumbnail_id = None
            self._render_all_regions()
        else:
            self.show_all_regions = False
            self.selected_thumbnail_id = view_id
            self._render_window_detail(view_id)
    
    def _render_all_regions(self) -> None:
        """Render all regions from all windows"""
        # Clear region container
        if dpg.does_item_exist("region_container"):
            dpg.delete_item("region_container", children_only=True)
        
        thumbnails = self.config.get_all_thumbnails()
        total_regions = sum(len(t.get("monitored_regions", [])) for t in thumbnails)
        
        # Update info panel
        dpg.set_value("window_title", "All Windows")
        dpg.set_value("window_hwnd", "")
        dpg.set_value("window_regions", f"Total Regions: {total_regions}")
        
        if total_regions == 0:
            with dpg.group(parent="region_container"):
                dpg.add_text("No regions configured yet", color=(150, 150, 150))
                dpg.add_text("Select a window and click '🔧 Add Region'", color=(150, 150, 150))
            return
        
        # Render all regions
        for thumbnail in thumbnails:
            thumbnail_id = thumbnail.get("id")
            window_title = thumbnail.get("window_title", "Unknown")
            regions = thumbnail.get("monitored_regions", [])
            
            if not regions:
                continue
            
            # Window header
            with dpg.group(parent="region_container"):
                dpg.add_text(f"── {window_title} ──", color=(100, 200, 255))
                dpg.add_spacer(height=5)
            
            # Render each region
            for region in regions:
                region_id = region.get("id")
                if region_id:
                    self._render_region_card(thumbnail_id, region_id, region, window_title)
    
    def _render_window_detail(self, thumbnail_id: str) -> None:
        """Render details for a specific window"""
        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if not thumbnail:
            return
        
        # Clear region container
        if dpg.does_item_exist("region_container"):
            dpg.delete_item("region_container", children_only=True)
        
        title = thumbnail.get("window_title", "Unknown")
        hwnd = thumbnail.get("window_hwnd")
        regions = thumbnail.get("monitored_regions", [])
        
        # Update info panel
        dpg.set_value("window_title", f"Window: {title}")
        dpg.set_value("window_hwnd", f"HWND: {hwnd}")
        dpg.set_value("window_regions", f"Regions: {len(regions)}")
        
        if not regions:
            with dpg.group(parent="region_container"):
                dpg.add_text("No regions configured for this window", color=(150, 150, 150))
                dpg.add_text("Click '🔧 Add Region' to add a monitoring region", color=(150, 150, 150))
            return
        
        # Render each region
        for region in regions:
            region_id = region.get("id")
            if region_id:
                self._render_region_card(thumbnail_id, region_id, region)
    
    def _render_region_card(self, thumbnail_id: str, region_id: str, region: Dict, window_title: str = None) -> None:
        """Render a single region monitoring card - GPU accelerated"""
        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if not thumbnail:
            return
        
        with dpg.group(parent="region_container", horizontal=True):
            # Status pill (left)
            status = self.region_statuses.get(thumbnail_id, {}).get(region_id, "ok")
            status_color = self._get_status_color(status)
            
            with dpg.child_window(width=100, height=190):
                dpg.add_text(status.upper(), tag=f"status_pill_{region_id}",
                           color=status_color)
            
            # Thumbnail (center)
            hwnd = thumbnail.get("window_hwnd")
            window_image = None
            if hwnd:
                window_image = self.engine.cache_manager.get(hwnd)
            
            if window_image:
                try:
                    region_image = ImageProcessor.crop_region(window_image, 
                                                             region.get("rect", (0, 0, 0, 0)))
                    texture_data = self._pil_to_dpg_texture(region_image, 360, 180)
                    
                    # Create or update texture
                    texture_tag = f"texture_{region_id}"
                    with dpg.texture_registry():
                        if not dpg.does_item_exist(texture_tag):
                            dpg.add_raw_texture(width=360, height=180, 
                                              default_value=texture_data,
                                              format=dpg.mvFormat_Float_rgba,
                                              tag=texture_tag)
                        else:
                            dpg.set_value(texture_tag, texture_data)
                    
                    dpg.add_image(texture_tag, width=360, height=180,
                                tag=f"image_{region_id}")
                except Exception as e:
                    logger.error(f"Error creating region image: {e}", exc_info=True)
                    with dpg.child_window(width=360, height=190):
                        dpg.add_text("Error loading image")
            else:
                with dpg.child_window(width=360, height=190):
                    dpg.add_text("No image available", color=(150, 150, 150))
            
            # Controls (right)
            with dpg.child_window(width=180):
                region_name = region.get("name", "Region")
                dpg.add_input_text(default_value=region_name, 
                                 tag=f"name_{region_id}",
                                 width=-1,
                                 callback=lambda s, a: self._save_region_name(
                                     thumbnail_id, region_id, a))
                
                dpg.add_spacer(height=5)
                
                dpg.add_button(label="⏸ Pause", tag=f"pause_btn_{region_id}",
                             callback=lambda: self._toggle_region_pause(region_id),
                             width=-1)
                
                dpg.add_spacer(height=5)
                
                dpg.add_text(status.upper(), tag=f"status_label_{region_id}",
                           color=status_color)
        
        dpg.add_separator(parent="region_container")
    
    def _update_region_display(self, thumbnail_id: str, region_id: str) -> None:
        """Update a single region's display - GPU accelerated, zero flicker"""
        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if not thumbnail:
            return
        
        region = self.config.get_region(thumbnail_id, region_id)
        if not region:
            return
        
        hwnd = thumbnail.get("window_hwnd")
        if not hwnd:
            return
        
        window_image = self.engine.cache_manager.get(hwnd)
        if not window_image:
            return
        
        try:
            # Update thumbnail texture - GPU accelerated!
            region_image = ImageProcessor.crop_region(window_image, 
                                                     region.get("rect", (0, 0, 0, 0)))
            texture_data = self._pil_to_dpg_texture(region_image, 360, 180)
            texture_tag = f"texture_{region_id}"
            
            if dpg.does_item_exist(texture_tag):
                dpg.set_value(texture_tag, texture_data)
            
            # Update status colors
            status = self.region_statuses.get(thumbnail_id, {}).get(region_id, "ok")
            status_color = self._get_status_color(status)
            
            if dpg.does_item_exist(f"status_pill_{region_id}"):
                dpg.set_value(f"status_pill_{region_id}", status.upper())
                dpg.configure_item(f"status_pill_{region_id}", color=status_color)
            
            if dpg.does_item_exist(f"status_label_{region_id}"):
                dpg.set_value(f"status_label_{region_id}", status.upper())
                dpg.configure_item(f"status_label_{region_id}", color=status_color)
            
        except Exception as e:
            logger.error(f"Error updating region display: {e}", exc_info=True)
    
    def _on_alert(self, thumbnail_id: str, region_id: str, region_name: str) -> None:
        """Handle alert event - instant GPU update, no flicker"""
        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if thumbnail:
            title = thumbnail.get('window_title', 'Unknown')
            logger.info(f"[ALERT] {title} - {region_name}")
            
            # Update status
            if thumbnail_id not in self.region_statuses:
                self.region_statuses[thumbnail_id] = {}
            self.region_statuses[thumbnail_id][region_id] = "alert"
            
            # Update display immediately - GPU handles it smoothly!
            self._update_region_display(thumbnail_id, region_id)
            
            # Update status bar
            dpg.set_value("status_bar", f"🚨 ALERT: {title} - {region_name} changed!")
            dpg.configure_item("status_bar", color=(231, 76, 60))
            
            # TTS in background thread
            if self.tts_engine:
                def speak_alert():
                    try:
                        message = f"Alert! {title}, {region_name}"
                        self.tts_engine.say(message)
                        self.tts_engine.runAndWait()
                    except Exception as e:
                        logger.warning(f"TTS error: {e}")
                threading.Thread(target=speak_alert, daemon=True).start()
    
    def _on_region_change(self, thumbnail_id: str, region_id: str) -> None:
        """Handle region change - instant GPU update, no flicker"""
        if thumbnail_id not in self.region_statuses:
            self.region_statuses[thumbnail_id] = {}
        self.region_statuses[thumbnail_id][region_id] = "warning"
        
        # Update display immediately - GPU accelerated!
        self._update_region_display(thumbnail_id, region_id)
    
    def _on_window_lost(self, thumbnail_id: str, window_title: str) -> None:
        """Handle lost window"""
        logger.warning(f"Window lost: {window_title}")
        dpg.set_value("status_bar", f"⚠ Window lost: {window_title}")
        dpg.configure_item("status_bar", color=(243, 156, 18))
    
    # Window management methods
    def _add_window(self):
        """Add a new window - opens selection dialog"""
        def on_select(sender, app_data, user_data):
            hwnd, title = user_data
            
            # Check for duplicates
            if hwnd in self.thumbnail_map:
                logger.warning(f"Window '{title}' already being monitored")
                dpg.set_value("status_bar", f"⚠ Window '{title}' is already being monitored")
                return
            
            try:
                thumbnail_id = self.engine.add_thumbnail(window_title=title, window_hwnd=hwnd)
                if thumbnail_id:
                    self.thumbnail_map[hwnd] = thumbnail_id
                    self._update_window_tree()
                    dpg.set_value("status_bar", f"✓ Added: {title}")
                    dpg.configure_item("status_bar", color=(46, 204, 113))
            except Exception as e:
                logger.error(f"Error adding window: {e}", exc_info=True)
                dpg.set_value("status_bar", f"✗ Error adding window: {e}")
                dpg.configure_item("status_bar", color=(231, 76, 60))
        
        # Show simple window picker
        windows = self.window_manager.list_windows()
        
        if dpg.does_item_exist("window_picker"):
            dpg.delete_item("window_picker")
        
        with dpg.window(label="Select Window", modal=True, tag="window_picker", 
                       width=500, height=400, pos=[200, 100]):
            dpg.add_text("Select a window to monitor:")
            dpg.add_separator()
            
            for hwnd, title in windows:
                dpg.add_button(label=title, callback=on_select, 
                             user_data=(hwnd, title), width=-1)
    
    def _remove_window(self):
        """Remove selected window"""
        if not self.selected_thumbnail_id:
            dpg.set_value("status_bar", "⚠ Select a window first")
            return
        
        thumbnail = self.config.get_thumbnail(self.selected_thumbnail_id)
        if not thumbnail:
            return
        
        title = thumbnail.get("window_title", "Unknown")
        hwnd = thumbnail.get("window_hwnd")
        
        try:
            self.engine.remove_thumbnail(self.selected_thumbnail_id)
            self.config.remove_thumbnail(self.selected_thumbnail_id)
            if hwnd in self.thumbnail_map:
                del self.thumbnail_map[hwnd]
            self.selected_thumbnail_id = None
            self._update_window_tree()
            dpg.set_value("status_bar", f"✓ Removed: {title}")
            dpg.configure_item("status_bar", color=(46, 204, 113))
        except Exception as e:
            logger.error(f"Error removing window: {e}", exc_info=True)
    
    def _add_region(self):
        """Add region to selected window"""
        dpg.set_value("status_bar", "⚠ Region selection not yet implemented in DPG version")
        dpg.configure_item("status_bar", color=(243, 156, 18))
    
    def _remove_region(self):
        """Remove region from selected window"""
        dpg.set_value("status_bar", "⚠ Region removal not yet implemented in DPG version")
        dpg.configure_item("status_bar", color=(243, 156, 18))
    
    def _start_monitoring(self):
        """Start monitoring"""
        thumbnails = self.config.get_all_thumbnails()
        if not thumbnails:
            dpg.set_value("status_bar", "⚠ Add at least one window first")
            dpg.configure_item("status_bar", color=(243, 156, 18))
            return
        
        try:
            self.engine.start()
            self.monitoring_active = True
            dpg.configure_item("btn_start", enabled=False)
            dpg.configure_item("btn_pause", enabled=True)
            dpg.set_value("status_bar", "✓ Monitoring started - GPU rendering active")
            dpg.configure_item("status_bar", color=(46, 204, 113))
        except Exception as e:
            logger.error(f"Error starting monitoring: {e}", exc_info=True)
            dpg.set_value("status_bar", f"✗ Error: {e}")
            dpg.configure_item("status_bar", color=(231, 76, 60))
    
    def _pause_monitoring(self):
        """Pause monitoring"""
        try:
            self.engine.set_paused(True)
            self.monitoring_active = False
            dpg.configure_item("btn_start", enabled=True)
            dpg.configure_item("btn_pause", enabled=False)
            dpg.set_value("status_bar", "⏸ Monitoring paused")
            dpg.configure_item("status_bar", color=(243, 156, 18))
        except Exception as e:
            logger.error(f"Error pausing: {e}", exc_info=True)
    
    def _save_region_name(self, thumbnail_id: str, region_id: str, new_name: str):
        """Save region name change"""
        if new_name.strip():
            self.config.update_region(thumbnail_id, region_id, {"name": new_name.strip()})
            self.config.save()
    
    def _toggle_region_pause(self, region_id: str):
        """Toggle pause for a region"""
        monitor = self.engine.monitoring_engine.get_monitor(region_id)
        if monitor:
            paused = monitor.toggle_pause()
            if dpg.does_item_exist(f"pause_btn_{region_id}"):
                dpg.set_value(f"pause_btn_{region_id}", "▶ Resume" if paused else "⏸ Pause")
    
    def _show_settings(self):
        """Show settings dialog"""
        dpg.set_value("status_bar", "ℹ Settings dialog not yet implemented")
    
    def _show_about(self):
        """Show about dialog"""
        if dpg.does_item_exist("about_window"):
            dpg.delete_item("about_window")
        
        with dpg.window(label="About ScreenAlert", modal=True, tag="about_window",
                       width=400, height=200, pos=[400, 300]):
            dpg.add_text("ScreenAlert v2.0", color=(100, 200, 255))
            dpg.add_text("GPU-Accelerated Multi-Window Monitor")
            dpg.add_separator()
            dpg.add_text("Built with Dear PyGui for flicker-free rendering")
            dpg.add_text("Real-time change detection with color-coded alerts")
            dpg.add_separator()
            dpg.add_button(label="Close", callback=lambda: dpg.delete_item("about_window"))
    
    def _on_exit(self):
        """Handle exit"""
        try:
            if self.monitoring_active:
                self.engine.stop()
            self.config.save()
        except Exception as e:
            logger.error(f"Error on exit: {e}")
        dpg.stop_dearpygui()
    
    def run(self) -> None:
        """Run main window - GPU-accelerated render loop"""
        self._build_ui()
        dpg.show_viewport()
        dpg.set_primary_window("primary_window", True)
        
        logger.info("Starting GPU-accelerated render loop - 60fps with zero flicker!")
        
        # Main render loop - GPU handles all updates smoothly!
        while dpg.is_dearpygui_running():
            dpg.render_dearpygui_frame()
        
        dpg.destroy_context()
        logger.info("Dear PyGui context destroyed, application closed")
