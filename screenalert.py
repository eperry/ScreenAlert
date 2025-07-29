# -*- coding: utf-8 -*-
import pyautogui
from PIL import ImageTk, Image, ImageDraw, ImageFont, ImageFilter
import tkinter as tk
from tkinter import ttk
import json
import os
from skimage.metrics import structural_similarity as ssim
import numpy as np
import tkinter.filedialog as fd
import tkinter.colorchooser as cc
import tkinter.simpledialog as sd
import tkinter.messagebox as msgbox
import platform
import time
import cv2

# Application Information
APP_VERSION = "2.1.0"
APP_AUTHOR = "Ed Perry"
APP_REPO_URL = "https://github.com/eperry/ScreenAlert"

class ToolTip:
    """
    Create a tooltip for a given widget
    """
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.tipwindow = None

    def enter(self, event=None):
        self.showtip()

    def leave(self, event=None):
        self.hidetip()

    def showtip(self):
        if self.tipwindow or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert") if hasattr(self.widget, 'bbox') else (0, 0, 0, 0)
        x = x + self.widget.winfo_rootx() + 20
        y = y + cy + self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                      background="#1a1a1a", foreground="#ff9500", relief=tk.SOLID, borderwidth=2,
                      font=("Segoe UI", "9", "normal"), wraplength=300)
        label.pack(ipadx=5, ipady=3)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

def create_tooltip(widget, text):
    """Helper function to create tooltips easily"""
    return ToolTip(widget, text)
import imagehash
import win32gui
import win32ui
import win32con
import win32api
from ctypes import windll


# Platform-specific imports
if platform.system() == "Windows":
    import winsound
    try:
        import pyttsx3
    except ImportError:
        print("pyttsx3 not installed. TTS will not work.")
        pyttsx3 = None

CONFIG_FILE = "screenalert_config.json"

def get_window_list():
    """Get list of all visible windows with titles"""
    windows = []
    
    def enum_window_callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            window_title = win32gui.GetWindowText(hwnd)
            if window_title:  # Only include windows with titles
                class_name = win32gui.GetClassName(hwnd)
                rect = win32gui.GetWindowRect(hwnd)
                width = rect[2] - rect[0]
                height = rect[3] - rect[1]
                
                # Filter out very small windows (likely system windows)
                if width > 100 and height > 100:
                    windows.append({
                        'hwnd': hwnd,
                        'title': window_title,
                        'class_name': class_name,
                        'rect': rect,
                        'size': (width, height)
                    })
    
    win32gui.EnumWindows(enum_window_callback, windows)
    return windows

def capture_window(hwnd):
    """Capture screenshot of a specific window"""
    try:
        # First check if window is still valid
        if not win32gui.IsWindow(hwnd):
            # Silently return None for invalid windows (reduces log spam)
            return None
            
        if not win32gui.IsWindowVisible(hwnd):
            # Silently return None for invisible windows
            return None
        
        # Get window rectangle
        rect = win32gui.GetWindowRect(hwnd)
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        
        # Check if window is minimized or has invalid size
        if width <= 0 or height <= 0:
            return None
            
        # Get window device context
        hwndDC = win32gui.GetWindowDC(hwnd)
        mfcDC = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()
        
        # Create bitmap
        saveBitMap = win32ui.CreateBitmap()
        saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
        saveDC.SelectObject(saveBitMap)
        
        # Copy window content to bitmap
        result = windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)
        
        if result:
            # Convert to PIL Image
            bmpinfo = saveBitMap.GetInfo()
            bmpstr = saveBitMap.GetBitmapBits(True)
            
            img = Image.frombuffer(
                'RGB',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1
            )
        else:
            # Fallback to regular screenshot of window area
            img = pyautogui.screenshot(region=(rect[0], rect[1], width, height))
        
        # Cleanup
        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwndDC)
        
        return img
        
    except Exception as e:
        print(f"Failed to capture window {hwnd}: {e}")
        return None

def find_window_by_title(window_title, exact_match=False):
    """Try to find a window by its title with improved matching"""
    windows = get_window_list()
    
    # First try exact match
    for window in windows:
        if window['title'] == window_title:
            return window
    
    # If exact match fails and we're not forcing exact match, try partial matching
    if not exact_match:
        # Try partial match - useful if title changes slightly
        for window in windows:
            if window_title.lower() in window['title'].lower():
                return window
        
        # Try reverse match - see if window title is a subset of our stored title
        # This helps when applications add/remove version numbers or status text
        for window in windows:
            if window['title'].lower() in window_title.lower():
                return window
        
        # Try fuzzy matching for applications that change their titles significantly
        # Look for common words between titles
        title_words = set(window_title.lower().split())
        for window in windows:
            window_words = set(window['title'].lower().split())
            # If at least 50% of words match, consider it a potential match
            if title_words and window_words:
                common_words = title_words.intersection(window_words)
                match_ratio = len(common_words) / max(len(title_words), len(window_words))
                if match_ratio >= 0.5 and len(common_words) >= 2:  # At least 2 words in common
                    return window
    
    return None

def is_window_valid(hwnd):
    """Check if a window handle is still valid and visible"""
    try:
        return win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd)
    except:
        return False

def get_monitor_info():
    """Get information about all monitors"""
    import win32api
    monitors = []
    
    def monitor_enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
        monitors.append({
            'handle': hMonitor,
            'left': lprcMonitor[0],
            'top': lprcMonitor[1], 
            'right': lprcMonitor[2],
            'bottom': lprcMonitor[3],
            'width': lprcMonitor[2] - lprcMonitor[0],
            'height': lprcMonitor[3] - lprcMonitor[1]
        })
        return True
    
    try:
        win32api.EnumDisplayMonitors(None, None, monitor_enum_proc, 0)
    except:
        # Fallback to primary monitor
        monitors = [{
            'handle': 0,
            'left': 0,
            'top': 0,
            'right': 1920,
            'bottom': 1080,
            'width': 1920,
            'height': 1080
        }]
    
    return monitors

def get_windows_by_monitor():
    """Get windows organized by monitor"""
    monitors = get_monitor_info()
    windows_by_monitor = {i: [] for i in range(len(monitors))}
    
    all_windows = get_window_list()
    
    for window in all_windows:
        rect = window['rect']
        window_center_x = (rect[0] + rect[2]) // 2
        window_center_y = (rect[1] + rect[3]) // 2
        
        # Find which monitor this window belongs to
        assigned = False
        for i, monitor in enumerate(monitors):
            if (monitor['left'] <= window_center_x < monitor['right'] and 
                monitor['top'] <= window_center_y < monitor['bottom']):
                windows_by_monitor[i].append(window)
                assigned = True
                break
        
        # If not assigned to any monitor, assign to primary (0)
        if not assigned and windows_by_monitor:
            windows_by_monitor[0].append(window)
    
    return windows_by_monitor, monitors

def create_no_window_image(width=120, height=100, bg_color="#333"):
    """Create an image showing 'No Window Available' with customizable background color"""
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except:
        font = ImageFont.load_default()
    
    text = "No Window\nAvailable"
    
    # Get text dimensions
    if hasattr(draw, "textbbox"):
        lines = text.split('\n')
        text_height = 0
        max_width = 0
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            line_height = bbox[3] - bbox[1]
            text_height += line_height + 2
            max_width = max(max_width, line_width)
    else:
        # Fallback for older PIL versions
        lines = text.split('\n')
        text_height = 0
        max_width = 0
        for line in lines:
            line_width, line_height = font.getsize(line)
            text_height += line_height + 2
            max_width = max(max_width, line_width)
    
    # Center text
    y = (height - text_height) // 2
    for line in text.split('\n'):
        if hasattr(draw, "textbbox"):
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
        else:
            line_width, _ = font.getsize(line)
        x = (width - line_width) // 2
        draw.text((x, y), line, font=font, fill="#999")
        y += 16
    
    return img

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                # Convert old tuple regions to dicts if needed
                new_regions = []
                for r in config.get("regions", []):
                    if isinstance(r, dict):
                        for k in ["sound_file", "sound_enabled", "tts_enabled", "tts_message"]:
                            r.pop(k, None)
                        new_regions.append(r)
                    else:
                        new_regions.append({"rect": r})
                config["regions"] = new_regions
                # Add defaults for all states
                if "highlight_time" not in config:
                    config["highlight_time"] = 5
                if "green_text" not in config:
                    config["green_text"] = "Green"
                if "green_color" not in config:
                    config["green_color"] = "#080"
                if "paused_text" not in config:
                    config["paused_text"] = "Paused"
                if "paused_color" not in config:
                    config["paused_color"] = "#08f"
                if "alert_text" not in config:
                    config["alert_text"] = "Alert"
                if "alert_color" not in config:
                    config["alert_color"] = "#a00"
                if "pause_reminder_interval" not in config:
                    config["pause_reminder_interval"] = 60  # seconds
                if "disabled_text" not in config:
                    config["disabled_text"] = "Disabled"
                if "disabled_color" not in config:
                    config["disabled_color"] = "#fa0"
                if "unavailable_text" not in config:
                    config["unavailable_text"] = "Unavailable"
                if "unavailable_color" not in config:
                    config["unavailable_color"] = "#05f"
                if "target_window" not in config:
                    config["target_window"] = None
                if "window_filter" not in config:
                    config["window_filter"] = ""
                return config
        except Exception as e:
            print(f"Config load failed: {e}, using defaults.")
    return {
        "regions": [],
        "interval": 1000,
        "highlight_time": 5,
        "default_sound": "",
        "default_tts": "Alert {name}",
        "alert_threshold": 0.99,
        "green_text": "Green",
        "green_color": "#080",
        "paused_text": "Paused",
        "paused_color": "#08f",
        "alert_text": "Alert",
        "alert_color": "#a00",
        "disabled_text": "Disabled",
        "disabled_color": "#fa0",
        "unavailable_text": "Unavailable",
        "unavailable_color": "#05f",
        "pause_reminder_interval": 60,
        "target_window": None,
        "window_filter": ""
    }

