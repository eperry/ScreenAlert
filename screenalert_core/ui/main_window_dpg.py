"""Main window UI for ScreenAlert using Dear PyGui (GPU-accelerated)"""

import logging
import dearpygui.dearpygui as dpg
from typing import Optional, Dict, List
import win32gui
import pyttsx3
from PIL import Image
import numpy as np

from screenalert_core.screening_engine import ScreenAlertEngine
from screenalert_core.ui.window_selector_dialog import WindowSelectorDialog
from screenalert_core.core.image_processor import ImageProcessor

logger = logging.getLogger(__name__)


class ScreenAlertMainWindowDPG:
    """Main control window using Dear PyGui for flicker-free updates"""
    
    def __init__(self, engine: ScreenAlertEngine):
        """Initialize main window
        
        Args:
            engine: ScreenAlertEngine instance
        """
        self.engine = engine
        self.config = engine.config
        self.window_manager = engine.window_manager
        self.thumbnail_map = {}  # hwnd -> thumbnail_id mapping
        self.selected_thumbnail_id: Optional[str] = None
        self.region_statuses: Dict[str, Dict[str, str]] = {}
        self.region_textures: Dict[str, int] = {}  # region_id -> texture_id
        self.region_to_thumbnail: Dict[str, str] = {}
        self.show_all_regions = True
        
        # Dear PyGui widget tags
        self.window_tree_tag = "window_tree"
        self.region_container_tag = "region_container"
        self.status_bar_tag = "status_bar"
        
        # Initialize text-to-speech
        try:
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty('rate', 150)
        except Exception as e:
            logger.warning(f"Could not initialize TTS: {e}")
            self.tts_engine = None
        
        # Setup callbacks
        self.engine.on_alert = self._on_alert
        self.engine.on_region_change = self._on_region_change
        self.engine.on_window_lost = self._on_window_lost
    
    def _pil_to_dpg_texture(self, pil_image: Image.Image, width: int, height: int) -> np.ndarray:
        """Convert PIL image to Dear PyGui texture format"""
        # Resize image
        pil_image = pil_image.resize((width, height), Image.Resampling.LANCZOS)
        # Convert to RGBA
        if pil_image.mode != 'RGBA':
            pil_image = pil_image.convert('RGBA')
        # Convert to numpy array and normalize to 0-1 range
        img_array = np.array(pil_image).astype('float32') / 255.0
        return img_array
    
    def _build_ui(self) -> None:
        """Build main UI"""
        dpg.create_context()
        
        # Setup viewport
        dpg.create_viewport(title="ScreenAlert v2.0 - Multibox Monitor", 
                           width=1200, height=800)
        dpg.setup_dearpygui()
        
        # Apply dark theme
        with dpg.theme() as global_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5)
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 5)
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (32, 32, 32))
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (40, 40, 40))
        dpg.bind_theme(global_theme)
        
        # Main window
        with dpg.window(label="ScreenAlert", tag="primary_window"):
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
                dpg.add_button(label="➕ Add Window", callback=self._add_window)
                dpg.add_button(label="▶ Start Monitoring", tag="btn_start",
                             callback=self._start_monitoring)
                dpg.add_button(label="⏸ Pause All", tag="btn_pause",
                             callback=self._pause_monitoring, enabled=False)
                dpg.add_button(label="🔧 Add Region", callback=self._add_region)
                dpg.add_button(label="❌ Remove Region", callback=self._remove_region)
                dpg.add_button(label="❌ Remove Window", callback=self._remove_thumbnail)
            
            dpg.add_separator()
            
            # Main content area
            with dpg.group(horizontal=True):
                # Left: Window tree
                with dpg.child_window(width=250, tag="tree_panel"):
                    dpg.add_text("Windows", color=(100, 200, 255))
                    dpg.add_separator()
                    with dpg.tree_node(label="All", tag=self.window_tree_tag, 
                                      default_open=True, selectable=True,
                                      callback=self._on_tree_select):
                        pass
                
                # Right: Region details
                with dpg.child_window(tag="detail_panel"):
                    # Window info header
                    with dpg.child_window(height=150, tag="info_panel"):
                        dpg.add_text("Window Info", color=(100, 200, 255))
                        dpg.add_separator()
                        dpg.add_text("Title:", tag="window_title")
                        dpg.add_text("HWND:", tag="window_hwnd")
                        dpg.add_text("Regions: 0", tag="window_regions")
                    
                    dpg.add_separator()
                    
                    # Regions container
                    with dpg.child_window(tag=self.region_container_tag):
                        dpg.add_text("No regions to display", tag="no_regions_text")
            
            # Status bar
            dpg.add_separator()
            dpg.add_text("Ready", tag=self.status_bar_tag, color=(150, 150, 150))
    
    def _render_region_card(self, thumbnail_id: str, region_id: str, region: Dict, 
                           window_image, window_title: str = None) -> None:
        """Render a region monitoring card using Dear PyGui"""
        with dpg.group(horizontal=True, parent=self.region_container_tag):
            # Status pill (left)
            status = self.region_statuses.get(thumbnail_id, {}).get(region_id, "ok")
            status_color = self._get_status_color(status)
            with dpg.child_window(width=100, height=180):
                dpg.add_text(status.upper(), tag=f"status_pill_{region_id}",
                           color=status_color)
            
            # Thumbnail (center)
            if window_image:
                try:
                    region_image = ImageProcessor.crop_region(window_image, 
                                                             region.get("rect", (0, 0, 0, 0)))
                    texture_data = self._pil_to_dpg_texture(region_image, 360, 180)
                    
                    # Create or update texture
                    texture_tag = f"texture_{region_id}"
                    if dpg.does_item_exist(texture_tag):
                        dpg.set_value(texture_tag, texture_data)
                    else:
                        with dpg.texture_registry():
                            dpg.add_raw_texture(width=360, height=180, 
                                              default_value=texture_data,
                                              format=dpg.mvFormat_Float_rgba,
                                              tag=texture_tag)
                    
                    dpg.add_image(texture_tag, width=360, height=180,
                                tag=f"image_{region_id}")
                except Exception as e:
                    logger.error(f"Error creating region image: {e}")
                    with dpg.child_window(width=360, height=180):
                        dpg.add_text("No image", tag=f"image_{region_id}")
            else:
                with dpg.child_window(width=360, height=180):
                    dpg.add_text("No image", tag=f"image_{region_id}")
            
            # Controls (right)
            with dpg.child_window(width=150):
                region_name = region.get("name", "Region")
                dpg.add_input_text(default_value=region_name, 
                                 tag=f"name_{region_id}",
                                 callback=lambda s, a: self._save_region_name(
                                     thumbnail_id, region_id, a))
                dpg.add_button(label="Pause", tag=f"pause_btn_{region_id}",
                             callback=lambda: self._toggle_region_pause(region_id))
                dpg.add_text(status.upper(), tag=f"status_label_{region_id}",
                           color=status_color)
    
    def _get_status_color(self, status: str) -> tuple:
        """Get color tuple for status"""
        colors = {
            "alert": (231, 76, 60),      # Red
            "warning": (243, 156, 18),    # Yellow
            "paused": (52, 152, 219),     # Blue
            "unavailable": (44, 62, 80),  # Dark blue
            "ok": (46, 204, 113)          # Green
        }
        return colors.get(status, (150, 150, 150))
    
    def _update_region_display(self, thumbnail_id: str, region_id: str) -> None:
        """Update a single region's display - GPU accelerated, no flicker"""
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
            # Update thumbnail texture
            region_image = ImageProcessor.crop_region(window_image, 
                                                     region.get("rect", (0, 0, 0, 0)))
            texture_data = self._pil_to_dpg_texture(region_image, 360, 180)
            texture_tag = f"texture_{region_id}"
            
            if dpg.does_item_exist(texture_tag):
                dpg.set_value(texture_tag, texture_data)
            
            # Update status
            status = self.region_statuses.get(thumbnail_id, {}).get(region_id, "ok")
            status_color = self._get_status_color(status)
            
            if dpg.does_item_exist(f"status_pill_{region_id}"):
                dpg.set_value(f"status_pill_{region_id}", status.upper())
                dpg.configure_item(f"status_pill_{region_id}", color=status_color)
            
            if dpg.does_item_exist(f"status_label_{region_id}"):
                dpg.set_value(f"status_label_{region_id}", status.upper())
                dpg.configure_item(f"status_label_{region_id}", color=status_color)
            
            logger.debug(f"[DPG UPDATE] Updated region {region_id} - GPU accelerated")
        except Exception as e:
            logger.error(f"Error updating region display: {e}", exc_info=True)
    
    def _on_alert(self, thumbnail_id: str, region_id: str, region_name: str) -> None:
        """Handle alert event"""
        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if thumbnail:
            title = thumbnail.get('window_title', 'Unknown')
            logger.info(f"[ALERT] {title} - {region_name}")
            
            # Update status
            if thumbnail_id not in self.region_statuses:
                self.region_statuses[thumbnail_id] = {}
            self.region_statuses[thumbnail_id][region_id] = "alert"
            
            # Update display immediately (GPU accelerated - no flicker!)
            self._update_region_display(thumbnail_id, region_id)
            
            # Update status bar
            dpg.set_value(self.status_bar_tag, f"🚨 ALERT: {title} - {region_name} changed!")
            
            # TTS
            if self.tts_engine:
                try:
                    message = f"Alert! {title}, {region_name}"
                    self.tts_engine.say(message)
                    self.tts_engine.runAndWait()
                except Exception as e:
                    logger.warning(f"TTS error: {e}")
    
    def _on_region_change(self, thumbnail_id: str, region_id: str) -> None:
        """Handle region change"""
        if thumbnail_id not in self.region_statuses:
            self.region_statuses[thumbnail_id] = {}
        self.region_statuses[thumbnail_id][region_id] = "warning"
        
        # Update display immediately (GPU accelerated - no flicker!)
        self._update_region_display(thumbnail_id, region_id)
    
    def _on_window_lost(self, thumbnail_id: str, window_title: str) -> None:
        """Handle lost window"""
        logger.warning(f"Window lost: {window_title}")
        dpg.set_value(self.status_bar_tag, f"Window lost: {window_title}")
    
    # Placeholder methods for other functionality
    def _add_window(self): pass
    def _start_monitoring(self): pass
    def _pause_monitoring(self): pass
    def _add_region(self): pass
    def _remove_region(self): pass
    def _remove_thumbnail(self): pass
    def _show_settings(self): pass
    def _show_about(self): pass
    def _on_tree_select(self): pass
    def _save_region_name(self, thumbnail_id, region_id, new_name): pass
    def _toggle_region_pause(self, region_id): pass
    
    def _on_exit(self):
        """Handle window close"""
        try:
            self.engine.stop()
            self.config.save()
        except Exception as e:
            logger.error(f"Error stopping: {e}")
        dpg.stop_dearpygui()
    
    def run(self) -> None:
        """Run main window"""
        self._build_ui()
        dpg.show_viewport()
        dpg.set_primary_window("primary_window", True)
        
        # Main render loop - GPU accelerated!
        while dpg.is_dearpygui_running():
            dpg.render_dearpygui_frame()
        
        dpg.destroy_context()
