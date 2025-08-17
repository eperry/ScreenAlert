# ScreenAlert Logging System

## Overview
ScreenAlert v1.4.2.1 now includes professional logging capabilities with timestamped rotating log files and a silent executable.

## Features

### 🔇 Silent Operation
- **No Console Window**: The compiled executable runs silently without showing a console
- **Professional Appearance**: Clean, distraction-free operation
- **Background Monitoring**: Runs quietly in the system tray

### 📝 Comprehensive Logging
- **Timestamped Files**: Each run creates a unique log file with timestamp
- **Rotating Logs**: Automatically manages log file size and retention
- **Multiple Log Levels**: DEBUG, INFO, WARNING, ERROR with detailed context

### 📍 Log Location
```
%APPDATA%\ScreenAlert\logs\
Example: C:\Users\YourName\AppData\Roaming\ScreenAlert\logs\
```

### 📊 Log Format
```
2025-08-15 20:45:22,886 - INFO - main:1135 - ScreenAlert starting up...
2025-08-15 20:45:36,405 - DEBUG - speak_tts:1004 - TTS: Attempting to speak: 'Alert Region 1'
2025-08-15 20:45:38,608 - DEBUG - speak_tts:1014 - TTS: Windows SAPI speech completed successfully
```

## Log File Naming
- **Pattern**: `screenalert_YYYYMMDD_HHMMSS.log`
- **Example**: `screenalert_20250815_204522.log`
- **Rotation**: Keeps last 10 files, 10MB max each

## What's Logged

### Startup Information
- ✅ Application version and startup time
- ✅ Platform and Python version information
- ✅ Configuration loading and migration
- ✅ Single instance lock acquisition

### Runtime Operations
- ✅ TTS operations with method selection and success/failure
- ✅ Screen capture events and file saves
- ✅ Region monitoring status changes
- ✅ Configuration changes and updates

### Error Handling
- ✅ Module import failures and fallbacks
- ✅ TTS method failures with detailed error messages
- ✅ Configuration loading errors
- ✅ Screen capture and file operation errors

## Performance Optimizations

### Compilation Improvements
- **LTO Enabled**: Link-Time Optimization for better performance
- **Production Build**: Removed debug assertions and docstrings
- **Parallel Compilation**: 8-core build process for faster compilation
- **Optimized Runtime**: Native C++ compilation with speed improvements

### Runtime Benefits
- **Faster Startup**: Optimized module loading
- **Reduced Memory**: Stripped debug information
- **Better Performance**: Native execution vs interpreted Python
- **Professional Operation**: Silent background execution

## Troubleshooting

### Finding Log Files
1. Press `Win + R`, type `%APPDATA%\ScreenAlert\logs`
2. Or navigate to: `C:\Users\[YourUsername]\AppData\Roaming\ScreenAlert\logs\`

### Reading Recent Logs
- Sort by date to find the most recent log file
- Each application start creates a new timestamped log
- Look for ERROR or WARNING entries for issues

### Common Log Entries
- `ScreenAlert starting up...` - Normal startup
- `Single instance lock acquired` - Running normally
- `TTS: Windows SAPI completed successfully` - Audio working
- `Screen capture saved` - Alert detection working

## Benefits Over Console Output
1. **Clean Operation**: No distracting console window
2. **Persistent Records**: Logs survive application restarts
3. **Professional Appearance**: Suitable for business environments
4. **Detailed Troubleshooting**: Function names and line numbers included
5. **Automatic Management**: Log rotation prevents disk space issues
6. **Better Performance**: Optimized executable with production build flags

## Development vs Production
- **Script Mode**: Still shows console output for development
- **Compiled EXE**: Silent operation with file logging only
- **Best of Both**: Debug information available when needed, clean when deployed