def save_config(
    regions, interval, highlight_time, default_sound="", default_tts="", alert_threshold=0.99,
    green_text="Green", green_color="#080",
    paused_text="Paused", paused_color="#08f",
    alert_text="Alert", alert_color="#a00",
    disabled_text="Disabled", disabled_color="#fa0",
    unavailable_text="Unavailable", unavailable_color="#05f",
    pause_reminder_interval=60, target_window=None, window_filter=""
):
    serializable_regions = []
    for r in regions:
        r_copy = dict(r)
        r_copy.pop("_diff_img", None)
        serializable_regions.append(r_copy)
    config = {
        "regions": serializable_regions,
        "interval": interval,
        "highlight_time": highlight_time,
        "default_sound": default_sound,
        "default_tts": default_tts,
        "alert_threshold": alert_threshold,
        "green_text": green_text,
        "green_color": green_color,
        "paused_text": paused_text,
        "paused_color": paused_color,
        "alert_text": alert_text,
        "alert_color": alert_color,
        "disabled_text": disabled_text,
        "disabled_color": disabled_color,
        "unavailable_text": unavailable_text,
        "unavailable_color": unavailable_color,
        "pause_reminder_interval": pause_reminder_interval,
        "target_window": target_window,
        "window_filter": window_filter
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

class WindowSelector:
    def __init__(self, master, current_window=None, monitor_id=None, window_filter=""):
        self.selected_window = None
        self.monitor_id = monitor_id
        self.window_filter = window_filter
        self.top = tk.Toplevel(master)
        self.top.title(f"Select Target Window{f' (Monitor {monitor_id + 1})' if monitor_id is not None else ''}")
        self.top.geometry("700x600")
        self.top.transient(master)
        self.top.grab_set()
        
        # Get list of windows organized by monitor
        self.windows_by_monitor, self.monitors = get_windows_by_monitor()
        
        # Create GUI
        frame = ttk.Frame(self.top, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Monitor selection if multiple monitors available
        if len(self.monitors) > 1:
            monitor_frame = ttk.LabelFrame(frame, text="Monitor Selection", padding=5)
            monitor_frame.pack(fill=tk.X, pady=(0, 10))
            
            self.monitor_var = tk.IntVar(value=monitor_id if monitor_id is not None else 0)
            
            for i, monitor in enumerate(self.monitors):
                monitor_text = f"Monitor {i + 1} ({monitor['width']}x{monitor['height']}) at ({monitor['left']}, {monitor['top']})"
                ttk.Radiobutton(monitor_frame, text=monitor_text, variable=self.monitor_var, 
                               value=i, command=self.on_monitor_change).pack(anchor=tk.W)
        
        ttk.Label(frame, text="Select a window to monitor:", font=("Arial", 12, "bold")).pack(pady=(0, 10))
        
        # Create listbox with scrollbar
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("Arial", 10))
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)
        
        # Populate listbox based on selected monitor
        self.populate_window_list()
        
        # Pre-select current window if provided
        if current_window:
            self.preselect_current_window(current_window)
        
        # Window filter controls
        filter_frame = ttk.LabelFrame(frame, text="Window Filter", padding=5)
        filter_frame.pack(fill=tk.X, pady=(10, 10))
        
        filter_control_frame = ttk.Frame(filter_frame)
        filter_control_frame.pack(fill=tk.X)
        
        ttk.Label(filter_control_frame, text="Filter:").pack(side=tk.LEFT, padx=(0, 5))
        self.filter_var = tk.StringVar(value=self.window_filter)
        self.filter_entry = ttk.Entry(filter_control_frame, textvariable=self.filter_var, width=20)
        self.filter_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        # Bind to text changes for auto-refresh
        self.filter_var.trace_add("write", lambda *args: self.populate_window_list())
        
        # Status label for filter
        self.filter_status = ttk.Label(filter_frame, text=f"Current filter: '{self.window_filter}'" if self.window_filter else "No filter applied")
        self.filter_status.pack(pady=(5, 0))
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="Refresh List", command=self.refresh_list).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.RIGHT)
        
        # Single-click to select automatically
        self.listbox.bind("<Button-1>", self.on_single_click)
        # Double-click to select (backup)
        self.listbox.bind("<Double-Button-1>", lambda e: self.select())
    
    def on_monitor_change(self):
        """Handle monitor selection change"""
        self.populate_window_list()
    
    def on_single_click(self, event):
        """Handle single click on listbox to automatically select window"""
        # Small delay to ensure the selection is processed
        self.top.after(100, self.auto_select_on_click)
    
    def auto_select_on_click(self):
        """Automatically select the clicked window after a short delay"""
        selection = self.listbox.curselection()
        if selection and self.current_windows and len(self.current_windows) > 0:
            selected_index = selection[0]
            # Only auto-select if we clicked on a valid window (not on "No windows found" message)
            if selected_index < len(self.current_windows):
                self.select()
    
    def populate_window_list(self):
        """Populate the window list based on selected monitor and filter"""
        self.listbox.delete(0, tk.END)
        
        if hasattr(self, 'monitor_var'):
            selected_monitor = self.monitor_var.get()
        else:
            selected_monitor = self.monitor_id if self.monitor_id is not None else 0
            
        if selected_monitor in self.windows_by_monitor:
            all_windows = self.windows_by_monitor[selected_monitor]
        else:
            all_windows = []
        
        # Apply window filter
        self.current_windows = []
        current_filter = getattr(self, 'filter_var', None)
        filter_text = current_filter.get() if current_filter else self.window_filter
        
        for window in all_windows:
            if not filter_text or filter_text.lower() in window['title'].lower():
                self.current_windows.append(window)
        
        # Populate listbox with filtered windows
        for window in self.current_windows:
            display_text = f"{window['title']} ({window['size'][0]}x{window['size'][1]})"
            self.listbox.insert(tk.END, display_text)
        
        if not self.current_windows:
            if filter_text:
                self.listbox.insert(tk.END, f"No windows found matching filter '{filter_text}'")
            else:
                self.listbox.insert(tk.END, "No windows found on this monitor")
        
        # Update filter status
        if hasattr(self, 'filter_status'):
            if filter_text:
                self.filter_status.config(text=f"Filter: '{filter_text}' ({len(self.current_windows)} windows)")
            else:
                self.filter_status.config(text=f"No filter ({len(self.current_windows)} windows)")
    
    def preselect_current_window(self, current_window):
        """Pre-select the current window if it exists in the list"""
        for i, window in enumerate(self.current_windows):
            if window.get('hwnd') == current_window.get('hwnd'):
                self.listbox.selection_set(i)
                break
    
    def refresh_list(self):
        """Refresh the window list"""
        self.windows_by_monitor, self.monitors = get_windows_by_monitor()
        self.populate_window_list()
    
    def select(self):
        """Select the highlighted window"""
        selection = self.listbox.curselection()
        if selection and self.current_windows:
            selected_index = selection[0]
            if selected_index < len(self.current_windows):
                self.selected_window = self.current_windows[selected_index]
                # Store monitor information with the window
                if hasattr(self, 'monitor_var'):
                    monitor_id = self.monitor_var.get()
                else:
                    monitor_id = self.monitor_id if self.monitor_id is not None else 0
                self.selected_window['monitor_id'] = monitor_id
        self.top.destroy()
    
    def cancel(self):
        """Cancel selection"""
        self.selected_window = None
        self.top.destroy()

class RegionSelector:
    def __init__(self, master, window_img):
        self.region = None
        self.window_img = window_img
        
        self.top = tk.Toplevel(master)
        self.top.title("Select Region")
        self.top.geometry(f"{window_img.width}x{window_img.height}")
        self.top.resizable(False, False)
        self.top.transient(master)
        self.top.grab_set()
        
        # Create canvas with window screenshot as background
        self.canvas = tk.Canvas(self.top, cursor="cross", 
                               width=window_img.width, height=window_img.height)
        self.canvas.pack()
        
        # Display window screenshot
        self.bg_image = ImageTk.PhotoImage(window_img)
        self.canvas.create_image(0, 0, anchor="nw", image=self.bg_image)
        
        self.start_x = self.start_y = self.rect = None
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.top.bind("<Escape>", self.on_escape)
        self.canvas.focus_set()

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y, 
            outline='red', width=2
        )

    def on_drag(self, event):
        if self.start_x is None or self.start_y is None or self.rect is None:
            return
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        if self.start_x is None or self.start_y is None:
            return
        x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
        x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)
        width, height = x2 - x1, y2 - y1
        
        if width > 10 and height > 10:  # Minimum size
            self.region = (x1, y1, width, height)
            self.top.destroy()

    def on_escape(self, event):
        """Handle ESC key to cancel region selection"""
        self.region = None
        self.top.destroy()

    def select(self):
        self.top.wait_window()
        return self.region

def crop_region(img, region):
    left, top, width, height = region
    return img.crop((left, top, left + width, top + height))

