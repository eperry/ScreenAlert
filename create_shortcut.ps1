# Create Windows Shortcut for ScreenAlert
# This script creates a desktop shortcut for ScreenAlert

$WScriptShell = New-Object -ComObject WScript.Shell

# Get current directory (where ScreenAlert is located)
$CurrentDir = Get-Location
$BatchFile = Join-Path $CurrentDir "launch_screenalert.bat"

# Desktop shortcut path
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopPath "ScreenAlert.lnk"

# Create the shortcut
$Shortcut = $WScriptShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $BatchFile
$Shortcut.WorkingDirectory = $CurrentDir
$Shortcut.Description = "ScreenAlert - Screen Region Monitoring Application"
$Shortcut.IconLocation = "shell32.dll,23"  # Monitor icon from Windows
$Shortcut.WindowStyle = 1  # Normal window
$Shortcut.Save()

Write-Host "Desktop shortcut created successfully!" -ForegroundColor Green
Write-Host "Shortcut location: $ShortcutPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "You can also create shortcuts in other locations:" -ForegroundColor Yellow
Write-Host "- Start Menu: Copy shortcut to $env:APPDATA\Microsoft\Windows\Start Menu\Programs\" -ForegroundColor Gray
Write-Host "- Quick Launch: Pin to taskbar by right-clicking the shortcut" -ForegroundColor Gray

# Optional: Create Start Menu shortcut too
$StartMenuResponse = Read-Host "Would you like to create a Start Menu shortcut too? (y/n)"
if ($StartMenuResponse -eq "y" -or $StartMenuResponse -eq "Y") {
    $StartMenuPath = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
    $StartMenuShortcut = Join-Path $StartMenuPath "ScreenAlert.lnk"
    
    $StartShortcut = $WScriptShell.CreateShortcut($StartMenuShortcut)
    $StartShortcut.TargetPath = $BatchFile
    $StartShortcut.WorkingDirectory = $CurrentDir
    $StartShortcut.Description = "ScreenAlert - Screen Region Monitoring Application"
    $StartShortcut.IconLocation = "shell32.dll,23"
    $StartShortcut.WindowStyle = 1
    $StartShortcut.Save()
    
    Write-Host "Start Menu shortcut created successfully!" -ForegroundColor Green
}

Write-Host ""
Write-Host "Setup complete! You can now launch ScreenAlert from:" -ForegroundColor Magenta
Write-Host "✓ Desktop shortcut" -ForegroundColor Green
if ($StartMenuResponse -eq "y" -or $StartMenuResponse -eq "Y") {
    Write-Host "✓ Start Menu" -ForegroundColor Green
}
Write-Host "✓ Double-clicking launch_screenalert.bat" -ForegroundColor Green
