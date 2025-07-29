# ScreenAlert - Window-Specific Region Monitor

## Overview

ScreenAlert is an advanced region monitoring application that monitors specific application windows instead of the entire screen. This allows for more accurate monitoring even when other windows are overlaid on top of the target application.

## Key Features

### Window-Specific Monitoring
- **Target Window Selection**: Choose from a list of all visible windows on startup
- **Window Persistence**: Monitors the selected window even when obscured by other windows
- **Window Management**: Change target window anytime through the UI
- **Window Information**: View details about the currently monitored window

### Region Monitoring
- **Visual Region Selection**: Select monitoring regions directly on the target window
- **Multiple Regions**: Monitor multiple areas within the same window
- **Region Status**: Visual indicators for each region (Normal, Paused, Alert, Disabled)
- **Individual Controls**: Pause, mute, or disable regions independently

### Alert System
- **Visual Comparison**: Uses SSIM and pHash algorithms for reliable change detection
- **Sound Alerts**: Configurable sound files for different regions
- **Text-to-Speech**: Customizable TTS messages with region names
- **Mute Controls**: Temporary muting with countdown timers
- **Alert Thresholds**: Adjustable sensitivity for change detection

### Status Management
- **Global Pause**: Pause all monitoring with reminder tones
- **Individual Pause**: Pause specific regions
- **Disable Regions**: Completely disable regions (no processing, alerts, or reminders)
- **Status Display**: Real-time status with countdown timers

## System Requirements

- **Windows Only**: Uses Windows-specific APIs for window capture
- **Python 3.7+**: Required for all dependencies
- **Dependencies**: See `screenalert_requirements.txt`

## Installation

1. Install dependencies:
   ```bash
   pip install -r screenalert_requirements.txt
   ```

2. Run the application:
   ```bash
   python screenalert.py
   ```

## Usage

### First Run
1. **Window Selection**: On first startup, you'll see a list of all visible windows
2. **Choose Target**: Select the application window you want to monitor
3. **Add Regions**: Click "Add Region" to select areas within the window to monitor

### Adding Regions
1. Click "➕ Add Region" button
2. A screenshot of your target window will appear
3. Click and drag to select the area you want to monitor
4. Press Escape to cancel or click outside to confirm

### Changing Target Window
1. Go to the "Target Window" tab
2. Click "Change Target Window"
3. Select a new window from the list
4. Existing regions will be cleared (you'll need to recreate them)

### Configuration
All settings are automatically saved to `screenalert_config.json`:
- Target window information
- Region definitions and settings
- Alert thresholds and timing
- Sound and TTS preferences
- UI customization (colors, text)

## Differences from Basic ScreenAlert

| Feature | Basic ScreenAlert | ScreenAlert (Window-Specific) |
|---------|-------------|-------------|
| **Monitoring Target** | Entire screen | Specific window |
| **Overlay Handling** | Affected by overlays | Ignores overlays |
| **Window Selection** | N/A | Interactive window picker |
| **Region Selection** | Full screen overlay | Window-specific overlay |
| **Platform Support** | Cross-platform | Windows only |
| **Dependencies** | Basic | Requires pywin32 |

## Technical Details

### Window Capture
- Uses Windows `PrintWindow` API for direct window capture
- Fallback to screen capture if window capture fails
- Handles minimized and invalid windows gracefully

### Window Detection
- Enumerates all visible windows with titles
- Filters out small/system windows
- Provides window information (title, class, size, handle)

### Visual Comparison
- **SSIM**: Structural Similarity Index for accurate change detection
- **pHash**: Perceptual hashing for additional verification
- **Combined Method**: Weighted combination of both algorithms

## Gaming Compliance

Like other ScreenAlert variants, this application is designed for compliance with gaming rules (e.g., EVE Online):
- **Observation Only**: Does not interact with or automate any game functions
- **No Input**: Cannot send keyboard/mouse input to applications
- **Detection Only**: Only detects and alerts on visual changes
- **Manual Response**: All actions require manual user intervention

## Configuration File

The `screenalert_config.json` file stores:
- Target window information (title, handle, class)
- Region definitions (coordinates, names, settings)
- Alert preferences (sounds, TTS, thresholds)
- UI customization (colors, text labels)
- Timing settings (intervals, timeouts)

## Troubleshooting

### Window Not Captured
- Ensure the target window is not minimized
- Try changing to a different window and back
- Some applications may block window capture - try fallback mode

### Regions Not Working
- Verify the target window is still open and visible
- Check that regions are not paused or disabled
- Ensure alert threshold is appropriate for the content

### Performance Issues
- Reduce monitoring frequency (increase interval)
- Disable unused regions
- Close unnecessary applications to free resources

## Support

This application is provided as-is for educational and monitoring purposes. Ensure compliance with the terms of service of any applications you monitor.
