"""Demo of Dear PyGui for ScreenAlert - shows flicker-free updates"""

import dearpygui.dearpygui as dpg
import numpy as np
from PIL import Image
import random
import time

def create_random_texture(width, height):
    """Create a random image texture"""
    img = Image.new('RGBA', (width, height))
    pixels = []
    for y in range(height):
        for x in range(width):
            r = random.randint(0, 255)
            g = random.randint(0, 255)
            b = random.randint(0, 255)
            pixels.append((r, g, b, 255))
    img.putdata(pixels)
    
    # Convert to DPG format
    img_array = np.array(img).astype('float32') / 255.0
    return img_array

def update_textures():
    """Update all textures - demonstrates GPU-accelerated updates"""
    for i in range(4):
        texture_tag = f"texture_{i}"
        texture_data = create_random_texture(360, 180)
        dpg.set_value(texture_tag, texture_data)
    
    # Update status colors
    colors = [(231, 76, 60), (243, 156, 18), (52, 152, 219), (46, 204, 113)]
    for i in range(4):
        color = random.choice(colors)
        dpg.configure_item(f"status_{i}", color=color)
        dpg.configure_item(f"pill_{i}", color=color)

def main():
    dpg.create_context()
    
    # Setup viewport
    dpg.create_viewport(title="Dear PyGui Demo - Flicker-Free Updates", 
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
    
    # Create textures
    with dpg.texture_registry():
        for i in range(4):
            texture_data = create_random_texture(360, 180)
            dpg.add_raw_texture(width=360, height=180, 
                              default_value=texture_data,
                              format=dpg.mvFormat_Float_rgba,
                              tag=f"texture_{i}")
    
    # Main window
    with dpg.window(label="Demo", tag="primary_window"):
        dpg.add_text("Watch these update every 1000ms - NO FLICKER!", 
                    color=(100, 200, 255))
        dpg.add_text("This is GPU-accelerated rendering", color=(150, 150, 150))
        dpg.add_separator()
        
        dpg.add_button(label="🔄 Update All (simulates monitoring refresh)",
                      callback=update_textures)
        
        dpg.add_separator()
        
        # Create 4 region cards
        for i in range(4):
            with dpg.group(horizontal=True):
                # Status pill
                with dpg.child_window(width=100, height=180):
                    dpg.add_text(f"STATUS {i}", tag=f"pill_{i}",
                               color=(46, 204, 113))
                
                # Thumbnail
                dpg.add_image(f"texture_{i}", width=360, height=180)
                
                # Controls
                with dpg.child_window(width=150):
                    dpg.add_text(f"Region {i+1}")
                    dpg.add_button(label="Pause")
                    dpg.add_text("OK", tag=f"status_{i}",
                               color=(46, 204, 113))
            
            if i < 3:
                dpg.add_separator()
    
    dpg.show_viewport()
    dpg.set_primary_window("primary_window", True)
    
    # Auto-update loop
    last_update = time.time()
    while dpg.is_dearpygui_running():
        # Auto update every 1 second
        if time.time() - last_update > 1.0:
            update_textures()
            last_update = time.time()
        
        dpg.render_dearpygui_frame()
    
    dpg.destroy_context()

if __name__ == "__main__":
    main()
