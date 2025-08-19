# Cross-Platform ScreenAlert Migration Guide

## Current Windows Dependencies → Cross-Platform Alternatives

### 1. **GUI Framework: tkinter → Cross-Platform Options**

**Current**: tkinter (already cross-platform!)
**Status**: ✅ **Already works on Linux** - tkinter is built into Python on most Linux distributions

**Alternative Options** (if you want to upgrade):
- **PyQt5/6** or **PySide2/6**: More modern, better looking
- **wxPython**: Native look and feel on each OS
- **Kivy**: Modern touch-friendly interfaces
- **Dear PyGui**: High-performance, gaming-style interfaces

### 2. **Screen Capture: pyautogui → Cross-Platform (Already Good!)**

**Current**: pyautogui
**Status**: ✅ **Already cross-platform** - works on Windows, Linux, macOS
**Linux Requirements**: Install `python3-tk python3-dev scrot` (for screenshots)

### 3. **Windows-Specific: pywin32 → Cross-Platform Alternatives**

**Problem**: `pywin32` only works on Windows
**Solutions**:

#### Option A: **psutil** (Process/System Info)
```python
import psutil
import platform

# Cross-platform system info
def get_system_info():
    return {
        'os': platform.system(),
        'version': platform.version(),
        'architecture': platform.architecture()[0]
    }

# Cross-platform process management
def get_running_processes():
    return [proc.info for proc in psutil.process_iter(['pid', 'name', 'username'])]
```

#### Option B: **plyer** (Platform-specific Features)
```python
from plyer import notification

# Cross-platform notifications
def show_notification(title, message):
    notification.notify(
        title=title,
        message=message,
        timeout=10
    )
```

#### Option C: **pynput** (Input/Hotkeys)
```python
from pynput import keyboard, mouse

# Cross-platform global hotkeys
def setup_global_hotkeys():
    def on_hotkey():
        print("Hotkey pressed!")
    
    with keyboard.GlobalHotKeys({'<ctrl>+<shift>+s': on_hotkey}):
        # Keep the program running
        keyboard.Listener().join()
```

### 4. **Text-to-Speech: pyttsx3 → Cross-Platform (Already Good!)**

**Current**: pyttsx3
**Status**: ✅ **Already cross-platform**
**Linux Requirements**: Install `espeak` or `festival`

## Updated Cross-Platform Requirements

### Windows Requirements (`screenalert_requirements_windows.txt`):
```
pyautogui==0.9.54
Pillow>=11.0.0
scikit-image>=0.25.0
numpy>=2.0.0
opencv-python>=4.8.0
imagehash>=4.3.0
pyttsx3>=2.90
psutil>=5.9.0
plyer>=2.1.0
pynput>=1.7.6
```

### Linux Requirements (`screenalert_requirements_linux.txt`):
```
pyautogui==0.9.54
Pillow>=11.0.0
scikit-image>=0.25.0
numpy>=2.0.0
opencv-python-headless>=4.8.0  # Headless version for Linux
imagehash>=4.3.0
pyttsx3>=2.90
psutil>=5.9.0
plyer>=2.1.0
pynput>=1.7.6
```

### System Dependencies for Linux:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3-tk python3-dev scrot espeak espeak-data libespeak1 libespeak-dev

# Fedora/RHEL
sudo dnf install tkinter python3-devel scrot espeak espeak-devel

# Arch
sudo pacman -S tk scrot espeak
```

## Code Migration Strategy

### 1. **Replace pywin32 with psutil/plyer**
```python
# OLD (Windows-only)
import win32api
import win32gui

def get_window_info():
    return win32gui.GetWindowText(win32gui.GetForegroundWindow())

# NEW (Cross-platform)
import psutil
import platform

def get_system_info():
    return {
        'platform': platform.system(),
        'processes': len(psutil.pids())
    }
```

### 2. **Conditional OS-Specific Code**
```python
import platform

if platform.system() == 'Windows':
    # Windows-specific features
    pass
elif platform.system() == 'Linux':
    # Linux-specific features
    pass
else:
    # macOS or other
    pass
```

### 3. **Cross-Platform File Paths**
```python
import os
from pathlib import Path

# Cross-platform paths
config_dir = Path.home() / '.screenalert'
config_file = config_dir / 'config.json'

# Create directory if it doesn't exist
config_dir.mkdir(exist_ok=True)
```

## Benefits of Going Cross-Platform

✅ **ACT Compatibility**: Will work perfectly in Linux containers
✅ **Broader User Base**: Linux and macOS users can use your app
✅ **Better Testing**: Can test on multiple platforms locally
✅ **Modern Dependencies**: Upgrade from old Windows-specific libraries
✅ **Container Friendly**: Works in Docker, CI/CD, cloud environments

## Migration Priority

1. **High Priority**: Replace `pywin32` with `psutil` + `plyer`
2. **Medium Priority**: Add Linux system dependencies to workflow
3. **Low Priority**: Consider upgrading GUI framework (optional)

This will make your ScreenAlert truly cross-platform and solve the ACT compatibility issue permanently!
