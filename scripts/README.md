# Copilot Chat Export Tools

This directory contains various tools for automatically exporting and managing Copilot chat sessions.

## Available Tools

### 1. PowerShell Auto-Export Script
**File:** `copilot-auto-export.ps1`

Monitors VS Code chat data and automatically exports sessions to markdown files.

**Usage:**
```powershell
# Start monitoring (runs continuously)
.\scripts\copilot-auto-export.ps1

# Test chat detection
.\scripts\copilot-auto-export.ps1 test

# Custom interval (check every 15 minutes)
.\scripts\copilot-auto-export.ps1 -IntervalMinutes 15
```

**Features:**
- Monitors VS Code chat data directories
- Automatically exports to timestamped markdown files
- Auto-commits to git repository
- Configurable check intervals
- Detailed logging

### 2. VS Code Task Integration
The auto-export script is configured as a VS Code task that runs automatically when the workspace opens.

**To start manually:**
1. Press `Ctrl+Shift+P`
2. Type "Tasks: Run Task"
3. Select "Auto-Export Copilot Chats"

### 3. GitHub Actions Backup
**File:** `.github/workflows/backup-copilot-chats.yml`

Automated workflow that:
- Creates daily summaries of chat sessions
- Generates backup archives
- Monitors for large files
- Runs on schedule and manual trigger

### 4. Browser Bookmarklet
For capturing web-based chat interfaces:

```javascript
javascript:(function(){
  const chatContent = document.querySelector('[data-testid="chat-container"], .chat-messages, .conversation')?.innerText || 'No chat content found';
  const date = new Date().toISOString().split('T')[0];
  const filename = `${date}_browser-chat-export.md`;
  
  const markdown = `# Browser Chat Export\n\n**Date:** ${date}\n**Time:** ${new Date().toLocaleTimeString()}\n**URL:** ${window.location.href}\n\n## Chat Content\n\n${chatContent}`;
  
  const blob = new Blob([markdown], {type: 'text/markdown'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
})();
```

**To use:**
1. Copy the JavaScript code above
2. Create a new bookmark in your browser
3. Paste the code as the bookmark URL
4. Click the bookmark when viewing a chat interface

## Setup Instructions

### Quick Start
1. **Enable PowerShell execution:**
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

2. **Start auto-export:**
   ```powershell
   .\scripts\copilot-auto-export.ps1
   ```

3. **Verify in VS Code:**
   - Open Command Palette (`Ctrl+Shift+P`)
   - Run "Tasks: Run Task" → "Auto-Export Copilot Chats"

### Advanced Configuration

#### Custom Chat Directories
Edit the PowerShell script to monitor additional directories:

```powershell
$AdditionalPaths = @(
    "$env:LOCALAPPDATA\Microsoft\Windows\PowerShell\copilot",
    "C:\CustomChatData"
)
```

#### Automatic Git Push
To automatically push exports to remote repository, uncomment this line in the script:
```powershell
# git push origin main
```

#### Schedule with Task Scheduler
Create a Windows scheduled task to run the export script:

```powershell
$Action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-File `"$PWD\scripts\copilot-auto-export.ps1`""
$Trigger = New-ScheduledTaskTrigger -Daily -At "09:00AM"
Register-ScheduledTask -TaskName "CopilotChatExport" -Action $Action -Trigger $Trigger
```

## File Organization

The auto-export system organizes files as follows:

```
docs/copilot-chats/
├── README.md                          # This file
├── _template.md                       # Template for manual sessions
├── session-summary.md                 # Auto-generated summary
├── auto-export.log                    # Export script log
├── 2025-08-12_enhanced-detection.md   # Manual session export
├── 2025-08-12_auto-exported-session.md # Auto-exported session
└── screenshots/                       # Optional screenshots
    └── important-features.png
```

## Troubleshooting

### Script Not Finding Chat Data
1. Check VS Code installation path
2. Verify user data directory location
3. Enable debug logging in script

### Permission Issues
```powershell
# Run as administrator if needed
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
```

### Git Commit Failures
```powershell
# Ensure git is configured
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

## Benefits of Automated Export

✅ **Continuous Backup**: Never lose important development conversations  
✅ **Version Control**: Track how features evolved over time  
✅ **Team Sharing**: Share insights and solutions with team members  
✅ **Documentation**: Automatic documentation of implementation decisions  
✅ **Learning**: Review past solutions for similar problems  
✅ **Compliance**: Maintain records for audit or review purposes  

## Next Steps

1. **Test the auto-export script** to ensure it captures your chat data
2. **Customize the export format** to include more metadata
3. **Set up the GitHub Actions workflow** for additional backup
4. **Create manual session summaries** for important conversations
5. **Consider adding AI-powered categorization** of exported sessions
