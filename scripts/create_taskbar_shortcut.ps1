# PowerShell script to create a taskbar-compatible ScreenAlert shortcut
# This creates a proper .lnk shortcut that can be pinned to taskbar

# Get current directory
$CurrentDir = (Get-Location).Path

# Create WScript Shell object
$WshShell = New-Object -comObject WScript.Shell

# Create desktop shortcut
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopPath "ScreenAlert.lnk"
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)

# Point to cmd.exe to run the batch file
$Shortcut.TargetPath = "C:\Windows\System32\cmd.exe"
$Shortcut.Arguments = "/c `"$CurrentDir\launch_screenalert.bat`""
$Shortcut.WorkingDirectory = $CurrentDir
$Shortcut.Description = "ScreenAlert - Screen Monitoring Tool"
$Shortcut.WindowStyle = 7  # Minimized window
$Shortcut.Save()

Write-Host "* Desktop shortcut created: $ShortcutPath"
Write-Host ""
Write-Host "To add to taskbar:"
Write-Host "1. Right-click the ScreenAlert shortcut on your desktop"
Write-Host "2. Select 'Pin to taskbar'"
Write-Host ""
Write-Host "Alternative method:"
Write-Host "1. Drag the desktop shortcut to your taskbar"
Write-Host "2. Drop it on the taskbar"

# Also create Start Menu shortcut
$StartMenuPath = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs"
$StartShortcutPath = Join-Path $StartMenuPath "ScreenAlert.lnk"
$StartShortcut = $WshShell.CreateShortcut($StartShortcutPath)
$StartShortcut.TargetPath = "C:\Windows\System32\cmd.exe"
$StartShortcut.Arguments = "/c `"$CurrentDir\launch_screenalert.bat`""
$StartShortcut.WorkingDirectory = $CurrentDir
$StartShortcut.Description = "ScreenAlert - Screen Monitoring Tool"
$StartShortcut.WindowStyle = 7  # Minimized window
$StartShortcut.Save()

Write-Host "* Start Menu shortcut created: $StartShortcutPath"
Write-Host ""
Write-Host "You can also pin from Start Menu:"
Write-Host "1. Press Windows key and search 'ScreenAlert'"
Write-Host "2. Right-click the result and select 'Pin to taskbar'"
