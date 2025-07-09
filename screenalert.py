import pyautogui
from PIL import ImageTk, Image, ImageDraw, ImageFont
import tkinter as tk
from tkinter import ttk
import json
import os
from skimage.metrics import structural_similarity as ssim
import numpy as np
import tkinter.filedialog as fd
import tkinter.colorchooser as cc
import tkinter.simpledialog as sd
import platform
import time
import cv2
import imagehash
import pytesseract
from difflib import SequenceMatcher

# Platform-specific imports
if platform.system() == "Windows":
    import winsound
    try:
        import pyttsx3
    except ImportError:
        print("pyttsx3 not installed. TTS will not work.")
        pyttsx3 = None

# Try to auto-detect Tesseract installation on Windows
if platform.system() == "Windows":
    possible_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe".format(os.getenv('USERNAME')),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            print(f"Found Tesseract at: {path}")
            break
    else:
        print("Tesseract not found in common locations. Text comparison may not work.")
        print("Please install Tesseract or set pytesseract.pytesseract.tesseract_cmd manually.")

CONFIG_FILE = "screenalert_config.json"

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
                # Add defaults for all three states
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
        "pause_reminder_interval": 60  # seconds
    }

def save_config(
    regions, interval, highlight_time, default_sound="", default_tts="", alert_threshold=0.99,
    green_text="Green", green_color="#080",
    paused_text="Paused", paused_color="#08f",
    alert_text="Alert", alert_color="#a00",
    disabled_text="Disabled", disabled_color="#fa0",
    pause_reminder_interval=60
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
        "pause_reminder_interval": pause_reminder_interval
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

class RegionSelector:
    def __init__(self, master):
        self.region = None
        self.top = tk.Toplevel(master)
        self.top.attributes('-alpha', 0.3)
        self.top.configure(bg='black')
        screen_width, screen_height = pyautogui.size()
        self.top.geometry(f"{screen_width}x{screen_height}+0+0")
        self.top.overrideredirect(True)
        self.top.lift()
        self.top.focus_force()
        self.canvas = tk.Canvas(self.top, cursor="cross", bg='gray')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.start_x = self.start_y = self.rect = None
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.top.bind("<Escape>", self.on_escape)
        self.canvas.focus_set()  # Make sure canvas can receive key events

    def on_press(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=2
        )

    def on_drag(self, event):
        if self.start_x is None or self.start_y is None or self.rect is None:
            return
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_release(self, event):
        if self.start_x is None or self.start_y is None:
            return
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        x1, y1 = int(self.start_x), int(self.start_y)
        x2, y2 = int(end_x), int(end_y)
        left, top = min(x1, x2), min(y1, y2)
        width, height = abs(x2 - x1), abs(y2 - y1)
        self.region = (left, top, width, height)
        self.top.destroy()

    def on_escape(self, event):
        """Handle ESC key to cancel region selection"""
        self.region = None  # Set region to None to indicate cancellation
        self.top.destroy()

    def select(self):
        self.top.grab_set()
        self.top.wait_window()
        return self.region

def take_full_screenshot():
    try:
        return pyautogui.screenshot()
    except Exception as e:
        print(f"Screen capture failed: {e}")
        screen_width, screen_height = pyautogui.size()
        return Image.new("RGB", (screen_width, screen_height), color="#222")

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
            import winsound
            # Play a gentle two-tone chime using Windows system sounds
            # First tone - higher pitch (800Hz for 200ms)
            winsound.Beep(800, 200)
            time.sleep(0.1)  # Brief pause between tones
            # Second tone - lower pitch (600Hz for 300ms)
            winsound.Beep(600, 300)
        else:
            # For non-Windows systems, try to use system bell or beep
            try:
                # Try using paplay (PulseAudio) to generate tones
                os.system("paplay /usr/share/sounds/alsa/Front_Left.wav 2>/dev/null || beep -f 800 -l 200; sleep 0.1; beep -f 600 -l 300 2>/dev/null || echo -e '\\a'")
            except:
                # Fallback to system bell
                print("\a")  # ASCII bell character
    except Exception as e:
        print(f"Failed to play pause reminder tone: {e}")
        # Fallback to system bell
        print("\a")

def play_sound(sound_file):
    if not sound_file:
        return
    try:
        if platform.system() == "Windows":
            import winsound
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
        if platform.system() == "Windows":
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(message)
            engine.runAndWait()
        else:
            if os.system(f"espeak '{message}' &") != 0:
                os.system(f"say '{message}' &")
    except Exception as e:
        print(f"Failed to speak TTS: {e}")

def main():
    config = load_config()
    regions = config["regions"]
    interval = int(config.get("interval", 1000))
    highlight_time = int(config.get("highlight_time", 5))

    root = tk.Tk()
    root.title("Screen Region Monitor")
    root.geometry("1000x600")

    interval_var = tk.IntVar(value=interval)
    highlight_time_var = tk.IntVar(value=highlight_time)
    alert_display_time_var = tk.IntVar(value=highlight_time)
    mute_timeout_var = tk.IntVar(value=10)
    default_sound_var = tk.StringVar(value=config.get("default_sound", ""))
    default_tts_var = tk.StringVar(value=config.get("default_tts", "Alert {name}"))
    alert_threshold_var = tk.DoubleVar(value=config.get("alert_threshold", 0.99))
    green_text_var = tk.StringVar(value=config.get("green_text", "Green"))
    green_color_var = tk.StringVar(value=config.get("green_color", "#080"))
    paused_text_var = tk.StringVar(value=config.get("paused_text", "Paused"))
    paused_color_var = tk.StringVar(value=config.get("paused_color", "#08f"))
    alert_text_var = tk.StringVar(value=config.get("alert_text", "Alert"))
    alert_color_var = tk.StringVar(value=config.get("alert_color", "#a00"))
    disabled_text_var = tk.StringVar(value=config.get("disabled_text", "Disabled"))
    disabled_color_var = tk.StringVar(value=config.get("disabled_color", "#fa0"))
    pause_reminder_interval_var = tk.IntVar(value=config.get("pause_reminder_interval", 60))

    # Notebook tabs
    notebook = ttk.Notebook(root)
    regions_tab = ttk.Frame(notebook)
    settings_tab = ttk.Frame(notebook)
    notebook.add(regions_tab, text="Regions")
    notebook.add(settings_tab, text="Settings")
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Status bar
    status = ttk.Label(root, text="Ready", anchor="w")
    status.pack(fill=tk.X, side=tk.BOTTOM)

    paused = False
    selecting_region = False  # Track when we're selecting a region
    last_reminder_time = 0  # Track when last pause reminder was played
    full_img = take_full_screenshot()
    previous_screenshots = [crop_region(full_img, r["rect"]) for r in regions]

    def update_pause_button_text():
        pause_button.config(text="Resume" if paused else "Pause")

    def toggle_pause():
        nonlocal paused, last_reminder_time
        paused = not paused
        if paused:
            last_reminder_time = time.time()  # Reset reminder timer when pausing
        update_pause_button_text()
        update_status_bar()  # Update status immediately

    def add_region():
        nonlocal selecting_region
        if paused or selecting_region:
            return
        selecting_region = True
        root.withdraw()
        region = RegionSelector(root).select()
        root.deiconify()
        if region and all(region):
            region_name = f"Region {len(regions)+1}"
            regions.append({
                "rect": region,
                "name": region_name,
                "paused": False,
                "disabled": False,
                "mute_sound": False,
                "mute_tts": False,
                "mute_sound_until": 0,
                "mute_tts_until": 0,
                "last_alert_time": 0
            })
            full_img = take_full_screenshot()
            previous_screenshots.append(crop_region(full_img, region))
            update_region_display()
        selecting_region = False

    region_widgets = []  # Track region widgets for reuse

    # --- Status Bar Update Function ---
    def update_status_bar():
        """Update status bar with pause information and handle pause reminders"""
        nonlocal last_reminder_time
        
        now = time.time()
        reminder_interval = pause_reminder_interval_var.get()
        
        # Check if anything is paused (disabled regions should NOT trigger reminders)
        global_paused = paused
        # Only count regions as paused if they are not disabled
        any_region_paused = any(region.get("paused", False) and not region.get("disabled", False) for region in regions)
        any_region_disabled = any(region.get("disabled", False) for region in regions)
        something_paused = global_paused or any_region_paused
        
        if something_paused:
            # Calculate time since last reminder
            time_since_reminder = now - last_reminder_time
            
            # Update status bar with countdown
            if reminder_interval > 0:
                remaining_time = max(0, reminder_interval - time_since_reminder)
                if global_paused and any_region_paused:
                    paused_count = sum(1 for r in regions if r.get('paused', False) and not r.get('disabled', False))
                    status_text = f"PAUSED (Global + {paused_count} regions) - Next reminder in {remaining_time:.0f}s"
                elif global_paused:
                    status_text = f"PAUSED (Global) - Next reminder in {remaining_time:.0f}s"
                else:
                    paused_count = sum(1 for r in regions if r.get('paused', False) and not r.get('disabled', False))
                    status_text = f"PAUSED ({paused_count} region{'s' if paused_count > 1 else ''}) - Next reminder in {remaining_time:.0f}s"
            else:
                if global_paused and any_region_paused:
                    paused_count = sum(1 for r in regions if r.get('paused', False) and not r.get('disabled', False))
                    disabled_count = sum(1 for r in regions if r.get("disabled", False))
                    status_text = f"PAUSED (Global + {paused_count} regions)"
                    if disabled_count > 0:
                        status_text += f", {disabled_count} disabled"
                elif global_paused:
                    disabled_count = sum(1 for r in regions if r.get("disabled", False))
                    status_text = "PAUSED (Global)"
                    if disabled_count > 0:
                        status_text += f", {disabled_count} regions disabled"
                else:
                    paused_count = sum(1 for r in regions if r.get('paused', False) and not r.get('disabled', False))
                    disabled_count = sum(1 for r in regions if r.get("disabled", False))
                    status_text = f"PAUSED ({paused_count} region{'s' if paused_count > 1 else ''})"
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
            if disabled_count > 0:
                status_text = f"Monitoring... ({disabled_count} region{'s' if disabled_count > 1 else ''} disabled)"
            else:
                status_text = "Monitoring..."
            
        status.config(text=status_text)

    def update_region_display():
        nonlocal paused

        full_img = take_full_screenshot()
        update_region_display.img_refs = []

        # Ensure region_widgets matches regions
        while len(region_widgets) < len(regions):
            # Create new region frame and widgets
            rf = ttk.Frame(regions_frame, style="Region.TFrame", padding=4, relief="raised")
            rf.grid_columnconfigure(0, minsize=28, weight=0)
            rf.grid_columnconfigure(1, minsize=120, weight=0)
            rf.grid_columnconfigure(2, weight=1)
            rf.grid_columnconfigure(3, weight=0)
            rf.grid_columnconfigure(4, weight=0)

            # Status canvas
            status_canvas = tk.Canvas(rf, width=48, height=100, highlightthickness=0, bd=0)
            status_canvas.grid(row=0, column=0, rowspan=3, sticky="nsw", padx=(0, 8), pady=0)

            # Thumbnail canvas
            img_canvas = tk.Canvas(rf, width=120, height=100, highlightthickness=0, bd=0, bg="#111")
            img_canvas.grid(row=0, column=1, rowspan=3, sticky="nsew", padx=0, pady=0)

            # Name label
            name_label = ttk.Label(rf, style="Region.TLabel")
            name_label.grid(row=0, column=2, sticky="w", padx=(0, 8))

            # Controls frame
            controls_frame = ttk.Frame(rf, style="Region.TFrame")
            controls_frame.grid(row=0, column=3, rowspan=3, sticky="e", padx=2)
            controls_frame.grid_columnconfigure(0, weight=1)

            # Pause button
            pause_btn = ttk.Button(controls_frame, width=10)
            pause_btn.grid(row=0, column=0, sticky="ew", pady=2)

            # Mute sound button
            mute_sound_btn = ttk.Button(controls_frame, style="Mute.TButton", width=14)
            mute_sound_btn.grid(row=1, column=0, sticky="ew", pady=2)

            # Mute TTS button
            mute_tts_btn = ttk.Button(controls_frame, style="Mute.TButton", width=14)
            mute_tts_btn.grid(row=2, column=0, sticky="ew", pady=2)

            # Disable button
            disable_btn = ttk.Button(controls_frame, width=14)
            disable_btn.grid(row=3, column=0, sticky="ew", pady=2)

            # Mute sound label
            mute_sound_label = ttk.Label(controls_frame, width=6)
            mute_sound_label.grid(row=1, column=2, sticky="w", padx=(4,0))

            # Mute TTS label
            mute_tts_label = ttk.Label(controls_frame, width=6)
            mute_tts_label.grid(row=2, column=2, sticky="w", padx=(4,0))

            # Edit button
            edit_btn = ttk.Button(rf, text="✏️", width=3)
            edit_btn.grid(row=0, column=4, sticky="ne", padx=(8,2), pady=2)

            # Remove button
            remove_btn = ttk.Button(rf, text="❌", width=3)
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
                "edit_btn": edit_btn,
                "remove_btn": remove_btn,
            })

        # Remove extra widgets if regions were deleted
        while len(region_widgets) > len(regions):
            widgets = region_widgets.pop()
            widgets["frame"].destroy()

        # Update all widgets in place
        for idx, region in enumerate(regions):
            widgets = region_widgets[idx]
            rf = widgets["frame"]
            status_canvas = widgets["status_canvas"]
            img_canvas = widgets["img_canvas"]
            name_label = widgets["name_label"]
            pause_btn = widgets["pause_btn"]
            mute_sound_btn = widgets["mute_sound_btn"]
            mute_tts_btn = widgets["mute_tts_btn"]
            disable_btn = widgets["disable_btn"]
            edit_btn = widgets["edit_btn"]
            remove_btn = widgets["remove_btn"]

            # Status Indicator
            status_height = 100
            status_width = 48
            if region.get("disabled", False):
                status_text = disabled_text_var.get()
                status_color = disabled_color_var.get()
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
            img_status = create_rotated_text_image(status_text, status_width, status_height, color="#fff", bgcolor=status_color, font_size=16)
            status_imgtk = ImageTk.PhotoImage(img_status)
            status_canvas.create_image(
                status_width // 2,
                status_height // 2,
                anchor="center",
                image=status_imgtk
            )
            update_region_display.img_refs.append(status_imgtk)

            # Thumbnail
            thumb_width, thumb_height = 120, 100
            cropped = crop_region(full_img, region["rect"])
            if cropped.width == 0 or cropped.height == 0:
                cropped = Image.new("RGB", (10, 10), "#222")
            cropped.thumbnail((thumb_width, thumb_height), Image.LANCZOS)
            thumb_img = cropped
            imgtk = ImageTk.PhotoImage(thumb_img)
            img_canvas.delete("all")
            img_canvas.create_image((thumb_width-thumb_img.width)//2, (thumb_height-thumb_img.height)//2, anchor="nw", image=imgtk)
            img_canvas.create_rectangle(2, 2, thumb_width-2, thumb_height-2, outline="#888", width=2, dash=(4,2))
            update_region_display.img_refs.append(imgtk)

            # Name label
            name_label.config(text=region.get("name", f"Region {idx+1}"))

            # Controls
            def toggle_pause_region(region=region):
                nonlocal last_reminder_time
                was_paused = region.get("paused", False)
                region["paused"] = not was_paused
                if region.get("paused", False):
                    last_reminder_time = time.time()  # Reset reminder timer when pausing a region
                save_config(
                    regions,
                    interval_var.get(),
                    highlight_time_var.get(),
                    default_sound_var.get(),
                    default_tts_var.get(),
                    alert_threshold_var.get(),
                    green_text=green_text_var.get(),
                    green_color=green_color_var.get(),
                    paused_text=paused_text_var.get(),
                    paused_color=paused_color_var.get(),
                    alert_text=alert_text_var.get(),
                    alert_color=alert_color_var.get(),
                    disabled_text=disabled_text_var.get(),
                    disabled_color=disabled_color_var.get(),
                    pause_reminder_interval=pause_reminder_interval_var.get()
                )
                update_region_display()
                update_status_bar()  # Update status immediately
            pause_btn.config(
                text="Resume" if region.get("paused", False) else "Pause",
                command=toggle_pause_region
            )

            def toggle_mute_sound(region=region):
                mute_timeout = mute_timeout_var.get() * 60  # minutes to seconds
                if not region.get("mute_sound", False):
                    region["mute_sound"] = True
                    region["mute_sound_until"] = time.time() + mute_timeout
                else:
                    region["mute_sound"] = False
                    region["mute_sound_until"] = 0
                save_config(
                    regions,
                    interval_var.get(),
                    highlight_time_var.get(),
                    default_sound_var.get(),
                    default_tts_var.get(),
                    alert_threshold_var.get(),
                    green_text=green_text_var.get(),
                    green_color=green_color_var.get(),
                    paused_text=paused_text_var.get(),
                    paused_color=paused_color_var.get(),
                    alert_text=alert_text_var.get(),
                    alert_color=alert_color_var.get(),
                    disabled_text=disabled_text_var.get(),
                    disabled_color=disabled_color_var.get(),
                    pause_reminder_interval=pause_reminder_interval_var.get()
                )
                update_region_display()
            mute_sound_btn.config(
                text="Sound Mute" if not region.get("mute_sound", False) else "Sound Muted",
                command=toggle_mute_sound
            )
            # Countdown label for mute sound
            if "mute_sound_label" not in widgets:
                mute_sound_label = ttk.Label(controls_frame, width=6)
                mute_sound_label.grid(row=1, column=2, sticky="w", padx=(4,0))
                widgets["mute_sound_label"] = mute_sound_label
            else:
                mute_sound_label = widgets["mute_sound_label"]
            if region.get("mute_sound", False):
                remaining = int(max(0, region.get("mute_sound_until", 0) - time.time()))
                if remaining <= 0:
                    region["mute_sound"] = False
                    region["mute_sound_until"] = 0
                    mute_sound_label.config(text="")
                else:
                    mute_sound_label.config(text=f"{remaining}s")
            else:
                mute_sound_label.config(text="")

            # --- TTS Button and Countdown ---
            def toggle_mute_tts(region=region):
                mute_timeout = mute_timeout_var.get() * 60  # minutes to seconds
                if not region.get("mute_tts", False):
                    region["mute_tts"] = True
                    region["mute_tts_until"] = time.time() + mute_timeout
                else:
                    region["mute_tts"] = False
                    region["mute_tts_until"] = 0
                save_config(
                    regions,
                    interval_var.get(),
                    highlight_time_var.get(),
                    default_sound_var.get(),
                    default_tts_var.get(),
                    alert_threshold_var.get(),
                    green_text=green_text_var.get(),
                    green_color=green_color_var.get(),
                    paused_text=paused_text_var.get(),
                    paused_color=paused_color_var.get(),
                    alert_text=alert_text_var.get(),
                    alert_color=alert_color_var.get(),
                    disabled_text=disabled_text_var.get(),
                    disabled_color=disabled_color_var.get(),
                    pause_reminder_interval=pause_reminder_interval_var.get()
                )
                update_region_display()
            mute_tts_btn.config(
                text="TTS Mute" if not region.get("mute_tts", False) else "TTS Muted",
                command=toggle_mute_tts
            )
            # Countdown label for mute tts
            mute_tts_label = widgets["mute_tts_label"]
            if region.get("mute_tts", False):
                remaining = int(max(0, region.get("mute_tts_until", 0) - time.time()))
                if remaining <= 0:
                    region["mute_tts"] = False
                    region["mute_tts_until"] = 0
                    mute_tts_label.config(text="")
                else:
                    mute_tts_label.config(text=f"{remaining}s")
            else:
                mute_tts_label.config(text="")

            # Edit button functionality
            def make_edit(idx=idx):
                def _edit():
                    current_name = regions[idx].get("name", f"Region {idx+1}")
                    new_name = sd.askstring("Edit Region Name", "Enter new name for this region:", initialvalue=current_name)
                    if new_name and new_name.strip():
                        regions[idx]["name"] = new_name.strip()
                        save_config(
                            regions,
                            interval_var.get(),
                            highlight_time_var.get(),
                            default_sound_var.get(),
                            default_tts_var.get(),
                            alert_threshold_var.get(),
                            green_text=green_text_var.get(),
                            green_color=green_color_var.get(),
                            paused_text=paused_text_var.get(),
                            paused_color=paused_color_var.get(),
                            alert_text=alert_text_var.get(),
                            alert_color=alert_color_var.get(),
                            disabled_text=disabled_text_var.get(),
                            disabled_color=disabled_color_var.get(),
                            pause_reminder_interval=pause_reminder_interval_var.get()
                        )
                        update_region_display()
                return _edit
            edit_btn.config(command=make_edit(idx))

            def make_remove(idx=idx):
                def _remove():
                    regions.pop(idx)
                    previous_screenshots.pop(idx)
                    update_region_display()
                return _remove
            remove_btn.config(command=make_remove(idx))

            # Disable button functionality
            def toggle_disable_region(region=region):
                nonlocal last_reminder_time
                import tkinter.messagebox as msgbox
                current_disabled = region.get("disabled", False)
                
                if not current_disabled:
                    # Confirm disabling
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
                    # Clear alert state when disabling
                    region["alert"] = False
                    region["last_alert_time"] = 0
                    # Also clear paused state if it was paused
                    region["paused"] = False
                    # Reset reminder timer since we're changing state
                    last_reminder_time = time.time()
                
                save_config(
                    regions,
                    interval_var.get(),
                    highlight_time_var.get(),
                    default_sound_var.get(),
                    default_tts_var.get(),
                    alert_threshold_var.get(),
                    green_text=green_text_var.get(),
                    green_color=green_color_var.get(),
                    paused_text=paused_text_var.get(),
                    paused_color=paused_color_var.get(),
                    alert_text=alert_text_var.get(),
                    alert_color=alert_color_var.get(),
                    disabled_text=disabled_text_var.get(),
                    disabled_color=disabled_color_var.get(),
                    pause_reminder_interval=pause_reminder_interval_var.get()
                )
                update_region_display()
                update_status_bar()
            
            disable_btn.config(
                text="Enable" if region.get("disabled", False) else "Disable",
                command=toggle_disable_region
            )

        regions_frame.update_idletasks()
        # Update status bar when regions display is updated
        update_status_bar()

    # --- Controls ---
    controls = ttk.LabelFrame(regions_tab, text="Controls", padding=10)
    controls.pack(fill=tk.X, pady=(0, 10))
    add_btn = ttk.Button(controls, text="➕ Add Region", command=add_region)
    add_btn.pack(side=tk.LEFT, padx=5)
    pause_button = ttk.Button(controls, text="Pause", command=toggle_pause)
    pause_button.pack(side=tk.LEFT, padx=5)

    # --- Monitored Regions Section ---
    regions_frame_outer = ttk.LabelFrame(regions_tab, text="Monitored Regions", padding=10)
    regions_frame_outer.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
    canvas = tk.Canvas(regions_frame_outer, borderwidth=0, background="#222", highlightthickness=0)
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

    # --- Settings Section ---
    settings_frame = ttk.LabelFrame(settings_tab, text="Settings", padding=10)
    settings_frame.pack(fill=tk.X, pady=(0, 10))
    ttk.Label(settings_frame, text="Interval (ms):").grid(row=0, column=0, sticky="e", padx=5, pady=2)
    interval_spin = ttk.Spinbox(settings_frame, from_=100, to=10000, increment=100, textvariable=interval_var, width=7)
    interval_spin.grid(row=0, column=1, sticky="w", padx=5, pady=2)
    ttk.Label(settings_frame, text="Alert Display Time (s):").grid(row=1, column=0, sticky="e", padx=5, pady=2)
    alert_display_spin = ttk.Spinbox(settings_frame, from_=1, to=60, increment=1, textvariable=alert_display_time_var, width=7)
    alert_display_spin.grid(row=1, column=1, sticky="w", padx=5, pady=2)
    alert_display_spin.bind("<FocusOut>", lambda e: save_settings())
    ttk.Label(settings_frame, text="Mute Timeout (min):").grid(row=2, column=0, sticky="e", padx=5, pady=2)
    mute_timeout_spin = ttk.Spinbox(settings_frame, from_=1, to=60, increment=1, textvariable=mute_timeout_var, width=5)
    mute_timeout_spin.grid(row=2, column=1, sticky="w", padx=5, pady=2)

    def browse_default_sound():
        file = fd.askopenfilename(title="Select Sound File", filetypes=[("Audio Files", "*.wav *.mp3 *.ogg"), ("All Files", "*.*")])
        if file:
            default_sound_var.set(file)
            save_settings()

    ttk.Label(settings_frame, text="Default Alert Sound:").grid(row=3, column=0, sticky="e", padx=5, pady=2)
    default_sound_entry = ttk.Entry(settings_frame, textvariable=default_sound_var, width=25)
    default_sound_entry.grid(row=3, column=1, sticky="w", padx=5, pady=2)
    default_sound_entry.bind("<FocusOut>", lambda e: save_settings())
    browse_default_btn = ttk.Button(settings_frame, text="Browse...", command=browse_default_sound)
    browse_default_btn.grid(row=3, column=2, sticky="w", padx=2, pady=2)
    ttk.Label(settings_frame, text="Default TTS:").grid(row=4, column=0, sticky="e", padx=5, pady=2)
    default_tts_entry = ttk.Entry(settings_frame, textvariable=default_tts_var, width=20)
    default_tts_entry.grid(row=4, column=1, sticky="w", padx=5, pady=2)
    default_tts_entry.bind("<FocusOut>", lambda e: save_settings())
    ttk.Label(settings_frame, text="Alert Threshold (0-1):").grid(row=5, column=0, sticky="e", padx=5, pady=2)
    threshold_spin = ttk.Spinbox(settings_frame, from_=0.80, to=1.00, increment=0.01, textvariable=alert_threshold_var, width=7, format="%.2f")
    threshold_spin.grid(row=5, column=1, sticky="w", padx=5, pady=2)
    threshold_spin.bind("<FocusOut>", lambda e: save_settings())

    # Pause Reminder Interval
    ttk.Label(settings_frame, text="Pause Reminder (sec):").grid(row=5, column=3, sticky="e", padx=5, pady=2)
    pause_reminder_spin = ttk.Spinbox(settings_frame, from_=10, to=600, increment=10, textvariable=pause_reminder_interval_var, width=7)
    pause_reminder_spin.grid(row=5, column=4, sticky="w", padx=5, pady=2)
    pause_reminder_spin.bind("<FocusOut>", lambda e: save_settings())

    # Green State
    ttk.Label(settings_frame, text="Normal Text:").grid(row=6, column=0, sticky="e", padx=5, pady=2)
    green_text_entry = ttk.Entry(settings_frame, textvariable=green_text_var, width=12)
    green_text_entry.grid(row=6, column=1, sticky="w", padx=2, pady=2)
    green_text_entry.bind("<FocusOut>", lambda e: save_settings())
    green_color_btn = ttk.Button(settings_frame, text="Color...", width=8)
    green_color_btn.grid(row=6, column=2, sticky="w", padx=2, pady=2)
    def choose_green_color():
        color = cc.askcolor(color=green_color_var.get())[1]
        if color:
            green_color_var.set(color)
            save_settings()
    green_color_btn.config(command=choose_green_color)

    # Paused State
    ttk.Label(settings_frame, text="Paused Text:").grid(row=7, column=0, sticky="e", padx=5, pady=2)
    paused_text_entry = ttk.Entry(settings_frame, textvariable=paused_text_var, width=12)
    paused_text_entry.grid(row=7, column=1, sticky="w", padx=2, pady=2)
    paused_text_entry.bind("<FocusOut>", lambda e: save_settings())
    paused_color_btn = ttk.Button(settings_frame, text="Color...", width=8)
    paused_color_btn.grid(row=7, column=2, sticky="w", padx=2, pady=2)
    def choose_paused_color():
        color = cc.askcolor(color=paused_color_var.get())[1]
        if color:
            paused_color_var.set(color)
            save_settings()
    paused_color_btn.config(command=choose_paused_color)

    # Alert State
    ttk.Label(settings_frame, text="Alert Text:").grid(row=8, column=0, sticky="e", padx=5, pady=2)
    alert_text_entry = ttk.Entry(settings_frame, textvariable=alert_text_var, width=12)
    alert_text_entry.grid(row=8, column=1, sticky="w", padx=2, pady=2)
    alert_text_entry.bind("<FocusOut>", lambda e: save_settings())
    alert_color_btn = ttk.Button(settings_frame, text="Color...", width=8)
    alert_color_btn.grid(row=8, column=2, sticky="w", padx=2, pady=2)
    def choose_alert_color():
        color = cc.askcolor(color=alert_color_var.get())[1]
        if color:
            alert_color_var.set(color)
            save_settings()
    alert_color_btn.config(command=choose_alert_color)

    # Disabled State
    ttk.Label(settings_frame, text="Disabled Text:").grid(row=9, column=0, sticky="e", padx=5, pady=2)
    disabled_text_entry = ttk.Entry(settings_frame, textvariable=disabled_text_var, width=12)
    disabled_text_entry.grid(row=9, column=1, sticky="w", padx=2, pady=2)
    disabled_text_entry.bind("<FocusOut>", lambda e: save_settings())
    disabled_color_btn = ttk.Button(settings_frame, text="Color...", width=8)
    disabled_color_btn.grid(row=9, column=2, sticky="w", padx=2, pady=2)
    def choose_disabled_color():
        color = cc.askcolor(color=disabled_color_var.get())[1]
        if color:
            disabled_color_var.set(color)
            save_settings()
    disabled_color_btn.config(command=choose_disabled_color)

    def save_settings():
        save_config(
            regions,
            interval_var.get(),
            alert_display_time_var.get(),
            default_sound_var.get(),
            default_tts_var.get(),
            alert_threshold_var.get(),
            green_text=green_text_var.get(),
            green_color=green_color_var.get(),
            paused_text=paused_text_var.get(),
            paused_color=paused_color_var.get(),
            alert_text=alert_text_var.get(),
            alert_color=alert_color_var.get(),
            disabled_text=disabled_text_var.get(),
            disabled_color=disabled_color_var.get(),
            pause_reminder_interval=pause_reminder_interval_var.get()
        )

    save_settings_btn = ttk.Button(settings_frame, text="Save Settings", command=save_settings)
    save_settings_btn.grid(row=10, column=0, columnspan=3, pady=(10, 0))

    update_region_display()
    
    # Initialize status bar
    update_status_bar()

    # --- Monitoring Loop ---
    def check_alerts():
        # Always update status bar to handle pause reminders
        update_status_bar()
        
        if paused or selecting_region:
            root.after(interval_var.get(), check_alerts)
            return

        full_img = take_full_screenshot()
        now = time.time()
        alert_display_time = alert_display_time_var.get()

        for idx, region in enumerate(regions):
            if region.get("paused", False) or region.get("disabled", False):
                continue
            if idx >= len(previous_screenshots):
                previous_screenshots.append(crop_region(full_img, region["rect"]))
                region["alert"] = False
                region["last_alert_time"] = 0
                continue

            prev_img = previous_screenshots[idx]
            curr_img = crop_region(full_img, region["rect"])

            if prev_img.size != curr_img.size or prev_img.width == 0 or prev_img.height == 0:
                previous_screenshots[idx] = curr_img
                region["alert"] = False
                region["last_alert_time"] = 0
                continue

            score = ssim(np.array(prev_img.convert("L")), np.array(curr_img.convert("L")))
            is_alert = bool(score < alert_threshold_var.get())

            play_alert = False
            if is_alert:
                last_alert = region.get("last_alert_time", 0)
                if not region.get("alert", False) or (now - last_alert > alert_display_time):
                    play_alert = True
                    region["last_alert_time"] = now
                region["alert"] = True
            else:
                if region.get("alert", False) and (now - region.get("last_alert_time", 0) >= alert_display_time):
                    region["alert"] = False
                region["last_alert_time"] = region.get("last_alert_time", 0)

            print(
                f"[DEBUG] Region {idx} '{region.get('name', idx)}': "
                f"SSIM={score:.4f}, "
                f"alert={region.get('alert', False)}, play_alert={play_alert}"
            )

            if play_alert:
                sound_file = region.get("sound_file") or default_sound_var.get()
                tts_message = region.get("tts_message") or default_tts_var.get().replace("{name}", region.get("name", f"Region {idx+1}"))
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

        update_region_display()
        root.after(interval_var.get(), check_alerts)

    root.after(5000, check_alerts)
    root.mainloop()

if __name__ == "__main__":
    main()

def extract_text_from_image(img, preprocess=True, debug_save=False):
    """
    Extract text from image using OCR with gaming UI optimizations
    Returns: (text, confidence)
    """
    try:
        # Convert PIL Image to numpy array for OpenCV processing
        img_array = np.array(img)
        
        if preprocess:
            # PERFORMANCE OPTIMIZATION: Reduced preprocessing for speed
            # Scale up the image for better OCR (but less than before for speed)
            scale_factor = 2 if min(img.size) < 200 else 1.5
            if scale_factor > 1:
                img_scaled = img.resize((int(img.width * scale_factor), int(img.height * scale_factor)), Image.LANCZOS)
                img_array = np.array(img_scaled)
            
            # Convert to grayscale
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array
            
            # Enhance contrast using CLAHE (reduced parameters for speed)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4,4))
            enhanced = clahe.apply(gray)
            
            # PERFORMANCE: Try only the 2 best preprocessing methods instead of 4
            processed_images = []
            
            # Method 1: Simple threshold with enhanced contrast (usually best for UI)
            _, thresh1 = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_images.append(("enhanced_threshold", Image.fromarray(thresh1)))
            
            # Method 2: Adaptive threshold (good for varied lighting)
            thresh2 = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            processed_images.append(("adaptive_threshold", Image.fromarray(thresh2)))
            
            # Debug: Save processed images if requested (but only first method for speed)
            if debug_save:
                timestamp = int(time.time())
                try:
                    if scale_factor > 1:
                        img_scaled.save(f"debug_scaled_{timestamp}.png")
                    Image.fromarray(enhanced).save(f"debug_enhanced_{timestamp}.png")
                    # Only save first processed image for performance
                    processed_images[0][1].save(f"debug_{processed_images[0][0]}_{timestamp}.png")
                    print(f"[OCR DEBUG] Saved processed images with timestamp {timestamp}")
                except:
                    pass
            
            # Try OCR on each processed version and pick the best result
            best_text, best_conf = "", 0
            best_method = "original"
            
            for method_name, processed_img in processed_images:
                try:
                    text, conf = _extract_text_with_tesseract(processed_img)
                    if conf > best_conf and len(text.strip()) > 0:
                        best_text, best_conf = text, conf
                        best_method = method_name
                except:
                    continue
                
                # PERFORMANCE: Early exit if we get good confidence
                if conf > 70:  # Good enough confidence, no need to try other methods
                    break
            
            # Also try the original enhanced image if we didn't get good results
            if best_conf < 50:  # Only if we don't have good results yet
                try:
                    text, conf = _extract_text_with_tesseract(Image.fromarray(enhanced))
                    if conf > best_conf and len(text.strip()) > 0:
                        best_text, best_conf = text, conf
                        best_method = "enhanced_original"
                except:
                    pass
            
            return best_text, best_conf
        else:
            return _extract_text_with_tesseract(img)
        
    except Exception as e:
        print(f"OCR extraction failed: {e}")
        return "", 0

def _extract_text_with_tesseract(img):
    """
    Helper function to extract text using Tesseract with optimized settings for gaming UI
    PERFORMANCE OPTIMIZED: Reduced configurations for speed
    """
    # Use fewer OCR configurations for better performance
    configs = [
        # Standard configuration - usually works best
        '--oem 3 --psm 6',
        # Single text line - good for UI elements
        '--oem 3 --psm 7',
        # Sparse text - find as much text as possible
        '--oem 3 --psm 11'
    ]
    
    best_text, best_conf = "", 0
    
    for config in configs:
        try:
            # Get text and confidence data
            data = pytesseract.image_to_data(img, config=config, output_type=pytesseract.Output.DICT)
            
            # Extract text and calculate average confidence
            text_parts = []
            confidences = []
            
            for i in range(len(data['text'])):
                if int(data['conf'][i]) > 15:  # Lower threshold for gaming UI
                    text = data['text'][i].strip()
                    if text and len(text) > 0:  # Only include non-empty text
                        text_parts.append(text)
                        confidences.append(int(data['conf'][i]))
            
            if text_parts:
                full_text = ' '.join(text_parts)
                avg_confidence = np.mean(confidences)
                
                # Prefer results with more text or higher confidence
                score = len(full_text) * 0.1 + avg_confidence
                current_score = len(best_text) * 0.1 + best_conf
                
                if score > current_score:
                    best_text, best_conf = full_text, avg_confidence
                
                # PERFORMANCE: Early exit if we get really good confidence
                if avg_confidence > 80 and len(full_text) > 3:
                    break
                    
        except Exception as e:
            continue
    
    return best_text, best_conf

def compare_text_content(text1, text2, similarity_threshold=0.8):
    """
    Compare two text strings and return similarity score
    Returns: (similarity_score, is_different, details)
    """
    try:
        if not text1 and not text2:
            return 1.0, False, "Both texts empty"
        
        if not text1 or not text2:
            return 0.0, True, f"One text empty: '{text1[:50]}...' vs '{text2[:50]}...'"
        
        # Clean and normalize text
        clean_text1 = ' '.join(text1.split()).lower().strip()
        clean_text2 = ' '.join(text2.split()).lower().strip()
        
        # Calculate similarity using SequenceMatcher
        similarity = SequenceMatcher(None, clean_text1, clean_text2).ratio()
        
        is_different = similarity < similarity_threshold
        
        # Create detailed comparison
        if len(clean_text1) > 100 or len(clean_text2) > 100:
            text1_preview = clean_text1[:50] + "..." if len(clean_text1) > 50 else clean_text1
            text2_preview = clean_text2[:50] + "..." if len(clean_text2) > 50 else clean_text2
        else:
            text1_preview = clean_text1
            text2_preview = clean_text2
        
        details = f"Text sim: {similarity:.3f}, '{text1_preview}' vs '{text2_preview}'"
        
        return similarity, is_different, details
        
    except Exception as e:
        print(f"Text comparison failed: {e}")
        return 0.5, False, f"Comparison error: {e}"

def advanced_image_comparison(img1, img2, method="combined"):
    """
    Advanced image comparison using multiple methods to reduce false positives
    PERFORMANCE OPTIMIZED: Early exits and selective processing
    Returns: (similarity_score, confidence_score, details)
    """
    if img1.size != img2.size:
        return 0.0, 1.0, "Size mismatch"
    
    results = {}
    
    # Method 1: Text comparison (OCR-based) - only if specifically requested
    if method in ["combined", "text"]:
        try:
            text1, conf1 = extract_text_from_image(img1, preprocess=False)  # Faster without preprocessing
            text2, conf2 = extract_text_from_image(img2, preprocess=False)
            
            # Only use text comparison if OCR confidence is reasonable
            min_confidence = 25  # Slightly lower threshold for performance
            if conf1 >= min_confidence or conf2 >= min_confidence:
                text_similarity, text_different, text_details = compare_text_content(text1, text2)
                results['text'] = text_similarity
                text_info = f"OCR: {text_details} (conf: {conf1:.0f}/{conf2:.0f})"
            else:
                # Fall back to visual comparison if OCR confidence is too low
                results['text'] = None
                text_info = f"OCR confidence too low ({conf1:.0f}/{conf2:.0f}), using visual"
        except Exception as e:
            print(f"Text comparison failed: {e}")
            results['text'] = None
            text_info = f"OCR failed: {e}"
    else:
        text_info = "OCR skipped"
    
    # Convert to numpy arrays for visual processing
    arr1 = np.array(img1.convert("RGB"))
    arr2 = np.array(img2.convert("RGB"))
    
    # Method 2: SSIM (fastest visual method)
    if method in ["combined", "ssim"] or results.get('text') is None:
        gray1 = cv2.cvtColor(arr1, cv2.COLOR_RGB2GRAY)
        gray2 = cv2.cvtColor(arr2, cv2.COLOR_RGB2GRAY)
        ssim_score = ssim(gray1, gray2)
        results['ssim'] = ssim_score
    
    # PERFORMANCE: For combined method, if SSIM shows high similarity, skip expensive methods
    if method == "combined" and results.get('ssim', 0) > 0.95:
        # High SSIM similarity - skip expensive methods
        if results.get('text') is not None:
            combined_score = results['text'] * 0.7 + results['ssim'] * 0.3
            details = f"Fast path: {text_info}, SSIM: {results['ssim']:.3f}"
        else:
            combined_score = results['ssim']
            details = f"Fast path: SSIM: {results['ssim']:.3f}"
        
        return combined_score, 0.9, details
    
    # Method 3: Perceptual Hash (only for combined method when needed)
    if method in ["combined", "phash"] or results.get('text') is None:
        try:
            hash1 = imagehash.phash(img1)
            hash2 = imagehash.phash(img2)
            hash_diff = hash1 - hash2  # Hamming distance
            hash_similarity = 1.0 - (hash_diff / 64.0)  # Normalize to 0-1
            results['phash'] = hash_similarity
        except Exception as e:
            print(f"pHash failed: {e}")
            results['phash'] = results.get('ssim', 0.5)  # Fallback
    
    # PERFORMANCE: Skip histogram and features for faster processing unless specifically requested
    if method == "combined":
        # Simplified combined method - fewer calculations
        if results.get('text') is not None:
            # Text-heavy weighting when OCR is available
            combined_score = results['text'] * 0.6 + results.get('ssim', 0.5) * 0.25 + results.get('phash', 0.5) * 0.15
            details = f"{text_info}, SSIM: {results.get('ssim', 'N/A'):.3f}, pHash: {results.get('phash', 'N/A'):.3f}"
        else:
            # Visual-only weighting when OCR fails
            combined_score = results.get('ssim', 0.5) * 0.6 + results.get('phash', 0.5) * 0.4
            details = f"{text_info}, SSIM: {results.get('ssim', 'N/A'):.3f}, pHash: {results.get('phash', 'N/A'):.3f}"
        
        # Calculate confidence - simplified
        scores = [v for v in [results.get('text'), results.get('ssim'), results.get('phash')] if v is not None]
        confidence = 0.9 if len(scores) > 1 else 0.7
        
        return combined_score, confidence, details
    
    elif method == "text" and results.get('text') is not None:
        return results['text'], 1.0, text_info
    
    elif method == "ssim":
        return results.get('ssim', 0.5), 1.0, f"SSIM: {results.get('ssim', 'N/A'):.4f}"
    
    elif method == "phash":
        return results.get('phash', 0.5), 1.0, f"pHash: {results.get('phash', 'N/A'):.4f}"
    
    else:
        return results.get('ssim', 0.5), 1.0, f"SSIM: {results.get('ssim', 'N/A'):.4f}"