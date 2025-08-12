# ScreenAlert Security Information

## Antivirus False Positives

ScreenAlert is a legitimate screen monitoring application that may trigger false positives in some antivirus software. This is common with PyInstaller-compiled executables.

### Why This Happens

1. **PyInstaller Compilation**: The executable contains a Python interpreter and all dependencies packed into a single file
2. **Screen Capture**: The application captures screenshots, which some AV software considers suspicious
3. **Automation Features**: Uses pyautogui for automation, which can trigger behavioral detection
4. **Unsigned Executable**: The application is not code-signed with a commercial certificate

### Verification Steps

1. **Source Code**: The complete source code is available on GitHub
2. **Build Process**: All builds are done via GitHub Actions with public logs
3. **Hash Verification**: Check file hashes against published releases

### Safe Usage

- Download only from the official GitHub releases page
- Verify the file hash if provided
- Add to antivirus exclusions if needed
- Run in a sandbox first if concerned

### Reporting False Positives

If you encounter false positives:

1. Report to your antivirus vendor
2. Add the application to your exclusions list
3. Verify the download source and hash

## Application Permissions

ScreenAlert requires the following permissions:

- **Screen Capture**: To monitor specified screen regions
- **File System**: To save configuration and screenshots
- **Audio**: For notification sounds
- **Network**: None (application runs entirely offline)

## Data Privacy

- No data is transmitted to external servers
- All screenshots and data remain on your local machine
- No telemetry or analytics are collected
