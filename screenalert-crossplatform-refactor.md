# ScreenAlert Cross-Platform Refactor Plan

## Current Windows Dependencies Analysis

Your ScreenAlert app uses these Windows-specific functions:

### **Window Management (win32gui/win32ui/win32con/win32api)**
- `win32gui.EnumWindows()` - List all windows
- `win32gui.GetWindowText()` - Get window title  
- `win32gui.GetClassName()` - Get window class
- `win32gui.GetWindowRect()` - Get window position/size
- `win32gui.IsWindow()` - Check if window exists
- `win32gui.IsWindowVisible()` - Check if window is visible
- `win32gui.GetWindowDC()` - Get window drawing context for screenshots
- `win32api.EnumDisplayMonitors()` - Get monitor information

## Cross-Platform Replacement Strategy

### **Phase 1: Replace Window Management**

Replace with **`pynput`** + **`psutil`** + **`pyautogui`**:

```python
# NEW: Cross-platform window management
import psutil
import pyautogui
from pynput import mouse, keyboard
import subprocess
import platform

def get_all_windows():
    """Cross-platform window enumeration"""
    windows = []
    
    if platform.system() == "Windows":
        # Use Windows-specific method (keep existing for now)
        return get_windows_windows()  # Your current code
    elif platform.system() == "Linux":
        try:
            # Use wmctrl for Linux window management
            result = subprocess.run(['wmctrl', '-l'], capture_output=True, text=True)
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(None, 3)
                    if len(parts) >= 4:
                        windows.append({
                            'hwnd': parts[0],
                            'title': parts[3],
                            'pid': None,  # wmctrl doesn't provide PID directly
                            'rect': get_window_geometry_linux(parts[0])
                        })
        except FileNotFoundError:
            print("wmctrl not found. Install with: sudo apt install wmctrl")
    
    return windows

def get_window_geometry_linux(window_id):
    """Get window position and size on Linux"""
    try:
        result = subprocess.run(['xwininfo', '-id', window_id], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        x = y = width = height = 0
        for line in lines:
            if 'Absolute upper-left X:' in line:
                x = int(line.split(':')[1].strip())
            elif 'Absolute upper-left Y:' in line:
                y = int(line.split(':')[1].strip())
            elif 'Width:' in line:
                width = int(line.split(':')[1].strip())
            elif 'Height:' in line:
                height = int(line.split(':')[1].strip())
        
        return (x, y, x + width, y + height)  # left, top, right, bottom
    except:
        return (0, 0, 0, 0)

def capture_window_cross_platform(window_info):
    """Cross-platform window screenshot"""
    if platform.system() == "Windows":
        # Keep your existing Windows implementation
        return capture_window_windows(window_info['hwnd'])
    elif platform.system() == "Linux":
        # Use pyautogui for Linux screenshots
        rect = window_info['rect']
        if rect != (0, 0, 0, 0):
            left, top, right, bottom = rect
            width = right - left
            height = bottom - top
            return pyautogui.screenshot(region=(left, top, width, height))
    
    return None
```

### **Phase 2: System Dependencies**

**Linux System Requirements:**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install wmctrl xwininfo python3-tk python3-dev scrot

# Fedora
sudo dnf install wmctrl xorg-x11-utils tkinter python3-devel

# Arch
sudo pacman -S wmctrl xorg-xwininfo tk
```

**Updated Requirements Files:**

**`screenalert_requirements.txt` (Universal):**
```
pyautogui>=0.9.54
Pillow>=11.0.0  
scikit-image>=0.25.0
numpy>=2.0.0
opencv-python>=4.8.0
imagehash>=4.3.0
pyttsx3>=2.90
psutil>=5.9.0
pynput>=1.7.6
```

**`screenalert_requirements_windows.txt` (Windows-specific):**
```
pyautogui>=0.9.54
Pillow>=11.0.0
scikit-image>=0.25.0  
numpy>=2.0.0
opencv-python>=4.8.0
imagehash>=4.3.0
pyttsx3>=2.90
psutil>=5.9.0
pynput>=1.7.6
pywin32>=306  # Keep for Windows-specific optimizations
```

### **Phase 3: Update GitHub Workflow**

```yaml
# .github/workflows/build-release.yml
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest]
    include:
      - os: ubuntu-latest
        requirements_file: screenalert_requirements.txt
        system_deps: "sudo apt update && sudo apt install wmctrl xwininfo python3-tk"
      - os: windows-latest  
        requirements_file: screenalert_requirements_windows.txt
        system_deps: ""

runs-on: ${{ matrix.os }}

steps:
  - name: Install system dependencies (Linux)
    if: matrix.os == 'ubuntu-latest'
    run: ${{ matrix.system_deps }}
    
  - name: Install Python dependencies
    run: |
      python -m pip install --upgrade pip
      pip install -r ${{ matrix.requirements_file }}
      pip install nuitka
```

## Migration Benefits

✅ **ACT Compatible**: Linux containers will work perfectly  
✅ **True Cross-Platform**: Works on Windows, Linux, macOS  
✅ **Better Architecture**: More maintainable, modern dependencies  
✅ **Wider User Base**: Linux users can use ScreenAlert  
✅ **Container Friendly**: Works in Docker, CI/CD systems  

## Implementation Strategy

1. **Keep Windows Code**: Don't remove `win32*` code yet
2. **Add Cross-Platform Layer**: Create platform detection and routing
3. **Test Both Platforms**: Ensure feature parity
4. **Gradual Migration**: Move features one by one
5. **Optimize Later**: Keep Windows-specific optimizations where beneficial

This approach gives you the best of both worlds - cross-platform compatibility for ACT while maintaining Windows-specific optimizations where they matter!