def create_rotated_text_image(text, width, height, color="#fff", bgcolor=None, font_size=18):
    img = Image.new("RGBA", (width, height), bgcolor or (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()
    if hasattr(draw, "textbbox"):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    else:
        text_width, text_height = font.getsize(text)
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    draw.text((x, y), text, font=font, fill=color)
    img = img.rotate(90, expand=1)
    return img

def play_pause_reminder_tone():
    """Play a gentle attention-grabbing tone for pause reminders"""
    try:
        if platform.system() == "Windows":
            # Play a gentle two-tone chime using Windows system sounds
            winsound.Beep(800, 200)
            time.sleep(0.1)
            winsound.Beep(600, 300)
        else:
            print("\a")  # ASCII bell character
    except Exception as e:
        print(f"Failed to play pause reminder tone: {e}")
        print("\a")

def play_sound(sound_file):
    if not sound_file:
        return
    try:
        if platform.system() == "Windows":
            winsound.PlaySound(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            if os.system(f"aplay '{sound_file}' &") != 0:
                os.system(f"afplay '{sound_file}' &")
    except Exception as e:
        print(f"Failed to play sound: {e}")

def speak_tts(message):
    if not message:
        return
    try:
        if platform.system() == "Windows" and pyttsx3:
            engine = pyttsx3.init()
            engine.say(message)
            engine.runAndWait()
        else:
            if os.system(f"espeak '{message}' &") != 0:
                os.system(f"say '{message}' &")
    except Exception as e:
        print(f"Failed to speak TTS: {e}")

def advanced_image_comparison(img1, img2, method="combined"):
    """
    Advanced image comparison using visual methods only (SSIM and pHash)
    Returns: (similarity_score, confidence_score, details)
    """
    if img1.size != img2.size:
        return 0.0, 1.0, "Size mismatch"
    
    results = {}
    
    # Convert to numpy arrays for visual processing
    arr1 = np.array(img1.convert("RGB"))
    arr2 = np.array(img2.convert("RGB"))
    
    # Method 1: SSIM (Structural Similarity Index)
    if method in ["combined", "ssim"]:
        gray1 = cv2.cvtColor(arr1, cv2.COLOR_RGB2GRAY)
        gray2 = cv2.cvtColor(arr2, cv2.COLOR_RGB2GRAY)
        ssim_score = ssim(gray1, gray2)
        results['ssim'] = ssim_score
    
    # Method 2: Perceptual Hash
    if method in ["combined", "phash"]:
        try:
            hash1 = imagehash.phash(img1)
            hash2 = imagehash.phash(img2)
            hash_diff = hash1 - hash2  # Hamming distance
            hash_similarity = 1.0 - (hash_diff / 64.0)  # Normalize to 0-1
            results['phash'] = hash_similarity
        except Exception as e:
            print(f"pHash failed: {e}")
            results['phash'] = results.get('ssim', 0.5)  # Fallback
    
    if method == "combined":
        # Combined visual-only method
        ssim_score = results.get('ssim', 0.5)
        phash_score = results.get('phash', 0.5)
        combined_score = ssim_score * 0.7 + phash_score * 0.3
        details = f"SSIM: {ssim_score:.3f}, pHash: {phash_score:.3f}"
        confidence = 0.9 if len(results) > 1 else 0.7
        return combined_score, confidence, details
    
    elif method == "ssim":
        return results.get('ssim', 0.5), 1.0, f"SSIM: {results.get('ssim', 'N/A'):.4f}"
    
    elif method == "phash":
        return results.get('phash', 0.5), 1.0, f"pHash: {results.get('phash', 'N/A'):.4f}"
    
    else:
        return results.get('ssim', 0.5), 1.0, f"SSIM: {results.get('ssim', 'N/A'):.4f}"

def main():
    config = load_config()
    regions = config["regions"]
    interval = int(config.get("interval", 1000))
    highlight_time = int(config.get("highlight_time", 5))
    target_window = config.get("target_window")

    root = tk.Tk()
    root.title("ScreenAlert - Enhanced Interface")
    root.geometry("1200x800")
    
    # Dark Gaming Style Theme Configuration
    root.configure(bg="#0a0a0a")  # Very dark background
    
    # Try to use a more futuristic font, fallback to Segoe UI
    try:
        ui_font_main = ("Orbitron", 9, "bold")  # Futuristic font if available
        ui_font_small = ("Orbitron", 8)
        ui_font_large = ("Orbitron", 11, "bold")
    except:
        ui_font_main = ("Segoe UI", 9, "bold")  # Fallback
        ui_font_small = ("Segoe UI", 8)
        ui_font_large = ("Segoe UI", 11, "bold")
    
    # Create dark theme
    style = ttk.Style()
    style.theme_use('clam')  # Use clam as base theme
    
    # Dark Color Palette
    ui_bg_dark = "#0a0a0a"      # Deep space black
    ui_bg_medium = "#1a1a1a"    # Panel background
    ui_bg_light = "#2a2a2a"     # Lighter panels
    ui_orange = "#ff9500"       # Signature orange
    ui_blue = "#00d4ff"         # Blue highlights
    ui_amber = "#ffb347"        # Amber/yellow accents
    ui_red = "#ff4444"          # Alert red
    ui_green = "#44ff44"        # Success green
    ui_text_light = "#cccccc"   # Light text
    ui_text_dark = "#888888"    # Dim text
    ui_border = "#444444"       # Border color
    
    # Configure ttk styles with dark theme
    style.configure('TNotebook', 
                   background=ui_bg_dark, 
                   borderwidth=0,
                   tabmargins=[2, 5, 2, 0])
    
    style.configure('TNotebook.Tab', 
                   background=ui_bg_medium,
                   foreground=ui_text_light,
                   borderwidth=1,
                   focuscolor='none',
                   padding=[12, 8])
    
    style.map('TNotebook.Tab',
             background=[('selected', ui_bg_light), 
                        ('active', ui_bg_medium)],
             foreground=[('selected', ui_orange), 
                        ('active', ui_amber)])
    
    # Frame styling
    style.configure('TFrame', 
                   background=ui_bg_dark,
                   borderwidth=1,
                   relief='flat')
    
    style.configure('Region.TFrame', 
                   background=ui_bg_medium,
                   borderwidth=2,
                   relief='raised',
                   bordercolor=ui_border)
    
    # Label styling  
    style.configure('TLabel', 
                   background=ui_bg_dark,
                   foreground=ui_text_light,
                   font=ui_font_small)
    
    style.configure('Region.TLabel', 
                   background=ui_bg_medium,
                   foreground=ui_text_light,
                   font=ui_font_main)
    
    # Button styling
    style.configure('TButton', 
                   background=ui_bg_light,
                   foreground=ui_text_light,
                   borderwidth=1,
                   focuscolor='none',
                   font=ui_font_small)
    
    style.map('TButton',
             background=[('active', ui_orange),
                        ('pressed', ui_amber)],
             foreground=[('active', ui_bg_dark),
                        ('pressed', ui_bg_dark)])
    
    style.configure('Mute.TButton', 
                   background=ui_red,
                   foreground=ui_bg_dark,
                   font=ui_font_small)
    
    style.map('Mute.TButton',
             background=[('active', '#ff6666'),
                        ('pressed', '#cc3333')])
    
    # Entry and Spinbox styling
    style.configure('TEntry', 
                   fieldbackground=ui_bg_light,
                   background=ui_bg_light,
                   foreground=ui_text_light,
                   borderwidth=1,
                   insertcolor=ui_orange)
    
    style.configure('TSpinbox', 
                   fieldbackground=ui_bg_light,
                   background=ui_bg_light,
                   foreground=ui_text_light,
                   borderwidth=1,
                   insertcolor=ui_orange,
                   arrowcolor=ui_orange)
    
    # LabelFrame styling
    style.configure('TLabelframe', 
                   background=ui_bg_dark,
                   foreground=ui_orange,
                   borderwidth=2,
                   relief='groove',
                   font=ui_font_large)
    
    style.configure('TLabelframe.Label', 
                   background=ui_bg_dark,
                   foreground=ui_orange,
                   font=ui_font_large)

    # Initialize variables
    interval_var = tk.IntVar(value=interval)
    highlight_time_var = tk.IntVar(value=highlight_time)
    alert_display_time_var = tk.IntVar(value=highlight_time)
    mute_timeout_var = tk.IntVar(value=10)
    default_sound_var = tk.StringVar(value=config.get("default_sound", ""))
    default_tts_var = tk.StringVar(value=config.get("default_tts", "Alert {name}"))
    alert_threshold_var = tk.DoubleVar(value=config.get("alert_threshold", 0.99))
    green_text_var = tk.StringVar(value=config.get("green_text", "stocc"))
    green_color_var = tk.StringVar(value=config.get("green_color", "#44ff44"))  # Success green
    paused_text_var = tk.StringVar(value=config.get("paused_text", "Paused"))
    paused_color_var = tk.StringVar(value=config.get("paused_color", "#00d4ff"))  # Blue highlights
    alert_text_var = tk.StringVar(value=config.get("alert_text", "ALERT"))
    alert_color_var = tk.StringVar(value=config.get("alert_color", "#ff4444"))  # Alert red
    disabled_text_var = tk.StringVar(value=config.get("disabled_text", "scanner"))
    disabled_color_var = tk.StringVar(value=config.get("disabled_color", "#ff9500"))  # Orange
    unavailable_text_var = tk.StringVar(value=config.get("unavailable_text", "necom"))
    unavailable_color_var = tk.StringVar(value=config.get("unavailable_color", "#666666"))  # Dark grey
    pause_reminder_interval_var = tk.IntVar(value=config.get("pause_reminder_interval", 60))
    window_filter_var = tk.StringVar(value=config.get("window_filter", ""))
    verbose_logging_var = tk.BooleanVar(value=False)  # Verbose debug logging toggle

    # Window selection on startup - now optional, can be done via menu
    # Application starts without requiring a target window selection

    # Menu Functions
    def save_settings_to_file():
        """Save current settings to a JSON file"""
        try:
            filename = fd.asksaveasfilename(
                title="Save Settings",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialfile="screenalert_settings.json"
            )
            if filename:
                # Collect all current settings
                settings_data = {
                    "regions": regions,
                    "interval": interval_var.get(),
                    "highlight_time": highlight_time_var.get(),
                    "default_sound": default_sound_var.get(),
                    "default_tts": default_tts_var.get(),
                    "alert_threshold": alert_threshold_var.get(),
                    "green_text": green_text_var.get(),
                    "green_color": green_color_var.get(),
                    "paused_text": paused_text_var.get(),
                    "paused_color": paused_color_var.get(),
                    "alert_text": alert_text_var.get(),
                    "alert_color": alert_color_var.get(),
                    "disabled_text": disabled_text_var.get(),
                    "disabled_color": disabled_color_var.get(),
                    "unavailable_text": unavailable_text_var.get(),
                    "unavailable_color": unavailable_color_var.get(),
                    "pause_reminder_interval": pause_reminder_interval_var.get(),
                    "target_window": target_window,
                    "window_filter": window_filter_var.get()
                }
                
                with open(filename, 'w') as f:
                    json.dump(settings_data, f, indent=2)
                
                msgbox.showinfo("Success", f"Settings saved to:\n{filename}")
        except Exception as e:
            msgbox.showerror("Error", f"Failed to save settings:\n{str(e)}")

    def show_about():
        """Show about dialog"""
        about_text = f"""ScreenAlert - Enhanced Interface

Version: {APP_VERSION}
Author: {APP_AUTHOR}
Repository: {APP_REPO_URL}

An advanced window monitoring application that watches 
specific regions for changes and provides alerts.

Features:
• Multi-window region monitoring
• Configurable alert thresholds
• Sound and TTS notifications
• Window reconnection
• Dark gaming-themed interface"""

        msgbox.showinfo("About", about_text)

    def show_settings_window():
        """Show settings in a separate window"""
        settings_window = tk.Toplevel(root)
        settings_window.title("Settings")
        settings_window.geometry("600x500")
        settings_window.configure(bg="#0a0a0a")
        settings_window.transient(root)
        settings_window.grab_set()
        
        # Apply EVE theme to settings window
        settings_frame = ttk.LabelFrame(settings_window, text="Application Settings", padding=10)
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Interval setting
        ttk.Label(settings_frame, text="Interval (ms):").grid(row=0, column=0, sticky="e", padx=5, pady=2)
        interval_spin = ttk.Spinbox(settings_frame, from_=100, to=10000, increment=100, 
                                   textvariable=interval_var, width=7)
        interval_spin.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        create_tooltip(interval_spin, "How often to check for changes (milliseconds)\n"
                                      "Lower values = more responsive but uses more CPU\n"
                                      "Recommended: 1000-2000ms for most applications")
        
        # Alert Display Time
        ttk.Label(settings_frame, text="Alert Display Time (s):").grid(row=1, column=0, sticky="e", padx=5, pady=2)
        alert_display_spin = ttk.Spinbox(settings_frame, from_=1, to=60, increment=1, 
                                        textvariable=alert_display_time_var, width=7)
        alert_display_spin.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        create_tooltip(alert_display_spin, "How long the alert state is displayed (seconds)\n"
                                          "Also prevents repeated alerts for the same change\n"
                                          "Recommended: 3-10 seconds")
        
        # Mute Timeout
        ttk.Label(settings_frame, text="Mute Timeout (min):").grid(row=2, column=0, sticky="e", padx=5, pady=2)
        mute_timeout_spin = ttk.Spinbox(settings_frame, from_=1, to=60, increment=1, 
                                       textvariable=mute_timeout_var, width=5)
        mute_timeout_spin.grid(row=2, column=1, sticky="w", padx=5, pady=2)
        create_tooltip(mute_timeout_spin, "How long to mute sounds/TTS when mute buttons are clicked\n"
                                         "Mute will automatically expire after this time\n"
                                         "Use for temporary silencing during meetings, etc.")

        # Default Sound
        def browse_default_sound():
            filename = fd.askopenfilename(
                title="Select Alert Sound",
                filetypes=[("Audio files", "*.wav *.mp3 *.ogg"), ("All files", "*.*")]
            )
            if filename:
                default_sound_var.set(filename)

        ttk.Label(settings_frame, text="Default Alert Sound:").grid(row=3, column=0, sticky="e", padx=5, pady=2)
        default_sound_entry = ttk.Entry(settings_frame, textvariable=default_sound_var, width=25)
        default_sound_entry.grid(row=3, column=1, sticky="w", padx=5, pady=2)
        browse_default_btn = ttk.Button(settings_frame, text="Browse...", command=browse_default_sound)
        browse_default_btn.grid(row=3, column=2, sticky="w", padx=2, pady=2)
        create_tooltip(default_sound_entry, "Default sound file to play when alerts trigger\n"
                                           "Supports .wav, .mp3, and .ogg files\n"
                                           "Leave empty to disable sound alerts")
        create_tooltip(browse_default_btn, "Click to browse and select a sound file")
        
        # Default TTS
        ttk.Label(settings_frame, text="Default TTS:").grid(row=4, column=0, sticky="e", padx=5, pady=2)
        default_tts_entry = ttk.Entry(settings_frame, textvariable=default_tts_var, width=20)
        default_tts_entry.grid(row=4, column=1, sticky="w", padx=5, pady=2)
        create_tooltip(default_tts_entry, "Default text-to-speech message for alerts\n"
                                         "Use {name} to include the region name\n"
                                         "Example: 'Alert in {name}' or 'Change detected'\n"
                                         "Leave empty to disable TTS alerts")
        
        # Alert Threshold
        ttk.Label(settings_frame, text="Alert Threshold (0-1):").grid(row=5, column=0, sticky="e", padx=5, pady=2)
        threshold_spin = ttk.Spinbox(settings_frame, from_=0.80, to=1.00, increment=0.01, 
                                    textvariable=alert_threshold_var, width=7, format="%.2f")
        threshold_spin.grid(row=5, column=1, sticky="w", padx=5, pady=2)
        create_tooltip(threshold_spin, "Similarity threshold for triggering alerts\n"
                                      "Lower values = more sensitive (more alerts)\n"
                                      "Higher values = less sensitive (fewer alerts)\n"
                                      "0.99 = very sensitive, 0.90 = moderate, 0.80 = less sensitive")
        
        # Status Text and Color Settings
        ttk.Label(settings_frame, text="Status Text Settings", font=("Segoe UI", 10, "bold")).grid(row=7, column=0, columnspan=3, pady=(20,10), sticky="w")
        
        # Green/Online Status
        ttk.Label(settings_frame, text="Online Status Text:").grid(row=8, column=0, sticky="e", padx=5, pady=2)
        green_text_entry = ttk.Entry(settings_frame, textvariable=green_text_var, width=15)
        green_text_entry.grid(row=8, column=1, sticky="w", padx=5, pady=2)
        
        # Paused Status
        ttk.Label(settings_frame, text="Paused Status Text:").grid(row=9, column=0, sticky="e", padx=5, pady=2)
        paused_text_entry = ttk.Entry(settings_frame, textvariable=paused_text_var, width=15)
        paused_text_entry.grid(row=9, column=1, sticky="w", padx=5, pady=2)
        
        # Disabled Status
        ttk.Label(settings_frame, text="Disabled Status Text:").grid(row=10, column=0, sticky="e", padx=5, pady=2)
        disabled_text_entry = ttk.Entry(settings_frame, textvariable=disabled_text_var, width=15)
        disabled_text_entry.grid(row=10, column=1, sticky="w", padx=5, pady=2)
        
        # Unavailable Status
        ttk.Label(settings_frame, text="Unavailable Status Text:").grid(row=11, column=0, sticky="e", padx=5, pady=2)
        unavailable_text_entry = ttk.Entry(settings_frame, textvariable=unavailable_text_var, width=15)
        unavailable_text_entry.grid(row=11, column=1, sticky="w", padx=5, pady=2)
        
        # Window Filter
        ttk.Label(settings_frame, text="Window Filter:").grid(row=12, column=0, sticky="e", padx=5, pady=2)
        window_filter_entry = ttk.Entry(settings_frame, textvariable=window_filter_var, width=20)
        window_filter_entry.grid(row=12, column=1, sticky="w", padx=5, pady=2)
        create_tooltip(window_filter_entry, "Filter for window selection\n"
                                           "Only windows containing this text will be shown\n"
                                           "Leave empty to show all windows")
        
        # Pause Reminder Interval
        ttk.Label(settings_frame, text="Pause Reminder (s):").grid(row=13, column=0, sticky="e", padx=5, pady=2)
        pause_reminder_spin = ttk.Spinbox(settings_frame, from_=0, to=300, increment=10, 
                                         textvariable=pause_reminder_interval_var, width=7)
        pause_reminder_spin.grid(row=13, column=1, sticky="w", padx=5, pady=2)
        create_tooltip(pause_reminder_spin, "Interval for pause reminder tone (seconds)\n"
                                           "Set to 0 to disable reminder tones\n"
                                           "Plays when monitoring is paused")
        
        # Verbose logging toggle
        verbose_check = ttk.Checkbutton(settings_frame, text="Verbose Debug Logging", variable=verbose_logging_var)
        verbose_check.grid(row=14, column=0, columnspan=2, sticky="w", padx=5, pady=2)
        create_tooltip(verbose_check, "Enable detailed debug output in console\n"
                                     "Shows comparison scores, timing, and processing details\n"
                                     "Useful for troubleshooting and optimizing settings\n"
                                     "May impact performance when enabled")
        
        # Apply and Close buttons
        button_frame = ttk.Frame(settings_frame)
        button_frame.grid(row=15, column=0, columnspan=3, pady=20)
        
        def apply_settings():
            # Save settings
            save_config(
                regions, interval_var.get(), highlight_time_var.get(),
                default_sound_var.get(), default_tts_var.get(), alert_threshold_var.get(),
                green_text=green_text_var.get(), green_color=green_color_var.get(),
                paused_text=paused_text_var.get(), paused_color=paused_color_var.get(),
                alert_text=alert_text_var.get(), alert_color=alert_color_var.get(),
                disabled_text=disabled_text_var.get(), disabled_color=disabled_color_var.get(),
                pause_reminder_interval=pause_reminder_interval_var.get(),
                target_window=target_window, window_filter=window_filter_var.get(),
                unavailable_text=unavailable_text_var.get(), unavailable_color=unavailable_color_var.get()
            )
            msgbox.showinfo("Settings", "Settings applied and saved!")
            update_region_display(force_update=True)
        
        apply_btn = ttk.Button(button_frame, text="Apply", command=apply_settings)
        apply_btn.pack(side=tk.LEFT, padx=5)
        
        close_btn = ttk.Button(button_frame, text="Close", command=settings_window.destroy)
        close_btn.pack(side=tk.LEFT, padx=5)

    def manual_reconnect():
        """Manually trigger window reconnection check"""
        print("Manual window reconnection check initiated...")
        reconnected = try_reconnect_windows()
        if reconnected > 0:
            msgbox.showinfo("Reconnection Success", f"Successfully reconnected {reconnected} window(s)!")
        else:
            msgbox.showinfo("Reconnection Check", "No disconnected windows found or no windows could be reconnected.")

    def toggle_pause():
        nonlocal paused, last_reminder_time
        paused = not paused
        if paused:
            last_reminder_time = time.time()
        update_status_bar()

    def change_target_window():
        nonlocal target_window, current_window_img, previous_screenshots
        # Get current monitor if window has one assigned
        current_monitor = target_window.get('monitor_id') if target_window else None
        
        selector = WindowSelector(root, target_window, current_monitor, window_filter_var.get())
        root.wait_window(selector.top)
        if selector.selected_window:
            target_window = selector.selected_window
            # Let capture_window handle validity checking
            current_window_img = capture_window(target_window['hwnd'])
            if not current_window_img:
                print(f"Selected window {target_window['title']} capture failed")
            
            # Clear existing screenshots to force refresh
            previous_screenshots = []
            save_config(
                regions, interval_var.get(), highlight_time_var.get(),
                default_sound_var.get(), default_tts_var.get(), alert_threshold_var.get(),
                green_text=green_text_var.get(), green_color=green_color_var.get(),
                paused_text=paused_text_var.get(), paused_color=paused_color_var.get(),
                alert_text=alert_text_var.get(), alert_color=alert_color_var.get(),
                disabled_text=disabled_text_var.get(), disabled_color=disabled_color_var.get(),
                pause_reminder_interval=pause_reminder_interval_var.get(),
                target_window=target_window, window_filter=window_filter_var.get(),
                unavailable_text=unavailable_text_var.get(), unavailable_color=unavailable_color_var.get()
            )

    def add_region():
        nonlocal selecting_region
        if paused or selecting_region:
            return
            
        selecting_region = True
        
        # First, prompt user to select a window for this region
        current_monitor = target_window.get('monitor_id') if target_window else None
        window_selector = WindowSelector(root, target_window, current_monitor, window_filter_var.get())
        root.wait_window(window_selector.top)
        
        if not window_selector.selected_window:
            # User cancelled window selection
            selecting_region = False
            return
        
        selected_window = window_selector.selected_window
        
        # Try to capture the window first - this is more reliable than just checking validity
        print(f"Attempting to capture window: {selected_window['title']} (HWND: {selected_window['hwnd']})")
        window_img = capture_window(selected_window['hwnd'])
        
        if not window_img:
            # If capture failed, try a brief delay and retry once
            print("First capture attempt failed, waiting 500ms and retrying...")
            root.after(500)  # Brief delay
            root.update()  # Process any pending events
            window_img = capture_window(selected_window['hwnd'])
            
            if not window_img:
                # Check if window is still valid for better error message
                is_valid = is_window_valid(selected_window['hwnd'])
                error_msg = f"Could not capture window '{selected_window['title']}'."
                if not is_valid:
                    error_msg += "\nThe window may have closed or become unavailable."
                else:
                    error_msg += "\nThe window exists but capture failed. Try selecting the window again."
                msgbox.showerror("Capture Failed", error_msg)
                selecting_region = False
                return
        
        print(f"Successfully captured window: {window_img.size}")
        
        # Now let user select the region within the chosen window
        region_selector = RegionSelector(root, window_img)
        region = region_selector.select()
        
        if region and all(region):
            region_name = f"Region {len(regions)+1}"
            print(f"Creating region: {region_name} with rect: {region}")
            regions.append({
                "rect": region,
                "name": region_name,
                "paused": False,
                "disabled": False,
                "mute_sound": False,
                "mute_tts": False,
                "mute_sound_until": 0,
                "mute_tts_until": 0,
                "last_alert_time": 0,
                "target_window": selected_window  # Use the specifically selected window
            })
            previous_screenshots.append(crop_region(window_img, region))
            print(f"Successfully added region: {region_name}")
            print(f"Total regions now: {len(regions)}")
            update_region_display(force_update=True)  # Force update after adding region
            save_config(
                regions, interval_var.get(), highlight_time_var.get(),
                default_sound_var.get(), default_tts_var.get(), alert_threshold_var.get(),
                green_text=green_text_var.get(), green_color=green_color_var.get(),
                paused_text=paused_text_var.get(), paused_color=paused_color_var.get(),
                alert_text=alert_text_var.get(), alert_color=alert_color_var.get(),
                disabled_text=disabled_text_var.get(), disabled_color=disabled_color_var.get(),
                pause_reminder_interval=pause_reminder_interval_var.get(),
                target_window=target_window, window_filter=window_filter_var.get(),
                unavailable_text=unavailable_text_var.get(), unavailable_color=unavailable_color_var.get()
            )
        else:
            print(f"Region selection failed or cancelled. Region: {region}")
        selecting_region = False

    # Create Menu Bar
    menubar = tk.Menu(root)
    root.config(menu=menubar)
    
    # File Menu
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="File", menu=file_menu)
    file_menu.add_command(label="Save Settings...", command=save_settings_to_file, accelerator="Ctrl+S")
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=root.quit, accelerator="Ctrl+Q")
    
    # Edit Menu
    edit_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Edit", menu=edit_menu)
    edit_menu.add_command(label="Add Region", command=add_region, accelerator="Ctrl+N")
    edit_menu.add_command(label="Change Window", command=change_target_window, accelerator="Ctrl+W")
    edit_menu.add_command(label="Reconnect Windows", command=lambda: manual_reconnect(), accelerator="Ctrl+R")
    edit_menu.add_separator()
    edit_menu.add_command(label="Pause/Resume", command=toggle_pause, accelerator="Space")
    edit_menu.add_separator()
    edit_menu.add_command(label="Select All", command=lambda: None, accelerator="Ctrl+A", state="disabled")  # Placeholder
    edit_menu.add_command(label="Copy", command=lambda: None, accelerator="Ctrl+C", state="disabled")  # Placeholder
    edit_menu.add_command(label="Paste", command=lambda: None, accelerator="Ctrl+V", state="disabled")  # Placeholder
    edit_menu.add_separator()
    edit_menu.add_command(label="Settings...", command=show_settings_window, accelerator="Ctrl+,")
    
    # Help Menu
    help_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Help", menu=help_menu)
    help_menu.add_command(label="About", command=show_about)
    
    # Bind keyboard shortcuts
    root.bind('<Control-s>', lambda e: save_settings_to_file())
    root.bind('<Control-q>', lambda e: root.quit())
    root.bind('<Control-comma>', lambda e: show_settings_window())
    root.bind('<Control-n>', lambda e: add_region())
    root.bind('<Control-w>', lambda e: change_target_window())
    root.bind('<Control-r>', lambda e: manual_reconnect())
    root.bind('<space>', lambda e: toggle_pause())

    # Main content area (no tabs, just regions)
    main_frame = ttk.Frame(root)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Status bar
    status = ttk.Label(root, text="Ready", anchor="w")
    status.pack(fill=tk.X, side=tk.BOTTOM)

    # Initialize monitoring variables
    paused = False
    selecting_region = False
    last_reminder_time = 0
    current_window_img = None
    previous_screenshots = []
    last_window_recheck = 0  # Track when we last checked for missing windows
    
    # Performance optimization: Cache window captures to avoid redundant captures
    window_capture_cache = {}
    cache_lifetime = 1.0  # Cache captures for 1 second

    # Initialize window capture
    def update_window_capture():
        nonlocal current_window_img
        if target_window:
            # Let capture_window handle the validity checking
            current_window_img = capture_window(target_window['hwnd'])
            if not current_window_img:
                print(f"Target window {target_window['title']} capture failed")
                return
            
            if current_window_img and len(regions) > len(previous_screenshots):
                # Initialize screenshots for new regions
                for i in range(len(previous_screenshots), len(regions)):
                    if i < len(regions):
                        previous_screenshots.append(crop_region(current_window_img, regions[i]["rect"]))

    update_window_capture()

    def get_cached_window_capture(hwnd):
        """Get cached window capture or create new one if cache expired"""
        nonlocal window_capture_cache
        current_time = time.time()
        
        # Check if we have a valid cached capture
        if hwnd in window_capture_cache:
            cached_img, cache_time = window_capture_cache[hwnd]
            if current_time - cache_time < cache_lifetime:
                return cached_img
        
        # Capture new image and cache it - let capture_window handle validity checking
        img = capture_window(hwnd)
        if img:
            window_capture_cache[hwnd] = (img, current_time)
            
            # Clean old cache entries (older than cache_lifetime)
            to_remove = []
            for cached_hwnd, (_, cached_time) in window_capture_cache.items():
                if current_time - cached_time > cache_lifetime:
                    to_remove.append(cached_hwnd)
            for hwnd_to_remove in to_remove:
                del window_capture_cache[hwnd_to_remove]
        
        return img

    def are_all_regions_connected():
        """Check if all active regions are successfully connected to their windows"""
        if not regions:
            return False  # No regions to be connected
            
        active_regions = [r for r in regions if not r.get("disabled", False)]
        if not active_regions:
            return False  # No active regions
            
        for region in active_regions:
            region_window = region.get("target_window", target_window)
            if not region_window:
                return False  # Region has no target window
                
            # Try quick capture to check if window is available
            test_img = capture_window(region_window['hwnd'])
            if not test_img:
                return False  # Window is not available
                
        return True  # All active regions are connected

    def try_reconnect_windows():
        """Try to reconnect to windows that are no longer available - Enhanced version"""
        nonlocal target_window, current_window_img
        
        reconnected_count = 0
        failed_reconnections = []
        
        # Check global target window
        if target_window:
            # Always try to capture to see if window is still available
            test_img = capture_window(target_window['hwnd'])
            if not test_img:
                print(f"Global target window unavailable: {target_window['title']} (HWND: {target_window['hwnd']})")
                
                # Try only exact title matching - no fuzzy matching to prevent wrong windows
                new_window = None
                
                # Only try exact title match - safer and more reliable
                new_window = find_window_by_title(target_window['title'], exact_match=True)
                if new_window:
                    print(f"  Found exact match: {new_window['title']} (HWND: {new_window['hwnd']})")
                else:
                    print(f"  No exact match found for: {target_window['title']}")
                    print(f"  (Fuzzy matching disabled to prevent incorrect window attachment)")
                
                if new_window:
                    print(f"Successfully reconnected global target window: {new_window['title']} (new HWND: {new_window['hwnd']})")
                    target_window = new_window
                    current_window_img = capture_window(target_window['hwnd'])
                    reconnected_count += 1
                    # Save the updated window info
                    save_config(
                        regions, interval_var.get(), highlight_time_var.get(),
                        default_sound_var.get(), default_tts_var.get(), alert_threshold_var.get(),
                        green_text=green_text_var.get(), green_color=green_color_var.get(),
                        paused_text=paused_text_var.get(), paused_color=paused_color_var.get(),
                        alert_text=alert_text_var.get(), alert_color=alert_color_var.get(),
                        disabled_text=disabled_text_var.get(), disabled_color=disabled_color_var.get(),
                        pause_reminder_interval=pause_reminder_interval_var.get(),
                        target_window=target_window, window_filter=window_filter_var.get(),
                        unavailable_text=unavailable_text_var.get(), unavailable_color=unavailable_color_var.get()
                    )
                else:
                    failed_reconnections.append(f"Global target: {target_window['title']}")
        
        # Check each region's target window with enhanced matching
        for idx, region in enumerate(regions):
            region_window = region.get("target_window")
            if region_window:
                # Always try to capture to see if window is still available
                test_img = capture_window(region_window['hwnd'])
                if not test_img:
                    region_name = region.get('name', f'Region {idx+1}')
                    print(f"Region {idx} '{region_name}' window unavailable: {region_window['title']} (HWND: {region_window['hwnd']})")
                    
                    # Try only exact title matching - no fuzzy matching to prevent wrong windows
                    new_window = None
                    
                    # Only try exact title match - safer and more reliable
                    new_window = find_window_by_title(region_window['title'], exact_match=True)
                    if new_window:
                        print(f"  Found exact match for region {idx}: {new_window['title']}")
                    else:
                        print(f"  No exact match found for region {idx}: {region_window['title']}")
                        print(f"  (Fuzzy matching disabled to prevent incorrect window attachment)")
                    
                    if new_window:
                        print(f"Successfully reconnected region {idx} to window: {new_window['title']} (new HWND: {new_window['hwnd']})")
                        region["target_window"] = new_window
                        reconnected_count += 1
                        
                        # Reset the previous screenshot for this region to force refresh
                        if idx < len(previous_screenshots):
                            try:
                                new_window_img = capture_window(new_window['hwnd'])
                                if new_window_img:
                                    previous_screenshots[idx] = crop_region(new_window_img, region["rect"])
                            except Exception as e:
                                print(f"Error updating screenshot for reconnected region {idx}: {e}")
                    else:
                        failed_reconnections.append(f"Region {idx} '{region_name}': {region_window['title']}")
        
        if reconnected_count > 0:
            print(f"Reconnected {reconnected_count} window(s)")
            # Save all region updates
            save_config(
                regions, interval_var.get(), highlight_time_var.get(),
                default_sound_var.get(), default_tts_var.get(), alert_threshold_var.get(),
                green_text=green_text_var.get(), green_color=green_color_var.get(),
                paused_text=paused_text_var.get(), paused_color=paused_color_var.get(),
                alert_text=alert_text_var.get(), alert_color=alert_color_var.get(),
                disabled_text=disabled_text_var.get(), disabled_color=disabled_color_var.get(),
                pause_reminder_interval=pause_reminder_interval_var.get(),
                target_window=target_window, window_filter=window_filter_var.get(),
                unavailable_text=unavailable_text_var.get(), unavailable_color=unavailable_color_var.get()
            )
            update_region_display(force_update=True)
        
        if failed_reconnections:
            print(f"Failed to reconnect {len(failed_reconnections)} window(s):")
            for failure in failed_reconnections:
                print(f"  - {failure}")
        
        return reconnected_count

    update_window_capture()

    region_widgets = []

    # Status Bar Update Function
    def update_status_bar():
        nonlocal last_reminder_time
        
        now = time.time()
        reminder_interval = pause_reminder_interval_var.get()
        
        # Check if window is still valid
        window_status = ""
        if target_window:
            # Try a quick capture to see if window is available
            test_img = capture_window(target_window['hwnd'])
            if not test_img:
                window_status = " - WINDOW NOT AVAILABLE"
            else:
                window_title = target_window['title'][:50]
                monitor_id = target_window.get('monitor_id', 0)
                window_status = f" - [{window_title}] (Monitor {monitor_id + 1})"
        else:
            window_status = " - No Window Selected"
        
        # Check if anything is paused (disabled regions should NOT trigger reminders)
        global_paused = paused
        any_region_paused = any(region.get("paused", False) and not region.get("disabled", False) for region in regions)
        something_paused = global_paused or any_region_paused
        
        if something_paused:
            time_since_reminder = now - last_reminder_time
            
            if reminder_interval > 0:
                remaining_time = max(0, reminder_interval - time_since_reminder)
                if global_paused and any_region_paused:
                    paused_count = sum(1 for r in regions if r.get('paused', False) and not r.get('disabled', False))
                    status_text = f"PAUSED (Global + {paused_count} regions) - Next reminder in {remaining_time:.0f}s{window_status}"
                elif global_paused:
                    status_text = f"PAUSED (Global) - Next reminder in {remaining_time:.0f}s{window_status}"
                else:
                    paused_count = sum(1 for r in regions if r.get('paused', False) and not r.get('disabled', False))
                    status_text = f"PAUSED ({paused_count} region{'s' if paused_count > 1 else ''}) - Next reminder in {remaining_time:.0f}s{window_status}"
            else:
                if global_paused and any_region_paused:
                    paused_count = sum(1 for r in regions if r.get('paused', False) and not r.get('disabled', False))
                    disabled_count = sum(1 for r in regions if r.get("disabled", False))
                    status_text = f"PAUSED (Global + {paused_count} regions){window_status}"
                    if disabled_count > 0:
                        status_text += f", {disabled_count} disabled"
                elif global_paused:
                    disabled_count = sum(1 for r in regions if r.get("disabled", False))
                    status_text = f"PAUSED (Global){window_status}"
                    if disabled_count > 0:
                        status_text += f", {disabled_count} regions disabled"
                else:
                    paused_count = sum(1 for r in regions if r.get('paused', False) and not r.get('disabled', False))
                    disabled_count = sum(1 for r in regions if r.get("disabled", False))
                    status_text = f"PAUSED ({paused_count} region{'s' if paused_count > 1 else ''}){window_status}"
                    if disabled_count > 0:
                        status_text += f", {disabled_count} disabled"
            
            # Play reminder if enough time has passed
            if reminder_interval > 0 and time_since_reminder >= reminder_interval:
                try:
                    play_pause_reminder_tone()
                    last_reminder_time = now
                except Exception as e:
                    print(f"Failed to play pause reminder: {e}")
        else:
            disabled_count = sum(1 for r in regions if r.get("disabled", False))
            active_regions = [r for r in regions if not r.get("disabled", False)]
            
            if active_regions:
                # Count unique windows being monitored
                unique_windows = set()
                for region in active_regions:
                    region_window = region.get("target_window", target_window)
                    if region_window:
                        # Try capture to check availability
                        test_img = capture_window(region_window['hwnd'])
                        if test_img:
                            unique_windows.add(region_window['title'])
                
                if unique_windows:
                    if len(unique_windows) == 1:
                        window_title = list(unique_windows)[0][:30]
                        status_text = f"Monitoring [{window_title}]"
                    else:
                        status_text = f"Monitoring {len(unique_windows)} windows"
                else:
                    status_text = "Monitoring (no valid windows)"
            else:
                status_text = "No active regions"
            
            if disabled_count > 0:
                status_text += f" - ({disabled_count} region{'s' if disabled_count > 1 else ''} disabled)"
            
        status.config(text=status_text)

    def update_region_display(force_update=False):
        nonlocal paused
        
        # Performance optimization: Only update if regions changed or forced
        current_region_state = []
        for region in regions:
            region_window = region.get("target_window", target_window)
            if region_window:
                # Try capture to check availability
                test_img = capture_window(region_window['hwnd'])
                window_available = test_img is not None
            else:
                window_available = False
            current_region_state.append({
                'name': region.get('name'),
                'disabled': region.get('disabled', False),
                'paused': region.get('paused', False),
                'alert': region.get('alert', False),
                'window_available': window_available,
                'window_title': region_window['title'] if region_window else None
            })
        
        # Check if we need to update (compare with last state)
        # Note: Always update when called from monitoring loop to ensure thumbnails refresh
        if not force_update and hasattr(update_region_display, 'last_state'):
            if (update_region_display.last_state == current_region_state and 
                len(region_widgets) == len(regions)):
                # Still update thumbnails even if status hasn't changed, but less frequently
                # Skip the full update only if we've updated recently
                current_time = time.time()
                if (hasattr(update_region_display, 'last_update_time') and 
                    current_time - update_region_display.last_update_time < 2.0):
                    return  # Skip update if we updated less than 2 seconds ago
        
        update_region_display.last_state = current_region_state
        update_region_display.last_update_time = time.time()

        update_region_display.img_refs = []

        # Ensure region_widgets matches regions
        while len(region_widgets) < len(regions):
            # Create new region frame and widgets
            rf = ttk.Frame(regions_frame, style="Region.TFrame", padding=4, relief="raised")
            rf.grid_columnconfigure(0, minsize=80, weight=0)  # Increased to accommodate status canvas width
            rf.grid_columnconfigure(1, minsize=120, weight=0)
            rf.grid_columnconfigure(2, weight=1)
            rf.grid_columnconfigure(3, weight=0)
            rf.grid_columnconfigure(4, weight=0)

            # Status canvas
            status_canvas = tk.Canvas(rf, width=80, height=100, highlightthickness=0, bd=0)
            status_canvas.grid(row=0, column=0, rowspan=3, sticky="nsw", padx=(0, 8), pady=0)

            # Thumbnail canvas
            img_canvas = tk.Canvas(rf, width=120, height=100, highlightthickness=0, bd=0, bg="#0a0a0a")
            img_canvas.grid(row=0, column=1, rowspan=3, sticky="nsew", padx=0, pady=0)

            # Name label
            name_label = ttk.Label(rf, style="Region.TLabel")
            name_label.grid(row=0, column=2, sticky="w", padx=(0, 8))

            # Controls frame
            controls_frame = ttk.Frame(rf, style="Region.TFrame")
            controls_frame.grid(row=0, column=3, rowspan=3, sticky="e", padx=2)
            controls_frame.grid_columnconfigure(0, weight=0, minsize=120)  # Button column

            # Pause button
            pause_btn = ttk.Button(controls_frame, width=10)
            pause_btn.grid(row=0, column=0, sticky="ew", pady=2)

            # Mute sound button
            mute_sound_btn = ttk.Button(controls_frame, style="Mute.TButton", width=14)
            # Note: grid() will be called conditionally based on sound availability

            # Mute TTS button
            mute_tts_btn = ttk.Button(controls_frame, style="Mute.TButton", width=14)
            # Note: grid() will be called conditionally based on TTS availability

            # Disable button
            disable_btn = ttk.Button(controls_frame, width=14)
            disable_btn.grid(row=3, column=0, sticky="ew", pady=2)

            # Mute sound label
            mute_sound_label = ttk.Label(controls_frame, width=6, text="")
            # Note: grid() will be called conditionally based on sound availability

            # Mute TTS label
            mute_tts_label = ttk.Label(controls_frame, width=6, text="")
            # Note: grid() will be called conditionally based on TTS availability

            # Change Window button - larger and more prominent
            change_window_btn = ttk.Button(rf, text="WINDOW", width=10)
            change_window_btn.grid(row=2, column=4, sticky="ew", padx=(8,2), pady=2)
            
            # Add tooltip-like help text (you can implement a proper tooltip library if needed)
            def show_help(event):
                print("Change Window button: Click to select a different window for this region to monitor")
            change_window_btn.bind("<Button-3>", show_help)  # Right-click for help

            # Edit button
            edit_btn = ttk.Button(rf, text="EDIT", width=6)
            edit_btn.grid(row=0, column=4, sticky="ne", padx=(8,2), pady=2)

            # Remove button
            remove_btn = ttk.Button(rf, text="DEL", width=6)
            remove_btn.grid(row=1, column=4, sticky="e", padx=(8,2), pady=2)

            rf.grid(row=len(region_widgets), column=0, sticky="ew", padx=8, pady=6)
            region_widgets.append({
                "frame": rf,
                "status_canvas": status_canvas,
                "img_canvas": img_canvas,
                "name_label": name_label,
                "pause_btn": pause_btn,
                "mute_sound_btn": mute_sound_btn,
                "mute_tts_btn": mute_tts_btn,
                "mute_sound_label": mute_sound_label,
                "mute_tts_label": mute_tts_label,
                "disable_btn": disable_btn,
                "change_window_btn": change_window_btn,
                "edit_btn": edit_btn,
                "remove_btn": remove_btn,
                # Store command functions to prevent recreation
                "commands": {}
            })

        # Remove extra widgets if regions were deleted
        while len(region_widgets) > len(regions):
            widgets = region_widgets.pop()
            widgets["frame"].destroy()

        # Update all widgets
        for idx, region in enumerate(regions):
            widgets = region_widgets[idx]
            status_canvas = widgets["status_canvas"]
            img_canvas = widgets["img_canvas"]
            name_label = widgets["name_label"]
            pause_btn = widgets["pause_btn"]
            mute_sound_btn = widgets["mute_sound_btn"]
            mute_tts_btn = widgets["mute_tts_btn"]
            disable_btn = widgets["disable_btn"]
            change_window_btn = widgets["change_window_btn"]
            edit_btn = widgets["edit_btn"]
            remove_btn = widgets["remove_btn"]

            # Status Indicator - Check window availability first
            status_height = 100
            status_width = 80  # Increased width to accommodate longer text
            
            # Get the target window for this specific region to check availability
            region_window = region.get("target_window", target_window)
            window_available = False
            if region_window:
                # Try capture to check availability
                test_img = capture_window(region_window['hwnd'])
                window_available = test_img is not None
            
            # Determine status with priority: Disabled > Unavailable > Paused > Alert > Normal
            if region.get("disabled", False):
                status_text = disabled_text_var.get()
                status_color = disabled_color_var.get()
            elif not window_available and region_window:  # Only show unavailable if we have a target window but can't capture it
                status_text = unavailable_text_var.get()
                status_color = unavailable_color_var.get()
            elif region.get("paused", False) or paused:
                status_text = paused_text_var.get()
                status_color = paused_color_var.get()
            elif region.get("alert", False):
                status_text = alert_text_var.get()
                status_color = alert_color_var.get()
            else:
                status_text = green_text_var.get()
                status_color = green_color_var.get()
            
            status_canvas.configure(bg=status_color)
            status_canvas.delete("all")
            img_status = create_rotated_text_image(status_text, status_width, status_height, 
                                                 color="#fff", bgcolor=status_color, font_size=16)
            status_imgtk = ImageTk.PhotoImage(img_status)
            status_canvas.create_image(status_width // 2, status_height // 2, anchor="center", image=status_imgtk)
            update_region_display.img_refs.append(status_imgtk)

            # Thumbnail
            thumb_width, thumb_height = 120, 100
            try:
                # Get the target window for this specific region
                region_window = region.get("target_window", target_window)
                region_img = None
                
                if region_window:
                    # Use cached capture for better performance - it handles validity internally
                    region_img = get_cached_window_capture(region_window['hwnd'])
                
                # Check if window is available
                if not region_img:
                    # Show "No Window Available" image with blue background for unavailable status
                    if region_window and not window_available:
                        # Unavailable - use configurable unavailable color
                        unavailable_color = unavailable_color_var.get()
                        no_window_img = create_no_window_image(thumb_width, thumb_height, bg_color=unavailable_color)
                        img_canvas.configure(bg=unavailable_color)
                    else:
                        # No window assigned - use default dark background
                        no_window_img = create_no_window_image(thumb_width, thumb_height)
                        img_canvas.configure(bg="#2a2a2a")
                    
                    imgtk = ImageTk.PhotoImage(no_window_img)
                    img_canvas.delete("all")
                    img_canvas.create_image(0, 0, anchor="nw", image=imgtk)
                    update_region_display.img_refs.append(imgtk)
                else:
                    cropped = crop_region(region_img, region["rect"])
                    if cropped.width == 0 or cropped.height == 0:
                        cropped = Image.new("RGB", (10, 10), "#222")
                    
                    # Optimize thumbnail creation
                    if cropped.size != (thumb_width, thumb_height):
                        cropped.thumbnail((thumb_width, thumb_height), Image.LANCZOS)
                    
                    thumb_img = cropped
                    imgtk = ImageTk.PhotoImage(thumb_img)
                    img_canvas.delete("all")
                    img_canvas.configure(bg="#0a0a0a")
                    img_canvas.create_image((thumb_width-thumb_img.width)//2, 
                                          (thumb_height-thumb_img.height)//2, anchor="nw", image=imgtk)
                    img_canvas.create_rectangle(2, 2, thumb_width-2, thumb_height-2, 
                                              outline="#ff9500", width=2, dash=(4,2))
                    update_region_display.img_refs.append(imgtk)
            except Exception as e:
                print(f"Error updating thumbnail for region {idx}: {e}")
                # Show "No Window Available" image as fallback
                no_window_img = create_no_window_image(thumb_width, thumb_height)
                imgtk = ImageTk.PhotoImage(no_window_img)
                img_canvas.delete("all")
                img_canvas.configure(bg="#2a2a2a")
                img_canvas.create_image(0, 0, anchor="nw", image=imgtk)
                update_region_display.img_refs.append(imgtk)

            # Name label - show window info
            region_window = region.get("target_window", target_window)
            if region_window:
                window_info = f" [{region_window['title'][:20]}...]" if len(region_window['title']) > 20 else f" [{region_window['title']}]"
                # Use the window availability we already checked
                if not window_available:
                    window_info += " - UNAVAILABLE"
            else:
                window_info = " [No Window]"
            
            name_label.config(text=region.get("name", f"Region {idx+1}") + window_info)

            # Controls - using closures to capture region
            def make_toggle_pause(region=region):
                def toggle_pause_region():
                    nonlocal last_reminder_time
                    region["paused"] = not region.get("paused", False)
                    if region.get("paused", False):
                        last_reminder_time = time.time()
                    save_config(
                        regions, interval_var.get(), highlight_time_var.get(),
                        default_sound_var.get(), default_tts_var.get(), alert_threshold_var.get(),
                        green_text=green_text_var.get(), green_color=green_color_var.get(),
                        paused_text=paused_text_var.get(), paused_color=paused_color_var.get(),
                        alert_text=alert_text_var.get(), alert_color=alert_color_var.get(),
                        disabled_text=disabled_text_var.get(), disabled_color=disabled_color_var.get(),
                        pause_reminder_interval=pause_reminder_interval_var.get(),
                        target_window=target_window, window_filter=window_filter_var.get(),
                        unavailable_text=unavailable_text_var.get(), unavailable_color=unavailable_color_var.get()
                    )
                    update_region_display()
                    update_status_bar()
                return toggle_pause_region
            
            # Create or reuse the toggle function
            widgets = region_widgets[idx]
            if "pause_toggle" not in widgets["commands"]:
                widgets["commands"]["pause_toggle"] = make_toggle_pause()
            
            pause_btn.config(
                text="Resume" if region.get("paused", False) else "Pause",
                command=widgets["commands"]["pause_toggle"]
            )

            def make_toggle_mute_sound(region=region, btn=mute_sound_btn):
                def toggle_mute_sound():
                    mute_timeout = mute_timeout_var.get() * 60
                    
                    # Immediately update the state and button for instant feedback
                    if not region.get("mute_sound", False):
                        region["mute_sound"] = True
                        region["mute_sound_until"] = time.time() + mute_timeout
                        btn.config(text=f"Sound Muted ({int(mute_timeout)}s)")
                    else:
                        region["mute_sound"] = False
                        region["mute_sound_until"] = 0
                        btn.config(text="Sound Mute")
                    
                    # Force immediate UI update
                    btn.update_idletasks()
                    
                    # Schedule background save and full UI update after a short delay
                    def background_save():
                        save_config(
                            regions, interval_var.get(), highlight_time_var.get(),
                            default_sound_var.get(), default_tts_var.get(), alert_threshold_var.get(),
                            green_text=green_text_var.get(), green_color=green_color_var.get(),
                            paused_text=paused_text_var.get(), paused_color=paused_color_var.get(),
                            alert_text=alert_text_var.get(), alert_color=alert_color_var.get(),
                            disabled_text=disabled_text_var.get(), disabled_color=disabled_color_var.get(),
                            pause_reminder_interval=pause_reminder_interval_var.get(),
                            target_window=target_window, window_filter=window_filter_var.get(),
                            unavailable_text=unavailable_text_var.get(), unavailable_color=unavailable_color_var.get()
                        )
                    
                    # Schedule the save for 50ms later to allow button to respond immediately
                    root.after(50, background_save)
                    
                return toggle_mute_sound
            
            # Check if sound is available for this region (either region-specific or default)
            has_sound = bool(region.get("sound_file") or default_sound_var.get().strip())
            
            if has_sound:
                # Show mute sound button and configure it
                mute_sound_btn.grid(row=1, column=0, sticky="ew", pady=2)
                
                # Create or reuse the toggle function
                if "sound_toggle" not in widgets["commands"]:
                    widgets["commands"]["sound_toggle"] = make_toggle_mute_sound()
                
                # Show countdown label only when sound is muted and has remaining time
                mute_sound_label = widgets["mute_sound_label"]
                if region.get("mute_sound", False):
                    remaining = int(max(0, region.get("mute_sound_until", 0) - time.time()))
                    if remaining <= 0:
                        region["mute_sound"] = False
                        region["mute_sound_until"] = 0
                        mute_sound_btn.config(text="Sound Mute", command=widgets["commands"]["sound_toggle"])
                    else:
                        mute_sound_btn.config(text=f"Sound Muted ({remaining}s)", command=widgets["commands"]["sound_toggle"])
                else:
                    mute_sound_btn.config(text="Sound Mute", command=widgets["commands"]["sound_toggle"])
                # Hide the countdown label since we're putting it in the button
                mute_sound_label.grid_remove()
            else:
                # Hide mute sound button and label when no sound is available
                mute_sound_btn.grid_remove()
                mute_sound_label = widgets["mute_sound_label"]
                mute_sound_label.grid_remove()

            def make_toggle_mute_tts(region=region, btn=mute_tts_btn):
                def toggle_mute_tts():
                    mute_timeout = mute_timeout_var.get() * 60
                    
                    # Immediately update the state and button for instant feedback
                    if not region.get("mute_tts", False):
                        region["mute_tts"] = True
                        region["mute_tts_until"] = time.time() + mute_timeout
                        btn.config(text=f"TTS Muted ({int(mute_timeout)}s)")
                    else:
                        region["mute_tts"] = False
                        region["mute_tts_until"] = 0
                        btn.config(text="TTS Mute")
                    
                    # Force immediate UI update
                    btn.update_idletasks()
                    
                    # Schedule background save and full UI update after a short delay
                    def background_save():
                        save_config(
                            regions, interval_var.get(), highlight_time_var.get(),
                            default_sound_var.get(), default_tts_var.get(), alert_threshold_var.get(),
                            green_text=green_text_var.get(), green_color=green_color_var.get(),
                            paused_text=paused_text_var.get(), paused_color=paused_color_var.get(),
                            alert_text=alert_text_var.get(), alert_color=alert_color_var.get(),
                            disabled_text=disabled_text_var.get(), disabled_color=disabled_color_var.get(),
                            pause_reminder_interval=pause_reminder_interval_var.get(),
                            target_window=target_window, window_filter=window_filter_var.get(),
                            unavailable_text=unavailable_text_var.get(), unavailable_color=unavailable_color_var.get()
                        )
                    
                    # Schedule the save for 50ms later to allow button to respond immediately
                    root.after(50, background_save)
                    
                return toggle_mute_tts
            
            # Check if TTS is available for this region (either region-specific or default)
            has_tts = bool(region.get("tts_message") or default_tts_var.get().strip())
            
            if has_tts:
                # Show mute TTS button and configure it
                mute_tts_btn.grid(row=2, column=0, sticky="ew", pady=2)
                
                # Create or reuse the toggle function
                if "tts_toggle" not in widgets["commands"]:
                    widgets["commands"]["tts_toggle"] = make_toggle_mute_tts()
                
                # Show countdown label only when TTS is muted and has remaining time
                mute_tts_label = widgets["mute_tts_label"]
                if region.get("mute_tts", False):
                    remaining = int(max(0, region.get("mute_tts_until", 0) - time.time()))
                    if remaining <= 0:
                        region["mute_tts"] = False
                        region["mute_tts_until"] = 0
                        mute_tts_btn.config(text="TTS Mute", command=widgets["commands"]["tts_toggle"])
                    else:
                        mute_tts_btn.config(text=f"TTS Muted ({remaining}s)", command=widgets["commands"]["tts_toggle"])
                else:
                    mute_tts_btn.config(text="TTS Mute", command=widgets["commands"]["tts_toggle"])
                # Hide the countdown label since we're putting it in the button
                mute_tts_label.grid_remove()
            else:
                # Hide mute TTS button and label when no TTS is available
                mute_tts_btn.grid_remove()
                mute_tts_label = widgets["mute_tts_label"]
                mute_tts_label.grid_remove()

            # Edit button
            def make_edit(idx=idx):
                def edit_region():
                    current_name = regions[idx].get("name", f"Region {idx+1}")
                    new_name = sd.askstring("Edit Region Name", "Enter new name for this region:", 
                                          initialvalue=current_name)
                    if new_name and new_name.strip():
                        regions[idx]["name"] = new_name.strip()
                        save_config(
                            regions, interval_var.get(), highlight_time_var.get(),
                            default_sound_var.get(), default_tts_var.get(), alert_threshold_var.get(),
                            green_text=green_text_var.get(), green_color=green_color_var.get(),
                            paused_text=paused_text_var.get(), paused_color=paused_color_var.get(),
                            alert_text=alert_text_var.get(), alert_color=alert_color_var.get(),
                            disabled_text=disabled_text_var.get(), disabled_color=disabled_color_var.get(),
                            pause_reminder_interval=pause_reminder_interval_var.get(),
                            target_window=target_window, window_filter=window_filter_var.get(),
                            unavailable_text=unavailable_text_var.get(), unavailable_color=unavailable_color_var.get()
                        )
                        update_region_display()
                return edit_region
            edit_btn.config(command=make_edit())

            # Remove button
            def make_remove(idx=idx):
                def remove_region():
                    regions.pop(idx)
                    if idx < len(previous_screenshots):
                        previous_screenshots.pop(idx)
                    
                    # Save config to persist the removal
                    save_config(
                        regions, interval_var.get(), highlight_time_var.get(),
                        default_sound_var.get(), default_tts_var.get(), alert_threshold_var.get(),
                        green_text=green_text_var.get(), green_color=green_color_var.get(),
                        paused_text=paused_text_var.get(), paused_color=paused_color_var.get(),
                        alert_text=alert_text_var.get(), alert_color=alert_color_var.get(),
                        disabled_text=disabled_text_var.get(), disabled_color=disabled_color_var.get(),
                        pause_reminder_interval=pause_reminder_interval_var.get(),
                        target_window=target_window, window_filter=window_filter_var.get(),
                        unavailable_text=unavailable_text_var.get(), unavailable_color=unavailable_color_var.get()
                    )
                    update_region_display()
                return remove_region
            remove_btn.config(command=make_remove())

            # Disable button
            def make_toggle_disable(region=region):
                def toggle_disable_region():
                    nonlocal last_reminder_time
                    current_disabled = region.get("disabled", False)
                    
                    if not current_disabled:
                        result = msgbox.askyesno(
                            "Confirm Disable", 
                            f"Are you sure you want to disable region '{region.get('name', f'Region {idx+1}')}'?\n\n"
                            "When disabled:\n"
                            "• No screenshots will be taken\n"
                            "• No comparisons will be performed\n"
                            "• No alerts will be triggered\n"
                            "• No reminder tones will play"
                        )
                        if not result:
                            return
                    
                    region["disabled"] = not current_disabled
                    if region.get("disabled", False):
                        region["alert"] = False
                        region["last_alert_time"] = 0
                        region["paused"] = False
                        last_reminder_time = time.time()
                    
                    save_config(
                        regions, interval_var.get(), highlight_time_var.get(),
                        default_sound_var.get(), default_tts_var.get(), alert_threshold_var.get(),
                        green_text=green_text_var.get(), green_color=green_color_var.get(),
                        paused_text=paused_text_var.get(), paused_color=paused_color_var.get(),
                        alert_text=alert_text_var.get(), alert_color=alert_color_var.get(),
                        disabled_text=disabled_text_var.get(), disabled_color=disabled_color_var.get(),
                        pause_reminder_interval=pause_reminder_interval_var.get(),
                        target_window=target_window, window_filter=window_filter_var.get(),
                        unavailable_text=unavailable_text_var.get(), unavailable_color=unavailable_color_var.get()
                    )
                    update_region_display()
                    update_status_bar()
                return toggle_disable_region
            
            disable_btn.config(
                text="Enable" if region.get("disabled", False) else "Disable",
                command=make_toggle_disable()
            )

            # Change Window button
            def make_change_window(idx=idx):
                def change_region_window():
                    current_region_window = regions[idx].get("target_window", target_window)
                    current_monitor = current_region_window.get('monitor_id') if current_region_window else None
                    
                    selector = WindowSelector(root, current_region_window, current_monitor, window_filter_var.get())
                    root.wait_window(selector.top)
                    if selector.selected_window:
                        regions[idx]["target_window"] = selector.selected_window
                        save_config(
                            regions, interval_var.get(), highlight_time_var.get(),
                            default_sound_var.get(), default_tts_var.get(), alert_threshold_var.get(),
                            green_text=green_text_var.get(), green_color=green_color_var.get(),
                            paused_text=paused_text_var.get(), paused_color=paused_color_var.get(),
                            alert_text=alert_text_var.get(), alert_color=alert_color_var.get(),
                            disabled_text=disabled_text_var.get(), disabled_color=disabled_color_var.get(),
                            pause_reminder_interval=pause_reminder_interval_var.get(),
                            target_window=target_window, window_filter=window_filter_var.get(),
                            unavailable_text=unavailable_text_var.get(), unavailable_color=unavailable_color_var.get()
                        )
                        # Reset the previous screenshot for this region to force refresh
                        if idx < len(previous_screenshots):
                            try:
                                new_window_img = capture_window(selector.selected_window['hwnd'])
                                if new_window_img:
                                    previous_screenshots[idx] = crop_region(new_window_img, regions[idx]["rect"])
                            except:
                                pass
                        update_region_display()
                return change_region_window
            change_window_btn.config(command=make_change_window())

        regions_frame.update_idletasks()
        update_status_bar()



    # Monitored Regions Section
    regions_frame_outer = ttk.LabelFrame(main_frame, text="Monitored Regions", padding=10)
    regions_frame_outer.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
    canvas = tk.Canvas(regions_frame_outer, borderwidth=0, background="#0a0a0a", highlightthickness=0)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    regions_frame = ttk.Frame(canvas, style="Region.TFrame")
    canvas_window = canvas.create_window((0, 0), window=regions_frame, anchor="nw", tags="regions_window")

    def on_frame_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
    def on_canvas_configure(event):
        canvas.itemconfig("regions_window", width=event.width)
    regions_frame.bind("<Configure>", on_frame_configure)
    canvas.bind("<Configure>", on_canvas_configure)
    regions_frame.grid_columnconfigure(0, weight=1)

    # Initialize displays
    update_region_display(force_update=True)  # Force initial update
    update_status_bar()

    # Monitoring Loop
    def check_alerts():
        nonlocal current_window_img, last_window_recheck, target_window
        
        # Always update status bar
        update_status_bar()
        
        now = time.time()
        
        # Periodic window reconnection disabled per user request
        # Check for missing windows more frequently - every 30 seconds
        # This is more responsive for detecting when applications restart
        # if now - last_window_recheck >= 30:  # 30 seconds instead of 2 minutes
        #     print("Performing periodic window availability check...")
        #     reconnected = try_reconnect_windows()
        #     if reconnected > 0:
        #         print(f"Window recheck completed - reconnected {reconnected} window(s)")
        #     else:
        #         print("Window recheck completed - no reconnections needed")
        #     last_window_recheck = now
        
        if paused or selecting_region:
            root.after(interval_var.get(), check_alerts)
            return

        # Check if all regions are connected - if so, optimize by skipping extra work
        all_regions_connected = are_all_regions_connected()
        
        # Log optimization status periodically (every 30 seconds) when all connected
        if all_regions_connected:
            if not hasattr(check_alerts, 'last_optimization_log'):
                check_alerts.last_optimization_log = 0
            
            if now - check_alerts.last_optimization_log >= 30:  # Log every 30 seconds
                active_count = len([r for r in regions if not r.get("disabled", False)])
                print(f"Optimization: All {active_count} regions connected - purging unnecessary connection attempts")
                check_alerts.last_optimization_log = now
        
        # Update current_window_img for the global target window (for adding new regions)
        # Only do this if not all regions are connected, to avoid unnecessary captures
        if target_window and not all_regions_connected:
            # Use cached capture - it will handle validity checking internally
            current_window_img = get_cached_window_capture(target_window['hwnd'])
            if not current_window_img:
                # Log the failure but don't attempt automatic reconnection
                if verbose_logging_var.get():
                    print(f"Global target window {target_window['title']} capture failed - window unavailable")
                pass
        elif all_regions_connected and target_window:
            # All regions connected - purge unnecessary global window capture attempts
            current_window_img = None
            # Only log this once per connection state change
            if not hasattr(check_alerts, 'logged_purge'):
                print(f"All regions connected - purged global target window capture for {target_window['title']}")
                check_alerts.logged_purge = True
        else:
            # Reset the purge logging flag when not all regions are connected
            if hasattr(check_alerts, 'logged_purge'):
                delattr(check_alerts, 'logged_purge')

        alert_display_time = alert_display_time_var.get()
        region_updates_needed = False  # Track if we need to update the display

        for idx, region in enumerate(regions):
            if region.get("paused", False) or region.get("disabled", False):
                continue
            
            # Get the target window for this specific region
            region_window = region.get("target_window", target_window)
            if not region_window:
                continue
            
            # Use cached capture for this specific region - it handles validity checking
            region_img = get_cached_window_capture(region_window['hwnd'])
            if not region_img:
                # Only log failure if not all regions are connected (to reduce spam when things are working)
                if not all_regions_connected and verbose_logging_var.get():
                    region_name = region.get('name', f'Region {idx+1}')
                    print(f"Region {idx} '{region_name}' window capture failed - window unavailable")
                
                # Window is unavailable - clear alert status and skip processing
                if region.get("alert", False):
                    region["alert"] = False
                    region["last_alert_time"] = 0
                    region_updates_needed = True
                continue
                
            # Initialize previous screenshots if needed
            if idx >= len(previous_screenshots):
                previous_screenshots.append(crop_region(region_img, region["rect"]))
                region["alert"] = False
                region["last_alert_time"] = 0
                continue

            try:
                prev_img = previous_screenshots[idx]
                curr_img = crop_region(region_img, region["rect"])

                if prev_img.size != curr_img.size or prev_img.width == 0 or prev_img.height == 0:
                    previous_screenshots[idx] = curr_img
                    region["alert"] = False
                    region["last_alert_time"] = 0
                    continue

                # Simple structural similarity comparison
                # Convert to grayscale for comparison
                prev_gray = prev_img.convert("L")
                curr_gray = curr_img.convert("L")
                
                # Use SSIM (Structural Similarity Index) for change detection
                score = ssim(np.array(prev_gray), np.array(curr_gray))
                is_alert = bool(score < alert_threshold_var.get())

                play_alert = False
                if is_alert:
                    last_alert = region.get("last_alert_time", 0)
                    if not region.get("alert", False) or (now - last_alert > alert_display_time):
                        play_alert = True
                        region["last_alert_time"] = now
                    region["alert"] = True
                    region_updates_needed = True
                else:
                    # Clear alert if it's been active for the display time OR if no alert is detected
                    if region.get("alert", False):
                        last_alert_time = region.get("last_alert_time", 0)
                        if (now - last_alert_time) >= alert_display_time:
                            region["alert"] = False
                            region_updates_needed = True
                            print(f"Cleared alert for region {idx} '{region.get('name', f'Region {idx+1}')}' after {alert_display_time}s")
                    
                # Force clear very old alerts (safety mechanism)
                if region.get("alert", False):
                    last_alert_time = region.get("last_alert_time", 0)
                    if (now - last_alert_time) > (alert_display_time * 2):  # Double the normal time
                        region["alert"] = False
                        region_updates_needed = True
                        print(f"Force cleared old alert for region {idx} '{region.get('name', f'Region {idx+1}')}' after {now - last_alert_time:.1f}s")

                # Only print debug info if verbose logging is enabled
                if verbose_logging_var.get() and (play_alert or region.get("alert", False)):
                    window_title = region_window.get('title', 'Unknown Window')
                    print(
                        f"[DEBUG] Region {idx} '{region.get('name', idx)}' [{window_title}]: "
                        f"SSIM={score:.4f}, alert={region.get('alert', False)}, play_alert={play_alert}"
                    )

                if play_alert:
                    sound_file = region.get("sound_file") or default_sound_var.get()
                    tts_message = region.get("tts_message") or default_tts_var.get().replace(
                        "{name}", region.get("name", f"Region {idx+1}")
                    )
                    if not region.get("mute_sound", False) and sound_file:
                        try:
                            play_sound(sound_file)
                        except Exception as e:
                            print(f"[ERROR] play_sound failed: {e}")
                    if not region.get("mute_tts", False) and tts_message:
                        try:
                            speak_tts(tts_message)
                        except Exception as e:
                            print(f"[ERROR] speak_tts failed: {e}")

                previous_screenshots[idx] = curr_img
                
            except Exception as e:
                print(f"Error processing region {idx}: {e}")

        # Only update display if there were actual changes, or periodically for thumbnail refresh
        current_time = time.time()
        if region_updates_needed:
            update_region_display()
            update_region_display.last_forced_update = current_time
        else:
            # Force periodic updates for thumbnail refresh (every 5 seconds)
            if (not hasattr(update_region_display, 'last_forced_update') or 
                current_time - update_region_display.last_forced_update > 5.0):
                update_region_display()
                update_region_display.last_forced_update = current_time
        
        root.after(interval_var.get(), check_alerts)

    root.after(5000, check_alerts)
    root.mainloop()

if __name__ == "__main__":
    main()


